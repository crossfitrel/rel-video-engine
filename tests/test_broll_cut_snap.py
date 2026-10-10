# -*- coding: utf-8 -*-
"""
יישור בירול לגבולות החיתוך (v9.11) — שתי שכבות, שתיהן נבדקות.

הראל, 1.8.26: "אם קטע נגמר ב-1.5 שניות אז הבירול חייב להיגמר ב-1.55 ולא
ב-1.4, כדי שלא יקרה מצב שיש 0.1 שניה של קפיצה או קטיעה כזו."

הליקוי הזה חי בשתי שכבות שונות, וזו הסיבה שתיקון בשכבה אחת בלבד היה משאיר
אותו על המסך:
  1. **תכנון** — איפה הקצה נוחת ביחס לגבול (`broll_director.snap_to_cuts`).
  2. **רינדור** — האם התפר מקבל `fade`. fade על אלפא חושף את הפנים מתחת,
     ולכן בירול שחוצה קאט היה דוהה בדיוק בקאט (`relvid.render`).

כל בדיקה כאן מזריקה את המצב שהראל תיאר ומוודאת שהוא נחסם.
"""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_director as BD          # noqa: E402

# ציר הפלט: keep ראשון 5ש → גבול ב-5.0; שני 12ש → גבול ב-17.0. האחרון אינו גבול.
KEEPS = [{"start": 0.5, "end": 5.5}, {"start": 8.0, "end": 20.0},
         {"start": 25.0, "end": 40.0}]
OUT_DUR = 32.0
DOC = {"mode": "continuous_bed", "bed_start": 3.0, "bed_end": 24.0}


def item(cid, at, end, dur=6.0, role="bed", off=1.0):
    return {"id": cid, "label": cid, "role": role, "insert_at": at,
            "insert_end": end, "clip_len": round(end - at, 2), "src_offset": off}


def clip(cid, dur=6.0):
    return {"clip_id": cid, "label": cid, "dur": dur}


class TestTheBoundaryIsTheUnit(unittest.TestCase):
    def test_cut_boundaries_are_the_cumulative_keep_ends(self):
        self.assertEqual([5.0, 17.0], BD.cut_boundaries(KEEPS))

    def test_a_single_keep_has_no_internal_boundary(self):
        self.assertEqual([], BD.cut_boundaries([{"start": 0.0, "end": 32.0}]))


class TestSliverBeforeTheCutIsClosed(unittest.TestCase):
    """המקרה של הראל: הבירול נגמר לפני הקאט ונשארת פיסת-דובר."""

    def test_clip_ending_just_before_a_cut_is_extended_past_it(self):
        plan = [item("a", 2.5, 4.9)]          # נגמר 0.1ש לפני הגבול 5.0
        plan, slivers = BD.snap_to_cuts(plan, KEEPS, [clip("a")], DOC, OUT_DUR)
        self.assertEqual([], slivers)
        self.assertGreater(plan[0]["insert_end"], 5.0,
                           "הקצה נשאר לפני הקאט — זו הקפיצה הכפולה עצמה")
        self.assertAlmostEqual(5.0 + BD.CUT_OVERHANG, plan[0]["insert_end"], places=2)
        self.assertEqual(5.0, plan[0]["snapped_to_cut"])

    def test_landing_exactly_on_the_boundary_still_gets_the_overhang(self):
        """קצה שנוחת בדיוק על הגבול תלוי בעיגול ובכימות פריימים — הפריים
        שעל הגבול יכול להישאר חשוף. זו אותה משפחת ליקוי, קטנה יותר."""
        plan = [item("a", 2.5, 5.0)]
        plan, _ = BD.snap_to_cuts(plan, KEEPS, [clip("a")], DOC, OUT_DUR)
        self.assertAlmostEqual(5.0 + BD.CUT_OVERHANG, plan[0]["insert_end"], places=2)

    def test_clip_length_grows_and_the_head_does_not_move(self):
        plan = [item("a", 2.5, 4.9)]
        plan, _ = BD.snap_to_cuts(plan, KEEPS, [clip("a")], DOC, OUT_DUR)
        self.assertEqual(2.5, plan[0]["insert_at"])
        self.assertAlmostEqual(plan[0]["insert_end"] - plan[0]["insert_at"],
                               plan[0]["clip_len"], places=2)


class TestSliverAfterTheCutIsClosed(unittest.TestCase):
    """התמונה בראי: הקאט קורה, ורק אז הבירול מתחיל."""

    def test_clip_starting_just_after_a_cut_is_pulled_back_across_it(self):
        plan = [item("a", 5.2, 8.0, off=1.0)]
        plan, slivers = BD.snap_to_cuts(plan, KEEPS, [clip("a")], DOC, OUT_DUR)
        self.assertEqual([], slivers)
        self.assertLess(plan[0]["insert_at"], 5.0)
        self.assertEqual(8.0, plan[0]["insert_end"], "הזנב לא אמור לזוז")

    def test_pulling_back_consumes_head_footage_via_src_offset(self):
        plan = [item("a", 5.2, 8.0, off=1.0)]
        plan, _ = BD.snap_to_cuts(plan, KEEPS, [clip("a")], DOC, OUT_DUR)
        self.assertLess(plan[0]["src_offset"], 1.0)
        self.assertGreaterEqual(plan[0]["src_offset"], 0.0)


class TestWhatMustNotBeTouched(unittest.TestCase):
    def test_a_cut_already_covered_by_broll_is_left_alone(self):
        plan = [item("a", 3.0, 9.0)]
        before = dict(plan[0])
        plan, slivers = BD.snap_to_cuts(plan, KEEPS, [clip("a", 12.0)], DOC, OUT_DUR)
        self.assertEqual(before, plan[0])
        self.assertEqual([], slivers)

    def test_a_cut_far_from_any_broll_is_not_a_defect(self):
        """קאט שעומד בפני עצמו הוא עריכה, לא ליקוי — אין מה ליישר ואין מה לדווח."""
        plan = [item("a", 10.0, 13.0)]
        plan, slivers = BD.snap_to_cuts(plan, KEEPS, [clip("a")], DOC, OUT_DUR)
        self.assertEqual(13.0, plan[0]["insert_end"])
        self.assertEqual([], slivers)

    def test_a_boundary_inside_the_protected_cta_is_skipped(self):
        doc = {"mode": "continuous_bed", "bed_start": 3.0, "bed_end": 16.0}
        plan = [item("a", 14.5, 16.9)]        # הגבול 17.0 מעבר ל-bed_end
        plan, slivers = BD.snap_to_cuts(plan, KEEPS, [clip("a")], doc, OUT_DUR)
        self.assertEqual(16.9, plan[0]["insert_end"])
        self.assertEqual([], slivers)

    def test_extension_never_overlaps_the_next_clip(self):
        plan = [item("a", 2.5, 4.9), item("b", 5.02, 8.0)]
        plan, slivers = BD.snap_to_cuts(plan, KEEPS, [clip("a"), clip("b")],
                                        DOC, OUT_DUR)
        self.assertLessEqual(plan[0]["insert_end"], plan[1]["insert_at"] + 1e-6)


class TestNoFootageIsReportedNotFaked(unittest.TestCase):
    """הארכה חלקית רק מזיזה את הסליבר ונראית כאילו טופלה — לכן: או שחוצים
    את הגבול, או שמדווחים חוב צילום."""

    def test_a_clip_with_no_tail_footage_reports_a_sliver(self):
        plan = [item("a", 2.5, 4.9, off=0.0)]
        plan, slivers = BD.snap_to_cuts(plan, KEEPS, [clip("a", dur=2.45)],
                                        DOC, OUT_DUR)
        self.assertEqual(1, len(slivers))
        self.assertEqual(5.0, slivers[0]["at_cut"])
        self.assertEqual("end", slivers[0]["side"])

    def test_the_reported_sliver_leaves_the_plan_untouched(self):
        plan = [item("a", 2.5, 4.9, off=0.0)]
        plan, _ = BD.snap_to_cuts(plan, KEEPS, [clip("a", dur=2.45)], DOC, OUT_DUR)
        self.assertEqual(4.9, plan[0]["insert_end"])
        self.assertIsNone(plan[0].get("snapped_to_cut"))


class TestAnchorsOnlyModeIsCoveredToo(unittest.TestCase):
    """ב-anchors_only אין `close_small_holes`, ולכן שם הליקוי היה
    בלתי-נראה למערכת לגמרי."""

    def test_value_content_gets_the_same_alignment(self):
        doc = {"mode": "anchors_only"}
        plan = [item("a", 4.5, 4.95, role="anchor")]
        plan, _ = BD.snap_to_cuts(plan, KEEPS, [clip("a")], doc, OUT_DUR)
        self.assertGreater(plan[0]["insert_end"], 5.0)


class TestFadeDoesNotReopenTheSeam(unittest.TestCase):
    """השכבה השנייה. `fade` על אלפא מוריד את שקיפות הבירול ומתחתיו נחשפות
    הפנים — ולכן בירול שחוצה קאט, ומפוצל לשני סגמנטים, היה דוהה בדיוק בקאט
    ומחזיר את הפנים לשבריר שנייה. זה היה מבטל את כל היישור שלמעלה."""

    def _mk(self):
        from relvid import render as R
        return R

    def test_a_clip_split_across_a_cut_has_no_fade_at_the_internal_seam(self):
        R = self._mk()
        segs = [R.Segment(src="i.mp4", t_in=0.0, t_out=5.0, out_start=0.0),
                R.Segment(src="i.mp4", t_in=8.0, t_out=20.0, out_start=5.0)]
        c = R.BrollClip(path="b.mp4", start=3.0, end=7.0, src_offset=0.5)
        frags = []
        R._clip_to_segments(
            [c], segs, lambda x: (x.start, x.end),
            lambda seg, x, ls, le, off: frags.append(R.broll_fragment(x, ls, le, off)))
        self.assertEqual(2, len(frags), "הקליפ אמור להתפצל בגבול")
        self.assertTrue(frags[0].fade_in)
        self.assertFalse(frags[0].fade_out, "דהייה בתפר הפנימי = הפנים נחשפות בקאט")
        self.assertFalse(frags[1].fade_in)
        self.assertTrue(frags[1].fade_out)

    def test_adjacent_brolls_share_a_hard_cut_not_a_fade(self):
        """v8.3, הראל 25.7.26 — הלקח שנסוג בשקט כשהמנוע הוחלף ל-v2."""
        R = self._mk()
        a = R.BrollClip(path="a.mp4", start=3.0, end=6.0, src_offset=0.0)
        b = R.BrollClip(path="b.mp4", start=6.0, end=9.0, src_offset=0.0)
        R.mark_seam_fades([a, b])
        self.assertTrue(a.fade_in)
        self.assertFalse(a.fade_out)
        self.assertFalse(b.fade_in)
        self.assertTrue(b.fade_out)

    def test_the_cache_key_changes_when_the_fade_flags_change(self):
        """מטמון שלא מכיר את הדגלים היה מגיש את הסגמנט הישן אחרי התיקון."""
        R = self._mk()
        orig = R._file_id
        R._file_id = lambda p: str(p)
        try:
            tl = R.Timeline(workdir=Path("/tmp"), input_path=Path("/tmp/i.mp4"),
                            segments=[], band={"y0": 0}, brand="rel", crf=19)
            seg = R.Segment(src="i.mp4", t_in=0.0, t_out=5.0, out_start=0.0)
            seg.broll = [R.BrollClip("b.mp4", 1.0, 3.0, 0.0)]
            k1 = R._segment_key(tl, seg)
            seg.broll[0].fade_out = False
            self.assertNotEqual(k1, R._segment_key(tl, seg))
        finally:
            R._file_id = orig

    def test_the_engine_version_was_bumped_so_old_segments_are_invalidated(self):
        """סגמנט שנשמר במטמון לפני התיקון נראה בדיוק כמו הבאג."""
        self.assertNotEqual("v2.1", self._mk().ENGINE_VERSION)


if __name__ == "__main__":
    unittest.main()
