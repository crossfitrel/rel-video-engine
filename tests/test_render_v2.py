#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_render_v2.py — מנוע הרינדור v2 (V2 שלב 2).

שתי שכבות:
  * לוגיקה טהורה — כימות הפריימים, חיתוך פריטים לגבולות סגמנט, יציבות מפתח
    המטמון, המרת ציר ההאצה. בלי ffmpeg, מהיר.
  * אינטגרציה — פרויקט סינתטי אמיתי עם ffmpeg: מוודא ש**ספירת הפריימים של
    המאסטר שווה בדיוק לסכום ה-n_frames**. זו הבדיקה שתפסה את הבאג האמיתי:
    בגרסה הראשונה כל סגמנט התעגל בנפרד וההצטברות נתנה +0.373ש מול v1.
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

HAS_FFMPEG = shutil.which("ffmpeg") is not None
try:
    from PIL import Image  # noqa: F401
    HAS_PIL = True
except Exception:
    HAS_PIL = False

from relvid import render as R                       # noqa: E402


def run(cmd, timeout=300):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          timeout=timeout)


def frames(p):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
             "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(p)])
    return int((r.stdout or "0").strip().rstrip(",").split(",")[0])


def mkproject(tmp: Path, *, keeps, tight=None, words=None, dur=20.0, speed_video=None):
    """פרויקט סינתטי: INPUT + edl + (tight_keeps) + (words_final)."""
    tmp.mkdir(parents=True, exist_ok=True)
    inp = tmp / "INPUT.mp4"
    r = run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", f"testsrc=s=270x480:d={dur}:r=30",
             "-f", "lavfi", "-i", f"sine=frequency=300:duration={dur}",
             "-c:v", "libx264", "-crf", "30", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", inp])
    assert r.returncode == 0, r.stderr[-400:]
    (tmp / "edl.json").write_text(json.dumps({
        "total_dur": dur, "keep_segments": keeps,
        "review": {"cuts": [], "hook_move": None, "speed": 1.0},
        "auto_cuts": [], "manual_review_cuts": []}), encoding="utf-8")
    if tight is not None:
        (tmp / "tight_keeps.json").write_text(json.dumps(tight), encoding="utf-8")
    if words is not None:
        (tmp / "words_final.json").write_text(json.dumps(words, ensure_ascii=False),
                                              encoding="utf-8")
    return inp


class TestFrameQuantization(unittest.TestCase):
    """הבאג שנמצא במדידה: עיגול לגבול פריים בכל סגמנט בנפרד ⇒ הצטברות."""

    def _tl(self, keeps, speed_ratio=1.0):
        segs = []
        acc = 0.0
        for i, k in enumerate(keeps):
            segs.append(R.Segment(src="x", t_in=k[0], t_out=k[1], out_start=acc,
                                  idx=i, speed=speed_ratio))
            acc += k[1] - k[0]
        fps = R.DELIVER["fps"]
        prev, cum = 0, 0.0
        for s in segs:
            cum += s.dur
            end = int(round((cum / speed_ratio) * fps))
            s.n_frames = max(1, end - prev)
            prev = end
        return segs

    def test_total_frames_is_exact(self):
        keeps = [(1.63, 7.38), (9.16, 16.24), (17.38, 23.15), (24.58, 30.91), (32.45, 41.68)]
        for sp in (1.0, 1.05, 1.096, 1.15):
            segs = self._tl(keeps, sp)
            total_src = sum(s.dur for s in segs)
            expected = int(round(total_src / sp * R.DELIVER["fps"]))
            self.assertEqual(sum(s.n_frames for s in segs), expected,
                             f"speed={sp}: סכום הפריימים חייב להיות מדויק")

    def test_no_segment_is_empty(self):
        segs = self._tl([(0.0, 0.05), (1.0, 1.02), (2.0, 9.0)], 1.15)
        self.assertTrue(all(s.n_frames >= 1 for s in segs))

    def test_dur_final_follows_frames(self):
        segs = self._tl([(0.0, 5.75)], 1.096)
        s = segs[0]
        self.assertEqual(s.dur_final, round(s.n_frames / 30, 3))

    def test_drift_would_have_been_caught(self):
        """הדריפט האמיתי שנמדד לא היה חשבוני אלא **ffmpeg**: בלי `-frames:v`
        כל סגמנט מקבל את כל הפריימים שנחתכו מהמקור, מעוגלים כלפי מעלה לגבול
        פריים בשני הקצוות — ונמדד +0.373ש על 5 סגמנטים (935 מול 946 פריימים).
        הבדיקה משחזרת את ההתנהגות ההיא ומראה שהאכיפה מבטלת אותה."""
        keeps = [(1.63, 7.38), (9.16, 16.24), (17.38, 23.15), (24.58, 30.91), (32.45, 41.68)]
        sp, fps = 1.096, 30

        def ffmpeg_like(k):
            # ffmpeg קורא פריימים שלמים שמכסים את החלון, ואז fps+setpts מעגלים מעלה
            import math
            src_frames = math.ceil(k[1] * fps) - math.floor(k[0] * fps)
            return math.ceil(src_frames / sp)

        naive = sum(ffmpeg_like(k) for k in keeps)
        exact = sum(s.n_frames for s in self._tl(keeps, sp))
        self.assertGreater(naive, exact,
                           "בלי אכיפה ffmpeg מייצר יותר פריימים — אם לא, הבדיקה חסרת משמעות")
        self.assertGreaterEqual((naive - exact) / fps, 0.1,
                                "הדריפט חייב להיות מורגש (>0.1ש) כדי שהבדיקה תהיה שווה משהו")


class TestClipping(unittest.TestCase):
    """פריט שחוצה גבול סגמנט מופיע בשניהם, עם היסט-מקור מתוקן."""

    def setUp(self):
        self.segs = [R.Segment(src="x", t_in=0, t_out=5, out_start=0, idx=0, n_frames=150),
                     R.Segment(src="x", t_in=10, t_out=15, out_start=5, idx=1, n_frames=150)]

    def test_cue_inside_one_segment(self):
        R._clip_to_segments([R.Cue(1.0, 1.4, "שלום")], self.segs,
                            lambda c: (c.start, c.end),
                            lambda seg, c, ls, le, off: seg.cues.append(R.Cue(ls, le, c.text)))
        self.assertEqual(len(self.segs[0].cues), 1)
        self.assertEqual(len(self.segs[1].cues), 0)
        self.assertAlmostEqual(self.segs[0].cues[0].start, 1.0, places=3)

    def test_broll_straddling_boundary_splits_with_offset(self):
        clip = R.BrollClip("b.mp4", start=4.0, end=6.0, src_offset=0.5)
        R._clip_to_segments([clip], self.segs,
                            lambda c: (c.start, c.end),
                            lambda seg, c, ls, le, off: seg.broll.append(
                                R.BrollClip(c.path, round(ls, 3), round(le, 3),
                                            round(c.src_offset + off, 3))))
        self.assertEqual(len(self.segs[0].broll), 1)
        self.assertEqual(len(self.segs[1].broll), 1)
        a, b = self.segs[0].broll[0], self.segs[1].broll[0]
        self.assertAlmostEqual(a.start, 4.0, places=3)
        self.assertAlmostEqual(a.end, 5.0, places=3)
        self.assertAlmostEqual(a.src_offset, 0.5, places=3)
        # החלק השני מתחיל שנייה אחת בתוך קובץ הבירול
        self.assertAlmostEqual(b.start, 0.0, places=3)
        self.assertAlmostEqual(b.end, 1.0, places=3)
        self.assertAlmostEqual(b.src_offset, 1.5, places=3)

    def test_item_entirely_outside_is_dropped(self):
        R._clip_to_segments([R.Cue(50.0, 50.4, "מחוץ")], self.segs,
                            lambda c: (c.start, c.end),
                            lambda seg, c, ls, le, off: seg.cues.append(R.Cue(ls, le, c.text)))
        self.assertEqual(sum(len(s.cues) for s in self.segs), 0)


class TestCacheKey(unittest.TestCase):
    """המטמון הוא הלב של שלב 2 — מפתח לא נכון הופך אותו למסוכן או לחסר-תועלת."""

    def _tl(self, **over):
        seg = R.Segment(src=str(TOOLS / "relvid" / "render.py"), t_in=1.0, t_out=3.0,
                        out_start=0.0, idx=0, n_frames=60)
        seg.cues = over.pop("cues", [R.Cue(0.1, 0.4, "שלום")])
        seg.broll = over.pop("broll", [])
        tl = R.Timeline(workdir=Path("/tmp"), input_path=Path("x"), segments=[seg],
                        band=over.pop("band", {"y0": 1400, "h": 240, "fontsize": 120,
                                               "stroke": 7, "baseline_in_band": 90,
                                               "outline": [135, 29, 31], "font": "f.ttf",
                                               "n_cues": 1}),
                        crf=over.pop("crf", 23), speed=over.pop("speed", 1.0))
        return tl, seg

    def test_stable_for_same_inputs(self):
        t1, s1 = self._tl()
        t2, s2 = self._tl()
        self.assertEqual(R._segment_key(t1, s1), R._segment_key(t2, s2))

    def test_cue_text_change_invalidates(self):
        t1, s1 = self._tl()
        t2, s2 = self._tl(cues=[R.Cue(0.1, 0.4, "עולם")])
        self.assertNotEqual(R._segment_key(t1, s1), R._segment_key(t2, s2))

    def test_cue_timing_change_invalidates(self):
        t1, s1 = self._tl()
        t2, s2 = self._tl(cues=[R.Cue(0.2, 0.5, "שלום")])
        self.assertNotEqual(R._segment_key(t1, s1), R._segment_key(t2, s2))

    def test_crf_and_band_change_invalidate(self):
        base = R._segment_key(*self._tl())
        self.assertNotEqual(base, R._segment_key(*self._tl(crf=20)))
        b = {"y0": 1200, "h": 240, "fontsize": 120, "stroke": 7,
             "baseline_in_band": 90, "outline": [0, 119, 182], "font": "f.ttf", "n_cues": 1}
        self.assertNotEqual(base, R._segment_key(*self._tl(band=b)))

    def test_frame_count_is_in_key(self):
        t1, s1 = self._tl()
        t2, s2 = self._tl()
        s2.n_frames = 61
        self.assertNotEqual(R._segment_key(t1, s1), R._segment_key(t2, s2))

    def test_music_is_not_in_key(self):
        """הבטחה מרכזית: שינוי מוזיקה = אפס רינדור וידאו. אם המוזיקה הייתה
        נכנסת למפתח, כל שינוי מפלס היה מקודד מחדש את כל הסרטון."""
        src = json.dumps(R._segment_key.__doc__ or "")
        self.assertNotIn("music", src.lower())
        t, s = self._tl()
        key_before = R._segment_key(t, s)
        # אין שדה מוזיקה ב-Timeline/Segment בכלל — זו ההוכחה המבנית
        self.assertFalse(any("music" in f for f in R.Segment.__dataclass_fields__))
        self.assertFalse(any("music" in f for f in R.Timeline.__dataclass_fields__))
        self.assertEqual(key_before, R._segment_key(t, s))


class TestDeliverParams(unittest.TestCase):
    def test_single_source_of_truth(self):
        for k in ("width", "height", "fps", "crf", "pix_fmt", "acodec", "colorspace"):
            self.assertIn(k, R.DELIVER)
        self.assertEqual((R.DELIVER["width"], R.DELIVER["height"]), (1080, 1920))
        self.assertEqual(R.DELIVER["acodec"], "pcm_s16le",
                         "ביניים חייב להיות lossless — אחרת ה-concat מוסיף דור AAC")

    def test_normalize_filter_covers_res_sar_fps_and_color(self):
        vf = R._vf_normalize()
        for needle in ("scale=1080:1920", "pad=1080:1920", "setsar=1", "fps=30",
                       "setparams=color_primaries="):
            self.assertIn(needle, vf)

    def test_color_tags_are_preserved_not_forced(self):
        """הכלל "אסור לגעת בצבע": מקור מתויג bt2020 חייב להישאר bt2020 — תיוגו
        מחדש כ-bt709 בלי המרה היה משנה את פרשנות הצבע."""
        vf = R._vf_normalize({"primaries": "bt2020", "trc": "arib-std-b67",
                              "space": "bt2020nc", "range": "tv"})
        self.assertIn("color_primaries=bt2020", vf)
        self.assertIn("color_trc=arib-std-b67", vf)
        self.assertNotIn("bt709", vf)


@unittest.skipUnless(HAS_FFMPEG and HAS_PIL, "ffmpeg+PIL נדרשים")
class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="relr2-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_master_frame_count_is_exact(self):
        """הבדיקה שתפסה את הבאג האמיתי."""
        keeps = [{"start": 1.0, "end": 4.33}, {"start": 6.17, "end": 9.5},
                 {"start": 12.05, "end": 16.4}]
        mkproject(self.tmp, keeps=keeps, dur=20.0)
        tl = R.build_timeline(self.tmp)
        self.assertEqual(len(tl.segments), 3)
        expected = sum(s.n_frames for s in tl.segments)
        out = self.tmp / "master.mkv"
        res = R.render(tl, out, jobs=2)
        self.assertTrue(res.get("ok"), res.get("error"))
        self.assertEqual(frames(out), expected,
                         "ספירת הפריימים של המאסטר חייבת להיות בדיוק סכום ה-n_frames")

    def test_cache_hit_on_second_run(self):
        mkproject(self.tmp, keeps=[{"start": 1.0, "end": 4.0},
                                   {"start": 6.0, "end": 9.0}], dur=15.0)
        tl = R.build_timeline(self.tmp)
        out = self.tmp / "m.mkv"
        r1 = R.render(tl, out, jobs=2)
        self.assertTrue(r1["ok"])
        self.assertEqual(r1["n_rendered"], 2)
        tl2 = R.build_timeline(self.tmp)
        r2 = R.render(tl2, out, jobs=2)
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["n_cached"], 2, "ריצה שנייה חייבת להיות כולה מהמטמון")
        self.assertEqual(r2["encode_secs"], 0.0)

    def test_caption_change_invalidates_only_affected_segment(self):
        """הבטחת שלב 2: תיקון כתובית ⇒ רינדור סגמנט אחד, לא סרטון."""
        words = [{"word": "אחת", "start": 0.2, "end": 0.6},
                 {"word": "שתיים", "start": 1.0, "end": 1.5},
                 {"word": "שלוש", "start": 4.2, "end": 4.7}]
        mkproject(self.tmp, keeps=[{"start": 1.0, "end": 4.0},
                                   {"start": 6.0, "end": 9.0}], dur=15.0, words=words)
        tl = R.build_timeline(self.tmp)
        out = self.tmp / "m.mkv"
        self.assertTrue(R.render(tl, out, jobs=2)["ok"])
        # משנים רק מילה שנופלת בסגמנט הראשון
        words[0]["word"] = "אחד"
        (self.tmp / "words_final.json").write_text(json.dumps(words, ensure_ascii=False),
                                                   encoding="utf-8")
        tl2 = R.build_timeline(self.tmp)
        r2 = R.render(tl2, out, jobs=2)
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["n_rendered"], 1, "רק הסגמנט שהכתובית בו השתנתה")
        self.assertEqual(r2["n_cached"], 1)

    def test_output_is_deliver_spec(self):
        mkproject(self.tmp, keeps=[{"start": 1.0, "end": 5.0}], dur=10.0)
        tl = R.build_timeline(self.tmp)
        out = self.tmp / "m.mkv"
        self.assertTrue(R.render(tl, out, jobs=1)["ok"])
        r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=width,height,pix_fmt,color_primaries", "-of", "json", out])
        s = json.loads(r.stdout)["streams"][0]
        self.assertEqual((s["width"], s["height"]), (1080, 1920),
                         "נרמול רזולוציה חייב לקרות בסגמנט — ב-v1 אין אף שלב שעושה זאת")
        self.assertEqual(s["pix_fmt"], "yuv420p")
        self.assertEqual(s.get("color_primaries"), "bt709", "תיוג צבע מפורש")

    def test_prune_keeps_current_segments(self):
        mkproject(self.tmp, keeps=[{"start": 1.0, "end": 4.0}], dur=10.0)
        tl = R.build_timeline(self.tmp)
        self.assertTrue(R.render(tl, self.tmp / "m.mkv", jobs=1)["ok"])
        before = R.cache_stats(self.tmp)["files"]
        self.assertGreaterEqual(before, 1)
        res = R.prune_cache(self.tmp, keep_keys=[s.key for s in tl.segments])
        self.assertEqual(res["removed"], 0)
        res2 = R.prune_cache(self.tmp, keep_keys=["nope"])
        self.assertEqual(res2["removed"], before)


class TestPipelineWiring(unittest.TestCase):
    """v2 חייב להיכנס מאחורי דגל, ולהשאיר את v1 כברירת מחדל עד שהשער עובר."""

    def setUp(self):
        self.src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")

    def test_flag_exists_and_defaults_to_v1(self):
        self.assertIn('"--render-engine"', self.src)
        i = self.src.index('"--render-engine"')
        self.assertIn('default="v1"', self.src[i:i + 300])

    def test_v2_skips_caption_encode_and_deliver(self):
        self.assertIn("captions_burned", self.src)
        self.assertIn("os.replace(MIXED, PENDING)", self.src)
        # ה-deliver חייב להיות מותנה, אחרת חוזר קידוד מלא
        i = self.src.index('st.step("deliver")')
        self.assertIn("if captions_burned:", self.src[i:i + 400])

    def test_gates_still_run_in_v2(self):
        """שלב 0 לא נסתר: v2 לא מדלג על אף שער."""
        for needle in ('st.step("cut_qa")', 'st.step("caption_safety")',
                       'st.step("canon")', 'st.step("qa")', "if blockers:"):
            self.assertIn(needle, self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ═══════════════════════════════════════ v8.8 — מקור פר-סגמנט
class TestSourceOverrides(unittest.TestCase):
    """
    החוב שנסגר כאן: פרויקטים שבהם הורכב ביניים ביד (EXPORT_with_effect,
    EXPORT_reordered) — v2 מרנדר מה-INPUT ולכן לא ידע עליהם. ההצהרה המפורשת
    פותרת את זה, ובלבד שהיא נכשלת בקול על כל אי-התאמה.
    """

    def setUp(self):
        from relvid import render as R
        self.R = R
        self.d = Path(tempfile.mkdtemp(prefix="relsrc_"))
        self.color = {"primaries": "bt709", "trc": "bt709",
                      "space": "bt709", "range": "tv", "source_tagged": True}
        self.segs = [R.Segment(src=str(self.d / "INPUT.mp4"), t_in=0.0, t_out=2.0,
                               out_start=0.0, idx=0, n_frames=60),
                     R.Segment(src=str(self.d / "INPUT.mp4"), t_in=5.0, t_out=7.0,
                               out_start=2.0, idx=1, n_frames=60)]
        (self.d / "INPUT.mp4").write_bytes(b"x")
        (self.d / "ALT.mp4").write_bytes(b"y")

    def _write(self, overrides):
        (self.d / "segment_sources.json").write_text(
            json.dumps({"schema_version": 1, "overrides": overrides}), encoding="utf-8")

    def test_absent_file_is_a_noop(self):
        self.assertEqual(self.R.apply_source_overrides(self.d, self.segs, None, self.color), [])

    def test_override_switches_source_and_window(self):
        self._write([{"idx": 1, "src": "ALT.mp4", "t_in": 30.0, "t_out": 32.0}])
        self.R.probe_color = lambda p: self.color
        got = self.R.apply_source_overrides(self.d, self.segs, None, self.color)
        self.assertEqual(len(got), 1)
        self.assertTrue(self.segs[1].src.endswith("ALT.mp4"))
        self.assertEqual((self.segs[1].t_in, self.segs[1].t_out), (30.0, 32.0))
        self.assertTrue(self.segs[0].src.endswith("INPUT.mp4"))

    def test_length_mismatch_is_hard_error(self):
        """חלון באורך שונה משנה את משך הפלט — חייב להיכשל, לא להתעגל."""
        self._write([{"idx": 0, "src": "ALT.mp4", "t_in": 0.0, "t_out": 3.0}])
        self.R.probe_color = lambda p: self.color
        with self.assertRaises(ValueError):
            self.R.apply_source_overrides(self.d, self.segs, None, self.color)

    def test_missing_file_is_hard_error(self):
        self._write([{"idx": 0, "src": "NOPE.mp4"}])
        with self.assertRaises(ValueError):
            self.R.apply_source_overrides(self.d, self.segs, None, self.color)

    def test_color_mismatch_is_hard_error(self):
        """אסור לתייג מחדש בלי המרה — הלקח מה-bt2020 שנמצא 30.7."""
        self._write([{"idx": 0, "src": "ALT.mp4"}])
        self.R.probe_color = lambda p: dict(self.color, primaries="bt2020")
        with self.assertRaises(ValueError):
            self.R.apply_source_overrides(self.d, self.segs, None, self.color)

    def test_idx_out_of_range_is_hard_error(self):
        self._write([{"idx": 9, "src": "ALT.mp4"}])
        with self.assertRaises(ValueError):
            self.R.apply_source_overrides(self.d, self.segs, None, self.color)

    def test_half_window_is_hard_error(self):
        self._write([{"idx": 0, "src": "ALT.mp4", "t_in": 1.0}])
        with self.assertRaises(ValueError):
            self.R.apply_source_overrides(self.d, self.segs, None, self.color)

    def test_override_changes_cache_key_only_for_that_segment(self):
        R = self.R
        tl = R.Timeline(workdir=self.d, input_path=self.d / "INPUT.mp4",
                        segments=self.segs, band={}, color=self.color)
        R._file_id = lambda p: Path(p).name
        k0_before = R._segment_key(tl, self.segs[0])
        k1_before = R._segment_key(tl, self.segs[1])
        self.segs[1].src = str(self.d / "ALT.mp4")
        self.assertEqual(k0_before, R._segment_key(tl, self.segs[0]))
        self.assertNotEqual(k1_before, R._segment_key(tl, self.segs[1]))
