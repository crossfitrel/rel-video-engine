#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""שער תקציב השקט (30.7.26).

הראל דחה תוצר עם 28.1% שקט ופאוזה ארוכה 0.88ש. הספים כאן נגזרו ממדידה של
19 סרטונים שהוא אישר ופרסם — ראה ההערה ב-`edit_plan.py`. כל בדיקה כאן היא
הזרקת-כשל: היא מוודאת שהשער **נכשל** כשצריך, לא רק שהוא רץ.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

import edit_plan as EP                                       # noqa: E402


def proj(gaps, keep_values, total=50.0, speech_block=40.0):
    """בונה פרויקט סינתטי: `gaps` = [(start, dur)], והתוכנית מקצרת כל אחד
    ל-`keep_values[i]`. מילה קצרה משני צידי כל פער כדי שהאימות הפיזי יעבור."""
    d = Path(tempfile.mkdtemp())
    cands, words, decs = [], [], []
    for i, (s, dur) in enumerate(gaps):
        cands.append({"candidate_id": f"gap_{i:04d}", "kind": "inter_word_gap",
                      "t_start": s, "t_end": round(s + dur, 3),
                      "prev_word": "א", "next_word": "ב",
                      "features": {"gap_sec": dur}, "hard_constraints": {}})
        words.append({"word": "א", "start": round(s - 0.4, 3), "end": s})
        words.append({"word": "ב", "start": round(s + dur, 3), "end": round(s + dur + 0.4, 3)})
        decs.append({"candidate_id": f"gap_{i:04d}", "action": "tighten_to",
                     "value": keep_values[i], "confidence": 0.9,
                     "reason": "בדיקה סינתטית לשער התקציב"})
    (d / "candidates.json").write_text(json.dumps(
        {"candidates": cands, "source": {"total_dur": total}}, ensure_ascii=False),
        encoding="utf-8")
    (d / "whisper_raw.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (d / "edit_plan.json").write_text(json.dumps({"decisions": decs}, ensure_ascii=False),
                                      encoding="utf-8")
    return d


class TestPauseBudget(unittest.TestCase):
    def test_long_pause_blocks(self):
        """הזרקת-כשל: פאוזה אחת של 0.90ש חייבת להפיל את התוכנית."""
        d = proj([(5.0, 2.0)], [0.90])
        res = EP.validate(d, verbose=False)
        self.assertFalse(res["ok"])
        self.assertTrue(any("הפאוזה הארוכה" in m for m in res["hard"]), res["hard"])

    def test_pause_at_limit_passes(self):
        """0.65ש בדיוק — הגבול העליון של הסרטונים שהראל אישר — עובר."""
        d = proj([(5.0, 2.0)], [0.65])
        res = EP.validate(d, verbose=False)
        self.assertTrue(all("הפאוזה הארוכה" not in m for m in res["hard"]), res["hard"])

    def test_total_budget_blocks(self):
        """הזרקת-כשל: הרבה פאוזות קצרות שסכומן חורג — נחסם גם בלי פאוזה ארוכה."""
        gaps = [(3.0 + i * 2.0, 1.5) for i in range(14)]
        d = proj(gaps, [0.90] * 14, total=40.0)
        res = EP.validate(d, verbose=False)
        self.assertGreater(res["pause_pct"], EP.PAUSE_BUDGET_HARD_PCT)
        self.assertFalse(res["ok"])
        self.assertTrue(any("תקציב שקט" in m for m in res["hard"]), res["hard"])

    def test_metrics_are_reported_even_when_passing(self):
        """המספר חייב להופיע גם כשעוברים — אחרת אי אפשר לעקוב אחרי מגמה."""
        d = proj([(5.0, 2.0), (12.0, 1.0)], [0.22, 0.25])
        res = EP.validate(d, verbose=False)
        self.assertAlmostEqual(res["pause_total"], 0.47, places=2)
        self.assertAlmostEqual(res["longest_gap"], 0.25, places=2)
        self.assertIn("pause_pct", res)

    def test_thresholds_match_measured_reference(self):
        """הספים אינם ניחוש — הם נגזרו מ-19 סרטונים מאושרים. אם מישהו משנה
        אותם, שיעשה זאת מול מדידה חדשה ולא בשקט."""
        # ספים צד-**תוכנית**. המדידה שמהם נגזרו נעשתה על התוצר, שכולל ריפוד
        # דעיכה — ולכן הם רופפים יותר ממנה במכוון. ראה ההערה ב-edit_plan.
        self.assertEqual(EP.MAX_KEPT_GAP, 0.78)
        self.assertEqual(EP.PAUSE_BUDGET_WARN_PCT, 19.0)
        self.assertEqual(EP.PAUSE_BUDGET_HARD_PCT, 26.0)
        # תקציב התפרים — נגזר מ-0.038-0.191 חיתוכים/ש בסרטונים המאושרים
        self.assertEqual(EP.CUTS_PER_SEC_WARN, 0.16)
        self.assertEqual(EP.CUTS_PER_SEC_HARD, 0.24)
        self.assertEqual(EP.MIN_SAVING_PER_CUT, 0.50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
