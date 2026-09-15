from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from qa_common import (
    DATA,
    QA,
    ROOT,
    aligned_records,
    canonical_same_form,
    compact_display_spacing,
    format_signature,
    has_han,
    has_kana,
    has_unpreserved_kana,
    load_json,
    load_policy,
    lyric_translation_only,
    numeric_signature,
    percentage_signature,
    resolve_dump_ref,
)


class Findings:
    def __init__(self, example_limit: int = 50) -> None:
        self.counts: Counter[tuple[str, str]] = Counter()
        self.examples: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.example_limit = example_limit

    def add(self, severity: str, code: str, message: str) -> None:
        key = (severity, code)
        self.counts[key] += 1
        if len(self.examples[key]) < self.example_limit:
            self.examples[key].append(message)

    def count(self, severity: str) -> int:
        return sum(n for (sev, _), n in self.counts.items() if sev == severity)

    def report(self) -> dict[str, Any]:
        groups = []
        for (severity, code), count in sorted(self.counts.items()):
            groups.append({
                "severity": severity,
                "code": code,
                "count": count,
                "examples": self.examples[(severity, code)],
            })
        return {
            "errors": self.count("error"),
            "warnings": self.count("warning"),
            "groups": groups,
        }


def check_current_structure(findings: Findings, baseline: dict[str, Any]) -> dict[str, int]:
    stats: dict[str, int] = {}
    known_duplicate_keys = set(baseline.get("scenario_duplicate_keys", []))

    localify = load_json(DATA / "localify.json")
    if not isinstance(localify, dict):
        findings.add("error", "schema-localify", "localify.json root must be an object")
    else:
        rows = 0
        for table, entries in localify.items():
            if not isinstance(entries, dict):
                findings.add("error", "schema-localify", f"table {table!r} is not an object")
                continue
            for key, value in entries.items():
                rows += 1
                if not isinstance(value, str):
                    findings.add("error", "schema-localify", f"{table}:{key} value is not a string")
        stats["localify_rows"] = rows

    for name in ("local2.json", "lyrics.json"):
        data = load_json(DATA / name)
        if not isinstance(data, dict):
            findings.add("error", f"schema-{name}", f"{name} root must be an object")
            continue
        bad = 0
        for key, value in data.items():
            if not isinstance(key, str) or not isinstance(value, str):
                bad += 1
        if bad:
            findings.add("error", f"schema-{name}", f"{bad} entries are not string-to-string mappings")
        stats[name.removesuffix(".json") + "_rows"] = len(data)

    scenario_files = 0
    scenario_rows = 0
    for path in (DATA / "scenario").rglob("*.json"):
        scenario_files += 1
        try:
            data = load_json(path)
        except Exception as exc:
            findings.add("error", "scenario-json-parse", f"{path.relative_to(ROOT)}: {exc}")
            continue
        if not isinstance(data, list):
            findings.add("error", "scenario-schema", f"{path.relative_to(ROOT)} root must be an array")
            continue
        seen: set[str] = set()
        for i, row in enumerate(data):
            scenario_rows += 1
            if not isinstance(row, dict):
                findings.add("error", "scenario-schema", f"{path.relative_to(ROOT)}[{i}] is not an object")
                continue
            key = row.get("key")
            text = row.get("text")
            if not isinstance(key, str) or not isinstance(text, str):
                findings.add("error", "scenario-schema", f"{path.relative_to(ROOT)}[{i}] requires string key/text")
                continue
            if key in seen:
                duplicate_id = f"{path.relative_to(ROOT).as_posix()}:{key}"
                if duplicate_id in known_duplicate_keys:
                    findings.add("warning", "scenario-duplicate-key-known", duplicate_id)
                else:
                    findings.add("error", "scenario-duplicate-key", duplicate_id)
            seen.add(key)

    stats["scenario_files"] = scenario_files
    stats["scenario_rows"] = scenario_rows
    return stats


def check_public_privacy(findings: Findings, rules: dict[str, Any]) -> None:
    patterns = [
        (row["name"], re.compile(row["pattern"]))
        for row in rules.get("privacy_patterns", [])
        if isinstance(row, dict) and isinstance(row.get("name"), str) and isinstance(row.get("pattern"), str)
    ]
    if not patterns:
        return

    skip_parts = {".git", "qa/generated", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(rel == part or rel.startswith(part + "/") for part in skip_parts):
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:
            continue
        if len(raw) > 24 * 1024 * 1024:
            continue
        text = raw.decode("utf-8", errors="ignore")
        for name, pattern in patterns:
            match = pattern.search(text)
            if match:
                excerpt = match.group(0)
                if len(excerpt) > 120:
                    excerpt = excerpt[:117] + "..."
                findings.add("error", "privacy-" + name, f"{rel}: {excerpt!r}")


def allowed_source_equal(
    source: str,
    surface: str,
    allowed: dict[str, Any],
    names: dict[str, Any],
) -> bool:
    if source in set(allowed.get("global", [])):
        return True
    by_surface = allowed.get("by_surface", {})
    if isinstance(by_surface, dict) and source in set(by_surface.get(surface, [])):
        return True
    return canonical_same_form(source, names)


def effective_severity(
    requested: str,
    record: dict[str, str],
    authoritative_dump: bool,
) -> str:
    if requested != "error":
        return requested
    if record.get("provenance") == "current-source-key":
        return "error"
    return "error" if authoritative_dump else "warning"


def known_format_exception(
    baseline: dict[str, Any],
    surface: str,
    identity: str,
    component: str,
) -> bool:
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    for row in baseline.get("format_exceptions", []):
        if not isinstance(row, dict):
            continue
        if row.get("surface") != surface:
            continue
        if row.get("identity_sha256") != identity_hash:
            continue
        if component in row.get("components", []):
            return True
    return False


def check_format(
    findings: Findings,
    record: dict[str, str],
    rules: dict[str, Any],
    baseline: dict[str, Any],
    authoritative_dump: bool,
) -> None:
    surface = record["surface"]
    source = record["source"]
    target = record["translation"]
    ident = record["identity"]
    policy = rules.get("surface_policy", {}).get(surface, {})
    hard_components = set(rules.get("hard_format_components", []))

    if surface == "lyrics":
        if target == source or target.startswith(source + "\n") or target.startswith(source + "\r\n"):
            return
        findings.add(
            "warning",
            "lyrics-source-prefix",
            f"{ident}: display value does not follow the usual source-prefix bilingual form",
        )
        return

    src_sig = format_signature(source)
    dst_sig = format_signature(target)
    for component in ("brace", "printf", "tags"):
        if src_sig[component] != dst_sig[component]:
            requested = "error" if component in hard_components else "warning"
            severity = effective_severity(requested, record, authoritative_dump)
            is_known_exception = known_format_exception(baseline, surface, ident, component)
            if severity == "error" and is_known_exception:
                severity = "warning"
            code = f"format-{component}-known" if is_known_exception else f"format-{component}"
            findings.add(severity, code, f"{surface}:{ident}")

    for component, policy_key in (("lf", "newline"), ("cr", "newline"), ("nbsp", "nbsp")):
        if src_sig[component] == dst_sig[component]:
            continue
        requested = policy.get(policy_key, "warning")
        if requested == "ignore":
            continue
        severity = effective_severity(requested, record, authoritative_dump)
        findings.add(
            severity,
            f"format-{component}",
            f"{surface}:{ident}: source={src_sig[component]} target={dst_sig[component]}",
        )

    if numeric_signature(source) != numeric_signature(target):
        requested = policy.get("numeric", "warning")
        if requested != "ignore":
            severity = effective_severity(requested, record, authoritative_dump)
            findings.add(severity, "numeric-signature", f"{surface}:{ident}")

    if percentage_signature(source) != percentage_signature(target):
        requested = policy.get("percentage", "warning")
        if requested != "ignore":
            severity = effective_severity(requested, record, authoritative_dump)
            findings.add(severity, "percentage-signature", f"{surface}:{ident}")


def glossary_matches(term: dict[str, Any], source: str) -> bool:
    needle = term.get("source")
    if not isinstance(needle, str):
        return False
    if term.get("match") == "exact":
        return source == needle
    return needle in source


def check_semantics(
    findings: Findings,
    records: list[dict[str, str]],
    glossary: dict[str, Any],
    names: dict[str, Any],
    allowed: dict[str, Any],
) -> None:
    terms = [x for x in glossary.get("terms", []) if isinstance(x, dict)]
    preserve_terms = [x for x in glossary.get("preserve_terms", []) if isinstance(x, str)]
    kana_preserve_terms = [
        *preserve_terms,
        *[x for x in glossary.get("kana_preserve_terms", []) if isinstance(x, str)],
    ]

    name_map = {
        row["source"]: row["translation"]
        for row in names.get("names", [])
        if isinstance(row, dict) and isinstance(row.get("source"), str) and isinstance(row.get("translation"), str)
    }

    by_source: dict[str, set[str]] = defaultdict(set)
    by_source_ids: dict[str, list[str]] = defaultdict(list)

    for record in records:
        surface = record["surface"]
        source = record["source"]
        target = record["translation"]
        ident = record["identity"]
        semantic_target = lyric_translation_only(source, target) if surface == "lyrics" else target

        if target == source and (has_kana(source) or has_han(source)) and not allowed_source_equal(source, surface, allowed, names):
            findings.add("warning", "source-equal", f"{surface}:{ident}")

        if (
            semantic_target
            and not (target == source and allowed_source_equal(source, surface, allowed, names))
            and has_unpreserved_kana(semantic_target, kana_preserve_terms)
        ):
            findings.add("warning", "target-has-kana", f"{surface}:{ident}: {semantic_target[:100]!r}")

        for term in terms:
            scopes = term.get("scopes", [])
            if scopes and surface not in scopes:
                continue
            if not glossary_matches(term, source):
                continue
            preferred = [x for x in term.get("preferred", []) if isinstance(x, str)]
            if preferred and not any(x in semantic_target for x in preferred):
                findings.add(
                    "warning",
                    "glossary-disagreement",
                    f"{surface}:{ident}: {term.get('source')!r} -> expected one of {preferred!r}",
                )

        for term in preserve_terms:
            if term in source and term not in target:
                findings.add("warning", "preserve-term-missing", f"{surface}:{ident}: {term!r}")

        if surface == "local2" and source in name_map and target != name_map[source]:
            findings.add(
                "warning",
                "canonical-name",
                f"local2:{source!r}: current={target!r} canonical={name_map[source]!r}",
            )

        if source.strip() and target != source:
            normalized_target = semantic_target if surface == "lyrics" else target
            by_source[source].add(normalized_target)
            if len(by_source_ids[source]) < 6:
                by_source_ids[source].append(f"{surface}:{ident}")

    for source, targets in by_source.items():
        if len(targets) <= 1 or len(source.strip()) <= 3:
            continue
        compact_targets = {compact_display_spacing(target) for target in targets}
        sample = sorted(targets)[:4]
        code = "duplicate-source-layout-variant" if len(compact_targets) == 1 else "duplicate-source-conflict"
        findings.add(
            "warning",
            code,
            f"{source[:80]!r}: {len(targets)} translations; locations={by_source_ids[source][:4]!r}; sample={sample!r}",
        )


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# SCSP Translation QA",
        "",
        f"- Status: **{report['status']}**",
        f"- Hard errors: **{report['findings']['errors']}**",
        f"- Review warnings: **{report['findings']['warnings']}**",
        f"- Dump reference: `{report.get('dump_ref') or 'not available'}`",
        f"- Dump treated as authoritative: **{str(report['authoritative_dump']).lower()}**",
        "",
        "## Dataset",
        "",
    ]
    for key, value in sorted(report["stats"].items()):
        lines.append(f"- {key}: {value}")
    lines += ["", "## Findings", ""]
    groups = report["findings"]["groups"]
    if not groups:
        lines.append("No findings.")
    else:
        lines.append("| Severity | Code | Count |")
        lines.append("| --- | --- | ---: |")
        for group in groups:
            lines.append(f"| {group['severity']} | `{group['code']}` | {group['count']} |")
    lines.append("")
    return "\n".join(lines)


def print_console(report: dict[str, Any], console_examples: int) -> None:
    print(json.dumps({
        "status": report["status"],
        "errors": report["findings"]["errors"],
        "warnings": report["findings"]["warnings"],
        "dump_ref": report.get("dump_ref"),
        "authoritative_dump": report["authoritative_dump"],
        "stats": report["stats"],
    }, ensure_ascii=False, indent=2))
    for group in report["findings"]["groups"]:
        print(f"[{group['severity'].upper()}] {group['code']}: {group['count']}")
        for example in group["examples"][:console_examples]:
            print(f"  - {example}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    ap = argparse.ArgumentParser(description="Public QA for SCSP Simplified Chinese translation data.")
    ap.add_argument("--dump-ref", help="Git ref containing dumps/ (default: auto-detect origin/DumpData or DumpData)")
    ap.add_argument(
        "--authoritative-dump",
        action="store_true",
        help="Treat --dump-ref source text as current/authoritative and enforce configured source-format hard gates.",
    )
    ap.add_argument("--report", type=Path, help="Write JSON report")
    ap.add_argument("--markdown-report", type=Path, help="Write Markdown summary")
    ap.add_argument("--warnings-as-errors", action="store_true")
    args = ap.parse_args()

    rules, glossary, names, allowed = load_policy()
    baseline = load_json(QA / "baseline-exceptions.json")
    findings = Findings()
    stats = check_current_structure(findings, baseline)
    check_public_privacy(findings, rules)

    try:
        dump_ref = resolve_dump_ref(args.dump_ref)
    except ValueError as exc:
        findings.add("error", "dump-ref", str(exc))
        dump_ref = None

    if dump_ref is None:
        findings.add(
            "warning",
            "dump-ref-unavailable",
            "DumpData ref not available; localify/scenario source-comparison checks were skipped.",
        )

    records = list(aligned_records(dump_ref))
    stats["aligned_records"] = len(records)
    stats.update(Counter(f"aligned_{r['surface']}" for r in records))

    for record in records:
        check_format(findings, record, rules, baseline, args.authoritative_dump)
    check_semantics(findings, records, glossary, names, allowed)

    finding_report = findings.report()
    hard_errors = finding_report["errors"]
    if args.warnings_as_errors:
        hard_errors += finding_report["warnings"]

    report = {
        "schema_version": 1,
        "status": "PASS" if hard_errors == 0 else "FAIL",
        "dump_ref": dump_ref,
        "authoritative_dump": bool(args.authoritative_dump),
        "warnings_as_errors": bool(args.warnings_as_errors),
        "stats": dict(stats),
        "findings": finding_report,
    }

    console_examples = int(rules.get("warning_limits", {}).get("console_examples_per_code", 12))
    print_console(report, console_examples)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.markdown_report:
        args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_report.write_text(markdown_report(report), encoding="utf-8", newline="\n")

    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
