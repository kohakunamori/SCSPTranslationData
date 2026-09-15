from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from qa_common import (
    QA,
    ROOT,
    aligned_records,
    has_han,
    has_kana,
    load_policy,
    lyric_translation_only,
    resolve_dump_ref,
    write_json,
)


def stable_id(surface: str, identity: str, source: str) -> str:
    raw = f"{surface}\0{identity}\0{source}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def source_equal_allowed(source: str, surface: str, allowed: dict[str, Any]) -> bool:
    if source in set(allowed.get("global", [])):
        return True
    by_surface = allowed.get("by_surface", {})
    return isinstance(by_surface, dict) and source in set(by_surface.get(surface, []))


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a public translation-memory view from TransData and public source references.")
    ap.add_argument("--dump-ref", help="Git ref containing dumps/ (default: auto-detect)")
    ap.add_argument("--output", type=Path, default=QA / "generated" / "translation-memory.jsonl")
    ap.add_argument("--conflicts", type=Path, default=QA / "generated" / "translation-memory-conflicts.json")
    ap.add_argument("--summary", type=Path, default=QA / "generated" / "translation-memory-summary.json")
    args = ap.parse_args()

    try:
        dump_ref = resolve_dump_ref(args.dump_ref)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    _, _, _, allowed = load_policy()
    records = list(aligned_records(dump_ref))
    rows: list[dict[str, Any]] = []

    for rec in records:
        source = rec["source"]
        target = rec["translation"]
        surface = rec["surface"]
        translation_only = lyric_translation_only(source, target) if surface == "lyrics" else target

        if target != source:
            status = "translated"
        elif source_equal_allowed(source, surface, allowed):
            status = "reviewed-same-form"
        elif has_kana(source) or has_han(source):
            status = "needs-review"
        else:
            status = "same-form"

        row = {
            "schema_version": 1,
            "memory_id": stable_id(surface, rec["identity"], source),
            "surface": surface,
            "identity": rec["identity"],
            "source": source,
            "translation": target,
            "translation_only": translation_only,
            "status": status,
            "provenance": rec["provenance"],
        }
        for optional in ("table", "key", "path"):
            if optional in rec:
                row[optional] = rec[optional]
        rows.append(row)

    rows.sort(key=lambda x: (x["surface"], x["identity"], x["source"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if not row["source"].strip():
            continue
        target = row["translation_only"] if row["surface"] == "lyrics" else row["translation"]
        if not target or target == row["source"]:
            continue
        grouped[row["source"]][target].append(row["memory_id"])

    conflicts = []
    for source, targets in grouped.items():
        if len(targets) <= 1:
            continue
        conflicts.append({
            "source": source,
            "translation_count": len(targets),
            "translations": [
                {"translation": target, "memory_ids": ids}
                for target, ids in sorted(targets.items())
            ],
        })
    conflicts.sort(key=lambda x: (-x["translation_count"], x["source"]))
    write_json(args.conflicts, {
        "schema_version": 1,
        "description": "Exact source strings with more than one maintained translation. These require context review before reuse.",
        "conflicts": conflicts,
    })

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts["rows"] += 1
        counts["surface_" + row["surface"]] += 1
        counts["status_" + row["status"]] += 1
    counts["conflict_sources"] = len(conflicts)

    def public_path(path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return path.name

    summary = {
        "schema_version": 1,
        "dump_ref": dump_ref,
        "counts": dict(sorted(counts.items())),
        "output": public_path(args.output),
        "conflicts": public_path(args.conflicts),
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
