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

    def test_numeric_signature_normalizes_full_width_digits(self) -> None:
        self.assertEqual(numeric_signature("第３章 10回"), Counter({"3": 1, "10": 1}))

    def test_percentage_signature_normalizes_percent_forms(self) -> None:
        self.assertEqual(percentage_signature("30％ / 25%"), Counter({"30%": 1, "25%": 1}))

    def test_lyric_translation_only_strips_preserved_source_prefix(self) -> None:
        source = "星の声"
        self.assertEqual(lyric_translation_only(source, "星の声\n星之声"), "星之声")
        self.assertEqual(lyric_translation_only(source, source), "")
        self.assertEqual(lyric_translation_only(source, "星之声"), "星之声")


if __name__ == "__main__":
    unittest.main()
