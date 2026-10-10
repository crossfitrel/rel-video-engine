# -*- coding: utf-8 -*-
"""למידה מ-n=1 — התיקונים של הראל מגיעים לפיילוד של הבמאי, בקובץ יציב.

שני חוקים נבדקים בהזרקה:
1. דטרמיניזם: אותו קלט → אותו קובץ, בית-בבית (יציבות digest של הפאס).
2. קיבעון בתוך פרויקט: הקובץ לא נכתב מחדש בלי --rebuild — תיקון חדש של
   הראל באמצע פרויקט לא משנה את ה-payload באמצע ריצה (חוק ברזל 4).
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))


def _mk_project(work, name, cohort_ct="conversion", brand="rel", events=()):
    d = work / name
    d.mkdir(parents=True)
    (d / "project_manifest.json").write_text(json.dumps(
        {"project_id": f"pid_{name}", "content_type": cohort_ct,
         "brand": brand}), encoding="utf-8")
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    if lines:
        (d / "corrections.jsonl").write_text("\n".join(lines), encoding="utf-8")
    return d


class TestDirectorLessons(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name) / "work"
        self.work.mkdir()
        os.environ["REL_WORK_ROOT"] = str(self.work)
        # מודולים שקוראים את work_root בזמן import — לטעון מחדש אחרי env
        for m in ("director_lessons", "learn_from_edits", "relvid.paths"):
            sys.modules.pop(m, None)
        import director_lessons as DL
        self.DL = DL

    def tearDown(self):
        os.environ.pop("REL_WORK_ROOT", None)
        self._tmp.cleanup()

    def test_patterns_from_same_cohort_only(self):
        _mk_project(self.work, "אחר", events=[
            {"type": "restore_cut", "reason": "שקט מכוון",
             "ts": "2026-08-01 10:00:00"},
            {"type": "restore_cut", "reason": "שקט",
             "ts": "2026-08-01 10:10:00"}])
        _mk_project(self.work, "כהורט-אחר", cohort_ct="value", events=[
            {"type": "add_cut", "ts": "2026-08-01 11:00:00"}])
        proj = _mk_project(self.work, "נוכחי")
        doc = self.DL.build(proj)
        codes = [p["code"] for p in doc["harel_patterns"]]
        self.assertIn("RC_SILENCE_RESTORE", codes)
        self.assertNotIn("RC_MANUAL_ADD", codes)   # cohort אחר — לא נספר
        self.assertTrue(doc["rules"], "הכללים הקבועים חסרים")

    def test_deterministic_and_frozen(self):
        _mk_project(self.work, "אחר", events=[
            {"type": "add_cut", "ts": "2026-08-01 10:00:00"},
            {"type": "add_cut", "ts": "2026-08-01 10:05:00"}])
        proj = _mk_project(self.work, "נוכחי")
        d1 = self.DL.build(proj)
        raw1 = (proj / "lessons_for_director.json").read_text(encoding="utf-8")
        # אירוע חדש נכנס — אבל הקובץ קפוא בלי --rebuild (יציבות בתוך פרויקט)
        other = self.work / "אחר" / "corrections.jsonl"
        with open(other, "a", encoding="utf-8") as f:
            f.write("\n" + json.dumps(
                {"type": "add_cut", "ts": "2026-08-02 10:00:00"}))
        d2 = self.DL.build(proj)
        raw2 = (proj / "lessons_for_director.json").read_text(encoding="utf-8")
        self.assertEqual(raw1, raw2, "הקובץ נכתב מחדש בלי --rebuild")
        self.assertEqual(d1, d2)
        # --rebuild כן מעדכן, וזה מפורש
        d3 = self.DL.build(proj, rebuild=True)
        self.assertNotEqual(d1["harel_patterns"], d3["harel_patterns"])

    def test_no_timestamps_in_output(self):
        proj = _mk_project(self.work, "נוכחי")
        self.DL.build(proj)
        raw = (proj / "lessons_for_director.json").read_text(encoding="utf-8")
        self.assertNotIn("ts", json.loads(raw).get("harel_patterns", [{}])[0]
                         if json.loads(raw).get("harel_patterns") else {})
        for bad in ("built_at", "created_at", "2026-"):
            self.assertNotIn(bad, raw)

    def test_burst_coalescing(self):
        # 5 גרירות תוך 90ש = אירוע אחד, לא חמישה (הלקח מ-v7.3.1)
        _mk_project(self.work, "אחר", events=[
            {"type": "adjust_cut", "ts": f"2026-08-01 10:00:{s:02d}"}
            for s in (0, 10, 20, 30, 40)])
        proj = _mk_project(self.work, "נוכחי")
        doc = self.DL.build(proj)
        adj = [p for p in doc["harel_patterns"]
               if p["code"] == "RC_BOUNDARY_ADJUST"]
        self.assertEqual(adj[0]["n_events"], 1, adj)


if __name__ == "__main__":
    unittest.main()
