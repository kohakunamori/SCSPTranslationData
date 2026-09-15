from __future__ import annotations

import unittest

from canonicalize_exact_source_conflicts import (
    find_candidates,
    full_signature_compatible,
)


class ExactSourceCanonicalizationTests(unittest.TestCase):
    def test_full_signature_compatibility(self) -> None:
        self.assertTrue(full_signature_compatible("報酬", "奖励"))
        self.assertTrue(full_signature_compatible("値 {0}", "数值 {0}"))
        self.assertFalse(full_signature_compatible("値 {0}", "数值 {1}"))
        self.assertFalse(full_signature_compatible("A\nB", "甲 乙"))
        self.assertFalse(full_signature_compatible("100%", "百分百"))

    def test_finds_unanimous_localify_canonical_target(self) -> None:
        records = [
            {
                "surface": "local2",
                "identity": "イベント",
                "source": "イベント",
                "translation": "事件",
                "provenance": "current-source-key",
            },
            {
                "surface": "localify",
                "identity": "table:1",
                "source": "イベント",
                "translation": "活动",
                "provenance": "origin/DumpData:dumps/localify.json",
            },
            {
                "surface": "localify",
                "identity": "table:2",
                "source": "イベント",
                "translation": "活动",
                "provenance": "origin/DumpData:dumps/localify.json",
            },
        ]
        candidates = find_candidates(records)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["old_translation"], "事件")
        self.assertEqual(candidates[0]["canonical_translation"], "活动")
        self.assertEqual(candidates[0]["canonical_occurrence_count"], 2)

    def test_rejects_spacing_only_and_ambiguous_conflicts(self) -> None:
        spacing = [
            {
                "surface": "local2",
                "identity": "name",
                "source": "七草\u00a0にちか",
                "translation": "七草 日花",
                "provenance": "current-source-key",
            },
            {
                "surface": "localify",
                "identity": "name:1",
                "source": "七草\u00a0にちか",
                "translation": "七草\u00a0日花",
                "provenance": "origin/DumpData:dumps/localify.json",
            },
        ]
        self.assertEqual(find_candidates(spacing), [])

        ambiguous = [
            {
                "surface": "local2",
                "identity": "x",
                "source": "アイテム名",
                "translation": "物品名称",
                "provenance": "current-source-key",
            },
            {
                "surface": "localify",
                "identity": "a",
                "source": "アイテム名",
                "translation": "道具名称",
                "provenance": "origin/DumpData:dumps/localify.json",
            },
            {
                "surface": "localify",
                "identity": "b",
                "source": "アイテム名",
                "translation": "物品名",
                "provenance": "origin/DumpData:dumps/localify.json",
            },
        ]
        self.assertEqual(find_candidates(ambiguous), [])


if __name__ == "__main__":
    unittest.main()
