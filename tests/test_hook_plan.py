# -*- coding: utf-8 -*-
"""v9.44 — שלב "בניית הוק" (hook_plan / P22) + מגברי ההוק ב-MG (spotlight / then_now).

הזרקת כשל: כל בדיקה כאן נכשלת אם השער מוחלש — P22 שמקבל ריל בלי הצהרה, שמקבל 'פרק 67'
בפתיחה, שמסמן 'פרק כף היד' כהכרזת פרק, שלא מבחין בין ממומן לאורגני, MG2 שלא בודק פנים
בפאנלים של then_now, או attach_freezes שמשאיר then_now עם פאנל ריק."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import hook_plan as hp  # noqa: E402
import motion_build as mb  # noqa: E402
import preflight_critic as pc  # noqa: E402


def mkw(words, manifest=None, plan=None, prov=None):
    W = Path(tempfile.mkdtemp())
    (W / "words_final.json").write_text(json.dumps(
        [{"word": w, "start": s, "end": s + 0.3} for w, s in words], ensure_ascii=False), encoding="utf-8")
    (W / "project_manifest.json").write_text(json.dumps(
        manifest or {"name": "בדיקה", "created_at": "2026-10-09T10:00:00", "dept": "קרוספיט אריאל",
                     "content_type": "value"}, ensure_ascii=False), encoding="utf-8")
    if plan is not None:
        (W / "HOOK_PLAN.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    if prov is not None:
        (W / "FINAL_PROVENANCE.json").write_text(json.dumps(prov), encoding="utf-8")
    return W


GOOD = {"version": 1, "technique": "real_scene", "anchor_type": "scene",
        "t0": "אוריה על הספה עם הטלפון, הראל במטבח", "t1": "'הראל?'", "t2": "'צריך מלפפונים'"}
SCENE = [("הראל?", 0.0), ("כן.", 1.0), ("צריך", 2.4)]


def sev(fs, needle=None):
    return [f["severity"] for f in fs if needle is None or needle in f["detail"]]


class HookPlanFindings(unittest.TestCase):
    def test_stamp_is_checked_against_target_file(self):
        """v10.1: preflight --target FINAL_PENDING.mp4 בודק את ההצהרה מול ה-PENDING, לא מול FINAL הישן."""
        W = mkw(SCENE, plan=dict(GOOD, sheet="HOOK_SHEET.jpg"))
        (W / "HOOK_SHEET.jpg").write_bytes(b"x")
        (W / "FINAL.mp4").write_bytes(b"old")
        (W / "FINAL_PENDING.mp4").write_bytes(b"newer-version")
        hp.cmd_stamp(W, "FINAL.mp4")          # נקשר לגרסה הישנה
        stale = "השתנה אחרי שההוק נבדק"
        self.assertEqual(sev(hp.evaluate(W, measure_video=False, target="FINAL_PENDING.mp4"), stale), ["medium"])
        hp.cmd_stamp(W, "FINAL_PENDING.mp4")
        self.assertEqual(sev(hp.evaluate(W, measure_video=False, target="FINAL_PENDING.mp4"), stale), [])
        self.assertEqual(sev(hp.evaluate(W, measure_video=False), stale), ["medium"])

    def test_no_plan_is_high_for_new_project(self):
        fs = hp.evaluate(mkw(SCENE), measure_video=False)
        self.assertIn("high", sev(fs, "HOOK_PLAN"))

    def test_no_plan_is_medium_for_legacy_project(self):
        W = mkw(SCENE, manifest={"name": "x", "created_at": "2026-09-01T10:00:00"})
        self.assertEqual(sev(hp.evaluate(W, measure_video=False), "HOOK_PLAN"), ["medium"])

    def test_declared_anchor_without_sheet_is_only_medium(self):
        fs = hp.evaluate(mkw(SCENE, plan=GOOD), measure_video=False)
        self.assertNotIn("high", sev(fs))
        self.assertIn("medium", sev(fs, "גיליון"))

    def test_missing_anchor_is_high(self):
        bad = dict(GOOD, anchor_type="principle", t0="")
        self.assertIn("high", sev(hp.evaluate(mkw(SCENE, plan=bad), measure_video=False), "עוגן"))

    def test_episode_card_in_opening_is_high(self):
        W = mkw([("פרק", 0.1), ("67", 0.5), ("של", 0.9), ("מדברים", 1.2)], plan=GOOD)
        self.assertIn("high", sev(hp.evaluate(W, measure_video=False), "פרק"))

    def test_wrist_is_not_an_episode(self):
        W = mkw([("פרק", 0.1), ("כף", 0.5), ("היד", 0.9)], plan=GOOD)
        self.assertEqual(sev(hp.evaluate(W, measure_video=False), "הכרזת פרק"), [])

    def test_geo_address_organic_medium_paid_clean(self):
        geo = [("תושבי", 0.0), ("אריאל", 0.4), ("והסביבה", 0.8)]
        self.assertIn("medium", sev(hp.evaluate(mkw(geo, plan=GOOD), measure_video=False), "גאוגרפית"))
        paid = mkw(geo, plan=GOOD, manifest={"name": "ממומן-ת1-תושבים", "created_at": "2026-10-09"})
        self.assertEqual(sev(hp.evaluate(paid, measure_video=False), "גאוגרפית"), [])

    def test_fixed_intro_before_hook_medium_and_shifts_words(self):
        W = mkw(SCENE, plan=GOOD, prov={"intro_offset_sec": 10.13})
        fs = hp.evaluate(W, measure_video=False)
        self.assertIn("medium", sev(fs, "פתיח קבוע"))
        self.assertEqual(hp.opening_words(W), [])      # בגוף אין מילים ב-2ש הראשונות של ה-FINAL

    def test_full_graphic_card_first_is_high(self):
        W = mkw(SCENE, plan=GOOD)
        (W / "motion_plan.json").write_text(json.dumps({"events": [{"id": "s", "type": "section", "start": 0.0, "end": 1.2}]}))
        self.assertIn("high", sev(hp.evaluate(W, measure_video=False), "מסך גרפי"))

    def test_toolbox_rows_cover_all_ten_content_types(self):
        tb = hp.toolbox()
        self.assertEqual(len(tb["content_types"]), 10)
        for row in tb["content_types"].values():
            self.assertTrue(2 <= len(row["techniques"]) <= 4)
            for t in row["techniques"]:
                self.assertIn(t, tb["techniques"])

    def test_row_mapping(self):
        W = mkw(SCENE, manifest={"name": "מאסל-מן-סיבוב-כתף", "dept": "שיקום בתנועה", "created_at": "2026-10-09"})
        self.assertEqual(hp.row_for(W), "שיקום/אנטומיה")
        W = mkw(SCENE, manifest={"name": "פיתוח אפליקצית קניות", "dept": "הראל חיון", "created_at": "2026-10-09"})
        self.assertEqual(hp.row_for(W), "אישי-מערכת שבניתי")

    def test_preflight_wires_p22(self):
        f = []
        pc.check_hook_anchor(f, mkw(SCENE))
        self.assertTrue(any(x["check"] == "P22_hook_anchor" and x["severity"] == "high" for x in f))


class HookTemplates(unittest.TestCase):
    def test_types_registered(self):
        self.assertIn("spotlight", mb.TYPES)
        self.assertIn("then_now", mb.TYPES)
        js = (HERE.parent / "tools" / "motion" / "templates" / "hook.js").read_text(encoding="utf-8")
        self.assertIn("REL.define('spotlight'", js)
        self.assertIn("REL.define('then_now'", js)

    def test_then_now_labels_go_through_mg4(self):
        p = {"duration": 5, "tail": 0, "facts": [], "_path": "x", "events": [
            {"id": "t", "type": "then_now", "start": 0, "end": 2, "label_a": "תכננתי", "label_b": "המצאה"}]}
        g = mb.gate_text_fidelity(p, [{"word": "תכננתי", "start": 0, "end": .3}])
        self.assertFalse(g["ok"])
        self.assertIn("המצאה", g["detail"])

    def test_then_now_without_base_is_dropped_not_black(self):
        p = {"duration": 5, "events": [{"id": "t", "type": "then_now", "start": 0, "end": 2,
                                        "freeze_a_at": 1.0, "freeze_b_at": 3.0}]}
        mb.attach_freezes(p, None)
        self.assertEqual(p["events"], [])

    def test_then_now_face_gate_reads_panel_frames(self):
        # פנים בפריים הקפוא של פאנל b (y 400-700 בפריים המלא, focal 0%) ⇒ בפאנל: 967+400..967+700
        p = {"events": [{"id": "t", "type": "then_now", "start": 0, "end": 2, "freeze_a_at": 1.0,
                         "freeze_b_at": 3.0, "focal_a": "50% 0%", "focal_b": "50% 0%"}]}
        m = {"events": [{"id": "t", "full": True, "samples": [{"t": 1.0, "boxes": [
            {"text": "סיימת", "x0": 400, "x1": 700, "y0": 1400, "y1": 1500}]}]}]}
        face = [[400 / 1080, 400 / 1920, 700 / 1080, 700 / 1920]]
        det = lambda v, t: (face, "fake") if t > 2 else ([], "fake")
        g = mb.gate_faces("x.mp4", p, m, detect=det, dur=10.0)
        self.assertFalse(g["ok"])
        self.assertIn("/b", g["detail"])
        det2 = lambda v, t: ([], "fake")
        self.assertTrue(mb.gate_faces("x.mp4", p, m, detect=det2, dur=10.0)["ok"])


if __name__ == "__main__":
    unittest.main()
