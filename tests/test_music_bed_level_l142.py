# -*- coding: utf-8 -*-
"""L142 — יישור מאקרו של המצע לפני המדידה (מוזג מ-L137 של המק, v9.50, 23.10.26).
הראל 23.10.26 על פינה-אנטומית-פרק2 (53.5ש): "המוזיקה רועשת מידיי. זה חוזר על עצמו כל הזמן".
השער האינטגרלי עבר 24.2 LU בזמן שהטראק "נבנה" ‎-60→‎-49 LUFS-M והסוף (CTA) היה הרגע הכי רועש.
הרצפה המקומית של L138 (3ש, min_local_gap_lu) נשארת מקור האמת לסף; כאן נבדק שהמצע עצמו
מגיע למדידה ולמיקס כבר בלי ה"בנייה", ושה-nudge/המעטפת עובדים על המצע המיושר.
(הועבר מ-tests/test_music_bed_envelope_l137.py של המק.)"""
import json, os, subprocess, sys, tempfile, types, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(HERE))
import audio_mix as AM  # noqa: E402

POL = json.loads((HERE / "music-level-policy.json").read_text(encoding="utf-8"))


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def ns(**kw):
    base = dict(music_lufs=-46.0, speech_lufs=None, speech_start=None, gap_speech=POL["speech_gap_lu"],
                gap_intro=POL["intro_gap_lu"], min_gap=POL["min_speech_gap_lu"], min_intro_gap=POL["min_intro_gap_lu"],
                gap_tolerance=0.6, local_gap=POL["min_local_gap_lu"], final_lufs=-14.0, music_offset=None,
                mute=None, tp_limit=0.75, bed_level=False, local_floor=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


class TestPolicy(unittest.TestCase):
    def test_one_source_of_truth_for_local_floor(self):
        # הסף המקומי = L138 (3ש). רצפת momentary של L137 לא נכנסה (לא הוכחה במדידה) — ראה bed_level._doc
        self.assertIsNotNone(POL.get("min_local_gap_lu"))
        self.assertTrue(POL["bed_level"]["enabled"])
        self.assertIsNone(POL["bed_level"].get("local_floor_momentary_lu"))

    def test_mac_legacy_key_kept(self):
        # המק (v9.50) קורא local_floor_lu ומעביר --local-floor; המפתח נשאר עד שהמק מסונכרן
        self.assertIn("local_floor_lu", POL)

    def test_pipeline_passes_bed_level(self):
        src = (HERE / "local_finish_pipeline.py").read_text(encoding="utf-8")
        # בריפו: --bed-level מהמדיניות. במק (צנרת v9.50 עד סנכרון): --local-floor ממופה ל-bed_level
        self.assertTrue('"--bed-level"' in src or '"--local-floor"' in src)

    def test_legacy_local_floor_maps_to_bed_level_and_l138(self):
        a = ns(local_floor=18.0, local_gap=None)
        AM._resolve_legacy_local_floor(a)
        self.assertTrue(a.bed_level)
        self.assertEqual(a.local_gap, POL["min_local_gap_lu"])


@unittest.skipUnless(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0, "ffmpeg")
class TestBedLevel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        cls.video = os.path.join(cls.d, "talk.mp4")
        cls.music = os.path.join(cls.d, "ramp.wav")
        # "דיבור" 24ש: 18ש רגילים, 6ש אחרונים דובר שקט ב-‎-12dB (ה-CTA)
        _ff("-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.3:d=24",
            "-f", "lavfi", "-i", "color=black:s=320x568:d=24",
            "-af", "volume='if(lt(mod(t,0.5),0.4),1,0)*if(gte(t,18),0.25,1)':eval=frame",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", cls.video)
        # טראק "נבנה": עולה 12dB לאורך 24ש (המקרה של פינה-אנטומית-פרק2)
        _ff("-f", "lavfi", "-i", "sine=f=220:d=24", "-f", "lavfi", "-i", "sine=f=1760:d=24",
            "-filter_complex", "amix=inputs=2,volume='pow(10,(-12+12*t/24)/20)':eval=frame", cls.music)

    def _mix(self, **kw):
        out = os.path.join(self.d, f"out_{len(os.listdir(self.d))}.mp4")
        rc = AM.cmd_mix(ns(video=self.video, music=self.music, out=out, **kw))
        rec = json.loads(Path(out + ".musicgap.json").read_text(encoding="utf-8"))
        return rc, rec, out

    def test_build_is_flattened_before_measurement(self):
        rc, rec, out = self._mix(bed_level=True)
        self.assertEqual(rc, 0)
        bl = rec["bed_level"]
        self.assertEqual(bl["status"], "applied")
        b0, b1 = bl["S_first10_last10_before"], bl["S_first10_last10_after"]
        self.assertGreater(b0[1] - b0[0], 6.0)                 # הטראק באמת נבנה
        self.assertLess(abs(b1[1] - b1[0]), 3.0)               # אחרי היישור — אין "סוף רועש"
        spread = lambda p: p[1] - p[0]
        self.assertLess(spread(bl["S_p10_p90_after"]), spread(bl["S_p10_p90_before"]) - 4.0)
        # השער האינטגרלי והרצפה המקומית של L138 רצים על המצע המיושר ועוברים
        self.assertGreaterEqual(rec["measured"]["gap_lu"], POL["min_speech_gap_lu"] - 0.6)
        self.assertGreaterEqual(rec["local"]["worst_local_gap_after"] if rec["local"].get("applied")
                                else rec["local"]["worst_local_gap"], POL["min_local_gap_lu"] - 1.5)
        left = [f for f in os.listdir(self.d) if f.startswith(os.path.basename(out)) and
                (".bed_" in f or ".music_from_" in f)]
        self.assertEqual(left, [])

    def test_leveling_reduces_envelope_work(self):
        # בלי יישור, המעטפת של L138 נאלצת להנמיך עמוק בסוף; עם יישור — פחות (שכבה אחת עושה את העבודה)
        _, rec0, _ = self._mix(bed_level=False)
        _, rec1, _ = self._mix(bed_level=True)
        cut0 = rec0["local"].get("max_cut_db", 0.0) if rec0["local"] else 0.0
        cut1 = rec1["local"].get("max_cut_db", 0.0) if rec1["local"] else 0.0
        self.assertLess(cut1, cut0)

    def test_leveling_failure_is_not_silent(self):
        orig = AM.macro_level_bed
        AM.macro_level_bed = lambda *a, **k: (None, {"status": "not_measured", "why": "fault injection"})
        try:
            rc = AM.cmd_mix(ns(video=self.video, music=self.music, out=os.path.join(self.d, "fail.mp4"), bed_level=True))
        finally:
            AM.macro_level_bed = orig
        self.assertEqual(rc, 3)

    def test_nudge_rerun_does_not_relevel(self):
        calls = []
        orig = AM.macro_level_bed
        def spy(*a, **k):
            calls.append(1)
            return orig(*a, **k)
        AM.macro_level_bed = spy
        orig_gap = AM.measure_bed_gap
        first = {"x": True}
        def fake_gap(*a, **k):                     # סבב ראשון "נמדד" קרוב מדי ⇒ nudge ⇒ ריצה שנייה
            g = orig_gap(*a, **k)
            if first["x"] and g:
                first["x"] = False
                g = dict(g, gap_lu=POL["min_speech_gap_lu"] - 2.0)
            return g
        AM.measure_bed_gap = fake_gap
        try:
            rc, rec, _ = self._mix(bed_level=True)
        finally:
            AM.macro_level_bed = orig
            AM.measure_bed_gap = orig_gap
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(rec["bed_level"]["status"], "applied")


if __name__ == "__main__":
    unittest.main()
