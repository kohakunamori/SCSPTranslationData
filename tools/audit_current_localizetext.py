from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from qa_common import DATA, QA, load_current_localizetext_source, load_json, write_json

KANA_RE = re.compile(r"[\u3041-\u3096\u309d-\u309f\u30a1-\u30fa\u30fd-\u30ff\uff66-\uff9d]")
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
MARKUP_TAG_RE = re.compile(r"<(?P<close>/)?(?P<name>link|color)(?:=[^>]*)?>", re.I)


def markup_balance_errors(text: str) -> list[str]:
    stack: list[str] = []
    errors: list[str] = []
    for match in MARKUP_TAG_RE.finditer(text):
        name = match.group("name").lower()
        if not match.group("close"):
            stack.append(name)
            continue
        if not stack:
            errors.append(f"orphan closing {name}")
            continue
        if stack[-1] != name:
            errors.append(f"closing {name} while {stack[-1]} is open")
            if name in stack:
                stack.remove(name)
            continue
        stack.pop()
    errors.extend(f"unclosed {name}" for name in reversed(stack))
    return errors


def source_class(text: str) -> str:
    if KANA_RE.search(text):
        return "kana"
    if HAN_RE.search(text):
        return "han"
    return "safe"


def flatten_translation_rows(data: dict[str, Any]) -> int:
    return sum(len(rows) for rows in data.values() if isinstance(rows, dict))


def audit_current_localizetext(
    source: dict[str, Any],
    translation: dict[str, Any],
    *,
    example_limit: int = 50,
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    mapped_rows = 0
    missing_examples: list[dict[str, str]] = []
    actionable_examples: list[dict[str, str | None]] = []
    missing_tables: list[dict[str, Any]] = []
    malformed_markup_rows = 0
    malformed_markup_examples: list[dict[str, Any]] = []

    for table_name, source_table in source.items():
        if not isinstance(source_table, dict):
            continue
        target_table = translation.get(table_name)
        if not isinstance(target_table, dict):
            missing_tables.append({"table": table_name, "rows": len(source_table)})
            target_table = {}

        for raw_key, source_text in source_table.items():
            if not isinstance(source_text, str):
                continue
            key = str(raw_key)
            target = target_table.get(key)
            cls = source_class(source_text)

            if not isinstance(target, str):
                status = f"missing_{cls}"
                if len(missing_examples) < example_limit:
                    missing_examples.append(
                        {"table": table_name, "key": key, "source": source_text}
                    )
            else:
                mapped_rows += 1
                if target == source_text:
                    status = f"same_{cls}"
                elif KANA_RE.search(target):
                    status = "changed_kana_residual"
                else:
                    status = "changed"

                source_markup_errors = markup_balance_errors(source_text)
                target_markup_errors = markup_balance_errors(target)
                if not source_markup_errors and target_markup_errors:
                    malformed_markup_rows += 1
                    if len(malformed_markup_examples) < example_limit:
                        malformed_markup_examples.append(
                            {
                                "table": table_name,
                                "key": key,
                                "source": source_text,
                                "translation": target,
                                "errors": target_markup_errors,
                            }
                        )

            counts[status] += 1

            if status in {"missing_kana", "same_kana", "changed_kana_residual"}:
                if len(actionable_examples) < example_limit:
                    actionable_examples.append(
                        {
                            "table": table_name,
                            "key": key,
                            "source": source_text,
                            "translation": target if isinstance(target, str) else None,
                            "status": status,
                        }
                    )

    source_rows = flatten_translation_rows(source)
    translation_rows = flatten_translation_rows(translation)
    missing_rows = source_rows - mapped_rows
    actionable_rows = (
        counts["missing_kana"]
        + counts["same_kana"]
        + counts["changed_kana_residual"]
        + malformed_markup_rows
    )

    source_tables = {
        name for name, rows in source.items() if isinstance(rows, dict)
    }
    translation_tables = {
        name for name, rows in translation.items() if isinstance(rows, dict)
    }
    extra_tables = sorted(translation_tables - source_tables)
    extra_rows = 0
    extra_row_examples: list[dict[str, str]] = []
    for table_name, target_table in translation.items():
        if not isinstance(target_table, dict):
            continue
        source_table = source.get(table_name)
        source_keys = set(source_table) if isinstance(source_table, dict) else set()
        for raw_key, target in target_table.items():
            key = str(raw_key)
            if key in source_keys:
                continue
            extra_rows += 1
            if len(extra_row_examples) < example_limit:
                extra_row_examples.append(
                    {
                        "table": str(table_name),
                        "key": key,
                        "translation": target if isinstance(target, str) else repr(target),
                    }
                )

    return {
        "source_tables": len(source_tables),
        "source_rows": source_rows,
        "translation_tables": len(translation_tables),
        "translation_rows": translation_rows,
        "mapped_rows": mapped_rows,
        "missing_rows": missing_rows,
        "missing_tables": len(missing_tables),
        "missing_table_rows": sum(int(row["rows"]) for row in missing_tables),
        "extra_translation_tables": len(extra_tables),
        "extra_translation_rows": extra_rows,
        "status_counts": dict(sorted(counts.items())),
        "actionable_rows": actionable_rows,
        "actionable_definition": [
            "missing_kana",
            "same_kana",
            "changed_kana_residual",
            "malformed_markup",
        ],
        "malformed_markup_rows": malformed_markup_rows,
        "malformed_markup_examples": malformed_markup_examples,
        "missing_examples": missing_examples,
        "actionable_examples": actionable_examples,
        "missing_table_inventory": sorted(
            missing_tables, key=lambda row: (-int(row["rows"]), str(row["table"]))
        )[:example_limit],
        "extra_translation_table_names": extra_tables[:example_limit],
        "extra_translation_row_examples": extra_row_examples,
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Current SCSP 2.17 localizetext audit",
        "",
        f"- Status: **{report['status']}**",
        f"- Game version: **{report['snapshot']['game_version']}**",
        f"- Current source rows: **{report['audit']['source_rows']}**",
        f"- Mapped rows: **{report['audit']['mapped_rows']}**",
        f"- Missing rows: **{report['audit']['missing_rows']}**",
        f"- Actionable rows: **{report['audit']['actionable_rows']}**",
        f"- Malformed current link/color markup rows: **{report['audit']['malformed_markup_rows']}**",
        f"- Extra historical translation rows: **{report['audit']['extra_translation_rows']}**",
        "",
        "## Status counts",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    for status, count in report["audit"]["status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines += [
        "",
        "This gate proves coverage against the bundled current 2.17 localizetext source universe. "
        "It intentionally does not require source/translation placeholder, newline, NBSP, or numeric "
        "signatures to be textually identical because runtime localization templates may differ from "
        "the current Japanese source representation. It does require translation-side link/color markup "
        "to remain structurally balanced whenever the authoritative current source markup is balanced.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit maintained localify translations against the bundled current SCSP 2.17 "
            "localizetext source universe."
        )
    )
    parser.add_argument(
        "--translation",
        type=Path,
        default=DATA / "localify.json",
        help="Translation table JSON to audit.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=QA / "generated" / "current-localizetext-audit.json",
    )
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=QA / "generated" / "current-localizetext-audit.md",
    )
    parser.add_argument("--example-limit", type=int, default=50)
    args = parser.parse_args()

    source, manifest = load_current_localizetext_source()
    if source is None or manifest is None:
        raise SystemExit(
            "current localizetext snapshot is unavailable; expected qa/current-source/ files"
        )

    translation = load_json(args.translation)
    if not isinstance(translation, dict):
        raise SystemExit("translation must be a JSON object")

    audit = audit_current_localizetext(
        source,
        translation,
        example_limit=max(0, args.example_limit),
    )
    hard_failures = audit["missing_rows"] + audit["actionable_rows"]
    report = {
        "schema_version": 1,
        "status": "PASS" if hard_failures == 0 else "FAIL",
        "snapshot": {
            "game_version": manifest.get("game_version"),
            "surface": manifest.get("surface"),
            "resource": manifest.get("resource"),
            "tables": manifest.get("tables"),
            "rows": manifest.get("rows"),
            "uncompressed_sha256": manifest.get("uncompressed_sha256"),
            "gzip_sha256": manifest.get("gzip_sha256"),
        },
        "hard_failures": hard_failures,
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
                "game_version": report["snapshot"]["game_version"],
                "source_tables": audit["source_tables"],
                "source_rows": audit["source_rows"],
                "mapped_rows": audit["mapped_rows"],
                "missing_rows": audit["missing_rows"],
                "actionable_rows": audit["actionable_rows"],
                "malformed_markup_rows": audit["malformed_markup_rows"],
                "extra_translation_rows": audit["extra_translation_rows"],
                "status_counts": audit["status_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
