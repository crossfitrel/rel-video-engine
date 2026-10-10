# -*- coding: utf-8 -*-
"""v9.34 (גל 6, 23.9.26) — הידוק שערי הראייה שנשארו מדווחים, לפי מדידה.

garbled_cue (g1 = f_ok1 × recall) חוסם ב-≥3 cues · face דורש ≥2 עיניים בתיבה ·
cover garbled_word (כותרת, ברמת מילה) חוסם · extra_ink ברכיבים וייחוס מילה
ל-Studentit נמדדו ונפלו ולכן אינם בקוד. כל בדיקה כאן היא הזרקת כשל.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "thumbnail"))
sys.path.insert(0, str(ROOT / "tests"))

import cv2                                   # noqa: E402

import caption_vision as CV                  # noqa: E402
from test_vision_gates_v929 import WORDS, _bg  # noqa: E402

CFG6 = dict(CV.DEFAULTS, source="measured", g1_max=0.30,
            blocking=["reversed", "missing", "tofu", "garbled_cue"],
            min_hits={"garbled_cue": 3})


def make_video(W_dir, shown, fps=30, dur=2.0):
    """FINAL סינתטי שבו על המסך נצרב `shown[i]` במקום מילת ה-cue (הזרקת 'מילה אחרת')."""
    W_dir = Path(W_dir)
    W_dir.mkdir(parents=True, exist_ok=True)
    (W_dir / "words_final.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    (W_dir / "project_manifest.json").write_text(json.dumps({"brand": "rel"}), encoding="utf-8")
    (W_dir / "FINAL_PROVENANCE.json").write_text(json.dumps({"intro_offset_sec": 0.0}), encoding="utf-8")
    cues = CV.group_cues(WORDS)
    g = CV.geometry(cues, 1080, 1920, "rel")
    bg = _bg()
    vw = cv2.VideoWriter(str(W_dir / "FINAL.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1080, 1920))
    for i in range(int(dur * fps)):
        t = i / float(fps)
        fr = bg.copy()
        k = next((j for j, c in enumerate(cues) if c["start"] <= t < c["end"]), None)
        if k is not None:
            band = fr[g["y0"]:g["y0"] + g["band_h"]]
            fr[g["y0"]:g["y0"] + g["band_h"]] = CV._composite(band, shown[k], g, 1080)
        vw.write(fr)
    vw.release()
    return W_dir


class TestGarbledCue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp(prefix="cv934_"))
        cls.cues = [c["text"] for c in CV.group_cues(WORDS)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def test_correct_captions_pass_garbled_cue(self):
        doc = CV.analyze(make_video(self.d / "ok", self.cues), cfg=CFG6, sheet=False, write=False)
        self.assertNotIn("garbled_cue", doc["counts"], doc["counts"])
        self.assertTrue(doc["ok"])

    def test_wrong_words_on_screen_block_by_count(self):
        # כל ה-cues מציגים מילה אחרת (קובץ מילים לא נכון) ⇒ 3 cues ⇒ חוסם בלי תנאי אחוז
        wrong = ["מזרון", "קטלבל", "סקוואט"]
        doc = CV.analyze(make_video(self.d / "wrong", wrong), cfg=CFG6, sheet=False, write=False)
        self.assertGreaterEqual(doc["counts"].get("garbled_cue", 0), 3, doc["counts"])
        self.assertIn("garbled_cue", doc["blocking_hits"])
        self.assertFalse(doc["ok"])

    def test_two_cues_report_but_do_not_block(self):
        # המקסימום בסרטון חי תקין היה 2 cues (דרג-לי-את-הפודיום) ⇒ 2 לא חוסמים
        shown = ["מזרון", "קטלבל", self.cues[2]]
        doc = CV.analyze(make_video(self.d / "two", shown), cfg=CFG6, sheet=False, write=False)
        self.assertEqual(doc["counts"].get("garbled_cue", 0), 2, doc["counts"])
        self.assertTrue(doc["ok"])

    def test_clutter_lowers_precision_not_recall(self):
        # הלב של המדד: דיו זר (רקע אירוע) פוגע ב-precision; גליף שגוי פוגע ב-recall
        m_clutter = {"ink_in": 0.9, "symmetric": True, "f_rev": 0, "f_ok": 0.8,
                     "f_ok1": 0.52, "r1": 0.95, "g1": round(0.52 * 0.95, 3),
                     "ink_out": 0.0, "bbox": [300, 0, 700, 10]}
        m_wrong = dict(m_clutter, f_ok1=0.52, r1=0.45, g1=round(0.52 * 0.45, 3))
        self.assertNotIn("garbled_cue", CV.classify(m_clutter, "דני", 1080, CFG6, []))
        self.assertIn("garbled_cue", CV.classify(m_wrong, "דני", 1080, CFG6, []))

    def test_unmeasured_g1_means_no_flag(self):
        cfg = dict(CFG6, g1_max=None)
        m = {"ink_in": 0.9, "symmetric": True, "f_rev": 0, "f_ok": 0.1, "f_ok1": 0.1, "r1": 0.1,
             "g1": 0.01, "ink_out": 0.0, "bbox": [300, 0, 700, 10]}
        self.assertNotIn("garbled_cue", CV.classify(m, "דני", 1080, cfg, []))

    def test_calibration_records_live_sweep_and_survives_recalibration(self):
        cal = json.loads((TOOLS / "caption-vision-calibration.json").read_text(encoding="utf-8"))
        p, ev = cal["params"], cal["evidence"]
        self.assertIn("garbled_cue", p["blocking"])
        self.assertEqual(p["min_hits"]["garbled_cue"], 3)
        w6 = ev["garbled_cue_w6"]
        self.assertLess(w6["worst_live_video"]["cues_below"], p["min_hits"]["garbled_cue"])
        self.assertGreaterEqual(w6["catch_per_cue_injection"]["scrambled"], 0.95)
        src = (TOOLS / "caption_vision.py").read_text(encoding="utf-8")
        self.assertIn('params["g1_max"] = prev["g1_max"]', src)


class TestFaceNeedsEyes(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="cvface934_"))
        cues = [c["text"] for c in CV.group_cues(WORDS)]
        self.W = make_video(self.d / "f", cues)
        self._faces, self._eyes = CV.faces, CV.eyes_in

    def tearDown(self):
        CV.faces, CV.eyes_in = self._faces, self._eyes
        shutil.rmtree(self.d, ignore_errors=True)

    def _run(self, n_eyes):
        CV.faces = lambda fr: [(300, 1400, 450, 450)]          # "פנים" על הכתובית
        CV.eyes_in = lambda fr, box: n_eyes
        return CV.analyze(self.W, cfg=CFG6, sheet=False, write=False)

    def test_haar_hit_without_eyes_is_not_face(self):
        doc = self._run(0)
        self.assertNotIn("face", doc["counts"])
        self.assertTrue(all(c.get("face_raw") for c in doc["cues"] if "f_ok" in c))

    def test_haar_hit_with_two_eyes_is_face(self):
        doc = self._run(2)
        self.assertEqual(doc["counts"].get("face"), 3, doc["counts"])

    def test_missing_eye_classifier_keeps_old_behaviour_marked(self):
        doc = self._run(None)
        self.assertEqual(doc["counts"].get("face"), 3)
        self.assertTrue(all(c.get("face_eye_check") is None for c in doc["cues"] if "f_ok" in c))


class TestMeasuredAndFailedStayOut(unittest.TestCase):
    def test_extra_ink_components_not_in_code(self):
        cal = json.loads((TOOLS / "caption-vision-calibration.json").read_text(encoding="utf-8"))
        self.assertIn("נפל", cal["evidence"]["extra_ink_components_w6"]["verdict"])
        src = (TOOLS / "caption_vision.py").read_text(encoding="utf-8")
        self.assertNotIn("connectedComponents", src)

    def test_no_word_attribution_for_studentit_subtitle(self):
        src = (TOOLS / "thumbnail" / "cover_vision.py").read_text(encoding="utf-8")
        self.assertIn('word_scores(m1, title, "title")', src)
        self.assertNotIn('word_scores(m2', src)


class TestCoverTitleWord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import thumbnail_build as tb
        import cover_vision as V
        cls.tb, cls.V = tb, V
        cls.d = Path(tempfile.mkdtemp(prefix="cov934_"))
        cls.frame = str(cls.d / "frame.png")
        cv2.imwrite(cls.frame, _bg(3))
        cls.T, cls.S = "מה זה באמת", "להיות בעל מועדון"
        cls.cfg = dict(V.DEFAULTS, source="measured", title_word_min=0.95,
                       blocking=["reversed", "line_count", "title_not_bigger", "caption_leak",
                                 "garbled_word"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def _build(self, name, t, s):
        import contextlib
        import io
        out = str(self.d / f"{name}.png")
        with contextlib.redirect_stdout(io.StringIO()):
            self.tb.build(self.frame, t, s, out, box_color=self.V.BRANDS["rel"])
        return out

    def test_canonical_title_words_pass(self):
        r = self.V.analyze(self._build("ok", self.T, self.S), self.T, self.S, "rel", self.cfg)
        ws = r["checks"]["CV5_order"]["title_words"]
        self.assertEqual(len(ws), 3)
        self.assertNotIn("garbled_word_title", r["flags"])
        self.assertTrue(r["ok"], r["flags"])

    def test_one_scrambled_title_word_blocks(self):
        # "באמת" → "אמתב": ברמת שורה מדולל (0/33 נתפסו בכיול), ברמת מילה נתפס
        p = self._build("scr", "מה זה אמתב", self.S)
        r = self.V.analyze(p, self.T, self.S, "rel", self.cfg)
        self.assertIn("garbled_word_title", r["flags"], r["checks"]["CV5_order"])
        self.assertFalse(r["ok"])

    def test_calibration_blocks_garbled_word_only_if_measured(self):
        cal = json.loads((TOOLS / "thumbnail" / "cover-vision-calibration.json").read_text(encoding="utf-8"))
        p, ev = cal["params"], cal["evidence"]
        if "garbled_word" in p["blocking"]:
            self.assertEqual(ev["neg"]["scr_word_title"]["pos_false_rate"], 0.0)
            self.assertGreaterEqual(ev["neg"]["scr_word_title"]["caught"], 0.95)
            self.assertLess(ev["neg_scr_word_title_max"], p["title_word_min"])
            self.assertLess(p["title_word_min"], ev["pos_title_word_min"])


if __name__ == "__main__":
    unittest.main()
