from __future__ import annotations

import unittest

from audit_current_localizetext import audit_current_localizetext
from qa_common import (
    load_current_localizetext_qa_scope,
    load_current_localizetext_source,
    load_json,
    DATA,
)


class CurrentLocalizetextAuditTests(unittest.TestCase):
    def test_snapshot_identity_and_scope(self) -> None:
        source, manifest = load_current_localizetext_source()
        self.assertIsNotNone(source)
        self.assertIsNotNone(manifest)
        assert source is not None
        assert manifest is not None
        self.assertEqual(manifest["game_version"], "2.17.0")
        self.assertEqual(manifest["tables"], 5631)
        self.assertEqual(manifest["rows"], 138036)
        self.assertEqual(
            manifest["uncompressed_sha256"],
            "33fe9de689b3ad0a3a94a6fce5f5805bca523d320f78286d9fc09a2c5999f99f",
        )
        self.assertEqual(
            sum(len(rows) for rows in source.values() if isinstance(rows, dict)),
            138036,
        )

        scope, scope_meta = load_current_localizetext_qa_scope()
        self.assertIsNotNone(scope)
        self.assertIsNotNone(scope_meta)
        assert scope is not None
        assert scope_meta is not None
        self.assertEqual(scope_meta["tables"], 1629)
        self.assertEqual(scope_meta["rows"], 39711)
        self.assertEqual(scope_meta["obsolete_historical_rows_excluded"], 5149)

    def test_current_public_translation_is_fully_mapped(self) -> None:
        source, _ = load_current_localizetext_source()
        assert source is not None
        translation = load_json(DATA / "localify.json")
        audit = audit_current_localizetext(source, translation, example_limit=3)
        self.assertEqual(audit["source_rows"], 138036)
        self.assertEqual(audit["mapped_rows"], 138036)
        self.assertEqual(audit["missing_rows"], 0)
        self.assertEqual(audit["actionable_rows"], 0)
        self.assertEqual(
            audit["status_counts"],
            {
                "changed": 120932,
                "same_han": 596,
                "same_safe": 16508,
            },
        )
        self.assertEqual(audit["extra_translation_rows"], 5149)

    def test_synthetic_actionable_and_missing_detection(self) -> None:
        source = {
            "table": {
                "1": "テスト",
                "2": "漢字",
                "3": "SAFE",
            }
        }
        translation = {
            "table": {
                "1": "テスト",
                "2": "汉字",
            }
        }
        audit = audit_current_localizetext(source, translation)
        self.assertEqual(audit["mapped_rows"], 2)
        self.assertEqual(audit["missing_rows"], 1)
        self.assertEqual(audit["actionable_rows"], 1)
        self.assertEqual(audit["status_counts"]["same_kana"], 1)
        self.assertEqual(audit["status_counts"]["changed"], 1)
        self.assertEqual(audit["status_counts"]["missing_safe"], 1)


if __name__ == "__main__":
    unittest.main()
