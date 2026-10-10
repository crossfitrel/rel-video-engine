#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L32 — תמלול שנקטע בשקט חייב להיראות במספר.

השורש (17.8.26, "דקה-להורים-אימוני-כוח-לילדים"): faster-whisper החזיר 134
מילים שנגמרו ב-155.57ש על קובץ של 181.39ש. ב-24 השניות שאחרי כן היה דיבור
אמיתי — כולל ה-CTA. אף שער לא תפס: כל השערים שאלו "האם המילים שיש
מסונכרנות", ואף אחד לא שאל "האם יש מילים לכל הדיבור".

זה כשל שקוף במיוחד — הכתוביות תואמות בדיוק את מה שתומלל, ולכן G6/G6b
עוברים בציון מלא בזמן שרבע מהסרטון חסר.
"""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import candidates as C  # noqa: E402


def envelope(loud_until_sec, total_sec, floor=-85.0, loud=-40.0):
    """מעטפת RMS מסונתזת: דיבור עד loud_until, ואז רצפת רעש."""
    n = int(total_sec / C.HOP) + 1
    return [loud if i * C.HOP <= loud_until_sec else floor for i in range(n)]


class TestAsrCoverage(unittest.TestCase):

    def test_truncated_transcript_is_measured(self):
        """המקרה שקרה: דיבור עד ~179ש, מילים עד 155.57ש."""
        words = [{"word": "גוף", "start": 155.0, "end": 155.57}]
        db = envelope(179.4, 181.39)
        cov = C.asr_coverage(words, 181.39, db, -85.0)
        self.assertTrue(cov["measurable"])
        self.assertAlmostEqual(cov["last_word_end"], 155.57, places=2)
        self.assertGreater(
            cov["trailing_untranscribed_sec"], 20.0,
            "24 שניות של דיבור לא-מתומלל חייבות להופיע כמספר, לא להיעלם")

    def test_healthy_transcript_reports_near_zero(self):
        """סרטון תקין: התמלול מגיע עד סוף הדיבור."""
        words = [{"word": "אליה.", "start": 64.8, "end": 65.79}]
        db = envelope(65.8, 66.98)
        cov = C.asr_coverage(words, 66.98, db, -85.0)
        self.assertTrue(cov["measurable"])
        self.assertLess(cov["trailing_untranscribed_sec"], 1.0)

    def test_reports_instead_of_guessing_when_unmeasurable(self):
        """בלי מעטפת אודיו אין מדידה — ואז לא ממציאים מספר."""
        words = [{"word": "x", "start": 1.0, "end": 2.0}]
        cov = C.asr_coverage(words, 60.0, None, None)
        self.assertFalse(cov["measurable"])
        self.assertIsNone(cov["trailing_untranscribed_sec"])
        self.assertEqual(cov["last_word_end"], 2.0)

    def test_no_words_does_not_crash(self):
        cov = C.asr_coverage([], 60.0, envelope(50, 60), -85.0)
        self.assertIsNone(cov["last_word_end"])
        self.assertFalse(cov["measurable"])


if __name__ == "__main__":
    unittest.main()
