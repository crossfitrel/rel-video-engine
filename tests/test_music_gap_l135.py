# -*- coding: utf-8 -*-
"""L135 — מפלס מוזיקה יחסי לדיבור + רצפה + שער מדוד (הראל 11.10.26: "כל פעם אנחנו נופלים עם המוזיקה")."""
import json, os, subprocess, sys, tempfile, types, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(HERE))
import audio_mix as AM  # noqa: E402

POL = json.loads((HERE / "music-level-policy.json").read_text(encoding="utf-8"))


def ns(**kw):
    base = dict(music_lufs=-46.0, speech_lufs=None, speech_start=None, gap_speech=None, gap_intro=None,
                min_gap=None, min_intro_gap=None, gap_tolerance=0.6)
    base.update(kw)
    return types.SimpleNamespace(**base)


class TestLevels(unittest.TestCase):
    def test_policy_floor_well_below_rejected_anchor(self):
        # L138 — E-Myth (20.9) נפסל אחרי פרסום 14.10.26: הרצפה לפחות 4 LU שקטה ממנו,
        # ולא בתוך טווח התלונות. ברירת המחדל לא נמוכה מהרצפה.
        self.assertGreaterEqual(POL["min_speech_gap_lu"], POL["anchor"]["gap_lu"] + 4.0)
        self.assertGreater(POL["min_speech_gap_lu"], max(POL["complaints_measured_gap_lu"]))
        self.assertGreaterEqual(POL["speech_gap_lu"], POL["min_speech_gap_lu"])
        self.assertIsNotNone(POL.get("min_local_gap_lu"))

    def test_relative_level_follows_dialog_not_absolute(self):
        for dialog in (-12.0, -23.0, -37.0):
            a = ns(gap_speech=22.0)
            g = AM.apply_dialog_relative_levels(a, dialog, D=30)
            self.assertAlmostEqual(g["speech_gap"], 22.0, places=1)
            self.assertAlmostEqual(a.music_lufs, dialog - 22.0, places=1)

    def test_absolute_manual_pref_is_clamped_by_floor(self):
        # מקרה TD26: דיאלוג ‎-23.2, מוזיקה ‎-43.1 (gap 19.9) → נחתך ל-21
        a = ns(music_lufs=-43.1, min_gap=21.0)
        g = AM.apply_dialog_relative_levels(a, -23.2, D=30)
        self.assertTrue(g["clamped"])
        self.assertAlmostEqual(a.music_lufs, -44.2, places=1)

    def test_intro_and_speech_levels(self):
        a = ns(speech_start=2.0, gap_speech=22.0, gap_intro=14.0, min_gap=21.0, min_intro_gap=13.0)
        AM.apply_dialog_relative_levels(a, -20.0, D=30)
        self.assertAlmostEqual(a.speech_lufs, -42.0)
        self.assertAlmostEqual(a.music_lufs, -34.0)

    def test_no_policy_args_is_noop(self):
        a = ns()
        self.assertIsNone(AM.apply_dialog_relative_levels(a, -20.0, D=30))
        self.assertEqual(a.music_lufs, -46.0)


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


@unittest.skipUnless(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0, "ffmpeg")
class TestMeasuredGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        cls.video = os.path.join(cls.d, "talk.mp4")
        cls.music = os.path.join(cls.d, "bed.wav")
        # "דיבור": רעש ורוד בפולסים (0.35ש דיבור / 0.15ש שקט) + וידאו שחור
        _ff("-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.3:d=12",
            "-f", "lavfi", "-i", "color=black:s=320x568:d=12",
            "-af", "volume='if(lt(mod(t,0.5),0.35),1,0)':eval=frame",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", cls.video)
        _ff("-f", "lavfi", "-i", "sine=f=220:d=20", "-f", "lavfi", "-i", "sine=f=1760:d=20",
            "-filter_complex", "amix=inputs=2", cls.music)

    def _mix(self, **kw):
        out = os.path.join(self.d, f"out_{len(os.listdir(self.d))}.mp4")
        a = ns(video=self.video, music=self.music, out=out, final_lufs=-14.0, music_offset=None,
               mute=None, tp_limit=0.75, **kw)
        rc = AM.cmd_mix(a)
        rec = json.loads(Path(out + ".musicgap.json").read_text(encoding="utf-8"))
        return rc, rec

    def test_default_policy_lands_on_target(self):
        rc, rec = self._mix(music_lufs=-46.0, gap_speech=22.0, gap_intro=14.0, min_gap=21.0, min_intro_gap=13.0)
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(rec["measured"]["gap_lu"], 21.0 - 0.6)

    def test_loud_manual_pref_is_clamped_and_passes(self):
        rc, rec = self._mix(music_lufs=-25.0, min_gap=21.0)
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(rec["measured"]["gap_lu"], 21.0 - 0.6)

    def test_closed_loop_retry_lands_above_floor(self):
        """L137 — מבקשים בדיוק את הרצפה אבל עם 'הטיה' מלאכותית של 1.5LU חזק מדי:
        הסבב הראשון נכשל במדידה, הסבב השני מתקן לפי המדידה ועובר."""
        orig = AM.apply_dialog_relative_levels
        def biased(args, dialog_i, D=None):
            r = orig(args, dialog_i, D)
            if r and not getattr(args, "_gap_nudge", 0):
                args.music_lufs += 1.5
            return r
        AM.apply_dialog_relative_levels = biased
        try:
            rc, rec = self._mix(music_lufs=-25.0, min_gap=21.0, gap_tolerance=0.6)
        finally:
            AM.apply_dialog_relative_levels = orig
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(rec["measured"]["gap_lu"], 21.0 - 0.6)

    def test_gate_catches_loud_bed(self):
        a = ns(music=self.music, music_lufs=-25.0)
        m = AM.measure_lufs(self.music)
        v = AM.measure_lufs(self.video)
        g = AM.measure_bed_gap(a, m, 12.0, v["I"])
        self.assertLess(g["gap_lu"], 21.0)


if __name__ == "__main__":
    unittest.main()
