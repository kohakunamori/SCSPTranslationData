from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from qa_common import (
    DATA,
    QA,
    aligned_records,
    compact_display_spacing,
    format_signature,
    lyric_translation_only,
    numeric_signatures_match,
    percentage_signature,
    resolve_dump_ref,
    write_json,
)


def full_signature_compatible(source: str, target: str) -> bool:
    source_sig = format_signature(source)
    target_sig = format_signature(target)
    protected = ("brace", "printf", "tags", "lf", "cr", "nbsp")
    return (
        all(source_sig[key] == target_sig[key] for key in protected)
        and numeric_signatures_match(source, target)
        and percentage_signature(source) == percentage_signature(target)
    )


def find_candidates(records: Iterable[dict[str, str]]) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in records:
        by_source[record["source"]].append(record)

    candidates: list[dict[str, Any]] = []
    for source, source_records in by_source.items():
        if len(source.strip()) <= 3:
            continue

        targets: dict[str, list[dict[str, str]]] = defaultdict(list)
        for record in source_records:
            target = (
                lyric_translation_only(source, record["translation"])
                if record["surface"] == "lyrics"
                else record["translation"]
            )
            if target and target != source:
                targets[target].append(record)

        # Only canonicalize a simple two-way conflict. Three or more maintained
        # targets require contextual review.
        if len(targets) != 2:
            continue

        local2_records = [record for record in source_records if record["surface"] == "local2"]
        if len(local2_records) != 1:
            continue
        local2_record = local2_records[0]
        old_target = local2_record["translation"]

        old_occurrences = targets.get(old_target)
        if (
            old_occurrences is None
            or len(old_occurrences) != 1
            or old_occurrences[0]["surface"] != "local2"
        ):
            continue

        alternatives = [target for target in targets if target != old_target]
        if len(alternatives) != 1:
            continue
        canonical_target = alternatives[0]
        canonical_occurrences = targets[canonical_target]

        # The canonical side must be unanimous and maintained only by localify
        # occurrences. This avoids cross-surface voting between unrelated forms.
        if not canonical_occurrences or any(
            record["surface"] != "localify" for record in canonical_occurrences
        ):
            continue

        # Pure whitespace/NBSP/full-width-space differences are intentional
        # display variants and belong to the layout backlog, not semantic
        # canonicalization.
        if compact_display_spacing(old_target) == compact_display_spacing(canonical_target):
            continue

        if not full_signature_compatible(source, canonical_target):
            continue

        candidates.append(
            {
                "schema_version": 1,
                "source": source,
                "surface": "local2",
                "identity": local2_record["identity"],
                "old_translation": old_target,
                "canonical_translation": canonical_target,
                "canonical_occurrence_count": len(canonical_occurrences),
                "canonical_occurrences": [
                    {
                        "surface": record["surface"],
                        "identity": record["identity"],
                        "provenance": record["provenance"],
                    }
                    for record in canonical_occurrences
                ],
                "source_authority": "current-key",
                "auto_apply_rule": "two-way-exact-source-local2-outlier-v1",
            }
        )

    candidates.sort(
        key=lambda row: (
            -row["canonical_occurrence_count"],
            row["source"],
            row["identity"],
        )
    )
    return candidates


def apply_candidates(path: Path, candidates: list[dict[str, Any]]) -> int:
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(text)
    applied = 0

    for row in candidates:
        source = row["source"]
        old = row["old_translation"]
        new = row["canonical_translation"]

        current = data.get(source)
        if current != old:
            raise RuntimeError(
                f"{source!r}: local2 changed since proposal generation; "
                f"expected {old!r}, found {current!r}"
            )

        old_pair = f"{json.dumps(source, ensure_ascii=False)}: {json.dumps(old, ensure_ascii=False)}"
        new_pair = f"{json.dumps(source, ensure_ascii=False)}: {json.dumps(new, ensure_ascii=False)}"
        matches = text.count(old_pair)
        if matches != 1:
            raise RuntimeError(
                f"{source!r}: expected one exact JSON pair, found {matches}"
            )
        text = text.replace(old_pair, new_pair, 1)
        data[source] = new
        applied += 1

    if applied:
        path.write_text(text, encoding="utf-8", newline="\n")
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Propose or apply strict exact-source canonicalization where local2 "
            "is the lone divergent translation and all maintained localify "
            "occurrences unanimously use one format-compatible target."
        )
    )
    parser.add_argument("--dump-ref", help="Git ref containing dumps/ (default: auto-detect)")
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--apply",
        action="store_true",
        help="Apply the generated proposal to scsp_localify/local2.json.",
    )
    action_group.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when strict canonicalization candidates exist.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Optional deterministic proposal/apply limit (0 = all candidates).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=QA / "generated" / "exact-source-canonicalization.json",
    )
    args = parser.parse_args()

    dump_ref = resolve_dump_ref(args.dump_ref)
    candidates = find_candidates(aligned_records(dump_ref))
    if args.max_items > 0:
        candidates = candidates[: args.max_items]

    report = {
        "schema_version": 1,
        "dump_ref": dump_ref,
        "rule": "two-way-exact-source-local2-outlier-v1",
        "candidate_count": len(candidates),
        "applied": False,
        "applied_count": 0,
        "candidates": candidates,
    }

    if args.apply:
        report["applied_count"] = apply_candidates(DATA / "local2.json", candidates)
        report["applied"] = True

    write_json(args.output, report)
    print(
        json.dumps(
            {
                "dump_ref": dump_ref,
                "candidate_count": len(candidates),
                "applied": report["applied"],
                "applied_count": report["applied_count"],
                "output": args.output.resolve().relative_to(QA.parent.resolve()).as_posix()
                if args.output.resolve().is_relative_to(QA.parent.resolve())
                else args.output.name,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.check and candidates:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
