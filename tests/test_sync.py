#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_sync — v7.7: סנכרון ציר האפליקציה ↔ מה שנחתך בפועל ↔ FINAL (הראל 25.7).
מכסה את הבאג המדווח: עריכה בצ'אט נגעה ב-keep_segments, review.cuts נשאר מאחור,
והאפליקציה הציגה את הגרסה הקודמת.
"""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

from relvid import atomic_write_json, read_json                        # noqa: E402
from relvid import sync as sync_mod                                    # noqa: E402
from relvid.edl_utils import derive_keep                               # noqa: E402


def make_workdir(tmp, name="פרויקט-סנכרון"):
    d = Path(tmp) / name
    d.mkdir(parents=True, exist_ok=True)
    edl = {
        "total_dur": 60.0, "kept_dur": 50.0,
        "keep_segments": [{"start": 0.0, "end": 10.0}, {"start": 20.0, "end": 60.0}],
        "auto_cuts": [{"start": 10.0, "end": 20.0, "reason": "שקט"}],
        "manual_review_cuts": [],
        "review": {"cuts": [{"start": 10.0, "end": 20.0, "reason": "שקט",
                             "source": "auto", "active": True}],
                   "hook_move": None, "speed": 1.0},
    }
    atomic_write_json(d / "edl.json", edl)
    (d / "INPUT.mp4").write_bytes(b"x" * 16)
    return d


class TestSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = make_workdir(self.tmp)

    def test_no_drift_on_consistent_edl(self):
        r = sync_mod.reconcile_edl(self.d)
        self.assertTrue(r["ok"])
        self.assertFalse(r["changed"])
        self.assertTrue(sync_mod.edl_drift(read_json(self.d / "edl.json"))["consistent"])

    def test_chat_edit_to_keep_segments_is_detected_and_healed(self):
        """עריכה בצ'אט: keep_segments התקצר, review.cuts לא — ואז ריפוי."""
        edl = read_json(self.d / "edl.json")
        edl["keep_segments"] = [{"start": 0.0, "end": 8.0}, {"start": 25.0, "end": 55.0}]
        edl["kept_dur"] = 38.0
        atomic_write_json(self.d / "edl.json", edl)

        drift = sync_mod.edl_drift(read_json(self.d / "edl.json"))
        self.assertFalse(drift["consistent"])
        self.assertEqual(drift["kept_dur_disk"], 38.0)
        self.assertEqual(drift["kept_dur_from_review"], 50.0)

        r = sync_mod.reconcile_edl(self.d, actor="claude")
        self.assertTrue(r["ok"] and r["changed"])
        self.assertIsNotNone(r["revision_id"])

        edl2 = read_json(self.d / "edl.json")
        self.assertTrue(sync_mod.edl_drift(edl2)["consistent"])
        # round-trip: הציר החדש מייצר בדיוק את keep_segments שנחתכו
        back = derive_keep(60.0, edl2["review"]["cuts"], None)
        self.assertTrue(sync_mod.keeps_equal(back, edl2["keep_segments"]))
        self.assertEqual(edl2["kept_dur"], 38.0)

    def test_cuts_from_keeps_roundtrip_with_hook_move(self):
        keeps = [{"start": 30.0, "end": 35.0}, {"start": 0.0, "end": 10.0},
                 {"start": 20.0, "end": 30.0}, {"start": 35.0, "end": 60.0}]
        hook = {"start": 30.0, "end": 35.0}
        cuts = sync_mod.cuts_from_keeps(60.0, keeps)
        back = derive_keep(60.0, cuts, hook)
        self.assertTrue(sync_mod.keeps_equal(back, keeps))
        self.assertAlmostEqual(back[0]["start"], 30.0, places=2)   # Hook נשאר בפתיחה

    def test_dry_run_does_not_write(self):
        edl = read_json(self.d / "edl.json")
        edl["keep_segments"] = [{"start": 0.0, "end": 5.0}]
        atomic_write_json(self.d / "edl.json", edl)
        before = read_json(self.d / "edl.json")["review"]["cuts"]
        r = sync_mod.reconcile_edl(self.d, dry_run=True)
        self.assertTrue(r["ok"])
        self.assertFalse(r["changed"])
        self.assertEqual(read_json(self.d / "edl.json")["review"]["cuts"], before)

    def test_tighten_trims_mapped_to_source_axis(self):
        """tight_keeps בציר EXPORT → מה שההידוק הוריד בציר המקור."""
        edl = read_json(self.d / "edl.json")
        # EXPORT = 0-10 (מקור 0-10) + 10-50 (מקור 20-60)
        atomic_write_json(self.d / "tight_keeps.json",
                          [{"start": 0.0, "end": 9.0}, {"start": 10.0, "end": 49.0}])
        trims = sync_mod.tighten_trims_in_source(edl, read_json(self.d / "tight_keeps.json"))
        self.assertAlmostEqual(sync_mod.keeps_dur(trims), 2.0, places=2)
        self.assertTrue(any(abs(t["start"] - 9.0) < 0.05 for t in trims))
        self.assertTrue(any(abs(t["end"] - 60.0) < 0.05 for t in trims))

    def test_provenance_and_status_lifecycle(self):
        self.assertEqual(sync_mod.sync_status(self.d)["state"], "no_final")
        (self.d / "FINAL.mp4").write_bytes(b"final" * 100)
        self.assertEqual(sync_mod.sync_status(self.d)["state"], "no_provenance")

        sync_mod.write_provenance(self.d, run_id="run_test")
        st = sync_mod.sync_status(self.d)
        self.assertEqual(st["state"], "in_sync")
        self.assertEqual(sync_mod.sync_badge(self.d), "in_sync")

        # עריכה אחרי הגימור → הציר חדש מה-FINAL
        edl = read_json(self.d / "edl.json")
        edl["review"]["cuts"][0]["end"] = 22.0
        edl["keep_segments"] = derive_keep(60.0, edl["review"]["cuts"], None)
        edl["kept_dur"] = sync_mod.keeps_dur(edl["keep_segments"])
        atomic_write_json(self.d / "edl.json", edl)
        self.assertEqual(sync_mod.sync_status(self.d)["state"], "edl_ahead")

    def test_final_replaced_outside_pipeline_invalidates_provenance(self):
        (self.d / "FINAL.mp4").write_bytes(b"a" * 100)
        sync_mod.write_provenance(self.d)
        (self.d / "FINAL.mp4").write_bytes(b"b" * 5000)
        self.assertEqual(sync_mod.sync_status(self.d)["state"], "final_ahead")


if __name__ == "__main__":
    unittest.main()
