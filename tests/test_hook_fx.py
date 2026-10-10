# -*- coding: utf-8 -*-
"""v9.46 — ארגז העריכה של ההוק (tools/hook_fx.py) + P22 לשכבת העריכה + audio_mix --mute.

הזרקת כשל: כל בדיקה כאן נכשלת אם השער מוחלש — פריז על דיבור שעובר, 3 תנועות שעוברות, וויפ בלי
חיתוך שעובר, זום שמזיז טלסטרייטור, רינדור שמזיז פריימים אחרי החלון (L127), רינדור שבור עם
יותר מצליל אחד (באג אינדקס 8.10.26), ו-P22 שמקבל תוכנית עריכה שלא הוחלה בתוצר."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import hook_fx as hf  # noqa: E402
import hook_plan as hp  # noqa: E402
import audio_mix as am  # noqa: E402

FF = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def W_(words=(), plan=None, mp=None):
    W = Path(tempfile.mkdtemp())
    (W / "words_final.json").write_text(json.dumps(
        [{"word": w, "start": s, "end": e} for w, s, e in words], ensure_ascii=False), encoding="utf-8")
    (W / "project_manifest.json").write_text(json.dumps(
        {"name": "בדיקה", "created_at": "2026-10-09T10:00:00", "dept": "קרוספיט אריאל", "content_type": "value"},
        ensure_ascii=False), encoding="utf-8")
    if plan is not None:
        (W / "HOOK_PLAN.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    if mp is not None:
        (W / "motion_plan.json").write_text(json.dumps(mp, ensure_ascii=False), encoding="utf-8")
    return W


class GatesTest(unittest.TestCase):
    def test_freeze_on_speech_blocks(self):
        mv = hf.norm_moves({"moves": [{"type": "impact_freeze", "at": 1.0, "hold": 0.3}]})
        g = hf.gate_speech(mv, [{"word": "מקום", "start": 0.9, "end": 1.2}])
        self.assertFalse(g["ok"])
        g2 = hf.gate_speech(mv, [{"word": "מקום", "start": 1.5, "end": 1.8}])
        self.assertTrue(g2["ok"])

    def test_dosage_max_two(self):
        mv = hf.norm_moves({"moves": [{"type": "shake", "at": 0.2}, {"type": "shake", "at": 1.0},
                                      {"type": "shake", "at": 2.0}]})
        self.assertFalse(hf.gate_dosage(mv)["ok"])
        self.assertTrue(hf.gate_dosage(mv[:2])["ok"])

    def test_window_and_bounds(self):
        self.assertFalse(hf.gate_window(hf.norm_moves({"moves": [{"type": "shake", "at": 3.9, "dur": 0.4}]}))["ok"])
        big = hf.norm_moves({"moves": [{"type": "snap_zoom", "at": 0.5, "scale": 1.6}]})
        self.assertFalse(hf.gate_ranges(big)["ok"])
        self.assertEqual(hf.gate_ranges(big)["level"], "reporting", "סף לא מדוד לא חוסם")
        self.assertFalse(hf.gate_bounds(hf.norm_moves({"moves": [{"type": "spin", "at": 0.5}]}))["ok"])
        self.assertFalse(hf.gate_bounds(hf.norm_moves({"moves": [{"type": "speed_ramp", "from": 0, "to": 2}]}))["ok"])

    def test_transition_needs_cut(self):
        mv = hf.norm_moves({"moves": [{"type": "whip", "at": 1.0}]})
        self.assertFalse(hf.gate_cuts(mv, [])["ok"])
        self.assertTrue(hf.gate_cuts(mv, [1.08])["ok"])

    def test_conflict_with_spatial_mg(self):
        W = W_(mp={"events": [{"type": "telestrator", "start": 0.8, "end": 2.0}]})
        zoom = hf.norm_moves({"moves": [{"type": "snap_zoom", "at": 1.0}]})
        self.assertFalse(hf.gate_conflict(zoom, W, False)["ok"])
        still = hf.norm_moves({"moves": [{"type": "impact_freeze", "at": 1.0, "hold": 0.5, "punch": 1.0}]})
        self.assertTrue(hf.gate_conflict(still, W, False)["ok"], "פריז בלי פאנץ' מותר מתחת לטלסטרייטור")
        self.assertFalse(hf.gate_conflict(zoom, None, True)["ok"], "punch-in של Visual Hook + זום = מגבר כפול")

    def test_ramp_preserves_timeline(self):
        m = hf.norm_moves({"moves": [{"type": "speed_ramp", "from": 0.5, "to": 2.5, "impact": 1.2}]})[0]
        mp, disp = hf.ramp_map(m, 30.0)
        self.assertAlmostEqual(mp[15] / 30.0, 0.5, places=2)
        self.assertGreater(disp, 1.2, "השיא מוצג מאוחר יותר בגלל ההאטה")

    def test_parse_mute(self):
        self.assertEqual(am.parse_mute("0-0.76;2.1-2.4;x", 2.3), [[0.0, 0.76], [2.1, 2.3]])
        self.assertEqual(am.parse_mute(None), [])


@unittest.skipUnless(Path(FF).exists() and hf.sfx_catalog(), "צריך ffmpeg וקטלוג צלילים")
class RenderTest(unittest.TestCase):
    """רינדור אמיתי על וידאו סינתטי 360×640: ציר קשיח, צבע, ושני צלילים."""

    @classmethod
    def setUpClass(cls):
        cls.D = Path(tempfile.mkdtemp())
        cls.src = cls.D / "src.mp4"
        subprocess.run([FF, "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=360x640:rate=30:duration=4", "-f", "lavfi", "-i",
                        "sine=frequency=330:duration=4:sample_rate=48000", "-c:v", "libx264", "-crf", "16",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.src)], check=True)

    def test_snap_zoom_two_sfx(self):
        out = self.D / "out.mp4"
        edit = {"recipe": "push_tension", "moves": [{"type": "snap_zoom", "at": 0.5, "scale": 1.15, "focus": [0.5, 0.5]}],
                "sfx": [{"at": 0.5, "kind": "impact"}, {"at": 1.4, "kind": "swish"}], "music_drop": [[0.0, 0.5]]}
        rep = hf.render(self.src, out, edit, W=None, words=[])
        self.assertTrue(rep.get("ok"), json.dumps([g for g in rep.get("gates", []) if not g["ok"]], ensure_ascii=False)
                        + str(rep.get("error"))[:300])
        names = {g["gate"]: g for g in rep["gates"]}
        self.assertTrue(names["HFX8_duration"]["ok"])
        self.assertTrue(names["HFX8b_frame_align"]["ok"], "פריימים אחרי החלון זזו (L127)")
        self.assertTrue(names["HFX9_color"]["ok"])
        self.assertEqual(len(rep["sfx"]), 2, "שני צלילים — רגרסיית אינדקס הקלט")
        self.assertEqual(rep["music_mute"], [[0.0, 0.5]])
        self.assertEqual(hf.probe(out)["dur"].__round__(1), hf.probe(self.src)["dur"].__round__(1))

    def test_sound_only_copies_video(self):
        out = self.D / "snd.mp4"
        rep = hf.render(self.src, out, {"sfx": [{"at": 1.0, "kind": "impact"}]}, W=None, words=[])
        self.assertTrue(rep.get("ok"), str(rep.get("error"))[:300])
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "h264")

    def test_speech_blocks_render(self):
        out = self.D / "blk.mp4"
        rep = hf.render(self.src, out, {"moves": [{"type": "impact_freeze", "at": 1.0, "hold": 0.3}]}, W=None,
                        words=[{"word": "שלום", "start": 0.9, "end": 1.4}])
        self.assertFalse(rep.get("ok"))
        self.assertFalse(out.exists())


class P22EditTest(unittest.TestCase):
    BASE = {"technique": "real_reaction", "anchor_type": "person_reaction", "t0": "x", "t1": "y", "t2": "z"}

    def _f(self, plan, report=None):
        W = W_(plan=plan)
        if report is not None:
            (W / "HOOK_FX_REPORT.json").write_text(json.dumps(report), encoding="utf-8")
            (W / "HOOK_FX_SHEET.jpg").write_bytes(b"x")
        return [x for x in hp.evaluate(W, measure_video=False) if "עריכ" in x["detail"] or "edit" in x["detail"]]

    def test_no_edit_block_is_medium(self):
        fs = self._f(dict(self.BASE))
        self.assertTrue(any(x["severity"] == hp.MED for x in fs))

    def test_declared_not_applied_is_high(self):
        ed = {"recipe": "reaction_punch", "moves": [{"type": "snap_zoom", "at": 0.7}]}
        fs = self._f(dict(self.BASE, edit=ed))
        self.assertTrue(any(x["severity"] == hp.HIGH for x in fs))
        ok = self._f(dict(self.BASE, edit=ed), {"ok": True, "edit_digest": hf.edit_digest(ed), "sheet": "HOOK_FX_SHEET.jpg"})
        self.assertFalse(any(x["severity"] == hp.HIGH for x in ok))
        stale = self._f(dict(self.BASE, edit=ed), {"ok": True, "edit_digest": "000000000000"})
        self.assertTrue(any(x["severity"] == hp.HIGH for x in stale), "דוח של תוכנית אחרת לא מתקבל")

    def test_none_with_why_is_clean(self):
        fs = self._f(dict(self.BASE, edit={"recipe": "none", "why": "אין רגע תגובה ברמה גבוהה"}))
        self.assertEqual(fs, [])

    def test_harel_reject_verdict_blocks_recipe(self):
        W = W_(plan=dict(self.BASE, edit={"recipe": "reaction_punch", "moves": [{"type": "snap_zoom", "at": 0.7}]}))
        W2 = W.parent / "ראיון-פודיומיסטים-המנצחים-מדברים"
        if W2.exists():
            shutil.rmtree(W2)
        W.rename(W2)
        fs = hp.evaluate(W2, measure_video=False)
        self.assertTrue(any("פסל" in x["detail"] and x["severity"] == hp.HIGH for x in fs))
        shutil.rmtree(W2)


if __name__ == "__main__":
    unittest.main()
