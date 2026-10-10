#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L33 — שתי מדיניות שחלוקות על אותו חיתוך אינן שער, הן תקלה.

השורש (17.8.26, "טיפ-אחד-בטן-בר"): הסרטון נפתח ב-7.14 שניות בלי אף מילה.
‏`edl_build` מתיר במפורש לקצץ שקט-הובלה, ו-`edit_plan` אף מדפיס "מותר,
ההוק עצמו לא נגע" — אבל `canon_lint.hook_protected` ספר שניות ולא תוכן,
ולכן הפיל את התוצר ב-HARD_FAIL אחרי שכל שאר השערים עברו, כולל qa ו-preflight.

הכלל: ההוק מתחיל במילה הראשונה. שקט שלפניה אינו הוק ואינו נספר.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SYS = Path(__file__).resolve().parent.parent
TOOLS = SYS / "tools"


def run_lint(work):
    r = subprocess.run(
        [sys.executable, str(TOOLS / "canon_lint.py"), "--workdir", str(work)],
        capture_output=True, text=True)
    return r.stdout + r.stderr


def scaffold(tmp, first_word_at, cuts, total=60.0):
    w = Path(tmp)
    (w / "whisper_raw.json").write_text(json.dumps(
        [{"word": "טיפ", "start": first_word_at, "end": first_word_at + 0.4},
         {"word": "סוף", "start": total - 3.0, "end": total - 2.5}],
        ensure_ascii=False), encoding="utf-8")
    (w / "edl.json").write_text(json.dumps({
        "total_dur": total,
        "review": {"cuts": cuts},
        "keep_segments": [{"start": 0.0, "end": total}],
    }, ensure_ascii=False), encoding="utf-8")
    return w


class TestHookLeadSilence(unittest.TestCase):

    def test_cutting_pure_lead_silence_is_allowed(self):
        """המקרה שקרה: 7.14ש בלי מילה, נחתכו — ונחסמו בטעות."""
        with tempfile.TemporaryDirectory() as tmp:
            w = scaffold(tmp, first_word_at=7.14,
                         cuts=[{"start": 0.0, "end": 6.9, "active": True}])
            out = run_lint(w)
            line = [l for l in out.splitlines() if "hook_protected" in l]
            self.assertTrue(line, "hook_protected לא הופיע בדוח")
            self.assertIn("✅", line[0],
                          "קיצוץ שקט שלפני המילה הראשונה נחסם — "
                          "זו בדיוק הסתירה בין canon_lint ל-edit_plan")

    def test_cutting_actual_speech_in_the_hook_still_fails(self):
        """התיקון לא רשאי לפתוח דלת: הוק אמיתי עדיין מוגן."""
        with tempfile.TemporaryDirectory() as tmp:
            w = scaffold(tmp, first_word_at=0.20,
                         cuts=[{"start": 0.0, "end": 6.0, "active": True}])
            out = run_lint(w)
            line = [l for l in out.splitlines() if "hook_protected" in l]
            self.assertTrue(line)
            self.assertIn("❌", line[0],
                          "חיתוך שמוחק את ההוק עצמו חייב להיכשל")

    def test_inactive_cuts_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = scaffold(tmp, first_word_at=0.20,
                         cuts=[{"start": 0.0, "end": 6.0, "active": False}])
            out = run_lint(w)
            line = [l for l in out.splitlines() if "hook_protected" in l]
            self.assertIn("✅", line[0])


if __name__ == "__main__":
    unittest.main()
