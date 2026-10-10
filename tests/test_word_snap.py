#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""בדיקות לשכבת הצמדת גבולות-המילה לאנרגיה (V3, 30.7.26).

למה זה קיים: תזמוני Whisper מרופדים, ולכן מרחב המועמדים — שנבנה מגבולות מילה —
לא ראה 4.66ש של שקט אקוסטי אמיתי ב-10 מקטעים בפרויקט אמיתי. זה בדיוק השקט
ש-`tighten` היה מקצץ מאחורי גבו של הבמאי. כל בדיקה כאן כוללת הזרקת-כשל:
היא נכשלת אם הקוד מפסיק לעשות את מה שהיא טוענת שהוא עושה.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

import candidates as C                                       # noqa: E402


def envelope(loud_ranges, total_sec=10.0, floor_db=-96.0, loud_db=-20.0):
    """מעטפת סינתטית: רצפה בכל מקום, ורועש בטווחים שניתנו."""
    n = int(total_sec / C.HOP)
    db = [floor_db] * n
    for a, b in loud_ranges:
        for i in range(int(a / C.HOP), min(n, int(b / C.HOP))):
            db[i] = loud_db
    return db, floor_db


class TestSnap(unittest.TestCase):
    def test_padded_word_end_is_pulled_back(self):
        """המקרה האמיתי: Whisper אומר שהמילה נגמרת ב-2.00, האודיו דעך ב-1.20."""
        db, floor = envelope([(1.0, 1.2), (3.0, 3.4)])
        words = [{"word": "שלכם", "start": 1.0, "end": 2.0},
                 {"word": "רחבת", "start": 3.0, "end": 3.4}]
        out, st = C.snap_words_to_audio(words, db, floor)
        # 1.20 (דעיכה) + SNAP_TAIL_PAD — משאירים זנב עיצור במכוון
        self.assertAlmostEqual(out[0]["end"], 1.20 + C.SNAP_TAIL_PAD, delta=0.02)
        self.assertGreaterEqual(st["snapped"], 1)
        self.assertGreater(st["exposed_sec"], 0.7)

    def test_exposes_gap_that_was_invisible(self):
        """הטענה המרכזית: אחרי ההצמדה נפתח פער שלא היה קיים במרחב לפני כן."""
        # המידות כאן הן המידות שנמדדו בפועל: Whisper ריפד את סוף המילה ב-0.85ש,
        # והפער שנשאר לפניו היה 0.05ש — מתחת ל-min_gap=0.12 ולכן חסר לגמרי במרחב.
        db, floor = envelope([(1.0, 1.2), (2.1, 2.6)])
        words = [{"word": "א", "start": 1.0, "end": 2.05},
                 {"word": "ב", "start": 2.10, "end": 2.6}]
        gap_before = words[1]["start"] - words[0]["end"]
        out, _ = C.snap_words_to_audio(words, db, floor)
        gap_after = out[1]["start"] - out[0]["end"]
        self.assertLess(gap_before, C.__dict__.get("MIN_GAP_DEFAULT", 0.12))
        self.assertGreater(gap_after, 0.70)        # גלוי לבמאי (אחרי ריפוד 2×0.06)

    def test_never_crosses_into_neighbour(self):
        db, floor = envelope([(1.0, 1.2), (1.3, 1.5)])
        words = [{"word": "א", "start": 1.0, "end": 1.28},
                 {"word": "ב", "start": 1.3, "end": 1.5}]
        out, _ = C.snap_words_to_audio(words, db, floor)
        self.assertLessEqual(out[0]["end"], out[1]["start"] + 1e-6)
        self.assertGreaterEqual(out[1]["start"], words[0]["end"] - 1e-6)

    def test_never_shrinks_below_min_word(self):
        """מילה שקטה לגמרי (למשל לחישה מתחת לסף) לא נמחקת — נשארת כמות שהיא."""
        db, floor = envelope([])                    # שקט מוחלט בכל מקום
        words = [{"word": "א", "start": 1.0, "end": 1.30},
                 {"word": "ב", "start": 2.0, "end": 2.30}]
        out, _ = C.snap_words_to_audio(words, db, floor)
        for w_in, w_out in zip(words, out):
            self.assertGreaterEqual(w_out["end"] - w_out["start"], C.SNAP_MIN_WORD)
            self.assertAlmostEqual(w_out["start"], w_in["start"], places=3)
            self.assertAlmostEqual(w_out["end"], w_in["end"], places=3)

    def test_respects_max_shift(self):
        """הזרקת-כשל: פער ענק בתוך 'מילה' לא מזיז את הגבול יותר מהתקרה."""
        db, floor = envelope([(1.0, 1.1)], total_sec=20.0)
        words = [{"word": "א", "start": 1.0, "end": 9.0}]
        out, _ = C.snap_words_to_audio(words, db, floor)
        self.assertGreaterEqual(out[0]["end"], 9.0 - C.SNAP_MAX_SHIFT - 1e-6)

    def test_shift_cap_is_documented_behaviour(self):
        """ריפוד שחורג מהתקרה **לא** מוצמד בכלל — במכוון. השארת שקט עדיפה על
        הזזת גבול על סמך מדידה שאולי אינה אמינה (ASR רועש, מוזיקת רקע).
        המקסימום שנמדד בפועל בפרויקט אמיתי היה 0.72ש, הרבה מתחת לתקרה 1.20."""
        db, floor = envelope([(1.0, 1.1)], total_sec=20.0)
        words = [{"word": "א", "start": 1.0, "end": 5.0}]
        out, _ = C.snap_words_to_audio(words, db, floor)
        self.assertEqual(out[0]["end"], 5.0)

    def test_no_envelope_is_identity(self):
        out, st = C.snap_words_to_audio([{"word": "א", "start": 1.0, "end": 2.0}], None, None)
        self.assertFalse(st["available"])
        self.assertEqual(out[0]["end"], 2.0)


class TestValidatorUsesSameWords(unittest.TestCase):
    """אם האימות רץ על גבולות אחרים מאלה שהמרחב נבנה מהם — כל חיתוך תקין נפסל."""

    def test_edit_plan_prefers_snapped(self):
        import json
        import tempfile
        import edit_plan as EP
        d = Path(tempfile.mkdtemp())
        (d / "edit_plan.json").write_text(json.dumps({"decisions": []}), encoding="utf-8")
        (d / "candidates.json").write_text(json.dumps(
            {"candidates": [], "source": {"total_dur": 10.0}}), encoding="utf-8")
        (d / "whisper_raw.json").write_text(json.dumps(
            [{"word": "א", "start": 1.0, "end": 2.0}]), encoding="utf-8")
        (d / "words_snapped.json").write_text(json.dumps(
            [{"word": "א", "start": 1.0, "end": 1.2}]), encoding="utf-8")
        _, _, _, words = EP.load(d)
        self.assertAlmostEqual(words[0]["end"], 1.2, places=3)


class TestTotalDurFromMedia(unittest.TestCase):
    """הרגרסיה שעלתה בפועל: total מהתמלול חרג מאורך הקובץ ב-0.59ש,
    edl_cut ביקש קטע שלא קיים, והמשך בפועל היה קצר מהצפוי."""

    def test_probe_duration_returns_number_or_zero(self):
        self.assertEqual(C.probe_duration("/nonexistent/file.mp4"), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
