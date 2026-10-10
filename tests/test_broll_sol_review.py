# -*- coding: utf-8 -*-
"""
ארבעת חיזוקי האכיפה מביקורת Sol (31.7.26) + חוב התוכן.

הביקורת: "‏MIN_CONF_BED מוגדר אך אינו נאכף; אותו קליפ יכול להופיע פעמיים
ב-bed_sequence; השדה bed_sequence אינו חובה; ויעד 70% מסומן כעובר כבר
ב-59.5% ואינו חוסם."

כל אחת מהארבע נבדקה ואומתה — כל הבדיקות כאן מזריקות בדיוק את הקלט
שהיה עובר לפני התיקון.
"""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_director as BD          # noqa: E402

KEEPS = [{"start": 0.0, "end": 50.0}]
OUT = 50.0
SENTS = [{"i": 0, "start": 0.15, "end": 4.96, "text": "המשפט הראשון"}]


def clip(cid, label, dur=3.6):
    return {"clip_id": cid, "label": label, "category": "אימון-כוח", "dur": dur,
            "vertical": True, "tags": []}


class TestBedConfidenceIsEnforced(unittest.TestCase):
    def setUp(self):
        self.doc = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)
        self.clips = [clip(f"c{i}", f"קליפ {i}") for i in range(1, 9)]
        self.paths = {c["clip_id"]: f"/tmp/{c['clip_id']}.mp4" for c in self.clips}

    def test_a_low_confidence_bed_clip_is_dropped(self):
        seq = [{"clip_id": "c1", "confidence": 0.59, "reason": "חלש"},
               {"clip_id": "c2", "confidence": 0.80, "reason": "טוב"}]
        items, _ = BD.pack_bed(seq, [], self.doc, self.clips, self.paths)
        self.assertNotIn("c1", [p["id"] for p in items])
        self.assertIn("c2", [p["id"] for p in items])

    def test_at_the_threshold_it_passes(self):
        seq = [{"clip_id": "c1", "confidence": BD.MIN_CONF_BED, "reason": "בדיוק בסף"}]
        items, _ = BD.pack_bed(seq, [], self.doc, self.clips, self.paths)
        self.assertIn("c1", [p["id"] for p in items])

    def test_a_clip_repeated_inside_the_sequence_appears_once(self):
        seq = [{"clip_id": "c1", "confidence": 0.8, "reason": "x"},
               {"clip_id": "c1", "confidence": 0.8, "reason": "שוב"},
               {"clip_id": "c2", "confidence": 0.8, "reason": "y"}]
        items, _ = BD.pack_bed(seq, [], self.doc, self.clips, self.paths)
        self.assertEqual([p["id"] for p in items].count("c1"), 1)

    def test_near_duplicate_labels_do_not_run_back_to_back(self):
        cl = [clip("c1", "דדליפט מתאמנת"), clip("c2", "דדליפט מתאמנת (2)"),
              clip("c3", "וול-בול")]
        seq = [{"clip_id": c["clip_id"], "confidence": 0.8, "reason": "r"} for c in cl]
        items, _ = BD.pack_bed(seq, [], self.doc, cl,
                               {c["clip_id"]: "/tmp/x.mp4" for c in cl})
        self.assertNotIn("c2", [p["id"] for p in items])


class TestCoverageVerdict(unittest.TestCase):
    def setUp(self):
        self.doc = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)

    def test_fifty_nine_percent_against_a_seventy_target_is_a_failure(self):
        """זה בדיוק המספר שעבר קודם — 0.85×70 = 59.5."""
        v = BD.coverage_verdict(59.5, self.doc)
        self.assertEqual(v["level"], "fail")
        self.assertFalse(v["ok"])

    def test_sixty_five_is_a_warning_not_a_pass(self):
        self.assertEqual(BD.coverage_verdict(65.0, self.doc)["level"], "warn")

    def test_seventy_four_is_a_pass(self):
        v = BD.coverage_verdict(74.1, self.doc)
        self.assertEqual(v["level"], "ok")
        self.assertTrue(v["ok"])

    def test_anchors_only_has_no_coverage_target(self):
        d = BD.doctrine("value", {}, SENTS, KEEPS, OUT)
        self.assertEqual(BD.coverage_verdict(0.0, d)["level"], "n/a")


class TestShotList(unittest.TestCase):
    """חוסר הופך לחוב תוכן, לא להערה שנעלמת."""

    def setUp(self):
        self.doc = BD.doctrine("conversion", {}, SENTS, KEEPS, OUT)
        self.windows = [
            {"candidate_id": "broll_005", "text": "כל יום מ-10 עד 4 בצהריים",
             "out_start": 15.9, "out_end": 19.4, "dur_sec": 3.5,
             "motion_norm": 1.0, "is_stalled": False},
            {"candidate_id": "broll_003", "text": "אתם נכנסים בטביעת אצבע",
             "out_start": 10.7, "out_end": 12.3, "dur_sec": 1.6,
             "motion_norm": 1.0, "is_stalled": False}]

    def test_an_uncovered_window_becomes_a_shot_to_film(self):
        sl = BD.shot_list(self.windows, [], [{"candidate_id": "broll_005",
                                              "why": "אין קליף שאומר זמן"}], self.doc)
        ids = [x["candidate_id"] for x in sl]
        self.assertIn("broll_005", ids)
        self.assertIn("broll_003", ids)
        self.assertIn("אין קליף שאומר זמן",
                      [x["why_no_clip"] for x in sl if x["candidate_id"] == "broll_005"])

    def test_a_covered_window_is_not_a_debt(self):
        plan = [{"candidate_id": "broll_005", "id": "c1", "role": "anchor"}]
        self.assertNotIn("broll_005",
                         [x["candidate_id"] for x in
                          BD.shot_list(self.windows, plan, [], self.doc)])

    def test_the_shot_line_carries_the_sentence_so_it_is_filmable(self):
        sl = BD.shot_list(self.windows, [], [], self.doc)
        self.assertIn("טביעת אצבע",
                      " ".join(x["needed_shot"] for x in sl))


class TestBedSequenceIsRequired(unittest.TestCase):
    def test_the_pass_demands_the_key(self):
        src = (Path(__file__).resolve().parents[1] /
               "tools/edit_director.py").read_text(encoding="utf-8")
        i = src.index('pv.ask("broll"')
        self.assertIn('"bed_sequence"', src[i:i + 700])


if __name__ == "__main__":
    unittest.main()
