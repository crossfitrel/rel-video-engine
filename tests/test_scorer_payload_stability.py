# -*- coding: utf-8 -*-
"""
רגרסיה: ה-payload של ה-scorer חייב להיות פונקציה של **התוכנית**, לא של הקידוד.

נתפס 31.7.26 — אותה תוכנית עריכה בדיוק, שתי ריצות גימור, שני digests שונים,
ו-`--backend replay` נכשל. הסיבה: `qa_report.json` נכתב מחדש בכל ריצה, וה-
`detail` של `G5_format` מכיל את **גודל הקובץ**. כל בדיקה כאן מזריקה שינוי
שקורה בפועל בין שתי ריצות ומוודאת שה-digest לא זז.
"""
import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import edit_director as ED                       # noqa: E402
from relvid.provider import digest               # noqa: E402


def _report(size_mb, lufs, tp):
    return {"video": "FINAL.mp4", "pass": True, "gates": [
        {"gate": "G1_duration", "pass": True, "hard": True,
         "detail": "50.1s (טווח 20–65)"},
        {"gate": "G4_loudness", "pass": True, "hard": False,
         "detail": f"I={lufs} LUFS, TP={tp}"},
        {"gate": "G5_format", "pass": True, "hard": True,
         "detail": f"1080x1920 @ 30fps · {size_mb}MB · faststart=✓"},
    ]}


VAL = {"n_decisions": 36, "n_cuts": 11, "kept_dur": 50.12, "n_segments": 10,
       "auto_applied": 8, "suggest_only": 3, "ok": True, "hard": []}


class TestScorerSeesThePlanNotTheRender(unittest.TestCase):
    """התיקון בשכבה הנכונה: ה-scorer מדרג תוכנית, ולכן הקלט שלו נגזר
    מהוולידטור — פונקציה טהורה של התוכנית — ולא מקובץ תוצר של ריצה קודמת."""

    def test_the_render_report_does_not_reach_the_scorer_at_all(self):
        with tempfile.TemporaryDirectory() as d:
            W = Path(d)
            (W / "qa_report.json").write_text(
                json.dumps(_report(22.4, -14.5, -0.9)), encoding="utf-8")
            a = ED.qa_snapshot(W, VAL)
            (W / "qa_report.json").write_text(
                json.dumps(_report(99.9, -9.9, -9.9)), encoding="utf-8")
            b = ED.qa_snapshot(W, VAL)
            self.assertEqual(digest("scorer", {"qa": a}), digest("scorer", {"qa": b}))
            self.assertEqual(a["source"], "validator")

    def test_a_different_plan_does_move_the_digest(self):
        """יציבות שמסתירה שינוי אמיתי בתוכנית אינה יציבות."""
        other = dict(VAL, n_cuts=24, kept_dur=47.0)
        self.assertNotEqual(digest("scorer", {"qa": ED.qa_snapshot(Path("/tmp"), VAL)}),
                            digest("scorer", {"qa": ED.qa_snapshot(Path("/tmp"), other)}))

    def test_hard_failures_reach_the_scorer(self):
        bad = dict(VAL, ok=False, hard=["תקציב שקט: 31%"])
        self.assertIn("תקציב שקט: 31%",
                      ED.qa_snapshot(Path("/tmp"), bad)["hard_failures"])


class TestScorerPayloadStability(unittest.TestCase):
    """השכבה הישנה — נשארת כי `_qa_report_snapshot` עדיין משמש לדוחות."""

    def _snap(self, report):
        with tempfile.TemporaryDirectory() as d:
            W = Path(d)
            (W / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False),
                                              encoding="utf-8")
            return ED.qa_snapshot(W)

    def test_encoder_output_size_does_not_move_the_digest(self):
        a = self._snap(_report(22.4, -14.5, -0.9))
        b = self._snap(_report(28.1, -14.5, -0.9))
        self.assertEqual(digest("scorer", {"qa": a}), digest("scorer", {"qa": b}),
                         "גודל הקובץ הזיז את ה-digest — replay יישבר בריצה הבאה")

    def test_measured_loudness_does_not_move_the_digest(self):
        a = self._snap(_report(22.4, -14.5, -0.9))
        b = self._snap(_report(22.4, -14.4, -1.1))
        self.assertEqual(digest("scorer", {"qa": a}), digest("scorer", {"qa": b}))

    def test_a_failing_hard_gate_does_move_the_digest(self):
        """הזרקת הכשל ההפוכה: יציבות שמסתירה כשל אמיתי אינה יציבות."""
        bad = _report(22.4, -14.5, -0.9)
        bad["gates"][0]["pass"] = False
        self.assertNotEqual(digest("scorer", {"qa": self._snap(_report(22.4, -14.5, -0.9))}),
                            digest("scorer", {"qa": self._snap(bad)}))

    def test_gate_names_reach_the_model(self):
        """הבאג השני: הקובץ כותב `gate`, הקוד קרא `name` — שערים בלי שמות."""
        snap = self._snap(_report(22.4, -14.5, -0.9))
        names = [g["name"] for g in snap["gates"]]
        self.assertNotIn(None, names)
        self.assertIn("G5_format", names)

    def test_pass_flag_reaches_the_model(self):
        snap = self._snap(_report(22.4, -14.5, -0.9))
        self.assertTrue(all(g["ok"] is True for g in snap["gates"]))


if __name__ == "__main__":
    unittest.main()
