from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from qa_common import (
    QA,
    aligned_records,
    canonical_same_form,
    has_han,
    has_kana,
    load_policy,
    lyric_translation_only,
    resolve_dump_ref,
    write_json,
)


def source_id(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]


def is_allowed_same_form(
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


def semantic_target(surface: str, source: str, target: str) -> str:
    return lyric_translation_only(source, target) if surface == "lyrics" else target


def relevant_terms(source: str, glossary: dict[str, Any], surfaces: set[str]) -> list[dict[str, Any]]:
    out = []
    for term in glossary.get("terms", []):
        if not isinstance(term, dict):
            continue
        needle = term.get("source")
        preferred = term.get("preferred")
        if not isinstance(needle, str) or not isinstance(preferred, list):
            continue
        scopes = {x for x in term.get("scopes", []) if isinstance(x, str)}
        if scopes and not (scopes & surfaces):
            continue
        match = source == needle if term.get("match") == "exact" else needle in source
        if not match:
            continue
        row = {
            "source": needle,
            "preferred": [x for x in preferred if isinstance(x, str)],
        }
        if isinstance(term.get("note"), str):
            row["note"] = term["note"]
        if row["preferred"]:
            out.append(row)
    return out


def relevant_names(source: str, names: dict[str, Any]) -> list[dict[str, str]]:
    compact_source = source.replace(" ", "").replace("\u00a0", "")
    out = []
    for row in names.get("names", []):
        if not isinstance(row, dict):
            continue
        name_source = row.get("source")
        translation = row.get("translation")
        if not isinstance(name_source, str) or not isinstance(translation, str):
            continue
        compact_name = name_source.replace(" ", "").replace("\u00a0", "")
        if compact_name and compact_name in compact_source:
            out.append({"source": name_source, "translation": translation})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare a model-agnostic translation batch from public SCSP translation data.")
    ap.add_argument("--dump-ref", help="Git ref containing dumps/ (default: auto-detect)")
    ap.add_argument(
        "--surface",
        action="append",
        choices=["localify", "local2", "lyrics", "scenario"],
        help="Limit to one or more surfaces (repeatable)",
    )
    ap.add_argument(
        "--include-tm-candidates",
        action="store_true",
        help="Include unresolved occurrences that have exactly one existing translation elsewhere for the same source.",
    )
    ap.add_argument(
        "--include-review",
        action="store_true",
        help="Include sources with conflicting maintained translations.",
    )
    ap.add_argument("--max-records", type=int, default=0, help="Optional deterministic output limit (0 = no limit)")
    ap.add_argument("--output", type=Path, default=QA / "generated" / "agent-batch.jsonl")
    ap.add_argument("--summary", type=Path, default=QA / "generated" / "agent-batch-summary.json")
    args = ap.parse_args()

    dump_ref = resolve_dump_ref(args.dump_ref)
    _, glossary, names, allowed = load_policy()
    selected_surfaces = set(args.surface or [])

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for rec in aligned_records(dump_ref):
        if selected_surfaces and rec["surface"] not in selected_surfaces:
            continue
        groups[rec["source"]].append(rec)

    batch = []
    skipped_allowed = 0
    skipped_resolved = 0
    skipped_tm = 0
    skipped_conflict = 0

    for source in sorted(groups):
        if not source.strip():
            continue
        occurrences = groups[source]
        unresolved = []
        existing_targets = set()

        for rec in occurrences:
            target = rec["translation"]
            target_only = semantic_target(rec["surface"], source, target)
            if target == source:
                if not is_allowed_same_form(source, rec["surface"], allowed, names):
                    unresolved.append(rec)
                else:
                    skipped_allowed += 1
            elif target_only and target_only != source:
                existing_targets.add(target_only)

        if not unresolved:
            skipped_resolved += 1
            continue

        if len(existing_targets) == 0:
            classification = "needs_translation"
        elif len(existing_targets) == 1:
            classification = "translation_memory_candidate"
            if not args.include_tm_candidates:
                skipped_tm += 1
                continue
        else:
            classification = "needs_review"
            if not args.include_review:
                skipped_conflict += 1
                continue

        if not (has_kana(source) or has_han(source)):
            continue

        occurrence_rows = []
        for rec in unresolved:
            occurrence_rows.append({
                "surface": rec["surface"],
                "identity": rec["identity"],
                "provenance": rec["provenance"],
            })
        occurrence_rows.sort(key=lambda x: (x["surface"], x["identity"]))
        occurrence_surfaces = {x["surface"] for x in occurrence_rows}
        preserve_candidates = [
            *[x for x in glossary.get("preserve_terms", []) if isinstance(x, str)],
            *[x for x in glossary.get("kana_preserve_terms", []) if isinstance(x, str)],
        ]
        preserve = [
            term
            for term in preserve_candidates
            if term in source
        ]

        batch.append({
            "schema_version": 1,
            "source_id": source_id(source),
            "source": source,
            "classification": classification,
            "occurrences": occurrence_rows,
            "existing_translations": sorted(existing_targets),
            "relevant_terms": relevant_terms(source, glossary, occurrence_surfaces),
            "relevant_names": relevant_names(source, names),
            "preserve_terms": sorted(set(preserve)),
        })

    batch.sort(key=lambda x: (x["classification"], x["source"], x["source_id"]))
    if args.max_records > 0:
        batch = batch[: args.max_records]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as f:
        for row in batch:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    counts = defaultdict(int)
    for row in batch:
        counts["records"] += 1
        counts["classification_" + row["classification"]] += 1
        counts["occurrences"] += len(row["occurrences"])

    summary = {
        "schema_version": 1,
        "dump_ref": dump_ref,
        "surfaces": sorted(selected_surfaces) if selected_surfaces else ["localify", "local2", "lyrics", "scenario"],
        "counts": dict(sorted(counts.items())),
        "skipped": {
            "reviewed_same_form_occurrences": skipped_allowed,
            "already_resolved_sources": skipped_resolved,
            "tm_candidate_sources": skipped_tm,
            "conflict_sources": skipped_conflict,
        },
        "output": args.output.resolve().relative_to(QA.parent.resolve()).as_posix()
        if args.output.resolve().is_relative_to(QA.parent.resolve())
        else args.output.name,
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
