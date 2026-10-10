#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_changelog — יומן השינויים פר-גרסה (v9.15).

מה נבדק כאן, ולמה דווקא זה:
  * **מיפוי טיימקוד בין צירי גרסאות** — הליבה של הפיצ'ר. הערה על 0:14 בגרסה
    ישנה חייבת להצביע על אותו **תוכן** בגרסה החדשה, גם אחרי שנחתכו שניות
    לפניה. טעות כאן שולחת את הראל לנקודה הלא נכונה — כלומר גרועה מכלום.
  * **נקודה שנחתכה מסומנת cut_out** ולא מוצגת כטיימקוד תקין.
  * **fixes=[] ≠ fixes חסר** — "לא תוקנה אף הערה" מול "לא ידוע".
  * **סבב הבדיקה ממזג קטעים חופפים** — אחרת קפיצה-ניגון-קפיצה על אותה שנייה.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

from relvid import changelog as cl        # noqa: E402


def tl(keeps, speed=1.0, total=100.0):
    return {"keeps": [{"start": s, "end": e} for s, e in keeps],
            "speed": speed, "total": total, "source": "test"}


class TestAxisMapping(unittest.TestCase):
    def test_out_to_src_walks_keeps(self):
        t = tl([(0, 10), (20, 30)])
        self.assertAlmostEqual(cl.out_to_src(5, t), 5.0, places=2)
        # 12ש בפלט = 10ש מהקטע הראשון + 2ש מהשני ⇒ 22ש במקור
        self.assertAlmostEqual(cl.out_to_src(12, t), 22.0, places=2)

    def test_speed_compresses_output_axis(self):
        t = tl([(0, 22)], speed=1.1)
        # 10ש בפלט ב-1.1x = 11ש של מקור
        self.assertAlmostEqual(cl.out_to_src(10, t), 11.0, places=2)
        out, st = cl.src_to_out(11, t)
        self.assertEqual(st, "exact")
        self.assertAlmostEqual(out, 10.0, places=2)

    def test_roundtrip_is_stable(self):
        t = tl([(0, 10), (20, 30), (40, 55)], speed=1.15)
        for x in (0.5, 4.0, 9.9, 12.3, 25.0):
            src = cl.out_to_src(x, t)
            back, st = cl.src_to_out(src, t)
            self.assertEqual(st, "exact")
            self.assertAlmostEqual(back, x, places=1)

    def test_point_removed_in_new_version_is_cut_out(self):
        new = tl([(0, 10), (20, 30)])
        out, st = cl.src_to_out(15.0, new)      # 10-20 נחתך בגרסה החדשה
        self.assertEqual(st, "cut_out")
        self.assertIsNotNone(out)

    def test_note_shifts_when_seconds_are_cut_before_it(self):
        """ההערה נכתבה על 0:14 בגרסה 4. בגרסה 5 נחתכו 3ש לפני הנקודה הזו —
        אותו תוכן יושב עכשיו ב-0:11, וזה מה שהמיפוי חייב להחזיר."""
        old = tl([(0, 60)])                      # גרסה 4: הכל
        new = tl([(0, 5), (8, 60)])              # גרסה 5: נחתך 5-8 (3ש)
        m = cl.map_time(14.0, old, new, on_final=True)
        self.assertEqual(m["status"], "exact")
        self.assertAlmostEqual(m["t"], 11.0, places=1)

    def test_unknown_timeline_never_invents_a_timecode(self):
        m = cl.map_time(14.0, None, None, on_final=True)
        self.assertIsNone(m["t"])
        self.assertEqual(m["status"], "unknown")

    def test_input_axis_note_skips_the_first_conversion(self):
        new = tl([(0, 5), (8, 60)])
        m = cl.map_time(14.0, None, new, on_final=False)   # הערה על ציר INPUT
        self.assertEqual(m["status"], "exact")
        self.assertAlmostEqual(m["t"], 11.0, places=1)


class TestReviewPlan(unittest.TestCase):
    def test_overlapping_spots_merge(self):
        v = {"items": [{"item_id": "a", "t": 10.0}, {"item_id": "b", "t": 12.0},
                       {"item_id": "c", "t": 40.0}, {"item_id": "d", "t": None}]}
        plan = cl.review_plan(v, pad_before=2.5, pad_after=2.5)
        self.assertEqual(len(plan["spots"]), 2)
        self.assertEqual(plan["spots"][0]["item_ids"], ["a", "b"])
        self.assertLess(plan["covered_secs"], 20)     # במקום סרטון שלם


class TestBuildOnDisk(unittest.TestCase):
    """פרויקט אמיתי על הדיסק — כולל artifacts, comments ו-revisions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = Path(self.tmp.name) / "proj"
        (self.w / "artifacts").mkdir(parents=True)
        (self.w / "revisions").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _rev(self, rid, seq, keeps, speed=1.0):
        (self.w / "revisions" / f"rev_{seq:04d}_{rid.replace('rev_', '')}.json").write_text(
            json.dumps({"revision_id": rid, "seq": seq, "edl": {
                "total_dur": 60.0,
                "keep_segments": [{"start": s, "end": e} for s, e in keeps],
                "review": {"cuts": [], "speed": speed}}}, ensure_ascii=False),
            encoding="utf-8")
        idx_p = self.w / "revisions" / "index.json"
        idx = json.loads(idx_p.read_text()) if idx_p.exists() else {"head": None, "order": []}
        idx["order"].append(rid)
        idx["head"] = rid
        idx_p.write_text(json.dumps(idx), encoding="utf-8")

    def _art(self, aid, version, created_at, rev, **kw):
        d = self.w / "artifacts" / aid
        d.mkdir()
        (d / "FINAL.mp4").write_bytes(b"x" * 10)
        rec = {"artifact_id": aid, "version": version, "created_at": created_at,
               "revision_id": rev, "file": "FINAL.mp4", "duration": kw.pop("duration", 50.0),
               "size_bytes": 10, "checksum": "sha256:" + aid}
        rec.update(kw)
        (d / "artifact.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    def _comments(self, rows):
        (self.w / "comments.json").write_text(json.dumps(rows, ensure_ascii=False),
                                              encoding="utf-8")

    def test_stamped_fixes_win_and_are_marked_certain(self):
        self._rev("rev_aaa", 1, [(0, 60)])
        self._comments([{"comment_id": "c_1", "text": "המוזיקה רועשת", "status": "resolved",
                         "category": "audio", "created_at": "2026-08-01 10:00:00",
                         "updated_at": "2026-08-01 11:00:00", "time_start": 12.0,
                         "on_final": True, "resolved_revision_id": "rev_aaa"}])
        self._art("art_1", 1, "2026-08-01 09:00:00", "rev_aaa", fixes=[])
        self._art("art_2", 2, "2026-08-01 12:00:00", "rev_aaa",
                  fixes=cl.stamp_fixes(self.w, since_ts="2026-08-01 09:00:00"))
        out = cl.build(self.w)
        v1, v2 = out["versions"]
        self.assertEqual([i for i in v1["items"] if i["kind"] == "comment"], [])
        notes = [i for i in v2["items"] if i["kind"] == "comment"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["comment_id"], "c_1")
        self.assertEqual(notes[0]["source"], "רשום בזמן היצירה")
        self.assertEqual(notes[0]["confidence"], "ודאי")
        self.assertEqual(notes[0]["t_status"], "exact")

    def test_legacy_versions_are_inferred_and_labelled(self):
        self._rev("rev_aaa", 1, [(0, 60)])
        self._rev("rev_bbb", 2, [(0, 20), (25, 60)])
        self._comments([{"comment_id": "c_9", "text": "תוריד את הבירול", "status": "resolved",
                         "category": "broll", "created_at": "2026-07-29 17:00:00",
                         "updated_at": "2026-07-30 01:00:00", "time_start": 30.0,
                         "on_final": True, "resolved_revision_id": "rev_bbb"}])
        self._art("art_1", 1, "2026-07-31 11:58:49", "rev_aaa")
        self._art("art_2", 2, "2026-08-01 01:44:01", "rev_bbb")
        out = cl.build(self.w)
        v2 = out["versions"][1]
        notes = [i for i in v2["items"] if i["kind"] == "comment"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["source"], "הוסק בדיעבד")
        # 30ש בפלט של גרסה 1 (ציר מלא) = 30ש במקור; בגרסה 2 נחתך 20-25 ⇒ 25ש
        self.assertAlmostEqual(notes[0]["t"], 25.0, places=1)

    def test_empty_stamp_is_not_the_same_as_missing_stamp(self):
        self._rev("rev_aaa", 1, [(0, 60)])
        self._comments([{"comment_id": "c_x", "text": "משהו", "status": "resolved",
                         "created_at": "2026-08-01 10:00:00",
                         "updated_at": "2026-08-01 10:30:00", "time_start": 5.0,
                         "on_final": True, "resolved_revision_id": "rev_aaa"}])
        self._art("art_1", 1, "2026-08-01 11:00:00", "rev_aaa", fixes=[])
        out = cl.build(self.w)
        self.assertEqual([i for i in out["versions"][0]["items"] if i["kind"] == "comment"], [])
        # ההערה לא נעלמה בשקט: הגרסה חתומה כ"בלי תיקונים", ולכן ההערה מדווחת
        # כלא-משויכת — ולא כאילו היא נכנסה לגרסה הזו.
        self.assertEqual([r["comment_id"] for r in out["unassigned"]], ["c_x"])
        self.assertEqual(out["pending_render"], [])

    def test_fix_after_the_last_version_is_pending_render(self):
        self._rev("rev_aaa", 1, [(0, 60)])
        self._comments([{"comment_id": "c_new", "text": "תיקון טרי", "status": "resolved",
                         "created_at": "2026-08-02 10:00:00",
                         "updated_at": "2026-08-02 10:30:00", "time_start": 5.0,
                         "on_final": True, "resolved_revision_id": "rev_aaa"}])
        self._art("art_1", 1, "2026-08-01 09:00:00", "rev_aaa", fixes=[])
        out = cl.build(self.w)
        self.assertEqual([r["comment_id"] for r in out["pending_render"]], ["c_new"])

    def test_checks_persist_and_reach_the_build(self):
        self._rev("rev_aaa", 1, [(0, 60)])
        self._comments([{"comment_id": "c_1", "text": "נו", "status": "resolved",
                         "created_at": "2026-08-01 10:00:00",
                         "updated_at": "2026-08-01 10:30:00", "time_start": 3.0,
                         "on_final": True, "resolved_revision_id": "rev_aaa"}])
        self._art("art_1", 1, "2026-08-01 09:00:00", "rev_aaa", fixes=[])
        self._art("art_2", 2, "2026-08-01 12:00:00", "rev_aaa",
                  fixes=cl.stamp_fixes(self.w, since_ts="2026-08-01 09:00:00"))
        cl.set_check(self.w, "art_2", "cmt_c_1", "ok", note="נבדק")
        out = cl.build(self.w, artifact_id="art_2")
        it = [i for i in out["versions"][0]["items"] if i["item_id"] == "cmt_c_1"][0]
        self.assertEqual(it["check"]["state"], "ok")
        self.assertEqual(out["versions"][0]["counts"]["checked"], 1)

    def test_mechanical_diff_reports_music_and_duration(self):
        self._rev("rev_aaa", 1, [(0, 60)])
        self._comments([])
        self._art("art_1", 1, "2026-08-01 09:00:00", "rev_aaa", fixes=[],
                  duration=50.0, music="a.mp3")
        self._art("art_2", 2, "2026-08-01 12:00:00", "rev_aaa", fixes=[],
                  duration=47.0, music="b.mp3")
        out = cl.build(self.w)
        ids = {i["item_id"] for i in out["versions"][1]["items"]}
        self.assertIn("mech_duration", ids)
        self.assertIn("mech_music", ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
