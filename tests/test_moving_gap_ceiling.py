#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L29 + L30 — פער שהגוף עובר בו מסלול רציף, ומי אחראי לחוקיות הערך.

L29: ה-nudge של best_split רשאי לשנות את אורך הפאוזה שהבמאי ביקש. אם הוא
     רשאי לחרוג מתקרת הפאוזה, הוא מייצר מצב שאין ממנו יציאה — אף ערך של
     tighten_to לא יעבור, כי מה שנכשל נוצר אחרי הבקשה.
L30: התקרה עצמה נגזרה מפאוזות-שקט על תמונה סטטית. פער שהדובר קם בתוכו הוא
     שוט, ולכן חלה עליו תקרה רחבה יותר — מותנית בתנועה מוכחת וחסומה.

השורש (17.8.26, "בריאות-לקום-מכיסא" gap_0003): הדובר קם מהכיסא בתוך הפער,
הראש עולה בפריים ברצף מונוטוני, ולכן **ככל שמשאירים פחות אוויר הקפיצה
גדלה** — ההפך מההנחה הרגילה. שני שערים חוסמים דחפו לכיוונים מנוגדים.
"""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import edit_plan as EP  # noqa: E402

# מסלול הראש שנמדד בפועל בפער הזה: y עולה 0.417 → 0.108 ברצף.
RISING = [[0.00, 0.475, 0.417, 0.166], [0.08, 0.475, 0.417, 0.166],
          [0.16, 0.475, 0.417, 0.166], [0.24, 0.467, 0.453, 0.166],
          [0.32, 0.467, 0.478, 0.175], [0.40, 0.467, 0.478, 0.175],
          [0.48, 0.467, 0.460, 0.181], [0.56, 0.467, 0.460, 0.181],
          [0.64, 0.469, 0.398, 0.184], [0.72, 0.469, 0.283, 0.191],
          [0.80, 0.469, 0.283, 0.191], [0.88, 0.461, 0.163, 0.194],
          [0.96, 0.461, 0.163, 0.194], [1.04, 0.461, 0.163, 0.194],
          [1.28, 0.475, 0.108, 0.178], [1.36, 0.475, 0.108, 0.178]]

STILL = [[round(i * 0.08, 2), 0.475, 0.400, 0.170] for i in range(18)]


def cand(profile, pose_range, motion=1.2):
    return {"candidate_id": "gap_x", "kind": "inter_word_gap",
            "t_start": 4.70, "t_end": 6.07, "pose_profile": profile,
            "features": {"gap_sec": 1.37, "pose_range_in_gap": pose_range,
                         "motion_around_norm": motion}}


class TestMovingGapCeiling(unittest.TestCase):

    def test_moving_gap_has_a_wider_but_bounded_ceiling(self):
        self.assertGreater(EP.MAX_KEPT_GAP_MOVING, EP.MAX_KEPT_GAP)
        # ההקלה חייבת להישאר בתוך טווח ה-nudge — לא פתח פתוח.
        self.assertLessEqual(EP.MAX_KEPT_GAP_MOVING,
                             EP.MAX_KEPT_GAP + EP.KEEP_NUDGE + 1e-9)
        # וסף התנועה חייב להיות גבוה בהרבה מהחציון הטיפוסי (~0.02).
        self.assertGreaterEqual(EP.MOVING_GAP_POSE_RANGE, 0.20)

    def test_nudge_never_exceeds_the_ceiling_on_a_still_gap(self):
        """L29: פער שקט על תמונה יציבה — ה-nudge לא רשאי לחרוג מ-0.78."""
        c = cand(STILL, pose_range=0.01)
        for req in (0.60, 0.70, 0.74, 0.76, 0.78):
            cs, ce = EP.best_split(c, 4.70, 6.07, req)
            keep = (cs - 4.70) + (6.07 - ce)
            self.assertLessEqual(
                round(keep, 3), EP.MAX_KEPT_GAP + 1e-6,
                "ה-nudge הפיק פאוזה %.2f מעל התקרה עבור בקשה %.2f" % (keep, req))

    def test_nudge_may_use_the_wider_ceiling_only_when_the_body_moves(self):
        """L30: פער שהדובר קם בתוכו — מותר עד 0.84, ולא מעבר."""
        c = cand(RISING, pose_range=0.3705)
        keeps = []
        for req in (0.60, 0.70, 0.76, 0.78):
            cs, ce = EP.best_split(c, 4.70, 6.07, req)
            keeps.append(round((cs - 4.70) + (6.07 - ce), 3))
        for k in keeps:
            self.assertLessEqual(k, EP.MAX_KEPT_GAP_MOVING + 1e-6)
        self.assertTrue(
            any(k > EP.MAX_KEPT_GAP for k in keeps),
            "בפער-בתנועה ה-nudge לא ניצל את התקרה הרחבה: %s" % keeps)

    def test_the_rising_gap_gets_a_smaller_pose_jump_with_more_air(self):
        """המדידה שהפכה את האינטואיציה: יותר אוויר = פחות קפיצה."""
        c = cand(RISING, pose_range=0.3705)
        short = EP.best_split(c, 4.70, 6.07, 0.55)
        long_ = EP.best_split(c, 4.70, 6.07, 0.78)
        j_short = EP.pose_jump(c, *short)
        j_long = EP.pose_jump(c, *long_)
        self.assertIsNotNone(j_short)
        self.assertIsNotNone(j_long)
        self.assertLess(j_long, j_short,
                        "בפער שהגוף עובר בו מסלול רציף, קיצור חייב להגדיל את הקפיצה")


if __name__ == "__main__":
    unittest.main()
