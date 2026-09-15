from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from validate_agent_result import validate


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class AgentResultValidationTests(unittest.TestCase):
    def test_valid_result_passes(self) -> None:
        batch = [{
            "schema_version": 1,
            "source_id": "0123456789abcdef01234567",
            "source": "確認 {0}",
            "classification": "needs_translation",
            "occurrences": [{"surface": "local2", "identity": "確認 {0}", "provenance": "current-source-key"}],
            "existing_translations": [],
            "relevant_terms": [],
            "relevant_names": [],
            "preserve_terms": [],
        }]
        result = [{
            "schema_version": 1,
            "source_id": "0123456789abcdef01234567",
            "source": "確認 {0}",
            "decision": "translate",
            "translation": "确认 {0}",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "batch.jsonl"
            rp = Path(tmp) / "result.jsonl"
            write_jsonl(bp, batch)
            write_jsonl(rp, result)
            report = validate(bp, rp)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["error_count"], 0)

    def test_missing_placeholder_fails(self) -> None:
        batch = [{
            "schema_version": 1,
            "source_id": "0123456789abcdef01234567",
            "source": "確認 {0}",
            "classification": "needs_translation",
            "occurrences": [{"surface": "local2", "identity": "確認 {0}", "provenance": "current-source-key"}],
            "existing_translations": [],
            "relevant_terms": [],
            "relevant_names": [],
            "preserve_terms": [],
        }]
        result = [{
            "schema_version": 1,
            "source_id": "0123456789abcdef01234567",
            "source": "確認 {0}",
            "decision": "translate",
            "translation": "确认",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "batch.jsonl"
            rp = Path(tmp) / "result.jsonl"
            write_jsonl(bp, batch)
            write_jsonl(rp, result)
            report = validate(bp, rp)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("brace signature changed" in x for x in report["errors"]))


if __name__ == "__main__":
    unittest.main()
