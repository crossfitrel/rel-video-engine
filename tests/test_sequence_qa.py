"""‏QA של רצף המצע (v9.8) — דקדוק חזותי, לא רק כיסוי.

הרקע: `coverage_pct` ו-`broll_seam_qa` שואלים "יש בירול?" ו"הוא חושף את
הדובר?". אף אחד מהם לא שואל אם הרצף **נקרא טוב**. נמדד על האופן-ג'ים:
‏11 שוטים בינוניים ברצף, אפס שוטים רחבים — עובר את כל השערים הקיימים.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import broll_sequence_qa as SQ  # noqa: E402


def _plan(shots, cats=None, cameras=None):
    cats = cats or [f"c{i}" for i in range(len(shots))]
    cameras = cameras or ["static"] * len(shots)
    plan = {"plan": []}
    for i, s in enumerate(shots):
        plan["plan"].append({"role": "bed",
                             "path": f"/x/{cats[i]}/clip{i}.mp4"})
    SQ.VM_LOOKUP = None
    return plan, shots, cameras


class TestRunLength(unittest.TestCase):
    def setUp(self):
        self._orig = SQ.VM.lookup

    def tearDown(self):
        SQ.VM.lookup = self._orig

    def _run(self, shots, cats=None, cameras=None):
        plan, shots, cameras = _plan(shots, cats, cameras)
        table = {}
        for i, p in enumerate(plan["plan"]):
            table[p["path"]] = {"shot": shots[i], "crowding": "solo",
                                "camera": cameras[i]}
        SQ.VM.lookup = lambda path: table.get(path)
        return SQ.analyze(plan, with_brightness=False)

    def test_four_mediums_in_a_row_is_flagged(self):
        r = self._run(["medium"] * 4)
        self.assertTrue([i for i in r["issues"] if i["check"] == "shot_variety"])

    def test_three_is_allowed(self):
        r = self._run(["medium"] * 3)
        self.assertEqual([i for i in r["issues"] if i["check"] == "shot_variety"], [])

    def test_one_issue_per_run_not_per_clip(self):
        """דיווח שמתנפח עם אורך הרצף מסתיר את גודל הבעיה."""
        r = self._run(["medium"] * 11)
        hits = [i for i in r["issues"] if i["check"] == "shot_variety"]
        self.assertEqual(len(hits), 1, f"דווח {len(hits)} פעמים על רצף אחד")
        self.assertEqual(hits[0]["run"], 11)

    def test_variety_passes(self):
        r = self._run(["wide", "medium", "close", "medium", "wide"])
        self.assertEqual([i for i in r["issues"] if i["check"] == "shot_variety"], [])

    def test_same_category_back_to_back_is_flagged(self):
        r = self._run(["wide", "medium"], cats=["כוח", "כוח"])
        self.assertTrue([i for i in r["issues"] if i["check"] == "movement_repeat"])

    def test_uniform_crowding_is_flagged(self):
        r = self._run(["wide", "medium", "close", "wide", "medium"])
        self.assertTrue([i for i in r["issues"]
                         if i["check"] == "crowding_variety"])

    def test_missing_vision_does_not_crash(self):
        plan, _, _ = _plan(["medium", "medium"])
        SQ.VM.lookup = lambda path: None
        r = SQ.analyze(plan, with_brightness=False)
        self.assertEqual(r["n_bed"], 2)

    def test_anchor_is_not_part_of_the_bed(self):
        plan = {"plan": [{"role": "anchor", "path": "/x/a/1.mp4"},
                         {"role": "bed", "path": "/x/b/2.mp4"}]}
        SQ.VM.lookup = lambda path: {"shot": "medium", "crowding": "solo",
                                     "camera": "static"}
        self.assertEqual(SQ.analyze(plan, with_brightness=False)["n_bed"], 1)


if __name__ == "__main__":
    unittest.main()
