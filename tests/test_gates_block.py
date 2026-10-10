#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_gates_block.py — שער שלב 0 של מיגרציית V2 (v8.6).

העיקרון שהמערכת מצהירה עליו: "מוגדר ≠ עובד". האודיט מ-30.7.26 מצא שלושה כלי
בקרה שהיו קיימים אך לא יכלו לחסום דבר: canon_lint (exit code נזרק ורץ אחרי
שה-FINAL כבר קודם), caption_safety (לא מחובר לצנרת בכלל), cut_qa (sys.exit(0)
תמיד). הקובץ הזה מזריק כשל אמיתי לכל אחד מהם ומוודא שהוא **באמת** נכשל —
כלומר בודק את החסימה, לא את קיום הקוד.

stdlib בלבד + ffmpeg (שנדרש בכל מקרה). כל בדיקה בתיקייה זמנית. אף בדיקה לא
נוגעת בפרויקט אמיתי.
"""
from __future__ import annotations
import json
import os
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


def run(cmd, timeout=300, cwd=None):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          timeout=timeout, cwd=cwd)


def words(pairs):
    return [{"word": w, "start": s, "end": e} for w, s, e in pairs]


class TmpWork(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="relgate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ─────────────────────────────── caption_safety
class TestCaptionSafetyBlocks(TmpWork):
    """P0-2: הכלי היה קוד מת. עכשיו מחובר לצנרת כשער חוסם."""

    def _run(self, w):
        p = self.tmp / "words.json"
        p.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
        return run([sys.executable, TOOLS / "caption_safety.py", "--words", p,
                    "--brand", "rel", "--out", self.tmp / "rep.json"], timeout=60)

    def test_clean_captions_pass(self):
        r = self._run(words([("שלום", 0.0, 0.4), ("עולם", 0.5, 0.9)]))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_raw_periods_are_warning_not_block(self):
        """חוק הקאנון "אין נקודות/פסיקים" נאכף **בזמן הצריבה** (clean_token מסיר
        [.,…]) — ולכן נקודה ב-words_final היא אזהרה, לא חסימה. נמדד: 205 מילים
        עם פיסוק גולמי מתוך 2,139 מילים בפרויקטים אמיתיים, וכולן נצרבות נקיות."""
        r = self._run(words([("שלום,", 0.0, 0.4), ("עולם.", 0.5, 0.9)]))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rep = json.loads((self.tmp / "rep.json").read_text(encoding="utf-8"))
        types = {w["type"] for w in rep.get("warnings", rep.get("warns", []))}
        self.assertIn("raw_punct_cleaned_at_burn", types, rep)

    def test_punct_that_survives_burn_fails(self):
        """מה שכן חייב לחסום: פיסוק ש**שורד** את clean_token ולכן נצרב על המסך."""
        r = self._run(words([("שלום;", 0.0, 0.4), ("עולם", 0.5, 0.9)]))
        self.assertEqual(r.returncode, 1, "נקודה-פסיק שורדת את הניקוי ונצרבת — חייב לחסום")

    def test_overlapping_cues_fail(self):
        r = self._run(words([("שלום", 0.0, 0.9), ("עולם", 0.2, 1.1)]))
        self.assertEqual(r.returncode, 1, "חפיפת cues חייבת להפיל")

    def test_non_monotonic_fails(self):
        r = self._run(words([("שלום", 1.0, 1.4), ("עולם", 0.2, 0.6)]))
        self.assertEqual(r.returncode, 1, "סדר לא-מונוטוני חייב להפיל")

    def test_arabic_char_fails(self):
        """לקח נעול: אף פעם לא תווים ערביים בתוכן עברי."""
        r = self._run(words([("مرحبا", 0.0, 0.5)]))
        self.assertEqual(r.returncode, 1, "תו ערבי חייב להפיל")


# ─────────────────────────────── canon_lint
class TestCanonLintBlocks(TmpWork):
    """P0-1: 8 חוקי HARD_FAIL שה-returncode שלהם נזרק, ורצו אחרי הקידום ל-FINAL."""

    def _mk(self, **files):
        for k, v in files.items():
            p = self.tmp / k
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v,
                         encoding="utf-8")

    def _run(self):
        return run([sys.executable, TOOLS / "canon_lint.py", "--workdir", self.tmp,
                    "--content-type", "value", "--brand", "rel",
                    "--out", self.tmp / "canon.json"], timeout=120)

    def test_missing_broll_files_hard_fails(self):
        # סכמת broll_plan.json בפועל: המערך תחת "plan", ולא "items"
        self._mk(**{"broll_plan.json": {"plan": [
            {"id": "x1", "path": "/nope/does-not-exist-12345.mp4",
             "file": "nope.mp4", "insert_at": 10.0, "clip_len": 2.8}]}})
        r = self._run()
        self.assertEqual(r.returncode, 1, "תוכנית בירול שמצביעה על קובץ שלא קיים חייבת להפיל")
        rep = json.loads((self.tmp / "canon.json").read_text(encoding="utf-8"))
        hard = [c for c in rep["checks"] if c["level"] == "HARD_FAIL"]
        self.assertTrue(any(c["rule"] == "broll_files_exist" for c in hard), hard)

    def test_captions_punct_surviving_burn_hard_fails(self):
        """הכלל "captions_no_periods_commas" היה טאוטולוגיה: הסיר [.,…] ואז חיפש
        [.,…] בתוצאה. עכשיו הוא חוסם על מה ששורד את הניקוי ונצרב בפועל."""
        self._mk(**{"words_final.json": words([("שלום;", 0.0, 0.4), ("עולם", 0.5, 0.9)])})
        r = self._run()
        self.assertEqual(r.returncode, 1)
        rep = json.loads((self.tmp / "canon.json").read_text(encoding="utf-8"))
        self.assertTrue(any(c["rule"] == "captions_no_periods_commas"
                            and c["level"] == "HARD_FAIL" for c in rep["checks"]))

    def test_captions_raw_periods_do_not_block(self):
        """נקודה/פסיק גולמיים ינוקו בצריבה — אסור שיחסמו (אחרת כל סרטון נחסם)."""
        self._mk(**{"words_final.json": words([("שלום.", 0.0, 0.4), ("עולם,", 0.5, 0.9)])})
        self.assertEqual(self._run().returncode, 0)

    def test_clean_workdir_does_not_hard_fail(self):
        """אזהרות מותרות; HARD_FAIL על תיקייה נקייה = שער רועש שמאלף להתעלם."""
        self._mk(**{"words_final.json": words([("שלום", 0.0, 0.4), ("עולם", 0.5, 0.9)])})
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout[-400:])

    def test_approve_gate_quiet_without_final(self):
        """P0-7: approve_publish_gate נכשל תמיד בגימור ידני כי הוא רץ אחרי יצירת
        FINAL. מרגע שהוא רץ לפני הקידום — אין FINAL, ולכן הוא שקט."""
        self._mk(**{"words_final.json": words([("שלום", 0.0, 0.4)])})
        r = self._run()
        rep = json.loads((self.tmp / "canon.json").read_text(encoding="utf-8"))
        g = [c for c in rep["checks"] if c["rule"] == "approve_publish_gate"]
        self.assertTrue(g and g[0]["level"] != "HARD_FAIL", g)
        self.assertEqual(r.returncode, 0)


# ─────────────────────────────── cut_qa
@unittest.skipUnless(HAS_FFMPEG, "ffmpeg נדרש")
class TestCutQaBlocks(TmpWork):
    """P0-3: sys.exit(0) תמיד + הגבולות לא חולקו ב-speed."""

    def _video_with_black_cut(self):
        """3 שניות: צבע → שחור → צבע. הגבול ב-1.0ש הוא פריים שחור אמיתי."""
        out = self.tmp / "v.mp4"
        r = run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=c=green:s=180x320:d=1:r=30",
                 "-f", "lavfi", "-i", "color=c=black:s=180x320:d=1:r=30",
                 "-f", "lavfi", "-i", "color=c=green:s=180x320:d=1:r=30",
                 "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
                 "-map", "[v]", "-c:v", "libx264", "-crf", "28", "-pix_fmt", "yuv420p", out])
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        return out

    def test_black_frame_at_boundary_blocks(self):
        v = self._video_with_black_cut()
        keeps = self.tmp / "keeps.json"
        keeps.write_text(json.dumps([{"start": 0.0, "end": 1.0},
                                     {"start": 1.0, "end": 2.0},
                                     {"start": 2.0, "end": 3.0}]), encoding="utf-8")
        py = Path.home() / ".rel-whisper" / "bin" / "python"
        py = py if py.exists() else Path(sys.executable)
        r = run([py, TOOLS / "cut_qa.py", "--video", v, "--keeps", keeps,
                 "--out", self.tmp / "cq.json"], timeout=300)
        if r.returncode == 2:
            self.skipTest("PIL לא זמין ל-cut_qa")
        rep = json.loads((self.tmp / "cq.json").read_text(encoding="utf-8"))
        self.assertEqual(r.returncode, 1,
                         f"פריים שחור בגבול חיתוך חייב לחסום. דוח: {rep.get('result')}")
        self.assertEqual(rep["result"], "FAIL")
        self.assertTrue(rep["blockers"])

    def test_report_only_when_block_on_empty(self):
        """תאימות לאחור: --block-on '' משחזר את התנהגות v7 (דיווח בלבד)."""
        v = self._video_with_black_cut()
        keeps = self.tmp / "keeps.json"
        keeps.write_text(json.dumps([{"start": 0.0, "end": 1.0},
                                     {"start": 1.0, "end": 3.0}]), encoding="utf-8")
        py = Path.home() / ".rel-whisper" / "bin" / "python"
        py = py if py.exists() else Path(sys.executable)
        r = run([py, TOOLS / "cut_qa.py", "--video", v, "--keeps", keeps,
                 "--block-on", "", "--out", self.tmp / "cq.json"], timeout=300)
        if r.returncode == 2:
            self.skipTest("PIL לא זמין ל-cut_qa")
        self.assertEqual(r.returncode, 0)

    def test_speed_divides_boundaries(self):
        """W10: tight_keeps נכתב לפני ההאצה, הווידאו כבר מואץ. בלי חלוקה ב-speed
        כל הגבולות שנבדקו היו במקום הלא-נכון — וזה קרה בכל סרטון שחרג מ-60ש
        מאז ש-speed_fit הפך אוטומטי."""
        from cut_qa import boundaries_from_keeps
        keeps = [{"start": 0, "end": 10}, {"start": 20, "end": 30}, {"start": 40, "end": 50}]
        self.assertEqual(boundaries_from_keeps(keeps, 1.0), [10.0, 20.0])
        self.assertEqual(boundaries_from_keeps(keeps, 1.1), [9.091, 18.182])
        self.assertEqual(boundaries_from_keeps(keeps, 2.0), [5.0, 10.0])


# ─────────────────────────────── sh() timeout
class TestPipelineTimeout(unittest.TestCase):
    """P0-4: TimeoutExpired לא נתפס ⇒ finish_status נשאר "running" לנצח."""

    def test_timeout_becomes_returncode_124(self):
        import local_finish_pipeline as P
        r = P.sh([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
        self.assertEqual(r.returncode, 124)
        self.assertIn("TIMEOUT", r.stderr)

    def test_normal_command_unaffected(self):
        import local_finish_pipeline as P
        r = P.sh([sys.executable, "-c", "print('ok')"], timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertIn("ok", r.stdout)


# ─────────────────────────────── tighten xfade+speed
class TestTightenXfadeSpeed(unittest.TestCase):
    """P0-6: השרשרת קיבעה [vc]/[ac] שלא קיימות בענף ה-xfade ⇒ ffmpeg נכשל תמיד."""

    def _fc(self, keeps, xfade, speed):
        """משחזר את בניית ה-filter_complex של tighten_finish בלי להריץ ffmpeg."""
        src = (TOOLS / "tighten_finish.py").read_text(encoding="utf-8")
        self.assertIn("_vin, _ain = vout, aout", src, "התיקון לא נמצא בקוד")
        return src

    def test_speed_chain_uses_actual_labels(self):
        src = self._fc(None, 0.15, 1.1)
        # השרשרת חייבת להשתמש בתוויות שחושבו, לא במחרוזות קבועות
        self.assertNotIn('fc += f"[vc]setpts', src)
        self.assertIn('fc += f"{_vin}setpts', src)

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg נדרש")
    def test_xfade_with_speed_runs_end_to_end(self):
        tmp = Path(tempfile.mkdtemp(prefix="relxf-"))
        try:
            src = tmp / "in.mp4"
            r = run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                     "-f", "lavfi", "-i", "testsrc=s=180x320:d=6:r=30",
                     "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                     "-c:v", "libx264", "-crf", "30", "-pix_fmt", "yuv420p",
                     "-c:a", "aac", "-shortest", src])
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            out = tmp / "out.mp4"
            r = run([sys.executable, TOOLS / "tighten_finish.py", "--in", src, "--out", out,
                     "--xfade", "0.15", "--speed", "1.1", "--noise", "-90",
                     "--min-sil", "0.2", "--keep-sil", "0.1"], timeout=300)
            # אין שקט ב-sine ⇒ ייתכן שאין מה להדק; מה שאסור הוא כשל ffmpeg על תווית
            self.assertNotIn("No such filter", (r.stdout + r.stderr))
            self.assertNotIn("Invalid file index", (r.stdout + r.stderr))
            if r.returncode != 0:
                self.assertNotIn("[vc]", r.stderr, f"נכשל על תווית לא קיימת: {r.stderr[-300:]}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────── review-app guards
class TestServerGuards(TmpWork):
    """P0-8/P0-9: נעילה על endpoints שכותבים + הגנת lost-update."""

    def setUp(self):
        super().setUp()
        os.environ["REL_WORK_ROOT"] = str(self.tmp)
        for m in [m for m in list(sys.modules) if m.startswith("relvid")]:
            del sys.modules[m]
        sys.path.insert(0, str(SYSDIR / "review-app"))
        for m in ("server",):
            sys.modules.pop(m, None)
        import server  # noqa
        self.server = server
        server.app.config["TESTING"] = True
        self.cli = server.app.test_client()
        self.name = "בדיקת-מערכת-gate"
        d = self.tmp / self.name
        d.mkdir(parents=True, exist_ok=True)
        (d / "edl.json").write_text(json.dumps({
            "total_dur": 30.0, "keep_segments": [{"start": 0, "end": 30}],
            "review": {"cuts": [], "hook_move": None, "speed": 1.0},
            "auto_cuts": [], "manual_review_cuts": []}, ensure_ascii=False), encoding="utf-8")
        (d / "whisper_raw.json").write_text("[]", encoding="utf-8")
        self.d = d

    def tearDown(self):
        os.environ.pop("REL_WORK_ROOT", None)
        super().tearDown()

    def test_save_succeeds_without_token(self):
        """תאימות לאחור: קליינט ישן שלא שולח base_token ממשיך לעבוד."""
        r = self.cli.post(f"/api/save/{self.name}", json={"cuts": [], "speed": 1.0})
        self.assertEqual(r.status_code, 200, r.data[:300])
        self.assertIn("edl_token", r.get_json())

    def test_stale_token_rejected_409(self):
        r1 = self.cli.post(f"/api/save/{self.name}", json={"cuts": [], "speed": 1.0})
        tok = r1.get_json()["edl_token"]
        # שמירה נוספת מזיזה את המצב
        self.cli.post(f"/api/save/{self.name}",
                      json={"cuts": [{"start": 1, "end": 2, "reason": "x",
                                      "source": "harel", "confidence": "harel"}],
                            "speed": 1.0})
        r3 = self.cli.post(f"/api/save/{self.name}",
                           json={"cuts": [], "speed": 1.0, "base_token": tok})
        self.assertEqual(r3.status_code, 409)
        self.assertEqual(r3.get_json()["code"], "STALE_EDL")

    def test_edit_blocked_while_finishing(self):
        """שורש: save/transcript/undo/redo/restore/recut כתבו את edl.json בזמן
        שהצנרת קוראת אותו תוך כדי ריצה."""
        lock = self.d / ".finish.lock"
        lock.mkdir()
        (lock / "meta.json").write_text(json.dumps(
            {"pid": os.getpid(), "run_id": "run_test", "started": "now"}), encoding="utf-8")
        for path, payload in (
            (f"/api/save/{self.name}", {"cuts": [], "speed": 1.0}),
            (f"/api/transcript/{self.name}", {"text": "שלום"}),
            (f"/api/undo/{self.name}", {}),
            (f"/api/redo/{self.name}", {}),
            (f"/api/restore/{self.name}", {"revision_id": "rev_x"}),
        ):
            r = self.cli.post(path, json=payload)
            self.assertEqual(r.status_code, 409, f"{path} לא נחסם בזמן גימור")
            self.assertEqual(r.get_json()["code"], "BUSY_FINISHING", path)

    def test_missing_project_is_404_not_500(self):
        r = self.cli.get("/api/project/אין-כזה-פרויקט")
        self.assertEqual(r.status_code, 404)

    def test_restore_without_id_is_400_not_500(self):
        r = self.cli.post(f"/api/restore/{self.name}", json={})
        self.assertEqual(r.status_code, 400)

    def test_compare_without_args_is_400_not_500(self):
        r = self.cli.get(f"/api/compare/{self.name}")
        self.assertEqual(r.status_code, 400)


# ─────────────────────────────── refinish gate coverage (structural)
class TestRefinishRunsGates(unittest.TestCase):
    """P0-5: שער הכיסוי, שער השקט ואכיפת 60ש ישבו בתוך ה-else של המסלול המלא."""

    def test_gates_are_outside_the_else_branch(self):
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8").splitlines()
        for needle in ('st.step("coverage")', 'st.step("gate")'):
            hits = [i for i, ln in enumerate(src) if needle in ln]
            self.assertTrue(hits, f"{needle} לא נמצא")
            for i in hits:
                indent = len(src[i]) - len(src[i].lstrip())
                self.assertEqual(indent, 4,
                                 f"{needle} בשורה {i+1} בהזחה {indent} — כלומר עדיין "
                                 f"בתוך ענף, ולא רץ ב---refinish")

    def test_refinish_enforces_hard_length_cap(self):
        # v9.25: תקרת ה-60ש בוטלה; refinish עדיין אוכף את הגבול הקשיח של length_policy.
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("a.refinish and dur > LP.HARD_MAX", src)


# ─────────────────────────────── learning gate
class TestLearningGate(unittest.TestCase):
    """P0-7: evaluate_proposal לא דרס את --allow-missed=3."""

    def test_evaluate_passes_allow_missed_zero(self):
        src = (TOOLS / "learn_from_edits.py").read_text(encoding="utf-8")
        self.assertIn('"--allow-missed", "0"', src)

    def test_classify_recognizes_real_event_names(self):
        import learn_from_edits as L
        self.assertEqual(L.classify({"type": "silence_restore",
                                     "reason": "שקט 0.9ש"}), "RC_SILENCE_RESTORE")
        self.assertEqual(L.classify({"type": "cut_edit",
                                     "reason": "טייק פסול"}), "RC_TAKE_RESTORE")


# ─────────────────────────────── qa_gates wiring
class TestQaGatesMeasured(unittest.TestCase):
    """P0-10: G6 השווה שתי נגזרות של אותו חישוב."""

    def test_measured_gate_has_a_blocking_branch(self):
        """G6b חייב להיות חוסם כשהמדידה אמינה. שני מסלולי-האזהרה (אין מדידה /
        התאמה נמוכה עם הסחה קטנה) הם במכוון — הם מבדילים בין "נמדד ורע" לבין
        "לא ניתן למדוד", כדי לא לייצר false-block בסרטונים קשים."""
        src = (TOOLS / "qa_gates.py").read_text(encoding="utf-8")
        i = src.index("G6b_captions_measured")
        seg = src[i:src.index("G8_opening_flash")]
        calls = [c for c in seg.split('gate("G6b_captions_measured"')[1:]]
        blocking = [c for c in calls if "hard=False" not in c.split("\n")[0] + c.split("\n")[1]]
        self.assertTrue(blocking, "אין אף מסלול חוסם ב-G6b")
        self.assertIn("score >= a.measured_pass", seg)
        self.assertIn("abs(ms0) < 0.35", seg, "חייבת הבחנה בין רעש ASR להסחה שיטתית")

    def test_pipeline_starts_verify_asr_before_music(self):
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
        self.assertLess(src.index("_verify_thread.start()"), src.index('st.step("music")'),
                        "תמלול האימות חייב להתחיל לפני המוזיקה (על אודיו נקי) וברקע")
        self.assertLess(src.index("_verify_thread.join"), src.index('st.step("qa")'),
                        "חייב להצטרף לפני qa_gates")

    def test_all_gates_run_before_promote(self):
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
        promote = src.index("\n    PENDING.replace(FINAL)")   # הקוד, לא ההערה
        for needle in ('st.step("cut_qa")', 'st.step("caption_safety")',
                       'st.step("canon")', 'st.step("qa")'):
            self.assertLess(src.index(needle), promote,
                            f"{needle} רץ אחרי הקידום ל-FINAL — כלומר לא יכול לחסום")
        self.assertIn("if blockers:", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
