# -*- coding: utf-8 -*-
"""
דוקטרינת הבירול — מי הקהל קובע את המבנה (v9.5, הראל 31.7.26).

"סרטון המרה פונה לקהל שלא מכיר אותנו... 70% בירולים, ישר אחרי המשפט הראשון
רצים בירולים אחד אחרי השני בלי לחזור אליי, עד לקריאה לפעולה."

הליקוי שהוליד את זה: הבירול נגמר 0.17ש לפני סוף המשפט, ובחור הזה נראה
מבט-למטה. כל בדיקה כאן מזריקה את המצב שייצר אותו.
"""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_director as BD          # noqa: E402

KEEPS = [{"start": 0.0, "end": 50.0}]
OUT = 50.0
SENTS = [{"i": 0, "start": 0.15, "end": 4.96, "text": "המשפט הראשון"},
         {"i": 1, "start": 5.2, "end": 8.87, "text": "כל הציוד זמין ברחבה"}]


def clip(cid, label, dur=3.6):
    return {"clip_id": cid, "label": label, "category": "אימון-כוח", "dur": dur,
            "vertical": True, "tags": [], "last_used_days": None}


class TestDoctrine(unittest.TestCase):
    def test_conversion_is_a_continuous_bed(self):
        d = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)
        self.assertEqual(d["mode"], "continuous_bed")
        self.assertEqual(d["audience_state"], "cold")

    def test_bed_starts_at_end_of_first_sentence(self):
        """'ישר אחרי המשפט הראשון' — לא בשנייה שרירותית."""
        d = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)
        self.assertAlmostEqual(d["bed_start"], 4.96, places=2)

    def test_bed_ends_before_the_cta(self):
        d = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)
        self.assertAlmostEqual(d["bed_end"], OUT - BD.CTA_GUARD, places=2)

    def test_projected_coverage_is_about_seventy(self):
        d = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)
        self.assertGreaterEqual(d["projected_coverage_pct"], 65)

    def test_value_content_stays_anchors_only(self):
        """הזרקת הכשל ההפוכה: מצע בתוכן ערך הוא רעש, לא שיפור."""
        d = BD.doctrine("value", {}, SENTS, KEEPS, OUT)
        self.assertEqual(d["mode"], "anchors_only")
        self.assertNotIn("bed_start", d)


class TestBedPacking(unittest.TestCase):
    def setUp(self):
        self.doc = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)
        self.clips = [clip(f"c{i}", f"קליפ {i}") for i in range(1, 20)]
        self.paths = {c["clip_id"]: f"/tmp/{c['clip_id']}.mp4" for c in self.clips}
        self.seq = [{"clip_id": c["clip_id"], "reason": "מה הצופה הקר לומד"}
                    for c in self.clips]

    def test_bed_fills_the_window_with_no_face_holes(self):
        items, _ = BD.pack_bed(self.seq, [], self.doc, self.clips, self.paths)
        plan = BD.close_small_holes(items, self.clips, self.doc)
        self.assertEqual(BD.face_holes(plan, self.doc), [],
                         "נשארו חורי-פנים בתוך המצע — זה בדיוק הליקוי")

    def test_bed_reaches_the_coverage_target(self):
        items, _ = BD.pack_bed(self.seq, [], self.doc, self.clips, self.paths)
        plan = BD.close_small_holes(items, self.clips, self.doc)
        self.assertGreaterEqual(BD.coverage(plan, OUT),
                                self.doc["coverage_target_pct"] * 0.85)

    def test_bed_never_touches_the_cta(self):
        items, _ = BD.pack_bed(self.seq, [], self.doc, self.clips, self.paths)
        for p in items:
            self.assertLessEqual(p["insert_end"], OUT - BD.CTA_GUARD + 0.01)

    def test_bed_never_touches_the_hook(self):
        items, _ = BD.pack_bed(self.seq, [], self.doc, self.clips, self.paths)
        for p in items:
            self.assertGreaterEqual(p["insert_at"], self.doc["bed_start"] - 0.01)

    def test_bed_does_not_reuse_an_anchor_clip(self):
        anchor = [{"id": "c1", "role": "anchor", "insert_at": 10.0,
                   "insert_end": 13.0, "clip_len": 3.0, "label": "קליפ 1"}]
        items, _ = BD.pack_bed(self.seq, anchor, self.doc, self.clips, self.paths)
        self.assertNotIn("c1", [p["id"] for p in items])

    def test_bed_flows_around_an_anchor_without_a_hole(self):
        anchor = [{"id": "c1", "role": "anchor", "insert_at": 10.0,
                   "insert_end": 13.0, "clip_len": 3.0, "label": "קליפ 1"}]
        items, _ = BD.pack_bed(self.seq, anchor, self.doc, self.clips, self.paths)
        plan = BD.close_small_holes(anchor + items, self.clips, self.doc)
        self.assertEqual(BD.face_holes(plan, self.doc), [])

    def test_clip_never_exceeds_footage_even_when_stretched(self):
        short = [clip(f"c{i}", f"קליפ {i}", dur=2.4) for i in range(1, 20)]
        items, _ = BD.pack_bed(self.seq, [], self.doc, short, self.paths)
        plan = BD.close_small_holes(items, short, self.doc)
        for p in plan:
            self.assertLessEqual(p["clip_len"], 2.4 - BD.SAFE_TAIL + 1e-6)

    def test_no_bed_sequence_means_no_bed(self):
        """'אין מכסה למלא בכוח' — מודל שלא נתן מצע לא מקבל מצע מומצא."""
        items, _ = BD.pack_bed([], [], self.doc, self.clips, self.paths)
        self.assertEqual(items, [])


class TestSliverRegression(unittest.TestCase):
    """הליקוי המקורי: בירול שנגמר 0.17ש לפני סוף המשפט ⇒ מבט-למטה בחור."""

    def test_a_seventeen_hundredths_sliver_is_closed(self):
        doc = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)
        clips = [clip("a", "עוגן"), clip("b", "מצע")]
        plan = [{"id": "a", "role": "anchor", "insert_at": 5.2, "insert_end": 8.70,
                 "clip_len": 3.5, "label": "עוגן"},
                {"id": "b", "role": "bed", "insert_at": 8.87, "insert_end": 11.67,
                 "clip_len": 2.8, "label": "מצע"}]
        out = BD.close_small_holes(plan, clips, doc)
        hole = round(out[1]["insert_at"] - out[0]["insert_end"], 3)
        self.assertLessEqual(hole, 0.01, f"נשאר סליבר של {hole}ש — המבט-למטה חוזר")


if __name__ == "__main__":
    unittest.main()
