from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from qa_common import DATA, QA, has_kana, load_json, write_json

DRAMA_SOURCE_SNAPSHOT = QA / "current-source" / "drama-2.17-source.json.gz"
DRAMA_SOURCE_MANIFEST = QA / "current-source" / "drama-2.17-manifest.json"

SCENARIO_KEYS = {"scenario_id", "selected_schema", "lines"}
LINE_KEYS = {
    "line_index",
    "identity_sha256",
    "runtime_key_sha256",
    "source_schema",
    "unique_id",
    "speaker",
    "display_speaker",
    "source",
    "previous_source",
    "next_source",
}
TRANSLATION_ENTRY_KEYS = {
    "scenarioId",
    "sourceSchema",
    "uniqueId",
    "source",
    "text",
    "talkerName",
}


def identity_sha256(
    scenario_id: str,
    source_schema: str,
    unique_id: str,
    source: str,
) -> str:
    raw = "\0".join([scenario_id, source_schema, unique_id, source]).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def runtime_key_sha256(unique_id: str, source: str) -> str:
    raw = "\0".join([unique_id, source]).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_current_drama_source() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_json(DRAMA_SOURCE_MANIFEST)
    if not isinstance(manifest, dict):
        raise ValueError("drama source manifest must be a JSON object")

    compressed = DRAMA_SOURCE_SNAPSHOT.read_bytes()
    actual_gzip = hashlib.sha256(compressed).hexdigest()
    expected_gzip = manifest.get("source_snapshot_gzip_sha256")
    if actual_gzip != expected_gzip:
        raise ValueError(
            f"drama source gzip hash mismatch: expected {expected_gzip}, got {actual_gzip}"
        )

    raw = gzip.decompress(compressed)
    actual_raw = hashlib.sha256(raw).hexdigest()
    expected_raw = manifest.get("source_snapshot_uncompressed_sha256")
    if actual_raw != expected_raw:
        raise ValueError(
            f"drama source raw hash mismatch: expected {expected_raw}, got {actual_raw}"
        )

    source = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(source, dict):
        raise ValueError("drama source snapshot must be a JSON object")
    if source.get("game_version") != manifest.get("game_version"):
        raise ValueError(
            f"drama source game_version mismatch: snapshot={source.get('game_version')!r}, "
            f"manifest={manifest.get('game_version')!r}"
        )
    if source.get("selection_rule") != manifest.get("selection_rule"):
        raise ValueError("drama source selection_rule mismatch with manifest")
    scenarios = source.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("drama source snapshot requires scenarios[]")
    row_count = sum(
        len(scenario.get("lines", []))
        for scenario in scenarios
        if isinstance(scenario, dict) and isinstance(scenario.get("lines"), list)
    )
    runtime_keys = {
        (line.get("unique_id"), line.get("source"))
        for scenario in scenarios
        if isinstance(scenario, dict) and isinstance(scenario.get("lines"), list)
        for line in scenario["lines"]
        if isinstance(line, dict)
    }
    if len(scenarios) != manifest.get("resolved_scenarios"):
        raise ValueError(
            f"drama source scenario count mismatch: snapshot={len(scenarios)}, "
            f"manifest={manifest.get('resolved_scenarios')}"
        )
    if row_count != manifest.get("source_rows"):
        raise ValueError(
            f"drama source row count mismatch: snapshot={row_count}, "
            f"manifest={manifest.get('source_rows')}"
        )
    if len(runtime_keys) != manifest.get("runtime_key_count"):
        raise ValueError(
            f"drama runtime-key count mismatch: snapshot={len(runtime_keys)}, "
            f"manifest={manifest.get('runtime_key_count')}"
        )
    return source, manifest


def flatten_source(
    source: dict[str, Any],
    *,
    example_limit: int = 50,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    scenarios = source.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("drama source snapshot requires scenarios[]")

    by_runtime_key: dict[tuple[str, str], dict[str, Any]] = {}
    identity_seen: set[str] = set()
    errors: list[str] = []
    scenario_ids: set[str] = set()
    line_count = 0

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            errors.append("scenario entry is not an object")
            continue
        extra_scenario_keys = set(scenario) - SCENARIO_KEYS
        if extra_scenario_keys:
            errors.append(
                f"scenario contains non-public fields: {sorted(extra_scenario_keys)}"
            )

        scenario_id = scenario.get("scenario_id")
        selected_schema = scenario.get("selected_schema")
        lines = scenario.get("lines")
        if not isinstance(scenario_id, str) or not isinstance(selected_schema, str):
            errors.append("scenario_id/selected_schema must be strings")
            continue
        if not isinstance(lines, list):
            errors.append(f"{scenario_id}: lines must be an array")
            continue
        if scenario_id in scenario_ids:
            errors.append(f"duplicate scenario_id: {scenario_id}")
        scenario_ids.add(scenario_id)

        for expected_index, line in enumerate(lines):
            line_count += 1
            if not isinstance(line, dict):
                errors.append(f"{scenario_id}[{expected_index}]: line is not an object")
                continue
            extra_line_keys = set(line) - LINE_KEYS
            if extra_line_keys:
                errors.append(
                    f"{scenario_id}[{expected_index}]: non-public fields {sorted(extra_line_keys)}"
                )

            required_strings = [
                "identity_sha256",
                "runtime_key_sha256",
                "source_schema",
                "unique_id",
                "speaker",
                "display_speaker",
                "source",
            ]
            if any(not isinstance(line.get(key), str) for key in required_strings):
                errors.append(
                    f"{scenario_id}[{expected_index}]: required string field missing"
                )
                continue
            if line.get("line_index") != expected_index:
                errors.append(
                    f"{scenario_id}[{expected_index}]: line_index={line.get('line_index')!r}"
                )

            source_text = line["source"]
            unique_id = line["unique_id"]
            source_schema = line["source_schema"]
            expected_identity = identity_sha256(
                scenario_id, source_schema, unique_id, source_text
            )
            if line["identity_sha256"] != expected_identity:
                errors.append(
                    f"{scenario_id}[{expected_index}]: identity_sha256 mismatch"
                )
            expected_runtime_hash = runtime_key_sha256(unique_id, source_text)
            if line["runtime_key_sha256"] != expected_runtime_hash:
                errors.append(
                    f"{scenario_id}[{expected_index}]: runtime_key_sha256 mismatch"
                )
            if expected_identity in identity_seen:
                errors.append(
                    f"{scenario_id}[{expected_index}]: duplicate collision-safe identity"
                )
            identity_seen.add(expected_identity)

            previous = lines[expected_index - 1]["source"] if expected_index else None
            next_source = (
                lines[expected_index + 1]["source"]
                if expected_index + 1 < len(lines)
                else None
            )
            if line.get("previous_source") != previous:
                errors.append(
                    f"{scenario_id}[{expected_index}]: previous_source mismatch"
                )
            if line.get("next_source") != next_source:
                errors.append(f"{scenario_id}[{expected_index}]: next_source mismatch")

            runtime_key = (unique_id, source_text)
            if runtime_key in by_runtime_key:
                errors.append(
                    f"{scenario_id}[{expected_index}]: duplicate runtime uniqueId+source key"
                )
            by_runtime_key[runtime_key] = {
                **line,
                "scenario_id": scenario_id,
                "selected_schema": selected_schema,
            }

    return by_runtime_key, {
        "scenario_count": len(scenario_ids),
        "line_count": line_count,
        "identity_count": len(identity_seen),
        "source_errors": errors[:example_limit],
        "source_error_count": len(errors),
    }


def audit_current_drama(
    source: dict[str, Any],
    translation: dict[str, Any],
    *,
    example_limit: int = 50,
) -> dict[str, Any]:
    source_rows, source_stats = flatten_source(source, example_limit=example_limit)

    target_version_error = int(translation.get("targetGameVersion") != "2.17.0")

    entries = translation.get("entries")
    if not isinstance(entries, list):
        raise ValueError("drama translation requires entries[]")

    target_rows: dict[tuple[str, str], dict[str, Any]] = {}
    target_errors: list[str] = []
    target_kana_rows = 0
    source_equal_rows = 0
    source_equal_han_rows = 0
    source_equal_safe_rows = 0
    empty_translation_rows = 0

    for index, row in enumerate(entries):
        if not isinstance(row, dict):
            target_errors.append(f"entries[{index}] is not an object")
            continue
        extra = set(row) - TRANSLATION_ENTRY_KEYS
        if extra:
            target_errors.append(
                f"entries[{index}] contains non-public fields: {sorted(extra)}"
            )
        if any(not isinstance(row.get(key), str) for key in TRANSLATION_ENTRY_KEYS):
            target_errors.append(f"entries[{index}] has missing/non-string fields")
            continue

        key = (row["uniqueId"], row["source"])
        if key in target_rows:
            target_errors.append(
                f"entries[{index}] duplicates runtime key uniqueId+source"
            )
        target_rows[key] = row

        text = row["text"]
        if not text:
            empty_translation_rows += 1
        if has_kana(text):
            target_kana_rows += 1
        if text == row["source"]:
            source_equal_rows += 1
            if any("\u3400" <= ch <= "\u9fff" for ch in text):
                source_equal_han_rows += 1
            elif not has_kana(text):
                source_equal_safe_rows += 1

    missing_keys = sorted(set(source_rows) - set(target_rows))
    extra_keys = sorted(set(target_rows) - set(source_rows))
    metadata_mismatches: list[dict[str, str]] = []
    metadata_mismatch_count = 0

    for key in sorted(set(source_rows) & set(target_rows)):
        src = source_rows[key]
        tgt = target_rows[key]
        mismatch_parts = []
        if tgt["scenarioId"] != src["scenario_id"]:
            mismatch_parts.append(
                f"scenarioId: {tgt['scenarioId']!r} != {src['scenario_id']!r}"
            )
        if tgt["sourceSchema"] != src["source_schema"]:
            mismatch_parts.append(
                f"sourceSchema: {tgt['sourceSchema']!r} != {src['source_schema']!r}"
            )
        if tgt["talkerName"] != src["speaker"]:
            mismatch_parts.append(
                f"talkerName: {tgt['talkerName']!r} != {src['speaker']!r}"
            )
        if mismatch_parts:
            metadata_mismatch_count += 1
            if len(metadata_mismatches) < example_limit:
                metadata_mismatches.append(
                    {
                        "uniqueId": key[0],
                        "source": key[1],
                        "detail": "; ".join(mismatch_parts),
                    }
                )

    return {
        **source_stats,
        "target_version_error": target_version_error,
        "translation_rows": len(entries),
        "translation_runtime_key_count": len(target_rows),
        "target_error_count": len(target_errors),
        "target_errors": target_errors[:example_limit],
        "mapped_rows": len(set(source_rows) & set(target_rows)),
        "missing_rows": len(missing_keys),
        "extra_rows": len(extra_keys),
        "missing_examples": [
            {"unique_id": uid, "source": source_text}
            for uid, source_text in missing_keys[:example_limit]
        ],
        "extra_examples": [
            {"unique_id": uid, "source": source_text}
            for uid, source_text in extra_keys[:example_limit]
        ],
        "metadata_mismatch_count": metadata_mismatch_count,
        "metadata_mismatches": metadata_mismatches,
        "target_kana_rows": target_kana_rows,
        "empty_translation_rows": empty_translation_rows,
        "source_equal_rows": source_equal_rows,
        "source_equal_han_rows": source_equal_han_rows,
        "source_equal_safe_rows": source_equal_safe_rows,
    }


def markdown_report(report: dict[str, Any]) -> str:
    audit = report["audit"]
    return "\n".join(
        [
            "# Current SCSP 2.17 Drama audit",
            "",
            f"- Status: **{report['status']}**",
            f"- Game version: **{report['snapshot']['game_version']}**",
            f"- Resolved scenarios: **{report['snapshot']['resolved_scenarios']} / {report['snapshot']['expected_scenarios']}**",
            f"- Current dialogue rows: **{audit['line_count']}**",
            f"- Runtime-key mapped rows: **{audit['mapped_rows']}**",
            f"- Missing / extra rows: **{audit['missing_rows']} / {audit['extra_rows']}**",
            f"- Metadata mismatches: **{audit['metadata_mismatch_count']}**",
            f"- Target kana rows: **{audit['target_kana_rows']}**",
            f"- Empty translations: **{audit['empty_translation_rows']}**",
            f"- Source-equal rows: **{audit['source_equal_rows']}** "
            f"({audit['source_equal_han_rows']} Han-only / {audit['source_equal_safe_rows']} safe)",
            "",
            "The runtime lookup identity is exact uniqueId + source. The public source snapshot also carries a collision-safe SHA-256 identity over scenario, selected schema, uniqueId, and source, plus previous/next source context. Bundle/resource-path metadata is intentionally excluded.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit public SCSP 2.17 Drama translations against the bundled current Drama source snapshot."
    )
    parser.add_argument(
        "--translation",
        type=Path,
        default=DATA / "drama.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=QA / "generated" / "current-drama-audit.json",
    )
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=QA / "generated" / "current-drama-audit.md",
    )
    parser.add_argument("--example-limit", type=int, default=50)
    args = parser.parse_args()

    source, manifest = load_current_drama_source()
    translation = load_json(args.translation)
    if not isinstance(translation, dict):
        raise SystemExit("drama translation must be a JSON object")

    audit = audit_current_drama(
        source,
        translation,
        example_limit=max(0, args.example_limit),
    )
    hard_failures = (
        audit["source_error_count"]
        + audit["target_version_error"]
        + audit["target_error_count"]
        + audit["missing_rows"]
        + audit["extra_rows"]
        + audit["metadata_mismatch_count"]
        + audit["target_kana_rows"]
        + audit["empty_translation_rows"]
    )
    report = {
        "schema_version": 1,
        "status": "PASS" if hard_failures == 0 else "FAIL",
        "hard_failures": hard_failures,
        "snapshot": {
            "game_version": manifest.get("game_version"),
            "expected_scenarios": manifest.get("expected_scenarios"),
            "resolved_scenarios": manifest.get("resolved_scenarios"),
            "source_rows": manifest.get("source_rows"),
            "source_snapshot_uncompressed_sha256": manifest.get(
                "source_snapshot_uncompressed_sha256"
            ),
            "source_snapshot_gzip_sha256": manifest.get(
                "source_snapshot_gzip_sha256"
            ),
        },
        "audit": audit,
    }

    write_json(args.report, report)
    args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_report.write_text(
        markdown_report(report), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "resolved_scenarios": manifest.get("resolved_scenarios"),
                "source_rows": audit["line_count"],
                "mapped_rows": audit["mapped_rows"],
                "missing_rows": audit["missing_rows"],
                "extra_rows": audit["extra_rows"],
                "metadata_mismatch_count": audit["metadata_mismatch_count"],
                "target_kana_rows": audit["target_kana_rows"],
                "source_equal_rows": audit["source_equal_rows"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
