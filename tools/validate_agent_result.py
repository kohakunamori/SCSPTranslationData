from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from qa_common import (
    format_signature,
    has_kana,
    has_unpreserved_kana,
    numeric_signatures_match,
    percentage_signature,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: record must be an object")
            rows.append(row)
    return rows


class Findings:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def validate(batch_path: Path, result_path: Path) -> dict[str, Any]:
    batch = read_jsonl(batch_path)
    result = read_jsonl(result_path)
    findings = Findings()

    expected: dict[str, dict[str, Any]] = {}
    for row in batch:
        sid = row.get("source_id")
        if not isinstance(sid, str):
            findings.error("batch record missing string source_id")
            continue
        if sid in expected:
            findings.error(f"batch duplicate source_id: {sid}")
        expected[sid] = row

    seen: dict[str, dict[str, Any]] = {}
    decisions: Counter[str] = Counter()

    for row in result:
        sid = row.get("source_id")
        if not isinstance(sid, str):
            findings.error("result record missing string source_id")
            continue
        if sid in seen:
            findings.error(f"duplicate result source_id: {sid}")
            continue
        seen[sid] = row

        source_row = expected.get(sid)
        if source_row is None:
            findings.error(f"unknown source_id: {sid}")
            continue

        if row.get("schema_version") != 1:
            findings.error(f"{sid}: schema_version must be 1")

        source = row.get("source")
        if source != source_row.get("source"):
            findings.error(f"{sid}: source text mismatch")
            continue

        decision = row.get("decision")
        if decision not in {"translate", "keep_source", "needs_review"}:
            findings.error(f"{sid}: unsupported decision {decision!r}")
            continue
        decisions[decision] += 1

        target = row.get("translation")
        if not isinstance(target, str):
            findings.error(f"{sid}: translation must be a string")
            continue

        if decision == "translate":
            if target == source:
                findings.error(f"{sid}: translate decision may not equal source")
            if not target.strip():
                findings.error(f"{sid}: translation may not be empty")

            src_sig = format_signature(source)
            dst_sig = format_signature(target)
            for component in ("brace", "printf", "tags"):
                if src_sig[component] != dst_sig[component]:
                    findings.error(f"{sid}: {component} signature changed")

            if not numeric_signatures_match(source, target):
                findings.warning(f"{sid}: numeric signature changed")
            if percentage_signature(source) != percentage_signature(target):
                findings.warning(f"{sid}: percentage signature changed")
            preserve_terms = [x for x in source_row.get("preserve_terms", []) if isinstance(x, str)]
            if has_unpreserved_kana(target, preserve_terms):
                findings.warning(f"{sid}: translation still contains kana")

        elif decision == "keep_source":
            if target != source:
                findings.error(f"{sid}: keep_source requires translation == source")
            note = row.get("note")
            if not isinstance(note, str) or not note.strip():
                findings.warning(f"{sid}: keep_source should explain why the source form is intentional")

        elif decision == "needs_review":
            note = row.get("note")
            if not isinstance(note, str) or not note.strip():
                findings.warning(f"{sid}: needs_review should include a note")

    missing = sorted(set(expected) - set(seen))
    for sid in missing[:100]:
        findings.error(f"missing result source_id: {sid}")
    if len(missing) > 100:
        findings.error(f"... and {len(missing) - 100} additional missing source_ids")

    report = {
        "schema_version": 1,
        "status": "PASS" if not findings.errors else "FAIL",
        "batch_rows": len(batch),
        "result_rows": len(result),
        "decision_counts": dict(sorted(decisions.items())),
        "error_count": len(findings.errors),
        "warning_count": len(findings.warnings),
        "errors": findings.errors,
        "warnings": findings.warnings,
    }
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    ap = argparse.ArgumentParser(description="Validate structured translation-agent output before applying it.")
    ap.add_argument("batch", type=Path)
    ap.add_argument("result", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    try:
        report = validate(args.batch, args.result)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
