# -*- coding: utf-8 -*-
"""v9.26 — שומרי הגלם (L68-L70). כל שומר עם בדיקת הזרקת-כשל: מזריקים את התקלה
שקרתה בארכיון Throwdown 2026 ומוודאים שהשומר תופס אותה."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
import intake_guard as IG  # noqa: E402


class TestStaleClipCopy(unittest.TestCase):          # L68
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.src = self.d / "src.mp4"
        self.W = self.d / "W"
        self.W.mkdir()
        self.dst = self.W / "clip_01.mp4"
        self.src.write_bytes(b"A" * 1000)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_first_copy_does_not_invalidate(self):
        (self.W / "INPUT.mp4").write_bytes(b"x")
        r = IG.sync_clip_copy(self.src, self.dst, self.W)
        self.assertTrue(r["copied"])
        self.assertEqual(r["invalidated"], [])

    def test_unchanged_clip_keeps_cache(self):
        IG.sync_clip_copy(self.src, self.dst, self.W)
        (self.W / "INPUT.mp4").write_bytes(b"x")
        r = IG.sync_clip_copy(self.src, self.dst, self.W)
        self.assertFalse(r["copied"])
        self.assertTrue((self.W / "INPUT.mp4").exists())

    def test_injected_stale_copy_is_refreshed(self):
        """הזרקת-כשל: הקליפ תוקן במקור (גודל חדש) והמטמון ישן ⇒ חייב להתרענן."""
        IG.sync_clip_copy(self.src, self.dst, self.W)
        for f in ("INPUT.mp4", "whisper_raw.json", "whisper_raw.orig.json", "ROUGH.mp4"):
            (self.W / f).write_bytes(b"old")
        self.src.write_bytes(b"B" * 1200)                 # סובב/צונזר
        r = IG.sync_clip_copy(self.src, self.dst, self.W)
        self.assertTrue(r["copied"])
        self.assertEqual(self.dst.read_bytes(), b"B" * 1200)
        for f in ("INPUT.mp4", "whisper_raw.json", "whisper_raw.orig.json", "ROUGH.mp4"):
            self.assertFalse((self.W / f).exists(), f"{f} נשאר במטמון — הבנייה תשקר")

    def test_same_size_newer_source_is_refreshed(self):
        """צנזור בנביחה יכול לשמור על אותו גודל בדיוק — mtime מכריע."""
        IG.sync_clip_copy(self.src, self.dst, self.W)
        (self.W / "INPUT.mp4").write_bytes(b"old")
        old = time.time() - 100
        os.utime(self.dst, (old, old))
        self.src.write_bytes(b"C" * 1000)
        r = IG.sync_clip_copy(self.src, self.dst, self.W)
        self.assertTrue(r["copied"])
        self.assertFalse((self.W / "INPUT.mp4").exists())


class TestOrientation(unittest.TestCase):              # L69
    PORTRAIT = {"display": "portrait", "rotation": 0}
    SIDEWAYS_META = {"display": "landscape", "rotation": 180}

    def test_upright_passes(self):
        r = IG.judge_orientation(self.PORTRAIT, {0: 3, 90: 0, 180: 1, 270: 0})
        self.assertTrue(r["pass"])
        self.assertFalse(r["sideways"])

    def test_injected_sideways_is_flagged(self):
        """הזרקת-כשל: המקרה של הארכיון — landscape+180 והפנים מופיעות רק בסיבוב."""
        r = IG.judge_orientation(self.SIDEWAYS_META, {0: 0, 90: 3, 180: 0, 270: 0})
        self.assertFalse(r["pass"])
        self.assertTrue(r["sideways"])
        self.assertEqual(r["transpose"], 1)
        r2 = IG.judge_orientation(self.PORTRAIT, {0: 0, 90: 0, 180: 0, 270: 3})
        self.assertFalse(r2["pass"])
        self.assertEqual(r2["transpose"], 2)
        # IMG_4997 (vibe) — הקליפ האמיתי מהארכיון: הפוך, נמדד 0:0 · 180:4
        r3 = IG.judge_orientation(self.PORTRAIT, {0: 0, 90: 2, 180: 4, 270: 1})
        self.assertFalse(r3["pass"])
        self.assertEqual(r3["fix_vf"], "hflip,vflip")

    def test_haar_noise_is_not_blocked(self):
        """פנים-שווא בקהל (נמדד: IMG_1759 0:1 · 180:2) לא מסומנות."""
        self.assertTrue(IG.judge_orientation(self.PORTRAIT, {0: 1, 90: 0, 180: 2, 270: 0})["pass"])
        self.assertTrue(IG.judge_orientation(self.PORTRAIT, {0: 0, 90: 0, 180: 2, 270: 0})["pass"])

    def test_real_landscape_is_not_blocked(self):
        """landscape אמיתי (פנים ישרות) לגיטימי — רקע מטושטש, לא חסימה."""
        r = IG.judge_orientation(self.SIDEWAYS_META, {0: 3, 90: 0, 180: 0, 270: 0})
        self.assertTrue(r["pass"])

    def test_no_detector_is_unmeasured_not_pass_silently(self):
        r = IG.judge_orientation(self.SIDEWAYS_META, None)
        self.assertFalse(r["measured"])
        self.assertIn("לא נמדד", r["detail"])

    def test_probe_reads_rotation(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("אין ffmpeg")
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "r.mp4")
            p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-display_rotation", "90",
                                "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=1",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)],
                               capture_output=True)
            if p.returncode != 0:
                self.skipTest("ffmpeg לא תומך ב--display_rotation")
            g = IG.probe_geometry(f)
            # ffmpeg 8 מסובב בקידוד (180×320, rotation 0); ישנים שומרים 320×180 + rotation.
            # בשני המקרים התצוגה אנכית — וזה מה שהשומר צריך.
            self.assertEqual(g["display"], "portrait")
            self.assertEqual((g["display_w"], g["display_h"]), (180, 320))

    def test_probe_math_landscape_with_rotation(self):
        """המקרה של אייפון: נשמר landscape עם displaymatrix ⇒ התצוגה אנכית."""
        from unittest import mock
        fake = json.dumps({"streams": [{"width": 1920, "height": 1080,
                                        "side_data_list": [{"rotation": -90}]}]})
        with mock.patch.object(IG.subprocess, "run",
                               return_value=mock.Mock(stdout=fake)):
            g = IG.probe_geometry("x.mov")
        self.assertEqual((g["rotation"], g["display"]), (270, "portrait"))
        fake180 = json.dumps({"streams": [{"width": 1920, "height": 1080,
                                           "side_data_list": [{"rotation": 180}]}]})
        with mock.patch.object(IG.subprocess, "run",
                               return_value=mock.Mock(stdout=fake180)):
            g = IG.probe_geometry("x.mov")
        self.assertEqual((g["rotation"], g["display"]), (180, "landscape"))


class TestCaptionDensity(unittest.TestCase):           # L70
    def test_dense_keep_is_clean(self):
        words = [{"word": "מילה", "start": t / 2} for t in range(20)]
        self.assertEqual(IG.word_density_gaps(words, [{"start": 0, "end": 10}]), [])

    def test_injected_silent_keep_is_reported(self):
        """הזרקת-כשל: turbo זרק דיבור רועש — 5ש עם מילה אחת חייבים לצוף."""
        words = [{"word": "מילה", "start": t / 2} for t in range(20)] + \
                [{"word": "רק", "start": 12.0}]
        gaps = IG.word_density_gaps(words, [{"start": 0, "end": 10}, {"start": 11, "end": 16}])
        self.assertEqual(len(gaps), 1)
        self.assertEqual((gaps[0]["start"], gaps[0]["words"]), (11.0, 1))

    def test_short_keep_not_judged(self):
        self.assertEqual(IG.word_density_gaps([], [{"start": 0, "end": 2.0}]), [])

    def test_music_montage_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            W = Path(d)
            (W / "edl.json").write_text(json.dumps({"keep_segments": [{"start": 0, "end": 10}]}))
            (W / "whisper_raw.json").write_text("[]")
            (W / "project_manifest.json").write_text(json.dumps({"topic": "מונטאז׳ מוזיקלי"}),
                                                     encoding="utf-8")
            self.assertEqual(IG.density_from_workdir(W)["gaps"], [])
            (W / "project_manifest.json").write_text("{}")
            self.assertEqual(len(IG.density_from_workdir(W)["gaps"]), 1)
            # ריל מדובר שהתיאור שלו מזכיר "מונטאז" — אסור לדלג (נמדד על ראיון הפודיומיסטים)
            (W / "project_manifest.json").write_text(json.dumps(
                {"topic": "המנצחים מדברים רגע אחרי, מונטאז של תגובות"}), encoding="utf-8")
            self.assertEqual(len(IG.density_from_workdir(W)["gaps"]), 1)


class TestWiring(unittest.TestCase):
    def test_preflight_runs_both(self):
        src = (TOOLS / "preflight_critic.py").read_text(encoding="utf-8")
        i = src.index("def run(")
        self.assertIn("check_caption_density(findings, W)", src[i:])
        self.assertIn("check_orientation_output(findings, W)", src[i:])

    def test_preflight_reports_density_gap(self):
        import preflight_critic as PC
        with tempfile.TemporaryDirectory() as d:
            W = Path(d)
            (W / "edl.json").write_text(json.dumps({"keep_segments": [{"start": 0, "end": 8}]}))
            (W / "whisper_raw.json").write_text(json.dumps([{"word": "א", "start": 1.0}]))
            f = []
            PC.check_caption_density(f, W)
            self.assertEqual(f[0]["check"], "P18_caption_density")
            self.assertEqual(f[0]["severity"], "medium")

    def test_registries(self):
        import gate_registry as GR
        import lesson_registry as LR
        for g in ("intake_guard:I1_orientation", "intake_guard:I2_stale_clip_copy",
                  "preflight:P18_caption_density", "preflight:P19_orientation"):
            self.assertIn(g, GR.GATES)
        # נמדד 2.7% חיובי-שגוי ⇒ אסור שיחסום (אין שער חוסם על סף שנכשל במדידה)
        self.assertEqual(GR.GATES["intake_guard:I1_orientation"]["enforcement"], "advisory")
        self.assertEqual(IG.ORIENT_EVIDENCE["false_pos"], 7)
        self.assertEqual(GR.GATES["preflight:P18_caption_density"]["enforcement"], "reporting")
        for k in ("L68_fixed_clip_must_invalidate_cache", "L69_sideways_raw_is_judged_by_frame",
                  "L70_turbo_vad_drops_noisy_speech"):
            self.assertIn(k, LR.LESSONS)


if __name__ == "__main__":
    unittest.main()
