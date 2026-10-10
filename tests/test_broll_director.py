# -*- coding: utf-8 -*-
"""
בדיקות שכבת הבירול (v9.4).

כל בדיקה כאן **מזריקה כשל אמיתי** — ההחלטה שהראל דחה בפועל, או ההחלטה
שהמנוע הישן היה מקבל — ומוודאת שהשער חוסם אותה. בדיקה שרק מאשרת מסלול
תקין אינה מוכיחה ששער חוסם.
"""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_director as BD          # noqa: E402
import broll_pick as BP              # noqa: E402


KEEPS = [{"start": 0.5, "end": 5.5}, {"start": 8.0, "end": 20.0},
         {"start": 25.0, "end": 40.0}]
OUT_DUR = 5.0 + 12.0 + 15.0          # 32.0


def win(cid, t0, t1, text, stalled=False, i=1):
    return {"candidate_id": cid, "kind": "broll_window", "t_start": t0, "t_end": t1,
            "text": text, "prev_text": None, "next_text": None,
            "features": {"dur_sec": round(t1 - t0, 3), "sentence_index": i,
                         "n_words": len(text.split()), "motion_norm": 0.55 if stalled else 1.2,
                         "is_stalled": stalled, "face_present_pct": 90}}


def clip(cid, label, dur=3.6, cat="אימון-כוח"):
    return {"clip_id": cid, "label": label, "category": cat, "dur": dur,
            "vertical": True, "tags": [], "last_used_days": None}


class TestQuoteGate(unittest.TestCase):
    """הנימוק הוא התנאי — תיאור של הקליפ אינו נימוק."""

    S = "רחבת האופן ג׳ים של המועדון שלנו פתוחה, כל הציוד זמין"

    def test_description_only_is_not_a_reason(self):
        # זה בדיוק מה שהמנוע הישן ייצר: reason="tags=[...]" — כותרת, לא נימוק.
        self.assertIsNone(BD.quoted_span("מתאמנת עושה דדליפט בריג", self.S))

    def test_bigram_from_sentence_passes(self):
        self.assertEqual(BD.quoted_span(
            "רואים בדיוק את מה שנאמר — כל הציוד זמין ואף אחד לא מחכה", self.S),
            "כל הציוד")

    def test_single_short_word_is_not_a_quote(self):
        # "של" / "כל" מופיעות כמעט בכל נימוק סביר — בדיקה כזאת עוברת תמיד
        # ולכן אינה שער.
        self.assertIsNone(BD.quoted_span("קליפ של מתאמנת, כל הכבוד", "כל הציוד של המועדון"))

    def test_hebrew_geresh_normalized(self):
        self.assertIsNotNone(BD.quoted_span("רחבת האופן ג'ים ריקה", self.S))


class TestEnforce(unittest.TestCase):
    def setUp(self):
        self.windows = BD.surviving_windows(
            [win("broll_001", 9.0, 13.0, "כל הציוד זמין בלי תור ובלי המתנה"),
             win("broll_002", 26.0, 31.0, "אתם נכנסים בטביעת אצבע לבד", i=2)],
            KEEPS, OUT_DUR)
        self.clips = [clip("c1", "דדליפט מתאמנת"), clip("c2", "דדליפט מתאמנת (2)"),
                      clip("c3", "כניסה בטביעת אצבע")]

    def _p(self, cid, clid, conf, reason):
        return {"candidate_id": cid, "clip_id": clid, "confidence": conf, "reason": reason}

    def test_below_threshold_is_dropped(self):
        acc, rej = BD.enforce(
            [self._p("broll_001", "c1", 0.74, "כל הציוד זמין ולכן רואים ציוד")],
            self.windows, self.clips)
        self.assertEqual(acc, [])
        self.assertIn("0.74", rej[0]["why"])

    def test_at_threshold_passes(self):
        acc, _ = BD.enforce(
            [self._p("broll_001", "c1", 0.75, "כל הציוד זמין ולכן רואים ציוד")],
            self.windows, self.clips)
        self.assertEqual(len(acc), 1)

    def test_unknown_clip_rejected(self):
        _, rej = BD.enforce(
            [self._p("broll_001", "NOT_IN_POOL", 0.9, "כל הציוד זמין")],
            self.windows, self.clips)
        self.assertEqual(len(rej), 1)

    def test_near_duplicate_label_rejected(self):
        """שני קליפים כמעט-זהים באותו סרטון = הצופה קורא תקלה."""
        acc, rej = BD.enforce(
            [self._p("broll_001", "c1", 0.9, "כל הציוד זמין"),
             self._p("broll_002", "c2", 0.9, "בטביעת אצבע נכנסים לבד")],
            self.windows, self.clips)
        self.assertEqual(len(acc), 1)
        self.assertIn("כמעט-זהה", rej[0]["why"])

    def test_same_clip_twice_rejected(self):
        acc, _ = BD.enforce(
            [self._p("broll_001", "c1", 0.9, "כל הציוד זמין"),
             self._p("broll_002", "c1", 0.9, "בטביעת אצבע נכנסים")],
            self.windows, self.clips)
        self.assertEqual(len(acc), 1)

    def test_window_that_was_cut_is_not_offered(self):
        """הליקוי השקט: קליפ שנבחר לרגע שכבר לא קיים בסרטון."""
        cut = win("broll_009", 21.0, 24.0, "משפט שנחתך לגמרי בעריכה")
        self.assertEqual(
            [w["candidate_id"] for w in BD.surviving_windows([cut], KEEPS, OUT_DUR)], [])


class TestWindowMapping(unittest.TestCase):
    def test_source_time_maps_to_output_time(self):
        # 9.0 במקור = 5.0ש שנשמרו לפני החיתוך + 1.0 אחריו
        self.assertAlmostEqual(BD.map_to_out(9.0, KEEPS), 6.0, places=3)
        self.assertAlmostEqual(BD.map_to_out(26.0, KEEPS), 18.0, places=3)

    def test_cta_guard_trims_window(self):
        w = BD.surviving_windows([win("broll_x", 36.0, 40.0, "משפט בתוך ה-CTA")],
                                 KEEPS, OUT_DUR)
        self.assertEqual(w, [])          # 8ש אחרונות מוגנות

    def test_hook_guard_pushes_start(self):
        w = BD.surviving_windows([win("broll_y", 1.0, 5.5, "משפט שמתחיל בהוק ונמשך")],
                                 KEEPS, OUT_DUR)
        self.assertTrue(all(x["out_start"] >= BD.HOOK_GUARD for x in w))


class TestBuildPlan(unittest.TestCase):
    def setUp(self):
        self.windows = BD.surviving_windows(
            [win("broll_001", 9.0, 13.0, "כל הציוד זמין בלי תור"),
             win("broll_002", 13.5, 18.0, "אתם נכנסים בטביעת אצבע", i=2)],
            KEEPS, OUT_DUR)
        self.clips = [clip("c1", "רחבה פתוחה"), clip("c2", "טביעת אצבע")]
        self.paths = {"c1": "/tmp/a.mp4", "c2": "/tmp/b.mp4"}

    def test_flash_gap_between_neighbours_is_closed(self):
        acc, _ = BD.enforce(
            [{"candidate_id": "broll_001", "clip_id": "c1", "confidence": 0.9,
              "reason": "כל הציוד זמין ורואים רחבה"},
             {"candidate_id": "broll_002", "clip_id": "c2", "confidence": 0.9,
              "reason": "נכנסים בטביעת אצבע"}], self.windows, self.clips)
        plan, _, gaps = BD.build_plan(acc, self.windows, self.clips, OUT_DUR, self.paths)
        self.assertEqual(len(plan), 2)
        hole = round(plan[1]["insert_at"] - plan[0]["insert_end"], 3)
        self.assertLessEqual(hole, 0.01, f"נשאר חור-פנים של {hole}ש בין שני בירולים")
        self.assertEqual(gaps, [])

    def test_never_shifts_the_next_clip_off_its_words(self):
        """גישור מותר רק בהארכת הקודם. הזזת הבא אחורה מנתקת אותו מהמילים
        שבגללן הוא נבחר — וזה בדיוק מה שהשכבה באה לתקן."""
        acc, _ = BD.enforce(
            [{"candidate_id": "broll_001", "clip_id": "c1", "confidence": 0.9,
              "reason": "כל הציוד זמין"},
             {"candidate_id": "broll_002", "clip_id": "c2", "confidence": 0.9,
              "reason": "נכנסים בטביעת אצבע"}], self.windows, self.clips)
        before = {w["candidate_id"]: w["out_start"] for w in self.windows}
        plan, _, _ = BD.build_plan(acc, self.windows, self.clips, OUT_DUR, self.paths)
        for p in plan[1:]:
            self.assertGreaterEqual(p["insert_at"], before[p["candidate_id"]] - 0.001)

    def test_short_window_is_dropped_not_shrunk(self):
        w = [dict(self.windows[0], out_end=self.windows[0]["out_start"] + 1.0,
                  dur_sec=1.0)]
        acc = [{"candidate_id": "broll_001", "clip_id": "c1", "confidence": 0.9,
                "reason": "כל הציוד זמין", "quoted": "כל הציוד"}]
        plan, dropped, _ = BD.build_plan(acc, w, self.clips, OUT_DUR, self.paths)
        self.assertEqual(plan, [])
        self.assertEqual(len(dropped), 1)

    def test_clip_never_exceeds_its_own_footage(self):
        short = [clip("c1", "רחבה פתוחה", dur=2.2)]
        acc = [{"candidate_id": "broll_001", "clip_id": "c1", "confidence": 0.9,
                "reason": "כל הציוד זמין", "quoted": "כל הציוד"}]
        plan, _, _ = BD.build_plan(acc, self.windows[:1], short, OUT_DUR,
                                   {"c1": "/tmp/a.mp4"})
        self.assertLessEqual(plan[0]["clip_len"], 2.2 - BD.SAFE_TAIL + 1e-6)


class TestTalkingHeadGate(unittest.TestCase):
    """הליקוי המקורי: נבחר 'ראיון עם מתאמנת' לסרטון על שעות ומחיר.
    ראיון אינו בירול — זה שוט דיבור שני."""

    def test_interview_clip_is_not_a_cutaway(self):
        self.assertFalse(BP.is_cutaway(
            {"file": "בירול - ראיון עם מתאמנת - 2025-08-22.mp4",
             "category": "קהילה-וצוות", "event": "- ראיון", "tags": ["interview"]}))

    def test_training_clip_is_a_cutaway(self):
        self.assertTrue(BP.is_cutaway(
            {"file": "בירול - דדליפט מתאמנת - 2025-08-22.mp4",
             "category": "אימון-כוח", "event": "- דדליפט", "tags": ["deadlift"]}))

    def test_label_strips_date_and_prefix(self):
        # `desc` בקטלוג מכיל '-08-22' — כל ניקוד שנשען עליו הוא רעש.
        self.assertEqual(BP.clip_label(
            {"file": "בירול - קפיצת קופסה מתאמנת - 2025-08-22.mp4"}),
            "קפיצת קופסה מתאמנת")


if __name__ == "__main__":
    unittest.main()
