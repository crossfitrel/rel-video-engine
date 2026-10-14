# -*- coding: utf-8 -*-
"""L138 — רצפה מקומית: בכל חלון 3ש עם דיבור המוזיקה לפחות local_gap מתחת לקול של אותו חלון.
מקרה המקור: E-Myth (14.10.26) — gap אינטגרלי 20.3, אבל ב-CTA השקט בסוף ‎~9.6 dB בלבד."""
import json, os, subprocess, sys, tempfile, types, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(HERE))
import audio_mix as AM  # noqa: E402


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def ns(**kw):
    base = dict(music_lufs=-46.0, speech_lufs=None, speech_start=None, gap_speech=None, gap_intro=None,
                min_gap=None, min_intro_gap=None, gap_tolerance=0.6, local_gap=None,
                final_lufs=-14.0, music_offset=None, mute=None, tp_limit=0.75)
    base.update(kw)
    return types.SimpleNamespace(**base)


@unittest.skipUnless(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0, "ffmpeg")
class TestLocalFloor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        cls.video = os.path.join(cls.d, "talk_quiet_end.mp4")
        cls.music = os.path.join(cls.d, "bed.wav")
        # "דיבור" 20ש: 14ש רגילים ואז 6ש שקטים ב-14dB (ה-CTA של E-Myth)
        _ff("-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.3:d=20",
            "-f", "lavfi", "-i", "color=black:s=320x568:d=20",
            "-af", "volume='if(lt(mod(t,0.5),0.35),1,0)*if(lt(t,14),1,0.2)':eval=frame",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", cls.video)
        _ff("-f", "lavfi", "-i", "sine=f=220:d=30", "-f", "lavfi", "-i", "sine=f=1760:d=30",
            "-filter_complex", "amix=inputs=2", cls.music)

    def _mix(self, **kw):
        out = os.path.join(self.d, f"out_{len(os.listdir(self.d))}.mp4")
        rc = AM.cmd_mix(ns(video=self.video, music=self.music, out=out, **kw))
        rec = json.loads(Path(out + ".musicgap.json").read_text(encoding="utf-8"))
        return rc, rec, out

    def test_quiet_tail_is_caught_and_fixed(self):
        rc, rec, out = self._mix(gap_speech=20.0, min_gap=19.0, local_gap=20.0)
        self.assertEqual(rc, 0)
        loc = rec["local"]
        self.assertTrue(loc["applied"])
        self.assertLess(loc["worst_local_gap_before"], 14.0)          # בלי התיקון: הזנב השקט חשוף
        self.assertGreaterEqual(loc["worst_local_gap_after"], 20.0 - 1.5)
        self.assertGreater(loc["max_cut_db"], 4.0)
        self.assertFalse(any(f.endswith(".relenv.cmd") for f in os.listdir(tempfile.gettempdir())
                             if f.startswith(os.path.basename(out))))

    def test_no_local_gap_keeps_old_behaviour(self):
        rc, rec, _ = self._mix(gap_speech=20.0, min_gap=19.0)
        self.assertEqual(rc, 0)
        self.assertIsNone(rec["local"])

    def test_only_lowers_never_raises(self):
        # מצע ממילא שקט מאוד → אין התערבות
        rc, rec, _ = self._mix(gap_speech=40.0, min_gap=19.0, local_gap=20.0)
        self.assertEqual(rc, 0)
        self.assertFalse(rec["local"]["applied"])

    def test_intro_step_and_mute_share_one_chain(self):
        # פתיח + מדרגת דיבור + השתקת hook_fx + מעטפת — כולם באותה שרשרת (bed_filter), גם בשער המדוד
        rc, rec, _ = self._mix(speech_start=1.0, gap_speech=20.0, gap_intro=12.0, min_gap=19.0,
                               min_intro_gap=11.0, local_gap=20.0, mute="0.4-0.8")
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(rec["measured"]["gap_lu"], 19.0 - 0.6)
        self.assertTrue(rec["local"]["applied"])

if __name__ == "__main__":
    unittest.main()
