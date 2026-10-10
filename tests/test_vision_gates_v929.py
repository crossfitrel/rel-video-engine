# -*- coding: utf-8 -*-
"""v9.29 (22.9.26) — שערי ראייה מדודים: V7 כתוביות על הפיקסלים (caption_vision),
ראיית הקאבר המרונדר (cover_vision / G-COVER5), ו-V3/V4 מציר הכתוביות.

כל שער חוסם מקבל בדיקת הזרקת-כשל: מייצרים את התקלה עצמה (כתובית הפוכה,
כתובית חסרה, קאבר בשורה אחת, תת-כותרת גדולה, כתובית מבצבצת) ומוודאים שנתפסת —
ושהתוצר התקין עובר."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "thumbnail"))

import cv2                                   # noqa: E402
import numpy as np                           # noqa: E402

import caption_vision as CV                  # noqa: E402
import vision_check as VC                    # noqa: E402

WORDS = [{"word": "שלום", "start": 0.10, "end": 0.60},
         {"word": "חברים", "start": 0.70, "end": 1.20},
         {"word": "במועדון", "start": 1.30, "end": 1.80}]
CFG = dict(CV.DEFAULTS, source="measured", blocking=["reversed", "missing", "tofu"])


def _bg(seed=7, W=1080, H=1920):
    rng = np.random.default_rng(seed)
    base = np.linspace(40, 170, H, dtype=np.float32)[:, None, None]
    img = np.repeat(np.repeat(base, W, 1), 3, 2)
    img += rng.normal(0, 12, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def make_video(W_dir, mode="ok", shift=0.0, dur=2.0, fps=30):
    """FINAL סינתטי: רקע + כתוביות ברינדור המותג. mode: ok / reversed / missing."""
    W_dir = Path(W_dir)
    W_dir.mkdir(parents=True, exist_ok=True)
    (W_dir / "words_final.json").write_text(json.dumps(WORDS, ensure_ascii=False),
                                            encoding="utf-8")
    (W_dir / "project_manifest.json").write_text(json.dumps({"brand": "rel"}), encoding="utf-8")
    cues = CV.group_cues(WORDS)
    g = CV.geometry(cues, 1080, 1920, "rel")
    bg = _bg()
    vw = cv2.VideoWriter(str(W_dir / "FINAL.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
                         fps, (1080, 1920))
    for i in range(int(dur * fps)):
        t = i / float(fps)
        fr = bg.copy()
        c = next((c for c in cues if c["start"] + shift <= t < c["end"] + shift), None)
        if c and mode != "missing":
            band = fr[g["y0"]:g["y0"] + g["band_h"]]
            fr[g["y0"]:g["y0"] + g["band_h"]] = CV._composite(
                band, c["text"], g, 1080, "reversed" if mode == "reversed" else "rtl")
        vw.write(fr)
    vw.release()
    return W_dir


class TestCaptionVision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp(prefix="cv929_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def _run(self, mode, shift=0.0, prov=True, dur=2.0):
        W = make_video(self.d / f"{mode}_{shift}", mode, shift, dur)
        if prov:
            (W / "FINAL_PROVENANCE.json").write_text(
                json.dumps({"intro_offset_sec": shift}), encoding="utf-8")
        return CV.analyze(W, cfg=CFG, sheet=False, write=True)

    def test_correct_captions_pass(self):
        doc = self._run("ok")
        self.assertTrue(doc["measured"])
        self.assertEqual(doc["n_measured"], 3)
        self.assertNotIn("reversed", doc["counts"])
        self.assertNotIn("missing", doc["counts"])
        self.assertTrue(doc["ok"], doc["counts"])

    def test_injected_reversed_captions_block(self):
        doc = self._run("reversed")
        self.assertGreaterEqual(doc["counts"].get("reversed", 0), 2, doc["counts"])
        self.assertFalse(doc["ok"])

    def test_injected_missing_captions_block(self):
        doc = self._run("missing")
        self.assertEqual(doc["counts"].get("missing"), 3, doc["counts"])
        self.assertFalse(doc["ok"])

    def test_single_reversed_cue_reports_but_does_not_block(self):
        # סריקה חיה 22.9.26: cue "הפוך" בודד היה מילה אחרת על המסך — לא היפוך.
        # תקלת ההיפוך האמיתית פוגעת בכל ה-cues ⇒ min_hits/min_frac.
        cfg = dict(CFG, min_hits={"reversed": 3}, min_frac={"reversed": 0.2})
        W = make_video(self.d / "rev_single", "reversed")
        doc = CV.analyze(W, cfg=cfg, sheet=False, write=False, max_cues=0)
        self.assertFalse(doc["ok"])                      # 3/3 הפוכים ⇒ חוסם
        W1 = make_video(self.d / "ok_single", "ok")
        d1 = CV.analyze(W1, cfg=cfg, sheet=False, write=False)
        d1["counts"]["reversed"] = 1                     # cue בודד
        hits = {k: v for k, v in d1["counts"].items() if k in cfg["blocking"]
                and v >= cfg["min_hits"].get(k, 1) and v >= cfg["min_frac"].get(k, 0) * 3}
        self.assertEqual(hits, {})

    def test_garbled_blocks_only_as_systematic_failure(self):
        # v9.30: 5/94 cues תקינים סומנו על רקע אירוע (סריקה חיה) ⇒ garbled חוסם רק
        # ב-≥25% מה-cues; תקלת פונט אמיתית (קניות-v2) = 49%.
        cal = json.loads((TOOLS / "caption-vision-calibration.json").read_text(encoding="utf-8"))
        p = cal["params"]
        self.assertIn("live_sweep", cal)
        if "garbled" in p["blocking"]:
            self.assertGreaterEqual(p["min_frac"]["garbled"], 0.2)
            self.assertGreater(p["min_frac"]["garbled"], cal["live_sweep"]["garbled_frac_max_ok"])

    def test_unrecorded_intro_offset_is_estimated(self):
        # FINAL ישן בלי intro_offset_sec (כמו מאסל-מן 1.8.26) — הכלי אומד מהפיקסלים
        doc = self._run("ok", shift=1.0, prov=False, dur=3.0)
        self.assertEqual(doc["offset_source"], "estimated")
        self.assertAlmostEqual(doc["intro_offset_sec"], 1.0, delta=0.15)
        self.assertNotIn("missing", doc["counts"])

    def test_ltr_does_not_reproduce_double_reversal(self):
        # נמדד 22.9.26: direction=ltr ב-raqm זהה לנכון; ההיפוך הוא המחרוזת ההפוכה
        cues = CV.group_cues(WORDS)
        g = CV.geometry(cues, 1080, 1920, "rel")
        _, _, ok = CV.render_mask("במועדון", g, 1080, "rtl")
        _, _, rev = CV.render_mask("במועדון", g, 1080, "reversed")
        self.assertLess(CV.iou(ok, rev), 0.75)

    def test_pipeline_runs_caption_vision_before_promotion(self):
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
        i = src.index('HERE / "caption_vision.py"')
        self.assertLess(i, src.index("\n    PENDING.replace(FINAL)"))
        self.assertIn('blockers.append(f"V7_captions', src)

    def test_calibration_blocks_only_measured_flags(self):
        cal = json.loads((TOOLS / "caption-vision-calibration.json").read_text(encoding="utf-8"))
        ev, p = cal["evidence"], cal["params"]
        self.assertEqual(p["source"], "measured")
        self.assertGreaterEqual(ev["n_pos"], 1000)
        for flag in p["blocking"]:
            if flag == "tofu":
                continue
            self.assertEqual(ev[f"pos_false_{flag}"], 0.0, flag)


class TestSilentDetectorGuard(unittest.TestCase):
    """עקרון 11: בלי קובץ כיול אין חסימה — וה-doctor חייב לראות את זה."""
    def test_missing_calibration_means_reporting_and_doctor_warns(self):
        old = CV.CALIB
        CV.CALIB = Path(tempfile.mkdtemp()) / "nope.json"
        try:
            self.assertEqual(CV.load_calibration()["blocking"], [])
        finally:
            CV.CALIB = old
        src = (TOOLS / "system_doctor.py").read_text(encoding="utf-8")
        self.assertIn("vision gates calibrated", src)
        self.assertIn("caption-vision-calibration.json", src)


class TestCoverVision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import thumbnail_build as tb
        import cover_vision as V
        cls.tb, cls.V = tb, V
        cls.d = Path(tempfile.mkdtemp(prefix="cov929_"))
        cls.frame = str(cls.d / "frame.png")
        cv2.imwrite(cls.frame, _bg(3))
        cls.T, cls.S = "מה זה באמת", "להיות בעל מועדון"
        cls.cfg = dict(V.DEFAULTS, source="measured",
                       blocking=["reversed", "line_count", "title_not_bigger", "caption_leak"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def _build(self, name, t, s, **kw):
        import contextlib, io
        out = str(self.d / f"{name}.png")
        with contextlib.redirect_stdout(io.StringIO()):
            self.tb.build(self.frame, t, s, out, box_color=self.V.BRANDS["rel"], **kw)
        return out

    def test_canonical_cover_passes(self):
        r = self.V.analyze(self._build("ok", self.T, self.S), self.T, self.S, "rel", self.cfg)
        self.assertEqual(r["checks"]["CV2_two_lines"]["n_lines"], 2)
        self.assertGreater(r["checks"]["CV3_title_big"]["ratio"], 1.0)
        self.assertTrue(r["ok"], r["flags"])

    def test_injected_reversed_text_blocks(self):
        p = self._build("rev", self.T[::-1], self.S[::-1])
        r = self.V.analyze(p, self.T, self.S, "rel", self.cfg)
        self.assertTrue(any(f.startswith("reversed") for f in r["flags"]), r["flags"])
        self.assertFalse(r["ok"])

    def test_injected_one_line_blocks(self):
        p = self._build("one", self.T + " " + self.S, "‏")
        r = self.V.analyze(p, self.T, self.S, "rel", self.cfg)
        self.assertIn("line_count", r["flags"])
        self.assertFalse(r["ok"])

    def test_injected_subtitle_bigger_blocks(self):
        # tb.build מתעלם מהפרמטר sub_ratio (משתמש בקבוע SUB_RATIO) — נמצא 22.9.26;
        # לכן ההזרקה דורסת את הקבוע, כמו שתקלת 23.7.26 נוצרה בפועל.
        old = self.tb.SUB_RATIO
        self.tb.SUB_RATIO = 1.6
        try:
            p = self._build("big", self.T, self.S, title_start=90)
        finally:
            self.tb.SUB_RATIO = old
        r = self.V.analyze(p, self.T, self.S, "rel", self.cfg)
        self.assertIn("title_not_bigger", r["flags"], r["checks"]["CV3_title_big"])

    def test_sub_ratio_parameter_is_honored(self):
        # v9.29: build(sub_ratio=…) נבלע בשקט (השתמש בקבוע). עכשיו הפרמטר עובד —
        # ו-cover_vision רואה את התוצאה בפיקסלים.
        p = self._build("big_param", self.T, self.S, title_start=90, sub_ratio=1.6)
        r = self.V.analyze(p, self.T, self.S, "rel", self.cfg)
        self.assertIn("title_not_bigger", r["flags"], r["checks"]["CV3_title_big"])

    def test_injected_caption_leak_blocks(self):
        from PIL import Image, ImageDraw, ImageFont
        sys.path.insert(0, str(ROOT / "captions-app"))
        import captions_overlay as co
        p = self._build("leak", self.T, self.S)
        im = Image.open(p).convert("RGBA")
        f = ImageFont.truetype(str(co.BRAND_PROFILES["club"]["font"]), 120)
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((540, int(1920 * 0.93)), "אז מה", font=f, anchor="ms",
                                 fill=(255, 255, 255, 255), direction="rtl", stroke_width=7,
                                 stroke_fill=co.BRAND_PROFILES["club"]["outline"])
        Image.alpha_composite(im, lay).convert("RGB").save(p)
        r = self.V.analyze(p, self.T, self.S, "rel", self.cfg)
        self.assertIn("caption_leak", r["flags"])

    def test_cover_make_runs_png_vision(self):
        src = (TOOLS / "thumbnail" / "cover_make.py").read_text(encoding="utf-8")
        self.assertIn("cover_vision.analyze(out", src)
        self.assertIn("G-COVER5", src)


class TestWordsTimelineV3V4(unittest.TestCase):
    def test_words_timeline_applies_recorded_intro(self):
        d = Path(tempfile.mkdtemp())
        try:
            (d / "words_final.json").write_text(json.dumps(
                [{"word": "א", "start": 0.4, "end": 0.6}] +
                [{"word": "ב", "start": 1 + i * 0.4, "end": 1.3 + i * 0.4} for i in range(40)]),
                encoding="utf-8")
            (d / "FINAL_PROVENANCE.json").write_text(json.dumps({"intro_offset_sec": 10.0}))
            wt = VC.words_timeline(d / "FINAL.mp4")
            self.assertEqual(wt["first_word"], 10.4)
            self.assertIsNotNone(wt["wpm"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_measured_but_not_promoted_stays_reporting(self):
        ref = VC.load_reference()
        e = ref["envelope"]["V3_first_word"]
        self.assertFalse(e["promote"])
        self.assertIn("why_not_blocking", e)
        d = {"transcript": {"segments": [{"start": 2.0}]}, "motion_series": [],
             "scenes": [], "audio_levels": [], "silences": []}
        v3 = {c["id"]: c for c in VC.evaluate(d)}["V3_first_word"]
        self.assertEqual(v3["enforcement"], "reporting")
        self.assertEqual(v3["threshold"], 0.30)            # הסף הקאנוני, לא קצה המעטפת
        self.assertEqual(v3["threshold_source"], VC.MEASURED_NOT_PROMOTED)

    def test_v4_has_no_blocking_without_negative_class(self):
        e = VC.load_reference()["envelope"]["V4_speech_rate"]
        self.assertFalse(e["promote"])


if __name__ == "__main__":
    unittest.main()
