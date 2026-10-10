#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""רציפות תנוחה וחיתוך על תמונה קפואה (V3, 30.7.26).

שתי הערות של הראל על אותו סרטון — "יש איזושהי תקיעה בסוף לפני אם בא לכם"
ו"יש רגע שאני מסתכל למטה" — התבררו במדידה כאותו רגע. הקאנון תיעד את זה
כקיר ("אין דרך אוטומטית לזהות זאת עדיין"); כאן הוא נמדד.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

import edit_plan as EP                                        # noqa: E402


def cand(profile, s=10.0, e=11.5, motion=1.0):
    return {"candidate_id": "gap_test", "kind": "inter_word_gap",
            "t_start": s, "t_end": e,
            "features": {"gap_sec": e - s, "motion_around_norm": motion},
            "pose_profile": profile}


# ה-hop כאן דק מצעד הסריקה של best_split (0.02) בכוונה — אחרת הפרופיל לא
# מפריד בין שני צידי המדרגה והבדיקה בודקת קוונטיזציה במקום לוגיקה.
def ramp(gap=1.5, hop=0.02, y0=0.40, y1=0.50):
    """הראש יורד בהדרגה לאורך הפער — בדיוק המקרה של 'מסתכל למטה'."""
    n = int(gap / hop) + 1
    return [[round(i * hop, 3), 0.5, round(y0 + (y1 - y0) * i / (n - 1), 4), 0.2]
            for i in range(n)]


def step(gap=1.5, hop=0.02, drop_at=0.17):
    """הראש יורד **בבת אחת** בתחילת הפער ואז יציב — אז יש פיצול בטוח.
    ‏drop_at=0.17 יושב בין הפיצול חצי-חצי (0.15) לבין קצה הסריקה (0.19),
    כך שהמדרגה נופלת בדיוק בטווח שבו הבחירה משנה."""
    n = int(gap / hop) + 1
    return [[round(i * hop, 3), 0.5, (0.40 if i * hop < drop_at else 0.50), 0.2]
            for i in range(n)]


class TestBestSplit(unittest.TestCase):
    def test_step_case_finds_continuous_split(self):
        """כשהתנוחה משתנה בנקודה אחת — יש פיצול שבו שני הצדדים זהים,
        והמנוע חייב למצוא אותו במקום לחתוך חצי-חצי."""
        c = cand(step())
        cs, ce = EP.best_split(c, 10.0, 11.5, 0.30)
        self.assertLess(EP.pose_jump(c, cs, ce), 0.01)

    def test_half_half_would_have_jumped(self):
        """הזרקת-כשל: הפיצול הישן (חצי-חצי) על אותו מקרה — קופץ."""
        c = cand(step())
        half = 0.30 / 2
        self.assertGreater(EP.pose_jump(c, 10.0 + half, 11.5 - half), 0.09)

    def test_ramp_case_cannot_be_hidden(self):
        """כשהגוף זז לאורך **כל** הפער אין פיצול בטוח — והמנוע לא מתיימר."""
        c = cand(ramp())
        cs, ce = EP.best_split(c, 10.0, 11.5, 0.30)
        self.assertGreater(EP.pose_jump(c, cs, ce), 0.02)

    def test_nudge_respects_word_margin(self):
        c = cand(step())
        for keep in (0.22, 0.26, 0.30, 0.40):
            cs, ce = EP.best_split(c, 10.0, 11.5, keep)
            self.assertGreaterEqual(cs - 10.0, EP.WORD_MARGIN - 1e-6)
            self.assertGreaterEqual(11.5 - ce, EP.WORD_MARGIN - 1e-6)

    def test_nudge_bounded(self):
        """אורך הפאוזה לא זז ביותר מ-KEEP_NUDGE ממה שהבמאי ביקש."""
        c = cand(step())
        keep = 0.30
        cs, ce = EP.best_split(c, 10.0, 11.5, keep)
        got = (cs - 10.0) + (11.5 - ce)
        self.assertLessEqual(abs(got - keep), EP.KEEP_NUDGE + 1e-6)

    def test_nudge_never_lengthens_on_frozen_picture(self):
        """הזרקת-כשל על באג אמיתי: ה-nudge 'תיקן' קפיצת תנוחה ע"י הארכת
        פאוזה — באזור שבו התמונה קפואה. זה בדיוק הליקוי שהוא אמור למנוע."""
        c = cand(step(), motion=0.60)          # מתחת ל-STALL_MOTION_NORM
        cs, ce = EP.best_split(c, 10.0, 11.5, 0.22)
        got = (cs - 10.0) + (11.5 - ce)
        self.assertLessEqual(got, max(0.22, EP.STALL_MIN_PAUSE) + 1e-6)

    def test_no_profile_falls_back_to_half(self):
        c = cand([])
        cs, ce = EP.best_split(c, 10.0, 11.5, 0.30)
        self.assertAlmostEqual(cs, 10.15, places=3)
        self.assertAlmostEqual(ce, 11.35, places=3)

    def test_thresholds_are_measured_not_guessed(self):
        self.assertEqual(EP.POSE_JUMP_WARN, 0.075)
        self.assertEqual(EP.STALL_MOTION_NORM, 0.70)
        self.assertEqual(EP.KEEP_NUDGE, 0.06)


if __name__ == "__main__":
    unittest.main(verbosity=2)
