#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
בדיקות שכבת ה-API של מרכז הגרסאות (v9.4) — דרך אפליקציית הרוויו עצמה.
=====================================================================
לא מספיק שהמודול "מוגדר": הבדיקות כאן מריצות את server.py מול תיקיית עבודה
זמנית (REL_WORK_ROOT) ומוודאות שהאפליקציה באמת מגישה את הגרסאות, שהברירת
מחדל היא המאושרת, ושגרסה מאושרת נשארת נגישה אחרי יצירת מועמד חדש.
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
APP = HERE.parent / "review-app"
sys.path.insert(0, str(TOOLS))

from relvid import atomic_write_json                     # noqa: E402


def build_project(root, name="פרויקט-API"):
    d = Path(root) / name
    d.mkdir(parents=True, exist_ok=True)
    atomic_write_json(d / "edl.json", {
        "total_dur": 60.0, "kept_dur": 55.0,
        "keep_segments": [{"start": 0.0, "end": 55.0}],
        "review": {"cuts": [], "hook_move": None, "speed": 1.0}})
    atomic_write_json(d / "project_manifest.json", {"project_id": "prj_api", "name": name})
    (d / "INPUT.mp4").write_bytes(b"IN" * 5000)
    (d / "whisper_raw.json").write_text("[]", encoding="utf-8")
    return d


@unittest.skipUnless(importlib.util.find_spec("flask"), "flask לא מותקן בפייתון הזה")
class TestArtifactsAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["REL_WORK_ROOT"] = self.tmp
        self.d = build_project(self.tmp)
        sys.path.insert(0, str(APP))
        for m in ("server",):
            sys.modules.pop(m, None)
        import server
        importlib.reload(server)
        self.server = server
        self.c = server.app.test_client()
        from relvid import artifacts as art
        self.art = art

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("REL_WORK_ROOT", None)

    def _final(self, payload):
        f = self.d / "FINAL.mp4"
        if f.exists():
            os.chmod(f, 0o644)
            f.replace(self.d / f"FINAL_prev_{os.urandom(3).hex()}.mp4")
        f.write_bytes(payload)
        return f

    def test_api_lists_and_serves_every_version(self):
        ids = []
        for i in range(5):
            self._final(f"V{i}".encode() * 4000)
            ids.append(self.art.create_artifact(self.d, run_id=f"run_{i}")["artifact_id"])
        r = self.c.get(f"/api/artifacts/{self.d.name}")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual(len(j["artifacts"]), 5)
        for i, aid in enumerate(ids):
            m = self.c.get(f"/artifact-media/{self.d.name}/{aid}")
            self.assertEqual(m.status_code, 200, f"גרסה {i} לא מוגשת ע\"י האפליקציה")
            self.assertEqual(m.data, f"V{i}".encode() * 4000)

    def test_approved_survives_new_candidate_and_failed_run(self):
        """ההוכחה המרכזית: מאשרים גרסה, מריצים עוד ריצה מוצלחת ואז ריצה כושלת —
        הגרסה המאושרת עדיין מוצגת כברירת מחדל ועדיין ניתנת לצפייה."""
        self._final(b"APPROVED-ONE" * 3000)
        a1 = self.art.create_artifact(self.d, run_id="run_1")["artifact_id"]
        r = self.c.post(f"/api/artifacts/{self.d.name}/{a1}/approve")
        self.assertTrue(r.get_json()["ok"])

        self._final(b"NEW-CANDIDATE" * 3000)          # ריצה מוצלחת נוספת
        a2 = self.art.create_artifact(self.d, run_id="run_2")["artifact_id"]
        atomic_write_json(self.d / "finish_status.json",
                          {"state": "failed", "detail": "gate חוסם"})   # ריצה כושלת

        j = self.c.get(f"/api/artifacts/{self.d.name}").get_json()
        self.assertEqual(j["display"]["artifact_id"], a1)
        self.assertTrue(j["display"]["is_approved"])
        self.assertEqual(j["display"]["newer_count"], 1)
        self.assertEqual(j["pointers"]["approved_final"], a1)
        m = self.c.get(f"/artifact-media/{self.d.name}/{a1}")
        self.assertEqual(m.status_code, 200)
        self.assertEqual(m.data, b"APPROVED-ONE" * 3000,
                         "הגרסה המאושרת השתנתה או נעלמה")
        self.assertEqual(self.c.get(f"/artifact-media/{self.d.name}/{a2}").data,
                         b"NEW-CANDIDATE" * 3000)

    def test_project_endpoint_exposes_display_target(self):
        self._final(b"P" * 4000)
        aid = self.art.create_artifact(self.d)["artifact_id"]
        j = self.c.get(f"/api/project/{self.d.name}").get_json()
        self.assertEqual(j["artifacts"]["count"], 1)
        self.assertEqual(j["artifacts"]["display"]["artifact_id"], aid)
        self.assertFalse(j["artifacts"]["display"]["is_approved"],
                         "מועמד לא-מאושר הוצג כמאושר")

    def test_damaged_version_cannot_be_approved_or_activated(self):
        self._final(b"BREAKME" * 3000)
        aid = self.art.create_artifact(self.d)["artifact_id"]
        f = self.art.artifact_final(self.d, aid)
        os.chmod(f, 0o644)
        f.unlink()
        for act in ("approve", "activate"):
            r = self.c.post(f"/api/artifacts/{self.d.name}/{aid}/{act}")
            self.assertEqual(r.status_code, 409, f"{act} על גרסה פגומה לא נחסם")
        self.assertEqual(self.c.get(f"/artifact-media/{self.d.name}/{aid}").status_code, 404)

    def test_comment_carries_and_resolves_its_own_version(self):
        self._final(b"C1" * 4000)
        a1 = self.art.create_artifact(self.d)["artifact_id"]
        r = self.c.post(f"/api/comments/{self.d.name}",
                        json={"text": "לתקן את הסיום", "on_final": True,
                              "time_start": 12.0, "artifact_id": a1})
        c = r.get_json()["comment"]
        self.assertEqual(c["artifact_id"], a1)
        self._final(b"C2" * 4000)
        self.art.create_artifact(self.d)
        j = self.c.get(f"/api/project/{self.d.name}").get_json()
        ref = j["comments"][-1]["artifact_ref"]
        self.assertEqual(ref["artifact_id"], a1)
        self.assertTrue(ref["resolved"])

    def test_compare_two_versions(self):
        self._final(b"X" * 4000)
        a1 = self.art.create_artifact(self.d)["artifact_id"]
        self._final(b"Y" * 9000)
        a2 = self.art.create_artifact(self.d)["artifact_id"]
        j = self.c.get(f"/api/artifacts/{self.d.name}/compare?a={a1}&b={a2}").get_json()
        self.assertTrue(j["ok"])
        self.assertEqual(j["diff"]["version"], [1, 2])
        self.assertFalse(j["diff"]["identical_content"])

    def test_activate_swaps_live_final_without_losing_anything(self):
        self._final(b"OLD" * 4000)
        a1 = self.art.create_artifact(self.d)["artifact_id"]
        self._final(b"NEWER" * 4000)
        a2 = self.art.create_artifact(self.d)["artifact_id"]
        r = self.c.post(f"/api/artifacts/{self.d.name}/{a1}/activate")
        self.assertTrue(r.get_json()["ok"])
        self.assertEqual((self.d / "FINAL.mp4").read_bytes(), b"OLD" * 4000)
        self.assertEqual(self.c.get(f"/artifact-media/{self.d.name}/{a2}").data,
                         b"NEWER" * 4000, "הגרסה שהוחלפה אבדה")


if __name__ == "__main__":
    unittest.main(verbosity=2)
