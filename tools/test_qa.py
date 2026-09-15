from __future__ import annotations

import unittest
from collections import Counter

from qa_common import (
    format_signature,
    lyric_translation_only,
    numeric_signature,
    percentage_signature,
)


class QaCommonTests(unittest.TestCase):
    def test_format_signature_tracks_runtime_tokens(self) -> None:
        text = "值 {0} %s\n<sprite=3>\u00a0"
        sig = format_signature(text)
        self.assertEqual(sig["brace"], {"{0}": 1})
        self.assertEqual(sig["printf"], {"%s": 1})
        self.assertEqual(sig["tags"], {"<sprite=3>": 1})
        self.assertEqual(sig["lf"], 1)
        self.assertEqual(sig["nbsp"], 1)

    def test_printf_signature_ignores_game_percent_words(self) -> None:
        self.assertEqual(format_signature("70%DOWN 50%UP")["printf"], {})
        self.assertEqual(
            format_signature("%s %d %1$s %%")["printf"],
            {"%s": 1, "%d": 1, "%1$s": 1, "%%": 1},
        )

    def test_numeric_signature_normalizes_full_width_digits(self) -> None:
        self.assertEqual(numeric_signature("第３章 10回"), Counter({"3": 1, "10": 1}))
        from qa_common import numeric_signatures_match
        self.assertTrue(numeric_signatures_match("４人", "四名成员"))
        self.assertTrue(numeric_signatures_match("最大２行", "最多两行"))
        self.assertTrue(numeric_signatures_match("シーズン1", "第一季"))
        self.assertTrue(numeric_signatures_match("あと10回", "还有十次"))
        self.assertTrue(numeric_signatures_match("2倍", "翻倍"))
        self.assertTrue(numeric_signatures_match("前へ", "上一个"))
        self.assertTrue(numeric_signatures_match("100件", "一次最多100件"))
        self.assertFalse(numeric_signatures_match("1日1回限定", "每日限定1次"))
        self.assertFalse(numeric_signatures_match("2回", "3次"))

    def test_reviewed_semantic_exception_is_exact(self) -> None:
        from qa_common import reviewed_semantic_exception
        rules = {
            "reviewed_semantic_exceptions": [
                {
                    "code": "numeric-signature",
                    "surface": "local2",
                    "source": "1日1回限定",
                    "translation": "每日限定1次",
                }
            ]
        }
        self.assertTrue(
            reviewed_semantic_exception(
                rules,
                "numeric-signature",
                "local2",
                "1日1回限定",
                "每日限定1次",
            )
        )
        self.assertFalse(
            reviewed_semantic_exception(
                rules,
                "numeric-signature",
                "local2",
                "1日1回限定",
                "每日限定2次",
            )
        )

    def test_percentage_signature_normalizes_percent_forms(self) -> None:
        self.assertEqual(percentage_signature("30％ / 25%"), Counter({"30%": 1, "25%": 1}))

    def test_kana_detection_ignores_japanese_middle_dot(self) -> None:
        from qa_common import (
            canonical_same_form,
            compact_display_spacing,
            has_kana,
            has_unpreserved_kana,
        )
        self.assertFalse(has_kana("Chill Out・Nokuchiruka"))
        self.assertTrue(has_kana("アイドル"))
        self.assertFalse(has_unpreserved_kana("游玩「ツバサグラビティ」吧", ["ツバサグラビティ"]))
        self.assertFalse(has_unpreserved_kana("《明日もBeautiful\u00a0Day》", ["明日もBeautiful Day"]))
        self.assertTrue(has_unpreserved_kana("游玩「ツバサグラビティ」して", ["ツバサグラビティ"]))
        self.assertEqual(compact_display_spacing("七草\u00a0日花"), "七草日花")
        names = {"names": [{"source": "大崎 甘奈", "translation": "大崎 甘奈"}]}
        self.assertTrue(canonical_same_form("大崎甘奈", names))
        self.assertFalse(canonical_same_form("大崎 甜花", names))

    def test_lyric_translation_only_strips_preserved_source_prefix(self) -> None:
        source = "星の声"
        self.assertEqual(lyric_translation_only(source, "星の声\n星之声"), "星之声")
        self.assertEqual(lyric_translation_only(source, source), "")
        self.assertEqual(lyric_translation_only(source, "星之声"), "星之声")


if __name__ == "__main__":
    unittest.main()
