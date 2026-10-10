#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_visual_hook_render.py — אותה תוכנית, שני מנועים, ffmpeg אמיתי (11.9.26).

הבדיקה אינה "מחרוזת הפילטר נראית נכון" אלא פיקסלים: הפלט מפוענח ומושווה
לטרנספורם ייחוס (cv2.warpAffine של הפריים הנקי לפי `rect_at`). מחוץ ל-cue
משווים לרינדור זהות תואם (אותו מקודד) — לא מבטיחים זהות-ביטים אחרי דור lossy.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
TOOLS = SYSDIR / "tools"
sys.path.insert(0, str(TOOLS))

from relvid import visual_hook as VH                 # noqa: E402
from relvid import hook_render as HR                 # noqa: E402

HAS_FFMPEG = shutil.which(VH.ffbin()) is not None or Path(VH.ffbin()).exists()
try:
    import numpy as np
    import cv2
    HAS_CV = True
except Exception:
    HAS_CV = False

W_, H_ = 540, 960
Z = "sha256:" + "0" * 64


def run(cmd, timeout=600):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    assert r.returncode == 0, (r.stderr or "")[-600:]
    return r


def make_body(path: Path, dur=5.0, size=(W_, H_), black_frame=None, audio_tail=0.0):
    vf = "null" if black_frame is None else \
        f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='eq(n\\,{black_frame})'"
    run([VH.ffbin(), "-nostdin", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", f"testsrc2=s={size[0]}x{size[1]}:r=30:d={dur}",
         "-f", "lavfi", "-i", f"sine=frequency=330:duration={dur + audio_tail}",
         "-vf", vf, "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p",
         "-c:a", "aac"] + ([] if audio_tail else ["-shortest"]) + [str(path)])
    return path


def gray_frames(path, w=W_, h=H_):
    r = subprocess.run([VH.ffbin(), "-nostdin", "-loglevel", "error", "-i", str(path),
                        "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    return a.reshape(-1, h, w)


def warp(frame, rect):
    h, w = frame.shape
    s = 1.0 / rect[2]
    M = np.array([[s, 0, -rect[0] * w * s], [0, s, -rect[1] * h * s]], dtype=np.float64)
    return cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def plan_for(fc, start=40, end=101, scale=1.06, cy=0.5, recipe="SMART_PUNCH_IN"):
    r = VH.crop_rect(scale, 0.5, cy)
    cues = [] if recipe == "NO_OP" else [{
        "id": "cue_1", "kind": "crop", "start_frame": start, "end_frame": end,
        "interpolation": "smoothstep",
        "keyframes": [{"frame": start, "rect": list(VH.IDENTITY)}, {"frame": start + 15, "rect": r},
                      {"frame": end - 16, "rect": r}, {"frame": end - 1, "rect": list(VH.IDENTITY)}]}]
    p = {"schema_version": 1, "project_id": "prj_test", "input_digest": Z, "policy_digest": Z,
         "reservation_digest": Z, "recipe": recipe, "recipe_version": 1, "candidate_id": "cand_000000000000",
         "timeline": {"axis": "body_final", "fps_num": 30, "fps_den": 1, "frame_count": fc, "intro_frames": 0},
         "audio_mode": "preserve",
         "evidence": {"word_ids": [], "quote": "", "grade": "supported", "reviewed_subjects": []},
         "assets": [], "cues": cues, "declared_transitions": [],
         "selection": {"actor": "harel", "reason_codes": ["operator_selected"]}}
    p["plan_digest"] = VH.digest_plan(p)
    return p


def mad(a, b, crop=8):
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16))[crop:-crop, crop:-crop].mean())


@unittest.skipUnless(HAS_FFMPEG and HAS_CV, "ffmpeg/cv2 חסרים")
class TestV1Adapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="vh_render_"))
        cls.body = make_body(cls.tmp / "EXPORT.mp4")
        cls.fc = VH.probe_video(cls.body)["frame_count"]
        cls.plan = plan_for(cls.fc)
        cls.receipt = HR.render_v1(cls.body, cls.plan, cls.tmp / "VISUAL_BASE.mp4")
        ident = plan_for(cls.fc, scale=1.0)
        cls.control = HR.render_v1(cls.body, ident, cls.tmp / "CONTROL.mp4")
        cls.src = gray_frames(cls.body)
        cls.out = gray_frames(cls.tmp / "VISUAL_BASE.mp4")
        cls.ctl = gray_frames(cls.tmp / "CONTROL.mp4")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_noop_does_not_encode(self):
        out = self.tmp / "NOOP.mp4"
        rc = HR.render_v1(self.body, plan_for(self.fc, recipe="NO_OP"), out)
        self.assertFalse(rc["applied"])
        self.assertFalse(out.exists())
        self.assertEqual(rc["output"]["path"], str(self.body))

    def test_frame_count_fps_dims_preserved(self):
        pv = VH.probe_video(self.tmp / "VISUAL_BASE.mp4")
        self.assertEqual(pv["frame_count"], self.fc)
        self.assertEqual((pv["width"], pv["height"], pv["fps_num"], pv["fps_den"]), (W_, H_, 30, 1))

    def test_audio_tail_longer_than_video_is_preserved(self):
        """נמדד על סקאלת-הבריאות: ‎-frames:v חתך את זנב האודיו כשהאודיו ארוך מהווידאו."""
        body = make_body(self.tmp / "EXPORT_tail.mp4", dur=4.0, audio_tail=0.6)
        fc = VH.probe_video(body)["frame_count"]
        rc = HR.render_v1(body, plan_for(fc), self.tmp / "VB_tail.mp4")
        self.assertTrue(rc["audio"]["equal"])
        self.assertEqual(VH.probe_video(self.tmp / "VB_tail.mp4")["frame_count"], fc)

    def test_audio_is_byte_identical(self):
        self.assertTrue(self.receipt["audio"]["equal"])
        self.assertEqual(HR._audio_md5(self.body), HR._audio_md5(self.tmp / "VISUAL_BASE.mp4"))

    def test_pixels_follow_plan_inside_cue(self):
        cue = self.plan["cues"][0]
        for f in (47, 55, 70, 85, 95):
            ref = warp(self.src[f], VH.rect_at(cue, f))
            e_ref, e_src = mad(self.out[f], ref), mad(self.out[f], self.src[f])
            self.assertLess(e_ref, 2.5, f"frame {f}: {e_ref}")
            if VH.rect_at(cue, f)[2] < 0.99:
                self.assertGreater(e_src, e_ref * 2, f"frame {f} לא זז מהמקור")

    def test_identity_outside_cue_matches_control_encode(self):
        for f in list(range(0, 40)) + list(range(101, self.fc)):
            self.assertLess(mad(self.out[f], self.ctl[f]), 0.6, f"frame {f}")

    def test_boundaries_are_identity_no_jump(self):
        for f in (39, 40, 100, 101):
            self.assertLess(mad(self.out[f], self.ctl[f]), 0.6, f"frame {f}")

    def test_deterministic_same_plan_same_frames(self):
        rc2 = HR.render_v1(self.body, self.plan, self.tmp / "VISUAL_BASE_2.mp4")
        a = subprocess.run([VH.ffbin(), "-loglevel", "error", "-i", str(self.tmp / "VISUAL_BASE.mp4"),
                            "-map", "0:v", "-f", "framemd5", "-"], capture_output=True, text=True).stdout
        b = subprocess.run([VH.ffbin(), "-loglevel", "error", "-i", str(self.tmp / "VISUAL_BASE_2.mp4"),
                            "-map", "0:v", "-f", "framemd5", "-"], capture_output=True, text=True).stdout
        strip = lambda t: [ln.split(",")[-1] for ln in t.splitlines() if not ln.startswith("#")]  # noqa: E731
        self.assertEqual(strip(a), strip(b))
        self.assertEqual(rc2["filter_sha256"], self.receipt["filter_sha256"])

    def test_timeline_mismatch_fails_loudly_not_noop(self):
        bad = plan_for(self.fc + 7)
        with self.assertRaises(VH.HookError) as cm:
            HR.render_v1(self.body, bad, self.tmp / "BAD.mp4")
        self.assertEqual(cm.exception.code, "HOOK_TIMELINE_MISMATCH")

    def test_missing_body_fails_candidate(self):
        with self.assertRaises(VH.HookError) as cm:
            HR.render_v1(self.tmp / "nope.mp4", self.plan, self.tmp / "X.mp4")
        self.assertEqual(cm.exception.code, "HOOK_ASSET_MISSING")

    def test_preview_is_not_publishable_and_bounded(self):
        info = HR.render_preview(self.body, self.plan, self.tmp / "VISUAL_HOOK_PREVIEW.mp4", seconds=3)
        self.assertFalse(info["publishable"])
        self.assertEqual(VH.probe_video(self.tmp / "VISUAL_HOOK_PREVIEW.mp4")["frame_count"], 90)
        sbs = HR.render_preview(self.body, self.plan, self.tmp / "VISUAL_HOOK_PREVIEW_SBS.mp4",
                                seconds=2, side_by_side=True)
        self.assertTrue(sbs["side_by_side"])
        self.assertEqual(VH.probe_video(self.tmp / "VISUAL_HOOK_PREVIEW_SBS.mp4")["width"], 1080)


class TestSegmentCompiler(unittest.TestCase):
    def test_unaffected_segment_gets_no_ir(self):
        p = plan_for(600)
        self.assertEqual(HR.compile_for_segment(p, 200, 100, 1.0), [])
        self.assertEqual(HR.compile_for_segment(p, 0, 40, 1.0), [])      # נגמר בדיוק לפני ה-cue

    def test_noop_never_compiles(self):
        self.assertEqual(HR.compile_for_segment(plan_for(600, recipe="NO_OP"), 0, 600, 1.0), [])

    def test_crossing_cue_compiles_in_both_segments(self):
        p = plan_for(600)
        a = HR.compile_for_segment(p, 0, 70, 1.15)
        b = HR.compile_for_segment(p, 70, 100, 1.15)
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)
        self.assertEqual(a[0]["global_frames"], [40, 70])
        self.assertEqual(b[0]["global_frames"], [70, 101])
        self.assertNotEqual(a[0]["fragment_digest"], b[0]["fragment_digest"])

    def test_single_speed_conversion(self):
        c = plan_for(600)["cues"][0]
        f1 = HR.perspective_filter(c, frame_offset=0, frame_scale=1.0)
        f2 = HR.perspective_filter(c, frame_offset=0, frame_scale=1.15)
        self.assertIn("between(n,40,100)", f1)
        self.assertIn("between(n,46,115)", f2)       # 40×1.15=46 · 100×1.15=115 (עיגול לפני floor/ceil)
        self.assertNotIn("drawtext", f1 + f2)

    def test_v1_filter_equals_v2_single_segment_filter(self):
        p = plan_for(600)
        ir = HR.compile_for_segment(p, 0, 600, 1.0)
        self.assertEqual(ir[0]["filter"], HR.perspective_filter(p["cues"][0]))


@unittest.skipUnless(HAS_FFMPEG and HAS_CV, "ffmpeg/cv2 חסרים")
class TestV2Engine(unittest.TestCase):
    """build_timeline(hook_plan) — מפתחות מטמון, פריימים, אודיו ופיקסלים."""

    def _project(self, tmp, keeps, speed=None, dur=8.0):
        sys.path.insert(0, str(HERE))
        from test_render_v2 import mkproject   # אותו מחולל פרויקט סינתטי של מנוע v2
        mkproject(tmp, keeps=keeps, dur=dur)
        if speed:
            total = sum(k["end"] - k["start"] for k in keeps)
            (tmp / "tight_keeps.json").write_text(json.dumps([{"start": 0.0, "end": round(total, 3)}]),
                                                  encoding="utf-8")
            run([VH.ffbin(), "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", f"color=c=black:s=64x64:r=30:d={total / speed:.4f}", "-c:v", "libx264",
                 str(tmp / "EXPORT_TIGHT.mp4")])

    def _keys(self, tl):
        return [s.key for s in tl.segments]

    def test_off_and_noop_keep_cache_keys_byte_identical(self):
        from relvid import render as R
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            self._project(t, [{"start": 0.0, "end": 3.0}, {"start": 3.5, "end": 7.0}])
            base = R.build_timeline(t)
            fc = sum(s.n_frames for s in base.segments)
            noop = R.build_timeline(t, hook_plan=plan_for(fc, recipe="NO_OP"))
            self.assertEqual(self._keys(base), self._keys(noop))
            self.assertTrue(all(not s.hooks for s in noop.segments))
            self.assertNotIn("visual_hook", base.meta)

    def test_only_affected_segment_key_changes(self):
        from relvid import render as R
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            self._project(t, [{"start": 0.0, "end": 3.0}, {"start": 3.5, "end": 7.0}])
            base = R.build_timeline(t)
            fc = sum(s.n_frames for s in base.segments)
            hooked = R.build_timeline(t, hook_plan=plan_for(fc, start=20, end=70))
            kb, kh = self._keys(base), self._keys(hooked)
            self.assertNotEqual(kb[0], kh[0])
            self.assertEqual(kb[1], kh[1])
            self.assertEqual(hooked.meta["visual_hook"]["affected_segments"], [0])

    def test_timeline_mismatch_raises(self):
        from relvid import render as R
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            self._project(t, [{"start": 0.0, "end": 3.0}])
            with self.assertRaises(ValueError):
                R.build_timeline(t, hook_plan=plan_for(500, start=20, end=70))

    def _render_pair(self, t, keeps, start, end, speed=None):
        from relvid import render as R
        self._project(t, keeps, speed=speed)
        base = R.build_timeline(t)
        fc = sum(s.n_frames for s in base.segments)
        plan = plan_for(fc, start=start, end=end)
        m0 = t / "m0.mkv"
        r0 = R.render(base, m0)
        self.assertTrue(r0["ok"], r0.get("error"))
        hooked = R.build_timeline(t, hook_plan=plan)
        m1 = t / "m1.mkv"
        r1 = R.render(hooked, m1)
        self.assertTrue(r1["ok"], r1.get("error"))
        return plan, m0, m1, r1, fc

    def _pcm(self, p):
        return subprocess.run([VH.ffbin(), "-loglevel", "error", "-i", str(p), "-map", "0:a",
                               "-f", "md5", "-"], capture_output=True, text=True).stdout.strip()

    def test_v2_frames_audio_and_pixels_speed_1(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            plan, m0, m1, r1, fc = self._render_pair(t, [{"start": 0.0, "end": 3.0},
                                                         {"start": 3.5, "end": 7.0}], 20, 70)
            self.assertEqual(VH.probe_video(m1)["frame_count"], fc)
            self.assertEqual(self._pcm(m0), self._pcm(m1))
            self.assertEqual(r1["n_cached"], 1)                 # הסגמנט שלא נחתך — מהמטמון
            a = gray_frames(m0, 270, 480)
            b = gray_frames(m1, 270, 480)
            cue = plan["cues"][0]
            for f in (10, 19, 30, 45, 55, 69, 70, 80):
                ref = warp(a[f], VH.rect_at(cue, f))
                self.assertLess(mad(b[f], ref, 4), 3.0, f"frame {f}")

    def test_v2_speed_115_cue_crosses_source_cut(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            keeps = [{"start": 0.0, "end": 2.3}, {"start": 3.0, "end": 6.4}]
            plan, m0, m1, r1, fc = self._render_pair(t, keeps, 45, 100, speed=1.15)
            self.assertEqual(VH.probe_video(m1)["frame_count"], fc)
            self.assertEqual(self._pcm(m0), self._pcm(m1))
            self.assertEqual(sorted(r1["meta"]["visual_hook"]["affected_segments"]), [0, 1])
            a = gray_frames(m0, 270, 480)
            b = gray_frames(m1, 270, 480)
            cue = plan["cues"][0]
            errs = [mad(b[f], warp(a[f], VH.rect_at(cue, f)), 4) for f in range(40, 106)]
            self.assertLess(max(errs), 4.0, errs)


class TestPipelineWiring(unittest.TestCase):
    """חיווט מבני: off = המסלול הישן; כל ענפי הבירול צורכים visual_base; v2 מקבל תוכנית."""

    @classmethod
    def setUpClass(cls):
        cls.src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")

    def test_flag_default_is_none_and_mode_defaults_off(self):
        self.assertIn('ap.add_argument("--visual-hook", choices=("off", "shadow", "auto"), default=None', self.src)
        self.assertIn('vh_mode = vh_pref.get("mode") or a.visual_hook or "off"', self.src)

    def test_every_broll_overlay_uses_visual_base(self):
        calls = [ln for ln in self.src.splitlines() if 'animation_overlay.py", "--base"' in ln]
        self.assertGreaterEqual(len(calls), 2)
        for ln in calls:
            self.assertIn("VISUAL_BASE", ln)
            self.assertNotIn('"--base", EXPORT', ln)

    def test_visual_base_defaults_to_clean_export(self):
        self.assertIn("VISUAL_BASE = EXPORT", self.src)
        self.assertIn('base = (W / "master_v2.mkv") if captions_burned else VISUAL_BASE', self.src)

    def test_export_never_overwritten_and_cover_uses_clean(self):
        self.assertNotIn("render_v1(EXPORT, vh_state[\"plan\"], EXPORT", self.src)
        self.assertIn('"--video", EXPORT,                     # תמיד המקור הנקי', self.src)

    def test_v2_receives_plan(self):
        self.assertIn("hook_plan=(vh_state[\"plan\"] if vh_state and vh_state[\"applied\"]", self.src)

    def test_prepare_review_exits_before_render_music_final(self):
        i_exit = self.src.index('print("DONE-VISUAL-HOOK-PREP")')
        for marker in ('st.step("render_v2")', 'st.step("music")', "PENDING.replace(FINAL)",
                       "_art.create_artifact("):
            self.assertLess(i_exit, self.src.rindex(marker), marker)

    def test_hook_qa_joins_blockers_before_promotion(self):
        i_q = self.src.index('blockers.append("visual_hook_qa: "')
        self.assertLess(i_q, self.src.rindex("PENDING.replace(FINAL)"))

    def test_runner_command_unchanged_without_hook(self):
        from relvid import runner
        with tempfile.TemporaryDirectory() as t:
            cmd = runner.build_command(t, {"content_type": "value", "brand": "rel"}, "py")
            self.assertNotIn("--visual-hook", cmd)
            cmd2 = runner.build_command(t, {"content_type": "value", "visual_hook_mode": "shadow"}, "py")
            self.assertEqual(cmd2[cmd2.index("--visual-hook") + 1], "shadow")
            cmd3 = runner.build_command(t, {"visual_hook_mode": "rm -rf"}, "py")
            self.assertNotIn("--visual-hook", cmd3)


if __name__ == "__main__":
    unittest.main()
