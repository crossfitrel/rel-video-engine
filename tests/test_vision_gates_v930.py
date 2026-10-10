# -*- coding: utf-8 -*-
"""v9.30 (22.9.26) — גלים 2-4: בירולים ב-FINAL (broll_vision_qa), קנון הלקחים,
והאוכפים של הלקחים שחיו רק בזיכרון (L74-L93). כל שער — הזרקת כשל + תוצר תקין."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import cv2                                    # noqa: E402
import numpy as np                            # noqa: E402

import broll_vision_qa as B                   # noqa: E402

FF = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def _vid(path, frames, fps=30):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()


def _pattern(seed, n=90, W=1080, H=1920):
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (24, 14, 3), dtype=np.uint8)
    big = cv2.resize(base, (W, H), interpolation=cv2.INTER_NEAREST)
    return [big.copy() for _ in range(n)]


class TestBrollLanded(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp(prefix="bv930_"))
        cls.clip = cls.d / "clip.mp4"
        _vid(cls.clip, _pattern(1))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def _work(self, name, burn):
        W = self.d / name
        W.mkdir()
        base = _pattern(2)
        _vid(W / "EXPORT.mp4", base)
        ov = B.expected_overlay(_pattern(1, 1)[0])
        final = [ov if (burn and 30 <= i < 60) else f for i, f in enumerate(base)]
        _vid(W / "FINAL.mp4", final)
        item = {"file": "clip.mp4", "path": str(self.clip), "insert_at": 1.0,
                "insert_end": 2.0, "src_offset": 0.0}
        (W / "broll_plan.json").write_text(json.dumps({"plan": [item]}), encoding="utf-8")
        (W / "project_manifest.json").write_text(json.dumps(
            {"brand": "rel", "finish_prefs": {"broll": {"items_applied": [item]}}}), encoding="utf-8")
        (W / "FINAL_PROVENANCE.json").write_text(json.dumps({"intro_offset_sec": 0.0}))
        return W

    def test_landed_broll_matches_and_missing_is_caught(self):
        cfg = dict(B.DEFAULTS, blocking=["not_landed"], source="measured")
        ok = B.check(self._work("ok", True), cfg=cfg, write=False)
        self.assertTrue(ok["items"][0]["B1"]["landed"], ok["items"][0]["B1"])
        self.assertTrue(ok["ok"])
        bad = B.check(self._work("bad", False), cfg=cfg, write=False)
        self.assertIn("not_landed", bad["items"][0]["flags"], bad["items"][0]["B1"])
        self.assertFalse(bad["ok"])

    def test_applied_record_beats_the_plan(self):
        W = self._work("applied", True)
        m = json.loads((W / "project_manifest.json").read_text())
        m["finish_prefs"]["broll"]["items_applied"] = []       # התוכנית לא הוחלה
        (W / "project_manifest.json").write_text(json.dumps(m))
        d = B.check(W, write=False)
        self.assertEqual(d.get("n_broll"), 0)
        self.assertIsNone(d.get("ok"))

    def test_harel_clip_in_club_is_flagged(self):
        it = {"file": "x.mp4", "path": "/a/בירולים/הראל חיון/x.mp4"}
        self.assertTrue(B.b3_identity(it, "rel", {}, {}, {})["violation"])
        self.assertFalse(B.b3_identity(it, "personal", {}, {}, {})["violation"])
        it2 = {"file": "y.mp4", "path": "/a/y.mp4"}
        ov = {"y.mp4": {"identity": "harel?"}}
        self.assertTrue(B.b3_identity(it2, "rel", {}, ov, {})["violation"])

    def test_anchor_answer_requires_all_booleans(self):
        W = self._work("anchor", True)
        (W / "words_final.json").write_text(json.dumps(
            [{"word": "קליפ", "start": 1.1, "end": 1.6}]), encoding="utf-8")
        req = B.anchor_request(W)
        self.assertEqual(len(req["windows"]), 1)
        (W / "BROLL_ANCHOR_ANSWER.json").write_text(json.dumps(
            {"windows": [{"ref": "w01", "anchored": True, "why": "x"}]}))
        with self.assertRaises(SystemExit):
            B.anchor_apply(W)
        (W / "BROLL_ANCHOR_ANSWER.json").write_text(json.dumps(
            {"windows": [{"ref": "w01", "anchored": False, "burned_text": False,
                          "harel_in_frame": False, "why": "x"}]}))
        v = B.anchor_apply(W)
        self.assertEqual(v["n_not_anchored"], 1)
        self.assertEqual(B.check(W, write=False)["counts"].get("not_anchored"), 1)

    def test_stale_anchor_verdict_is_rejected(self):
        W = self._work("stale", True)
        (W / "words_final.json").write_text(json.dumps(
            [{"word": "קליפ", "start": 1.1, "end": 1.6}]), encoding="utf-8")
        B.anchor_request(W)
        (W / "BROLL_ANCHOR_ANSWER.json").write_text(json.dumps(
            {"windows": [{"ref": "w01", "anchored": True, "burned_text": False,
                          "harel_in_frame": False, "why": "x"}]}))
        with open(W / "FINAL.mp4", "ab") as fh:                 # ה-FINAL השתנה
            fh.write(b"\0" * 1024)
        with self.assertRaises(SystemExit):
            B.anchor_apply(W)

    def test_dense_sampling_finds_clip_between_old_samples(self):
        """v9.32 (L94) — הקליפ על המסך ברגע שנופל בין 8 הדגימות הישנות.
        קליפ של 37 'סצנות' (כל 8 פריימים סצנה אחרת); ה-FINAL מציג סצנה שאינה
        באף אחת מ-8 הדגימות הישנות ⇒ המדידה הישנה אמרה 'לא נחת', הצפופה — נחת."""
        rng = np.random.default_rng(5)
        scenes = [cv2.resize(rng.integers(0, 255, (24, 14, 3), dtype=np.uint8), (1080, 1920),
                             interpolation=cv2.INTER_NEAREST) for _ in range(37)]
        frames = [scenes[i // 8] for i in range(296)]
        clip = self.d / "moving.mp4"
        _vid(clip, frames)
        old = {int(295 * (j + .5) / 8) // 8 for j in range(8)}
        pick = next(k for k in range(37) if k not in old and k - 1 not in old and k + 1 not in old)
        fr = B.expected_overlay(scenes[pick])
        old_best = max(B.ncc(fr, B.expected_overlay(scenes[k])) for k in old)
        self.assertLess(old_best, 0.55)                        # זו הייתה התקלה
        self.assertGreater(B.best_clip_sim(fr, clip), 0.9)     # הדגימה הצפופה מוצאת

    def test_window_median_survives_one_bad_moment(self):
        W = self._work("seam", True)
        fin = cv2.VideoCapture(str(W / "FINAL.mp4"))
        frames = []
        while True:
            ok, f = fin.read()
            if not ok:
                break
            frames.append(f)
        fin.release()
        frames[36] = frames[0]                                   # רגע אחד בחלון נופל על הבסיס
        _vid(W / "FINAL.mp4", frames)
        cfg = dict(B.DEFAULTS, blocking=["not_landed"], source="measured")
        r = B.check(W, cfg=cfg, write=False)
        self.assertTrue(r["items"][0]["B1"]["landed"], r["items"][0]["B1"])

    def test_duplicate_applied_record_counts_once(self):
        W = self._work("dup", True)
        m = json.loads((W / "project_manifest.json").read_text())
        it = m["finish_prefs"]["broll"]["items_applied"][0]
        m["finish_prefs"]["broll"]["items_applied"] = [it, dict(it)]
        (W / "project_manifest.json").write_text(json.dumps(m))
        self.assertEqual(len(B._plan(W)[0]), 1)

    def test_anchor_cohort_rejects_stale_and_needs_twenty(self):
        """L96 — פסיקת הראל על FINAL שהשתנה נפסלת; פחות מ-20 פסיקות = לא נמדד."""
        import anchor_cohort as AC
        root = self.d / "wr"
        root.mkdir()
        W = root / "p1"
        W.mkdir()
        (W / "FINAL.mp4").write_bytes(b"v1" * 100)
        sha = B._sha(W / "FINAL.mp4")
        (W / "BROLL_ANCHOR_VERDICT.json").write_text(json.dumps(
            {"final_sha": sha, "windows": [{"ref": "w01", "anchored": False}]}))
        lab = self.d / "labels.json"
        lab.write_text(json.dumps([
            {"id": "p1::w01", "anchored": False, "final_sha": sha},
            {"id": "p1::w02", "anchored": True, "final_sha": "sha-of-an-older-final"}]))
        old = (AC._work_root, AC.LABELS, AC.AGREE)
        try:
            AC._work_root = lambda: root
            AC.LABELS, AC.AGREE = self.d / "L.json", self.d / "A.json"
            by = AC.import_labels(lab)
            self.assertEqual(set(by), {"p1::w01"})
            rep = AC.agree()
            self.assertEqual(rep["n"], 1)
            self.assertEqual(rep["not_anchored_precision"], 1.0)
            self.assertFalse(rep["measured"])                   # 1 < 20
        finally:
            AC._work_root, AC.LABELS, AC.AGREE = old


class TestMemoryOnlyLessonsNowEnforced(unittest.TestCase):
    def test_audio_mix_never_reads_stdin(self):
        import audio_mix as A
        r = A.run([sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"])
        self.assertEqual(r.stdout.strip(), "''")

    def test_usage_commit_can_be_neutralized(self):
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("REL_BROLL_USAGE_COMMIT", "1") != "0"', src)

    @unittest.skipUnless(shutil.which("ffmpeg") or os.path.exists(FF), "ffmpeg")
    def test_concat_filter_joins_full_length(self):
        import edl_cut as E
        d = Path(tempfile.mkdtemp())
        try:
            segs = []
            for k in range(2):
                f = d / f"s{k}.mp4"
                subprocess.run([FF, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                                "testsrc=size=160x284:rate=30", "-f", "lavfi", "-i",
                                "sine=frequency=440", "-t", "1.5", "-c:v", "libx264",
                                "-c:a", "aac", "-shortest", str(f)], check=True)
                segs.append(f)
            out = d / "j.mp4"
            r = E.concat_filter(segs, out, 23, "veryfast")
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            self.assertAlmostEqual(E.ffprobe_vdur(out), 3.0, delta=0.15)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(shutil.which("ffmpeg") or os.path.exists(FF), "ffmpeg")
    def test_music_intro_dip_finds_the_known_track(self):
        import audio_mix as A
        d = Path(tempfile.mkdtemp())
        try:
            f = d / "m.wav"
            # פתיח חזק 2ש → צניחה ל-8ש → קטע חזק: בדיוק הפרופיל של 513742 (20.7.26)
            import wave
            t = np.arange(0, 30, 1 / 8000.0)
            amp = np.where(t < 2, 0.5, np.where(t < 8, 0.08, 0.5))
            pcm = (amp * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16)
            with wave.open(str(f), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
                w.writeframes(pcm.tobytes())
            r = A.music_intro_dip(str(f))
            self.assertTrue(r["dip"], r)
            self.assertAlmostEqual(r["suggested_offset"], 8.0, delta=2.1)
            real = ROOT / "brand-assets" / "music" / \
                "lightstockmusic-strong-character-powerful-fuzz-action-sport-rock-513742.mp3"
            if real.exists():
                rr = A.music_intro_dip(str(real))
                self.assertTrue(rr["dip"])
                self.assertEqual(rr["suggested_offset"], 12.0)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestLessonsCanon(unittest.TestCase):
    def test_every_feedback_file_is_mapped_and_enforced(self):
        import lessons_canon as LC
        ok, probs = LC.audit()
        self.assertTrue(ok, " | ".join(p for p in probs if p.startswith("❌"))[:600])
        self.assertEqual(len(LC.D.C), 133)

    def test_injected_unmapped_ops_rule_fails_audit(self):
        import lessons_canon as LC
        LC.D.C["zz_test_rule"] = {"status": "ops", "ids": [], "rule": "x", "debt": None}
        try:
            ok, probs = LC.audit()
            self.assertFalse(ok)
            self.assertTrue(any("zz_test_rule" in p for p in probs))
        finally:
            del LC.D.C["zz_test_rule"]

    def test_superseded_points_to_something_real(self):
        import lessons_canon as LC
        LC.D.C["zz_sup"] = {"status": "superseded", "ids": ["L999_nope"], "rule": "", "debt": None}
        try:
            self.assertFalse(LC.audit()[0])
        finally:
            del LC.D.C["zz_sup"]


if __name__ == "__main__":
    unittest.main()
