#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_visual_hook_qa.py — הזרקת כשל אמיתית ל-QA הפתיחה החזותית (11.9.26).

כל שער חוסם נבדק פעמיים: מקרה תקין עובר, כשל מוזרק באמת נחסם. וההזרקה הקשה
ביותר: **תקלה בדיוק בנקודת מעבר מוצהרת** — ההצהרה לא פוטרת אותה.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
TOOLS = SYSDIR / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from relvid import visual_hook as VH          # noqa: E402
from relvid import hook_render as HR          # noqa: E402

try:
    import numpy as np  # noqa: F401
    import cv2  # noqa: F401
    import visual_hook_qa as QA               # noqa: E402
    HAS = True
except Exception:
    HAS = False

from test_visual_hook_render import make_body, plan_for, run   # noqa: E402


def inject(src: Path, out: Path, vf: str):
    """קידוד מחדש עם פילטר הזרקה + אודיו stream-copy (כמו visual_base אמיתי)."""
    run([VH.ffbin(), "-nostdin", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf,
         "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "copy", str(out)])
    return out


@unittest.skipUnless(HAS, "numpy/cv2/ffmpeg חסרים")
class TestHookQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="vh_qa_"))
        cls.clean = make_body(cls.tmp / "EXPORT.mp4", dur=5.0)
        cls.fc = VH.probe_video(cls.clean)["frame_count"]
        cls.plan = plan_for(cls.fc, start=40, end=101)
        cls.rc = HR.render_v1(cls.clean, cls.plan, cls.tmp / "VISUAL_BASE.mp4")
        cls.good = cls.tmp / "VISUAL_BASE.mp4"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, video, plan=None, rc="default", **kw):
        return QA.check(self.clean, video, plan or self.plan, self.rc if rc == "default" else rc,
                        final_stage=False, **kw)

    def gate(self, rep, name):
        return next(g for g in rep["gates"] if g["gate"] == name)

    def test_correct_treatment_passes(self):
        rep = self.check(self.good)
        self.assertTrue(rep["pass"], rep["gates"])
        self.assertGreater(rep["frames_checked"], 80)

    def test_single_black_frame_inside_cue_blocks(self):
        bad = inject(self.good, self.tmp / "black.mp4",
                     "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='eq(n\\,60)'")
        rep = self.check(bad)
        self.assertFalse(rep["pass"])
        self.assertIn("VH5_introduced_flash", rep["hard_failures"])

    def test_single_white_frame_at_cue_entry_blocks(self):
        bad = inject(self.good, self.tmp / "white.mp4",
                     "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='eq(n\\,40)'")
        rep = self.check(bad)
        self.assertFalse(rep["pass"])
        self.assertTrue({"VH4_picture_matches_plan", "VH5_introduced_flash"} & set(rep["hard_failures"]))

    def test_a_b_a_one_frame_burst_blocks(self):
        # פריים 70 מוחלף בפריים ממקום אחר לגמרי בסרטון (A→B→A)
        bad = self.tmp / "aba.mp4"
        run([VH.ffbin(), "-nostdin", "-y", "-loglevel", "error", "-i", str(self.good),
             "-f", "lavfi", "-i", "smptebars=s=540x960:r=30:d=5",
             "-filter_complex", "[0:v][1:v]overlay=0:0:enable='eq(n\\,70)'[v]",
             "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p",
             "-c:a", "copy", str(bad)])
        rep = self.check(bad)
        self.assertFalse(rep["pass"], rep["gates"])
        self.assertIn("VH4_picture_matches_plan", rep["hard_failures"])
        self.assertIn("VH5_introduced_flash", rep["hard_failures"])

    def test_wrong_source_at_declared_transition_is_not_exempt(self):
        """ההצהרה על מעבר בפריים 70 לא פוטרת פריים ממקור לא נכון באותו פריים."""
        bad = inject(self.good, self.tmp / "wrong_at_cut.mp4",
                     "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='eq(n\\,70)'")
        declared = json.loads(json.dumps(self.plan))
        declared["declared_transitions"] = [{"cue_id": "cue_1", "frame": 70, "type": "cut",
                                             "from_source": "body", "to_source": "asset_x"}]
        declared["plan_digest"] = VH.digest_plan(declared)
        rc = dict(self.rc, plan_digest=declared["plan_digest"])
        # מתכון עתידי שמצהיר מעברים: עוקפים רק את בדיקת-הצורה (MVP אוסר הצהרות) כדי
        # לבדוק שהמסלול של הגליץ' לא מתחשב בהצהרה בכלל.
        with mock.patch.object(QA.VH, "validate_plan_shape", return_value=[]):
            rep = QA.check(self.clean, bad, declared, rc, final_stage=False)
        self.assertFalse(rep["pass"])
        self.assertTrue({"VH4_picture_matches_plan", "VH5_introduced_flash"} <= set(rep["hard_failures"]),
                        rep["hard_failures"])
        self.assertIn("expected_observed", {e["class"] for e in rep["events"]})

    def test_expected_low_contrast_cut_is_reported_not_failed(self):
        declared = json.loads(json.dumps(self.plan))
        declared["declared_transitions"] = [{"cue_id": "cue_1", "frame": 80, "type": "cut",
                                             "from_source": "body", "to_source": "body"}]
        declared["plan_digest"] = VH.digest_plan(declared)
        rc = dict(self.rc, plan_digest=declared["plan_digest"])
        with mock.patch.object(QA.VH, "validate_plan_shape", return_value=[]):
            rep = QA.check(self.clean, self.good, declared, rc, final_stage=False)
        self.assertTrue(rep["pass"], rep["gates"])
        self.assertIn("expected_not_detected", {e["class"] for e in rep["events"]})

    def test_inherited_darkness_is_not_punished(self):
        dark_clean = make_body(self.tmp / "EXPORT_dark.mp4", dur=5.0, black_frame=60)
        rc = HR.render_v1(dark_clean, self.plan, self.tmp / "VB_dark.mp4")
        rep = QA.check(dark_clean, self.tmp / "VB_dark.mp4", self.plan, rc, final_stage=False)
        self.assertTrue(rep["pass"], rep["gates"])

    def test_untreated_video_does_not_match_plan(self):
        """תוצר שבו הטיפול לא הוחל (או הוחל אחר) נכשל — "מוגדר ≠ עובד"."""
        rep = self.check(self.clean)
        self.assertIn("VH4_picture_matches_plan", rep["hard_failures"])

    def test_receipt_for_other_plan_is_invalid(self):
        rep = self.check(self.good, rc=dict(self.rc, plan_digest="sha256:" + "9" * 64))
        self.assertIn("VH1_receipt_valid", rep["hard_failures"])

    def test_missing_receipt_gives_no_exemption(self):
        rep = self.check(self.good, rc=None)
        self.assertIn("VH1_receipt_valid", rep["hard_failures"])

    def test_dropped_frame_blocks(self):
        short = inject(self.good, self.tmp / "short.mp4", "select='not(eq(n\\,120))',setpts=N/30/TB")
        rep = self.check(short)
        self.assertIn("VH2_frame_count", rep["hard_failures"])

    def test_audio_change_blocks(self):
        rep = self.check(self.good, rc=dict(self.rc, audio=dict(self.rc["audio"], equal=False)))
        self.assertIn("VH3_audio_preserved", rep["hard_failures"])

    def test_tampered_plan_blocks(self):
        t = json.loads(json.dumps(self.plan))
        t["cues"][0]["keyframes"][1]["rect"] = VH.crop_rect(1.02, 0.5, 0.5)
        rep = self.check(self.good, plan=t)
        self.assertIn("VH7_plan_contract", rep["hard_failures"])

    def test_approval_binding_mismatch_blocks(self):
        rep = self.check(self.good, approved_digest="sha256:" + "1" * 64)
        self.assertIn("VH8_review_binding", rep["hard_failures"])

    def test_intro_offset_maps_body_to_final(self):
        intro = self.tmp / "intro.mp4"
        run([VH.ffbin(), "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=c=red:s=540x960:r=30:d=1", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(intro)])
        lst = self.tmp / "cat.txt"
        lst.write_text(f"file '{intro}'\nfile '{self.good}'\n", encoding="utf-8")
        final = self.tmp / "with_intro.mp4"
        run([VH.ffbin(), "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-an", str(final)])
        ok = QA.check(self.clean, final, self.plan, self.rc, intro_frames=30, final_stage=True)
        self.assertTrue(ok["pass"], ok["gates"])
        wrong = QA.check(self.clean, final, self.plan, self.rc, intro_frames=0, final_stage=True)
        self.assertFalse(wrong["pass"])

    def test_caption_band_is_masked_not_blocking(self):
        cap = inject(self.good, self.tmp / "caps.mp4",
                     "drawbox=x=40:y=700:w=460:h=120:color=white:t=fill")
        rep = self.check(cap, band={"y0": 1360, "h": 300})     # ציר 1920 ⇒ 680-830 ב-960
        self.assertTrue(rep["pass"], rep["gates"])

    def test_noop_plan_checks_nothing_to_render(self):
        rep = QA.check(self.clean, self.clean, plan_for(self.fc, recipe="NO_OP"),
                       HR.render_v1(self.clean, plan_for(self.fc, recipe="NO_OP"), self.tmp / "n.mp4"),
                       final_stage=False)
        self.assertTrue(rep["pass"], rep["gates"])


@unittest.skipUnless(HAS, "numpy/cv2/ffmpeg חסרים")
class TestQaGatesLegacyG8(unittest.TestCase):
    """G8 הישן זהה כשאין תוכנית; G8b מופיע רק עם דוח."""

    def _run(self, video, extra=()):
        with tempfile.TemporaryDirectory() as t:
            rep = Path(t) / "qa.json"
            subprocess.run([sys.executable, str(TOOLS / "qa_gates.py"), "--video", str(video),
                            "--report", str(rep)] + list(extra), capture_output=True, text=True, timeout=300)
            return json.loads(rep.read_text(encoding="utf-8"))

    def test_no_plan_no_g8b(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_body(Path(t) / "v.mp4", dur=3.0)
            names = [g["gate"] for g in self._run(v)["gates"]]
            self.assertIn("G8_opening_flash", names)
            self.assertNotIn("G8b_visual_hook", names)

    def test_g8b_hard_only_on_hard_failures(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_body(Path(t) / "v.mp4", dur=3.0)
            good = Path(t) / "vq_ok.json"
            good.write_text(json.dumps({"pass": True, "hard_failures": [], "events": []}), encoding="utf-8")
            bad = Path(t) / "vq_bad.json"
            bad.write_text(json.dumps({"pass": False, "hard_failures": ["VH5_introduced_flash"],
                                       "events": []}), encoding="utf-8")
            g_ok = next(g for g in self._run(v, ["--visual-hook-qa", str(good)])["gates"]
                        if g["gate"] == "G8b_visual_hook")
            g_bad = next(g for g in self._run(v, ["--visual-hook-qa", str(bad)])["gates"]
                         if g["gate"] == "G8b_visual_hook")
            self.assertTrue(g_ok["pass"])
            self.assertFalse(g_bad["pass"])
            self.assertTrue(g_bad["hard"])
            g8 = [g for g in self._run(v)["gates"] if g["gate"] == "G8_opening_flash"][0]
            self.assertFalse(g8["hard"])            # G8 נשאר אזהרה בלבד


if __name__ == "__main__":
    unittest.main()
