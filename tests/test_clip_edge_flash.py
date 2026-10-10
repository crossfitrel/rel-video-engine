# -*- coding: utf-8 -*-
"""L104 — פלאש בגבול קליפ (הראל 23.9.26: "קפיצה מוזרה של קטע כפול", 3 סרטונים).
הזרקת-כשל: פלאש של 2 פריימים בגבול ⇒ cut_qa flash_frame; חיתוך רגיל (קפיצה אחת) ⇒ לא.
ייצוב: קליפ שנפתח ב-6 פריימים של 'לחיצה' ⇒ clip_edge_stabilize מזהה ראש לא-יציב וממלא."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
import cut_qa as CQ  # noqa: E402
import clip_edge_stabilize as CES  # noqa: E402
import tighten_finish as TF  # noqa: E402
import preflight_critic as PC  # noqa: E402


def mk(path, enable, audio_from=None):
    vf = f"drawbox=x=10:y=40:w=80:h=100:color=white:t=fill:enable='{enable}'"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=108x192:r=30:d=2"]
    if audio_from is not None:
        cmd += ["-f", "lavfi", "-i", "sine=f=300:d=2",
                "-af", f"volume=enable='lt(t,{audio_from})':volume=0", "-shortest"]
    cmd += ["-vf", vf, "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True)


class TestFlashGate(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_injected_two_frame_flash_is_flagged(self):
        v = self.d / "flash.mp4"; mk(v, "between(n,30,31)")
        self.assertTrue(CQ.is_flash(CQ.flash_probe(v, 1.0)))

    def test_plain_cut_is_not_a_flash(self):
        v = self.d / "cut.mp4"; mk(v, "gte(n,30)")
        self.assertFalse(CQ.is_flash(CQ.flash_probe(v, 1.0)))


class TestEdgeStabilize(unittest.TestCase):
    def test_unsettled_head_is_detected(self):
        d = Path(tempfile.mkdtemp()); v = d / "c.mp4"
        mk(v, "lt(n,6)", audio_from=0.5)
        r = CES.analyse(v, [{"start": 0.5, "end": 0.9, "word": "x"}])
        self.assertGreaterEqual(r["head_f"], 6)
        self.assertLessEqual(r["head_f"], int(round((0.5 + CES.HEAD_CAP) * 30)))


    def test_fill_keeps_length_and_has_no_frozen_pair(self):
        """ההאטה הרציפה: אותו מספר פריימים ואף זוג עוקב זהה בראש (הקפאה/מראה נפסלו — possible_freeze)."""
        import numpy as np
        d = Path(tempfile.mkdtemp()); src = d / "m.mp4"; out = d / "o.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=108x192:r=30:d=2",
                        "-f", "lavfi", "-i", "sine=f=300:d=2", "-shortest",
                        "-filter_complex", "color=c=white:s=30x60:r=30:d=2[b];[0:v][b]overlay=x='mod(t*90,60)':y=40[v]",
                        "-map", "[v]", "-map", "1:a",
                        "-pix_fmt", "yuv420p", str(src)], check=True)
        CES.rebuild(src, out, {"head_f": 8, "tail_f": 54, "n": 60})
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-vf", "format=gray", "-f", "rawvideo", "-"],
                           capture_output=True)
        F = np.frombuffer(p.stdout, np.uint8).reshape(-1, 192, 108).astype(float)
        self.assertEqual(len(F), 60)
        diffs = [float(np.mean(np.abs(F[j] - F[j - 1]))) for j in range(1, 20)]
        self.assertGreater(min(diffs), 0.05)


class TestTightenSnap(unittest.TestCase):          # L105
    def test_sliver_before_edl_boundary_is_snapped(self):
        """חלבון 23.9: keep הידוק שמתחיל 0.055ש לפני גבול קליפ ⇒ 2 פריימים מהקליפ הקודם."""
        ks, n = TF.snap_keeps([(7.755, 16.25), (16.501, 20.775)], [7.756, 16.556])
        self.assertEqual(ks[1][0], 16.556)
        self.assertEqual(n, 2)

    def test_far_edges_untouched(self):
        ks, n = TF.snap_keeps([(0.0, 5.0), (6.0, 9.0)], [5.5])
        self.assertEqual(ks, [(0.0, 5.0), (6.0, 9.0)])
        self.assertEqual(n, 0)


class TestP1WithSpeed(unittest.TestCase):          # L106
    def test_sped_cut_covered_by_broll_is_not_flagged(self):
        keeps = [{"start": 0.0, "end": 10.0}, {"start": 10.5, "end": 20.0}]
        plan = [{"insert_at": 8.9, "insert_end": 9.4, "id": "x"}]   # מכסה את החיתוך בציר המואץ (9.09)
        f1, f2 = [], []
        PC.check_cut_flash(f1, keeps, plan, 18.6, speed=1.1)
        PC.check_cut_flash(f2, keeps, plan, 18.6, speed=1.0)
        self.assertEqual(len(f1), 0)
        self.assertEqual(len(f2), 1)


if __name__ == "__main__":
    unittest.main()
