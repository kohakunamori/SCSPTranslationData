from __future__ import annotations

import unittest
from collections import Counter

from build_quality_backlog import build_items
from qa_common import resolve_dump_ref


class QualityBacklogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.items, cls.meta = build_items(resolve_dump_ref())

    def test_backlog_ids_are_unique_and_non_applying(self) -> None:
        ids = [row["backlog_id"] for row in self.items]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row["auto_apply_allowed"] is False for row in self.items))

    def test_spacing_variants_are_not_semantic_conflicts(self) -> None:
        by_code = Counter(row["code"] for row in self.items)
        self.assertGreater(by_code["duplicate-source-layout-variant"], 0)
        self.assertGreater(by_code["duplicate-source-conflict"], 0)
        layout_sources = {
            row["identity"]
            for row in self.items
            if row["code"] == "duplicate-source-layout-variant"
        }
        conflict_sources = {
            row["identity"]
            for row in self.items
            if row["code"] == "duplicate-source-conflict"
        }
        self.assertTrue(layout_sources.isdisjoint(conflict_sources))

    def test_every_item_has_public_review_metadata(self) -> None:
        required = {
            "schema_version",
            "backlog_id",
            "priority",
            "category",
            "code",
            "surface",
            "identity",
            "agent_ready",
            "recommended_action",
            "auto_apply_allowed",
        }
        for row in self.items:
            self.assertTrue(required.issubset(row))

    def test_current_key_backlog_is_clean_except_reviewed_baseline(self) -> None:
        allowed = {"baseline-format"}
        blockers = [
            row
            for row in self.items
            if row.get("source_authority") == "current-key"
            and row.get("category") not in allowed
        ]
        self.assertEqual(blockers, [])

    def test_source_authority_requires_historical_verification(self) -> None:
        historical = [
            row for row in self.items
            if "DumpData" in row.get("provenance", "")
        ]
        current_key = [
            row for row in self.items
            if row.get("provenance") == "current-source-key"
        ]
        self.assertTrue(historical)
        self.assertTrue(current_key)
        self.assertTrue(all(row.get("source_authority") == "historical-reference" for row in historical))
        self.assertTrue(all(row.get("requires_source_verification") is True for row in historical))
        self.assertTrue(all(row.get("source_authority") == "current-key" for row in current_key))
        self.assertTrue(all(row.get("requires_source_verification") is False for row in current_key))

    def test_historical_localify_items_are_cross_checked_against_current_source(self) -> None:
        historical_localify = [
            row
            for row in self.items
            if row.get("surface") == "localify"
            and "DumpData" in row.get("provenance", "")
        ]
        self.assertTrue(historical_localify)
        statuses = {
            (row.get("metadata") or {}).get("current_source_status")
            for row in historical_localify
        }
        self.assertTrue(statuses.issubset({"match", "changed", "missing"}))
        self.assertNotIn(None, statuses)

        current_confirmed_p1 = [
            row
            for row in historical_localify
            if row.get("priority") == "P1"
            and (row.get("metadata") or {}).get("current_source_status") == "match"
        ]
        self.assertEqual(current_confirmed_p1, [])


if __name__ == "__main__":
    unittest.main()
