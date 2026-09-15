from __future__ import annotations

import unittest

from audit_current_drama import (
    audit_current_drama,
    flatten_source,
    identity_sha256,
    load_current_drama_source,
    runtime_key_sha256,
)
from prepare_drama_review import build_review_records
from qa_common import DATA, load_json


class CurrentDramaAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source, cls.manifest = load_current_drama_source()
        cls.translation = load_json(DATA / "drama.json")

    def test_snapshot_identity(self) -> None:
        self.assertEqual(self.manifest["game_version"], "2.17.0")
        self.assertEqual(self.manifest["expected_scenarios"], 267)
        self.assertEqual(self.manifest["resolved_scenarios"], 267)
        self.assertEqual(self.manifest["source_rows"], 11402)
        self.assertEqual(self.manifest["runtime_key_count"], 11402)
        self.assertEqual(self.manifest["duplicate_runtime_keys"], 0)
        self.assertEqual(
            self.manifest["source_snapshot_uncompressed_sha256"],
            "3e2256bc909210e2fec06517d3693abb6bf369401429a78fe9b8ce27a15b9dc9",
        )

    def test_current_public_drama_is_exactly_covered(self) -> None:
        audit = audit_current_drama(self.source, self.translation, example_limit=3)
        self.assertEqual(audit["source_error_count"], 0)
        self.assertEqual(audit["target_error_count"], 0)
        self.assertEqual(audit["line_count"], 11402)
        self.assertEqual(audit["translation_rows"], 11402)
        self.assertEqual(audit["mapped_rows"], 11402)
        self.assertEqual(audit["missing_rows"], 0)
        self.assertEqual(audit["extra_rows"], 0)
        self.assertEqual(audit["metadata_mismatch_count"], 0)
        self.assertEqual(audit["target_kana_rows"], 0)
        self.assertEqual(audit["empty_translation_rows"], 0)
        self.assertEqual(audit["source_equal_rows"], 621)
        self.assertEqual(audit["source_equal_han_rows"], 31)
        self.assertEqual(audit["source_equal_safe_rows"], 590)

    def test_collision_safe_and_runtime_hashes_are_reproducible(self) -> None:
        rows, stats = flatten_source(self.source, example_limit=3)
        self.assertEqual(stats["source_error_count"], 0)
        self.assertEqual(len(rows), 11402)
        first = min(
            rows.values(),
            key=lambda row: (row["scenario_id"], row["line_index"]),
        )
        self.assertEqual(
            first["identity_sha256"],
            identity_sha256(
                first["scenario_id"],
                first["source_schema"],
                first["unique_id"],
                first["source"],
            ),
        )
        self.assertEqual(
            first["runtime_key_sha256"],
            runtime_key_sha256(first["unique_id"], first["source"]),
        )

    def test_agent_review_records_cover_current_drama(self) -> None:
        rows = build_review_records(self.source, self.translation)
        self.assertEqual(len(rows), 11402)
        self.assertEqual(sum(row["source_equal"] for row in rows), 621)
        self.assertTrue(all(len(row["identity_sha256"]) == 64 for row in rows))

        equal_only = build_review_records(
            self.source,
            self.translation,
            source_equal_only=True,
        )
        self.assertEqual(len(equal_only), 621)
        self.assertTrue(all(row["source_equal"] for row in equal_only))

    def test_synthetic_missing_and_kana_are_blockers(self) -> None:
        source = {
            "schema_version": 1,
            "game_version": "2.17.0",
            "resource": "drama",
            "selection_rule": "test",
            "scenarios": [
                {
                    "scenario_id": "s_test",
                    "selected_schema": "DramaSubtitlePlayableAsset",
                    "lines": [
                        {
                            "line_index": 0,
                            "identity_sha256": identity_sha256(
                                "s_test",
                                "DramaSubtitlePlayableAsset",
                                "uid-1",
                                "テスト",
                            ),
                            "runtime_key_sha256": runtime_key_sha256("uid-1", "テスト"),
                            "source_schema": "DramaSubtitlePlayableAsset",
                            "unique_id": "uid-1",
                            "speaker": "A",
                            "display_speaker": "",
                            "source": "テスト",
                            "previous_source": None,
                            "next_source": None,
                        }
                    ],
                }
            ],
        }
        translation = {"targetGameVersion": "2.17.0", "entries": []}
        audit = audit_current_drama(source, translation)
        self.assertEqual(audit["missing_rows"], 1)

        translation["entries"] = [
            {
                "scenarioId": "s_test",
                "sourceSchema": "DramaSubtitlePlayableAsset",
                "uniqueId": "uid-1",
                "source": "テスト",
                "text": "テスト",
                "talkerName": "A",
            }
        ]
        audit = audit_current_drama(source, translation)
        self.assertEqual(audit["missing_rows"], 0)
        self.assertEqual(audit["target_kana_rows"], 1)


if __name__ == "__main__":
    unittest.main()
