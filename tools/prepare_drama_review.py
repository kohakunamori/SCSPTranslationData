from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_current_drama import flatten_source, load_current_drama_source
from qa_common import DATA, QA, load_json


def build_review_records(
    source: dict[str, Any],
    translation: dict[str, Any],
    *,
    scenarios: set[str] | None = None,
    source_equal_only: bool = False,
) -> list[dict[str, Any]]:
    source_rows, source_stats = flatten_source(source)
    if source_stats["source_error_count"]:
        raise ValueError(
            f"current Drama source snapshot has {source_stats['source_error_count']} structural errors"
        )

    entries = translation.get("entries")
    if not isinstance(entries, list):
        raise ValueError("drama translation requires entries[]")
    target_rows = {
        (row["uniqueId"], row["source"]): row
        for row in entries
        if isinstance(row, dict)
        and isinstance(row.get("uniqueId"), str)
        and isinstance(row.get("source"), str)
        and isinstance(row.get("text"), str)
    }

    records: list[dict[str, Any]] = []
    for runtime_key, src in source_rows.items():
        target = target_rows.get(runtime_key)
        if target is None:
            continue
        if scenarios and src["scenario_id"] not in scenarios:
            continue
        source_equal = target["text"] == src["source"]
        if source_equal_only and not source_equal:
            continue
        records.append(
            {
                "schema_version": 1,
                "identity_sha256": src["identity_sha256"],
                "runtime_key_sha256": src["runtime_key_sha256"],
                "scenario_id": src["scenario_id"],
                "line_index": src["line_index"],
                "source_schema": src["source_schema"],
                "unique_id": src["unique_id"],
                "speaker": src["speaker"],
                "source": src["source"],
                "translation": target["text"],
                "previous_source": src["previous_source"],
                "next_source": src["next_source"],
                "source_equal": source_equal,
            }
        )

    records.sort(key=lambda row: (row["scenario_id"], row["line_index"], row["identity_sha256"]))
    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare public, context-rich SCSP 2.17 Drama review records for humans or translation agents."
    )
    parser.add_argument(
        "--translation",
        type=Path,
        default=DATA / "drama.json",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        help="Limit output to one or more exact scenario IDs.",
    )
    parser.add_argument(
        "--source-equal-only",
        action="store_true",
        help="Emit only current rows whose maintained translation equals the source.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Limit emitted rows after deterministic sorting; 0 means unlimited.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=QA / "generated" / "drama-review.jsonl",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=QA / "generated" / "drama-review-summary.json",
    )
    args = parser.parse_args()

    source, manifest = load_current_drama_source()
    translation = load_json(args.translation)
    if not isinstance(translation, dict):
        raise SystemExit("drama translation must be a JSON object")

    selected_scenarios = set(args.scenario or [])
    records = build_review_records(
        source,
        translation,
        scenarios=selected_scenarios or None,
        source_equal_only=args.source_equal_only,
    )
    total_before_limit = len(records)
    if args.max_items > 0:
        records = records[: args.max_items]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {
        "schema_version": 1,
        "game_version": manifest.get("game_version"),
        "source_rows": manifest.get("source_rows"),
        "filters": {
            "scenarios": sorted(selected_scenarios),
            "source_equal_only": bool(args.source_equal_only),
            "max_items": args.max_items,
        },
        "matching_records_before_limit": total_before_limit,
        "emitted_records": len(records),
        "source_equal_records": sum(row["source_equal"] for row in records),
        "output": args.output.resolve().relative_to(QA.parent.resolve()).as_posix()
        if args.output.resolve().is_relative_to(QA.parent.resolve())
        else str(args.output),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
