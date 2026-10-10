# -*- coding: utf-8 -*-
"""‏v9.9 — שלוש שכבות שנוספו, כל אחת עם הזרקת-כשל.

1. **ז'אנר לפי טון** — סרטון המרה בטון רגוע לא מקבל phonk. השורש: הסינון
   הכבד רץ רק כש-`content_type != conversion`, וסרטון האופן-ג'ים **הוא**
   המרה בטון "רגוע, בטוח ועובדתי… הזמנה לשקט". אז זה תוקן פעמיים באותה
   נשימה (ז'אנר וגם מפלס), ואחד התיקונים התיישן ונשאר.
2. **פעימת `trust`** — חזרה לפנים בכוונה בתוך המצע. עד v9.9 כל חזרה לפנים
   נספרה כליקוי, כלומר לתפקיד לגיטימי לא הייתה דרך להתקיים.
3. **ציון מעטפת נמדד** — במקום ציון שהמודל נותן לעצמו.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "bench"))


class TestToneDrivesGenre(unittest.TestCase):
    def setUp(self):
        import local_finish_pipeline as LFP
        self.LFP = LFP

    def test_the_open_gym_tone_is_calm(self):
        t = ("רגוע, בטוח ועובדתי. זו הזמנה לשקט ולמרחב אישי, לא דחיפה. "
             "בלי הבטחות גדולות ובלי סופרלטיבים")
        self.assertEqual("calm", self.LFP.tone_class(t))

    def test_an_explicitly_energetic_tone_wins(self):
        self.assertEqual("energetic",
                         self.LFP.tone_class("אנרגטי ורגוע בו-זמנית"))

    def test_an_unknown_tone_stays_neutral(self):
        self.assertEqual("neutral", self.LFP.tone_class("ענייני"))
        self.assertEqual("neutral", self.LFP.tone_class(""))

    def test_calm_conversion_filters_heavy_genres(self):
        """הזרקת הכשל: זה בדיוק המצב שנתן phonk לסרטון של שעות ומחיר."""
        import json
        cat = json.loads((ROOT / "tools" / "music-catalog.json")
                         .read_text(encoding="utf-8")).get("tracks", {})
        heavy = {n for n, v in cat.items()
                 if v.get("genre") in {"phonk", "trap", "rock_sport", "edm"}}
        self.assertTrue(heavy, "אין ז'אנרים כבדים בקטלוג — הבדיקה חסרת משמעות")
        # ‏`pick_music` כותב היסטוריית רוטציה. בדיקה לא נוגעת במצב אמיתי —
        # אחרת היא שורפת טראק מהרוטציה של הראל בכל הרצת בדיקות.
        import tempfile
        from pathlib import Path as _P
        orig = self.LFP.ROTATION_STATE
        with tempfile.TemporaryDirectory() as d:
            self.LFP.ROTATION_STATE = _P(d) / "rot.json"
            try:
                picked = self.LFP.pick_music("conversion", None,
                                             tone="רגוע, הזמנה לשקט")
            finally:
                self.LFP.ROTATION_STATE = orig
        if picked is not None:
            self.assertNotIn(picked.name, heavy)


class TestTrustBeatIsADecisionNotAHole(unittest.TestCase):
    def setUp(self):
        import broll_director as BD
        self.BD = BD
        self.doc = {"mode": "continuous_bed", "bed_start": 0.0, "bed_end": 12.0,
                    "bed_clips_needed": 4}
        self.clips = [{"clip_id": f"c{i}", "label": f"קליפ {i}", "dur": 6.0}
                      for i in range(4)]
        self.paths = {f"c{i}": f"/tmp/c{i}.mp4" for i in range(4)}

    def test_a_trust_beat_produces_no_clip_but_holds_the_timeline(self):
        seq = [{"clip_id": "c0", "confidence": 0.8},
               {"beat": "trust", "reason": "המחיר — נאמר לעיניים"},
               {"clip_id": "c1", "confidence": 0.8}]
        items, _ = self.BD.pack_bed(seq, [], self.doc, self.clips, self.paths)
        trust = [i for i in items if i["role"] == "trust"]
        self.assertEqual(1, len(trust))
        self.assertIsNone(trust[0]["path"])
        self.assertGreater(trust[0]["insert_end"], trust[0]["insert_at"])

    def test_a_trust_beat_is_not_reported_as_a_face_hole(self):
        seq = [{"clip_id": "c0", "confidence": 0.8},
               {"beat": "trust", "reason": "תנאי ביטול"},
               {"clip_id": "c1", "confidence": 0.8},
               {"clip_id": "c2", "confidence": 0.8},
               {"clip_id": "c3", "confidence": 0.8}]
        items, _ = self.BD.pack_bed(seq, [], self.doc, self.clips, self.paths)
        bed = [i for i in items if i["role"] != "trust"]
        trust = [i for i in items if i["role"] == "trust"]
        self.assertTrue(trust)
        with_trust = self.BD.face_holes(bed, self.doc, trust)
        without = self.BD.face_holes(bed, self.doc)
        self.assertLess(len(with_trust), len(without),
                        "הפעימה לא נספרה ככיסוי — התפקיד עדיין מדווח כליקוי")

    def test_bed_items_carry_their_beat(self):
        seq = [{"clip_id": "c0", "beat": "proof", "confidence": 0.8}]
        items, _ = self.BD.pack_bed(seq, [], self.doc, self.clips, self.paths)
        self.assertEqual("proof", items[0]["beat"])

    def test_an_unknown_beat_falls_back_to_texture_not_to_trust(self):
        """‏beat לא מוכר לא יהפוך בטעות לחור בציר."""
        seq = [{"clip_id": "c0", "beat": "המצאה", "confidence": 0.8}]
        items, _ = self.BD.pack_bed(seq, [], self.doc, self.clips, self.paths)
        self.assertEqual("texture", items[0]["beat"])
        self.assertEqual("bed", items[0]["role"])


class TestEnvelopeScoreIsMeasured(unittest.TestCase):
    def setUp(self):
        import output_profile as OP
        self.OP = OP
        self.ref = {"n_projects": 16, "envelope": {
            "silence_pct": {"min": 13.2, "max": 31.7},
            "longest_pause": {"min": 0.44, "max": 5.83},
            "cuts_per_sec": {"min": 0.043, "max": 0.296},
            "seam_median": {"min": 6.8, "max": 32.6}}}

    def _prof(self, **kw):
        base = {"silence_pct": 20.0, "longest_pause": 0.8,
                "cuts_per_sec": 0.18, "seam_median": 20.0}
        base.update(kw)
        return base

    def test_inside_the_envelope_scores_ten(self):
        r = self.OP.envelope_score(self._prof(), self.ref)
        self.assertEqual(10.0, r["score"])
        self.assertEqual("measured:reference_profile", r["source"])

    def test_outside_the_envelope_lowers_the_score_and_says_which(self):
        r = self.OP.envelope_score(self._prof(silence_pct=45.0), self.ref)
        self.assertLess(r["score"], 10.0)
        self.assertLess(r["components"]["silence_pct"]["score"], 1.0)
        self.assertEqual(1.0, r["components"]["cuts_per_sec"]["score"])

    def test_still_windows_are_reported_and_do_not_zero_a_valid_output(self):
        """הגרסה הראשונה של המדד הזה החזירה 0.0/10 על תוצר שכל ארבעת
        מדדיו בטווח — מספר עגול שאיש לא מדד שמאפס תוצר תקין."""
        a = self.OP.envelope_score(self._prof(), self.ref)
        b = self.OP.envelope_score(dict(self._prof(),
                                        still_windows=[1, 2, 3, 4]), self.ref)
        self.assertEqual(a["score"], b["score"])
        self.assertEqual(4, b["still_windows"])
        self.assertIn("מדווח", b["still_note"])


if __name__ == "__main__":
    unittest.main()
