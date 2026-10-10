# -*- coding: utf-8 -*-
"""v9.47 — L128 (פרופיל מוזיקה קליל v2 + offset שמתחיל בקצב) · L129 (צנזור קללות בכתוביות).

הזרקת כשל: הבדיקות נכשלות אם funk/afrobeat/hiphop חוזרים לפרופיל הקליל, אם ה-offset לא מדלג
על פתיח שקט, או אם הצנזור כותב את המילה המלאה / לא מסתיר כלום."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import audio_mix as am  # noqa: E402
import local_finish_pipeline as lfp  # noqa: E402

FF = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


class LightMusic(unittest.TestCase):
    def test_light_pool_excludes_funk_afro_hiphop(self):
        cat = json.loads((HERE.parent / "tools" / "music-catalog.json").read_text(encoding="utf-8"))["tracks"]
        bad = {"funk", "afrobeat", "hiphop"}
        picks = set()
        _orig = lfp.ROTATION_STATE
        lfp.ROTATION_STATE = Path(tempfile.mkdtemp()) / "rot.json"   # לא לשרוף את הרוטציה האמיתית
        try:
            for _ in range(12):
                t = lfp.pick_music("value", "auto", tone="חם, אותנטי, אנרגטי", light=True)
                picks.add(t.name)
        finally:
            lfp.ROTATION_STATE = _orig
        self.assertTrue(picks)
        for n in picks:
            self.assertNotIn((cat.get(n) or {}).get("genre"), bad, n)
            self.assertFalse(set((cat.get(n) or {}).get("moods") or []) & {"aggressive", "dark", "epic"}, n)

    def test_start_offset_skips_soft_intro(self):
        d = Path(tempfile.mkdtemp())
        f = d / "t.wav"
        # 10ש פתיח שקט (‎-40dB) ואז 40ש "קצב" חזק
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=10",
                        "-f", "lavfi", "-i", "sine=f=220:d=40",
                        "-filter_complex", "[0]volume=0.01[a];[1]volume=0.5[b];[a][b]concat=n=2:v=0:a=1",
                        str(f)], check=True)
        off = am.music_start_offset(str(f), need=20)
        self.assertIsNotNone(off)
        self.assertGreaterEqual(off, 9.5)
        self.assertLessEqual(off, 10.5)
        # need גדול מהשארית → ה-offset יורד כדי שיישאר מספיק טראק
        off2 = am.music_start_offset(str(f), need=45)
        self.assertLessEqual(off2, 5.01)
        shutil.rmtree(d, ignore_errors=True)


class CaptionCensor(unittest.TestCase):
    def test_censor_mask_half_word(self):
        self.assertEqual(lfp.censor_mask("שרמוטה"), "שרמ#$%")
        self.assertEqual(lfp.censor_mask("זין"), "זי#$%")
        d = Path(tempfile.mkdtemp())
        p = d / "w.json"
        p.write_text(json.dumps([{"word": "יא", "start": 0, "end": 0.2},
                                 {"word": "שרמוטה", "start": 0.2, "end": 0.6},
                                 {"word": "וזונה", "start": 0.6, "end": 0.9},
                                 {"word": "כוס", "start": 1.0, "end": 1.2}], ensure_ascii=False), encoding="utf-8")
        out, n = lfp.censor_caption_words(p, d, {})
        self.assertEqual(n, 2)
        ws = json.loads(Path(out).read_text(encoding="utf-8"))
        self.assertEqual([w["word"] for w in ws], ["יא", "שרמ#$%", "וזו#$%", "כוס"])
        # 'כוס' דו-משמעית — רק כשהמניפסט מבקש
        out, n = lfp.censor_caption_words(p, d, {"finish_prefs": {"captions": {"censor": ["כוס"]}}})
        self.assertEqual(n, 3)
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
