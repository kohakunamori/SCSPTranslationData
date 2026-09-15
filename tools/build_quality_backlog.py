from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from qa_common import (
    QA,
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
    numeric_signatures_match,
    percentage_signature,
    reviewed_semantic_exception,
    resolve_dump_ref,
    write_json,
)


def stable_id(*parts: str) -> str:
    raw = "\0".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def category_policy(policy: dict[str, Any], category: str) -> dict[str, Any]:
    row = policy.get("categories", {}).get(category, {})
    return row if isinstance(row, dict) else {}


def add_item(
    out: list[dict[str, Any]],
    policy: dict[str, Any],
    *,
    category: str,
    code: str,
    surface: str,
    identity: str,
    source: str | None = None,
    translation: str | None = None,
    provenance: str | None = None,
    detail: str | None = None,
    locations: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    cfg = category_policy(policy, category)
    backlog_id = stable_id(category, code, surface, identity, detail or "")
    row: dict[str, Any] = {
        "schema_version": 1,
        "backlog_id": backlog_id,
        "priority": cfg.get("priority", "P3"),
        "category": category,
        "code": code,
        "surface": surface,
        "identity": identity,
        "agent_ready": bool(cfg.get("agent_ready", False)),
        "recommended_action": cfg.get("recommended_action", ""),
        "auto_apply_allowed": False,
    }
    if source is not None:
        row["source"] = source
    if translation is not None:
        row["translation"] = translation
    if provenance is not None:
        row["provenance"] = provenance
        if provenance == "current-source-key":
            row["source_authority"] = "current-key"
            row["requires_source_verification"] = False
        elif "DumpData" in provenance:
            row["source_authority"] = "historical-reference"
            row["requires_source_verification"] = True
        else:
            row["source_authority"] = "unknown"
            row["requires_source_verification"] = True
    if detail:
        row["detail"] = detail
    if locations:
        row["locations"] = locations
    if metadata:
        row["metadata"] = metadata
    out.append(row)


def glossary_matches(term: dict[str, Any], source: str) -> bool:
    needle = term.get("source")
    if not isinstance(needle, str):
        return False
    return source == needle if term.get("match") == "exact" else needle in source


def source_equal_allowed(
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


def build_items(dump_ref: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rules, glossary, names, allowed = load_policy()
    baseline = load_json(QA / "baseline-exceptions.json")
    backlog_policy = load_json(QA / "backlog-policy.json")
    records = list(aligned_records(dump_ref))
    items: list[dict[str, Any]] = []
    preserve_terms = [x for x in glossary.get("preserve_terms", []) if isinstance(x, str)]
    kana_preserve_terms = [
        *preserve_terms,
        *[x for x in glossary.get("kana_preserve_terms", []) if isinstance(x, str)],
    ]

    hard_components = set(rules.get("hard_format_components", []))
    surface_policy = rules.get("surface_policy", {})

    for rec in records:
        surface = rec["surface"]
        identity = rec["identity"]
        source = rec["source"]
        target = rec["translation"]
        provenance = rec["provenance"]

        if surface != "lyrics":
            a = format_signature(source)
            b = format_signature(target)
            for component in ("brace", "printf", "tags"):
                if a[component] == b[component]:
                    continue
                is_known_exception = known_format_exception(baseline, surface, identity, component)
                if is_known_exception:
                    category = "baseline-format"
                    code = f"format-{component}-known"
                else:
                    category = "protected-format" if component in hard_components else "layout"
                    code = f"format-{component}"
                add_item(
                    items,
                    backlog_policy,
                    category=category,
                    code=code,
                    surface=surface,
                    identity=identity,
                    source=source,
                    translation=target,
                    provenance=provenance,
                    detail=f"{component} signature differs",
                    metadata={"source_signature": a[component], "translation_signature": b[component]},
                )

            policy = surface_policy.get(surface, {})
            for component, policy_key in (("lf", "newline"), ("cr", "newline"), ("nbsp", "nbsp")):
                if a[component] == b[component] or policy.get(policy_key, "warning") == "ignore":
                    continue
                add_item(
                    items,
                    backlog_policy,
                    category="layout",
                    code=f"format-{component}",
                    surface=surface,
                    identity=identity,
                    source=source,
                    translation=target,
                    provenance=provenance,
                    detail=f"{component}: source={a[component]} translation={b[component]}",
                )

            if (
                not numeric_signatures_match(source, target)
                and not reviewed_semantic_exception(
                    rules, "numeric-signature", surface, source, target
                )
            ):
                add_item(
                    items,
                    backlog_policy,
                    category="numeric-semantics",
                    code="numeric-signature",
                    surface=surface,
                    identity=identity,
                    source=source,
                    translation=target,
                    provenance=provenance,
                    detail="numeric token multiset differs",
                )
            if (
                percentage_signature(source) != percentage_signature(target)
                and not reviewed_semantic_exception(
                    rules, "percentage-signature", surface, source, target
                )
            ):
                add_item(
                    items,
                    backlog_policy,
                    category="numeric-semantics",
                    code="percentage-signature",
                    surface=surface,
                    identity=identity,
                    source=source,
                    translation=target,
                    provenance=provenance,
                    detail="percentage token multiset differs",
                )

        semantic_target = lyric_translation_only(source, target) if surface == "lyrics" else target

        if target == source and (has_kana(source) or has_han(source)) and not source_equal_allowed(source, surface, allowed, names):
            priority_override = "P1" if has_kana(source) else None
            add_item(
                items,
                backlog_policy,
                category="untranslated-or-intentional",
                code="source-equal",
                surface=surface,
                identity=identity,
                source=source,
                translation=target,
                provenance=provenance,
                detail="source and translation are identical",
                metadata={"priority_override": priority_override} if priority_override else None,
            )
            if priority_override:
                items[-1]["priority"] = priority_override

        if (
            semantic_target
            and not (target == source and source_equal_allowed(source, surface, allowed, names))
            and has_unpreserved_kana(semantic_target, kana_preserve_terms)
        ):
            add_item(
                items,
                backlog_policy,
                category="residual-japanese",
                code="target-has-kana",
                surface=surface,
                identity=identity,
                source=source,
                translation=target,
                provenance=provenance,
                detail=f"translated portion still contains kana: {semantic_target[:160]}",
            )

        for term in glossary.get("terms", []):
            if not isinstance(term, dict):
                continue
            scopes = term.get("scopes", [])
            if scopes and surface not in scopes:
                continue
            if not glossary_matches(term, source):
                continue
            preferred = [x for x in term.get("preferred", []) if isinstance(x, str)]
            if preferred and not any(x in semantic_target for x in preferred):
                add_item(
                    items,
                    backlog_policy,
                    category="terminology",
                    code="glossary-disagreement",
                    surface=surface,
                    identity=identity,
                    source=source,
                    translation=target,
                    provenance=provenance,
                    detail=f"{term.get('source')!r} expected one of {preferred!r}",
                    metadata={"glossary_source": term.get("source"), "preferred": preferred},
                )

    by_source: dict[str, dict[str, Any]] = {}
    for rec in records:
        source = rec["source"]
        if not source.strip():
            continue
        target = lyric_translation_only(source, rec["translation"]) if rec["surface"] == "lyrics" else rec["translation"]
        if not target or target == source:
            continue
        bucket = by_source.setdefault(source, {"targets": defaultdict(list), "locations": []})
        bucket["targets"][target].append(f"{rec['surface']}:{rec['identity']}")
        if len(bucket["locations"]) < 20:
            bucket["locations"].append(f"{rec['surface']}:{rec['identity']}")

    for source, bucket in by_source.items():
        targets: dict[str, list[str]] = bucket["targets"]
        if len(targets) <= 1 or len(source.strip()) <= 3:
            continue
        compact_targets = {compact_display_spacing(target) for target in targets}
        target_summary = [
            {"translation": target, "locations": locs[:12]}
            for target, locs in sorted(targets.items())
        ]
        if len(compact_targets) == 1:
            add_item(
                items,
                backlog_policy,
                category="display-spacing-variant",
                code="duplicate-source-layout-variant",
                surface="cross-surface",
                identity=source,
                source=source,
                detail=f"{len(targets)} maintained display-spacing variants for the same exact source",
                locations=bucket["locations"],
                metadata={"translations": target_summary},
            )
            continue
        add_item(
            items,
            backlog_policy,
            category="source-consistency",
            code="duplicate-source-conflict",
            surface="cross-surface",
            identity=source,
            source=source,
            detail=f"{len(targets)} maintained translations for the same exact source",
            locations=bucket["locations"],
            metadata={"translations": target_summary},
        )

    for duplicate in baseline.get("scenario_duplicate_keys", []):
        if not isinstance(duplicate, str):
            continue
        add_item(
            items,
            backlog_policy,
            category="baseline-structure",
            code="scenario-duplicate-key-known",
            surface="scenario",
            identity=duplicate,
            detail="grandfathered duplicate scenario key",
        )

    items.sort(key=lambda x: (x["priority"], x["category"], x["surface"], x["identity"], x["backlog_id"]))
    meta = {"dump_ref": dump_ref, "aligned_records": len(records)}
    return items, meta


def markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# SCSP Translation Quality Backlog",
        "",
        f"- Dump reference: {summary.get('dump_ref') or 'not available'}",
        f"- Total backlog items: **{summary['counts']['total']}**",
        f"- Agent-ready items: **{summary['counts']['agent_ready']}**",
        "",
        "## Priority",
        "",
        "| Priority | Count |",
        "| --- | ---: |",
    ]
    for priority, count in summary["by_priority"].items():
        lines.append(f"| {priority} | {count} |")
    lines += ["", "## Category", "", "| Category | Count |", "| --- | ---: |"]
    for category, count in summary["by_category"].items():
        lines.append(f"| {category} | {count} |")
    lines += [
        "",
        "Generated entries are review tasks, not automatic edit instructions. auto_apply_allowed is false for every item.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a structured, community-reviewable backlog from public SCSP translation QA signals.")
    ap.add_argument("--dump-ref", help="Git ref containing dumps/ (default: auto-detect)")
    ap.add_argument("--priority", action="append", choices=["P1", "P2", "P3"], help="Filter output by priority")
    ap.add_argument("--category", action="append", help="Filter output by backlog category")
    ap.add_argument("--agent-ready-only", action="store_true")
    ap.add_argument(
        "--check-current-key",
        action="store_true",
        help="Exit non-zero when non-exempt backlog items remain on current source-key surfaces.",
    )
    ap.add_argument("--max-items", type=int, default=0)
    ap.add_argument("--output", type=Path, default=QA / "generated" / "quality-backlog.jsonl")
    ap.add_argument("--summary", type=Path, default=QA / "generated" / "quality-backlog-summary.json")
    ap.add_argument("--markdown", type=Path, default=QA / "generated" / "quality-backlog-summary.md")
    args = ap.parse_args()

    dump_ref = resolve_dump_ref(args.dump_ref)
    items, meta = build_items(dump_ref)
    all_items = list(items)
    backlog_policy = load_json(QA / "backlog-policy.json")
    current_key_exempt = set(
        x
        for x in backlog_policy.get("current_key_gate_exempt_categories", [])
        if isinstance(x, str)
    )
    current_key_blockers = [
        item
        for item in all_items
        if item.get("source_authority") == "current-key"
        and item.get("category") not in current_key_exempt
    ]

    if args.priority:
        allowed_priorities = set(args.priority)
        items = [x for x in items if x["priority"] in allowed_priorities]
    if args.category:
        allowed_categories = set(args.category)
        items = [x for x in items if x["category"] in allowed_categories]
    if args.agent_ready_only:
        items = [x for x in items if x["agent_ready"]]
    if args.max_items > 0:
        items = items[: args.max_items]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")

    by_priority = Counter(x["priority"] for x in items)
    by_category = Counter(x["category"] for x in items)
    by_code = Counter(x["code"] for x in items)
    summary = {
        "schema_version": 1,
        **meta,
        "counts": {
            "total": len(items),
            "agent_ready": sum(1 for x in items if x["agent_ready"]),
        },
        "by_priority": dict(sorted(by_priority.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_code": dict(sorted(by_code.items())),
        "filters": {
            "priority": args.priority or [],
            "category": args.category or [],
            "agent_ready_only": bool(args.agent_ready_only),
            "max_items": args.max_items,
        },
        "current_key_gate": {
            "blocker_count": len(current_key_blockers),
            "exempt_categories": sorted(current_key_exempt),
        },
        "output": args.output.resolve().relative_to(QA.parent.resolve()).as_posix()
        if args.output.resolve().is_relative_to(QA.parent.resolve())
        else args.output.name,
    }
    write_json(args.summary, summary)
    args.markdown.write_text(markdown_summary(summary), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.check_current_key and current_key_blockers:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
