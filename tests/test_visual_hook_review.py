#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_visual_hook_review.py — העדפות, נעילה, אישור, עבודת תצוגה, artifacts ולמידה (11.9.26).

כל הבדיקות על תיקיות זמניות עם REL_WORK_ROOT מבודד — אף פריט Monday/Metricool
אמיתי, אף פרויקט אמיתי ושום endpoint פרסום.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
TOOLS = SYSDIR / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from relvid import visual_hook as VH           # noqa: E402
from relvid import registry as REG             # noqa: E402
from relvid import runner as RUNNER            # noqa: E402
from relvid import artifacts as ART            # noqa: E402

try:
    import flask  # noqa: F401
    HAS_FLASK = True
except Exception:
    HAS_FLASK = False
try:
    import numpy  # noqa: F401
    import cv2    # noqa: F401
    HAS_CV = True
except Exception:
    HAS_CV = False

Z = "sha256:" + "0" * 64


def write(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8") if not isinstance(obj, str) \
        else p.write_text(obj, encoding="utf-8")


def mini_project(w: Path, pid="prj_vhreview"):
    w.mkdir(parents=True, exist_ok=True)
    write(w / "project_manifest.json", {"project_id": pid, "name": w.name, "content_type": "value",
                                        "brand": "rel", "finish_prefs": {"music": {"track_auto": "x.mp3"}}})
    write(w / "edl.json", {"total_dur": 10.0, "keep_segments": [{"start": 0.0, "end": 10.0}],
                           "review": {"cuts": [], "hook_move": None, "speed": 1.0}})
    return w


class TestPrefs(unittest.TestCase):
    def test_roundtrip_preserves_other_groups(self):
        with tempfile.TemporaryDirectory() as t:
            w = mini_project(Path(t) / "p")
            m = REG.set_finish_prefs(w, {"visual_hook": {"mode": "shadow", "enabled": True}})
            fp = m["finish_prefs"]
            self.assertEqual(fp["visual_hook"], {"mode": "shadow", "enabled": True})
            self.assertEqual(fp["music"], {"track_auto": "x.mp3"})
            m = REG.set_finish_prefs(w, {"visual_hook": {"enabled": False}})
            self.assertEqual(m["finish_prefs"]["visual_hook"], {"mode": "shadow", "enabled": False})
            m = REG.set_finish_prefs(w, {"visual_hook": None})
            self.assertNotIn("visual_hook", m["finish_prefs"])

    def test_invalid_values_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            w = mini_project(Path(t) / "p")
            for bad in ({"mode": "always"}, {"strength": "strong"}, {"recipe": "PAYOFF_PREVIEW"},
                        {"approved_plan_digest": "md5:1"}, {"selected_candidate_id": "../x"},
                        {"enabled": "yes"}):
                with self.assertRaises(ValueError, msg=str(bad)):
                    REG.set_finish_prefs(w, {"visual_hook": bad})

    def test_legacy_manifest_means_off(self):
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('vh_pref = _prefs.get("visual_hook") or {}', src)
        self.assertIn('or a.visual_hook or "off"', src)


class TestRunnerJobKind(unittest.TestCase):
    def test_hook_preview_uses_cli_not_pipeline_and_same_lock(self):
        with tempfile.TemporaryDirectory() as t:
            w = mini_project(Path(t) / "p")
            (w / "INPUT.mp4").write_bytes(b"0" * 10)
            with mock.patch.object(RUNNER.subprocess, "Popen") as pop:
                r = RUNNER.start_detached(w, {"content_type": "value"}, "py", job_kind="hook_preview")
            cmd = pop.call_args[0][0]
            self.assertIn("prepare-review", cmd)
            self.assertTrue(any(str(c).endswith("visual_hook.py") for c in cmd))
            self.assertNotIn("run_finish.py", " ".join(map(str, cmd)))
            self.assertEqual(r["job_kind"], "hook_preview")
            self.assertTrue((w / RUNNER.LOCK_NAME).exists())            # אותו בעלים של נעילה
            rec = json.loads((w / "runs" / f"{r['run_id']}.json").read_text(encoding="utf-8"))
            self.assertEqual(rec["job_kind"], "hook_preview")
            with mock.patch.object(RUNNER.subprocess, "Popen") as pop2:
                r2 = RUNNER.start_detached(w, {"content_type": "value"}, "py")
            self.assertTrue(r2["already_running"])
            pop2.assert_not_called()

    def test_preview_prep_never_commits_broll_usage(self):
        """נמדד 11.9.26: הכנת תצוגה רשמה שימוש גלובלי בבירולים (usage.json)."""
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("commit=not a.prepare_visual_hook_review", src)
        self.assertIn('if commit and os.environ.get("REL_BROLL_USAGE_COMMIT", "1") != "0":', src)
        self.assertNotIn('"--json", str(existing), "--commit"]', src)

    def test_run_finish_never_registers_artifact_for_prep(self):
        src = (TOOLS / "run_finish.py").read_text(encoding="utf-8")
        i_guard = src.index('if "--prepare-visual-hook-review" in passthrough:')
        i_art = src.index("art_mod.create_artifact(")
        self.assertLess(i_guard, i_art)
        self.assertIn('elif rec["status"] == "done":', src)


def synthetic_workdir(root: Path, name="p", face=True) -> Path:
    """גוף סינתטי 1080×1920 שעבר 'גימור' קודם (provenance תואם) — הקשר בר-שימוש."""
    from relvid import sha256_json
    w = mini_project(root / name)
    vf = "drawbox=x=400:y=500:w=280:h=340:color=0xC89070:t=fill" if face else "null"
    subprocess.run([VH.ffbin(), "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=c=0x303840:s=1080x1920:r=30:d=10", "-f", "lavfi",
                    "-i", "sine=frequency=220:duration=10", "-vf", vf, "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(w / "EXPORT.mp4")],
                   check=True, capture_output=True)
    shutil.copy2(w / "EXPORT.mp4", w / "INPUT.mp4")
    write(w / "tight_keeps.json", [{"start": 0.0, "end": 10.0}])
    words = [{"word": x, "start": 0.3 + i * 0.9, "end": 0.3 + i * 0.9 + 0.6}
             for i, x in enumerate("תושבי אריאל והסביבה הגוף שלכם צריך תהליך אחר עכשיו".split())]
    write(w / "words_final.json", words)
    edl = json.loads((w / "edl.json").read_text(encoding="utf-8"))
    write(w / "FINAL_PROVENANCE.json", {"edl_hash": sha256_json(edl), "tight_keeps": [{"start": 0.0, "end": 10.0}]})
    (w / "FINAL.mp4").write_bytes(b"old-final")
    time.sleep(0.01)
    os.utime(w / "words_final.json")
    return w


@unittest.skipUnless(HAS_CV, "numpy/cv2 חסרים")
class TestPrepareReviewJob(unittest.TestCase):
    def _cli(self, w, *extra):
        return subprocess.run([sys.executable, str(TOOLS / "visual_hook.py"), "prepare-review",
                               "--workdir", str(w), *extra], capture_output=True, text=True, timeout=600,
                              env=dict(os.environ, REL_WORK_ROOT=str(w.parent)))

    def test_preview_job_never_touches_final_cover_artifacts_or_schedule(self):
        with tempfile.TemporaryDirectory() as t:
            w = synthetic_workdir(Path(t))
            before = (w / "FINAL.mp4").read_bytes()
            mani_before = json.loads((w / "project_manifest.json").read_text(encoding="utf-8"))
            r = self._cli(w, "--run-id", "run_test00000001")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual((w / "FINAL.mp4").read_bytes(), before)
            self.assertFalse((w / "artifacts").exists())
            self.assertFalse((w / "thumbnail.png").exists())
            self.assertFalse((w / "finish_status.json").exists())
            mani = json.loads((w / "project_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(mani.get("schedule_approval"), mani_before.get("schedule_approval"))
            rec = json.loads((w / "runs" / "run_test00000001.json").read_text(encoding="utf-8"))
            self.assertEqual(rec["job_kind"], "hook_preview")
            self.assertIsNone(rec["output_hash"])
            self.assertIsNone(rec["artifact_id"])
            self.assertFalse((w / RUNNER.LOCK_NAME).exists())           # הנעילה שוחררה
            cur = json.loads((w / "visual_hook" / "review" / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(cur["edit_token"], VH.edit_token(w))
            self.assertEqual(cur["context_source"], "workdir")

    def test_lock_contention_does_not_write(self):
        with tempfile.TemporaryDirectory() as t:
            w = synthetic_workdir(Path(t))
            (w / RUNNER.LOCK_NAME).mkdir()
            write(w / RUNNER.LOCK_NAME / "meta.json", {"pid": os.getpid(), "run_id": "run_other"})
            r = self._cli(w, "--run-id", "run_mine")
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertFalse((w / "visual_hook" / "review" / "current.json").exists())
            self.assertTrue((w / RUNNER.LOCK_NAME).exists())            # הנעילה של האחר לא נגעה

    def test_stale_completion_is_discarded(self):
        import visual_hook as CLI
        with tempfile.TemporaryDirectory() as t:
            w = synthetic_workdir(Path(t))
            real = CLI.VH.run_selection          # המודול שה-CLI באמת מחזיק (בדיקות אחרות מוחקות relvid מ-sys.modules)

            def mutate(*a, **k):
                res = real(*a, **k)
                e = json.loads((w / "edl.json").read_text(encoding="utf-8"))
                e["review"]["cuts"] = [[2.0, 3.0]]                    # עריכה בזמן שהעבודה רצה
                write(w / "edl.json", e)
                return res
            args = type("A", (), {"workdir": str(w), "run_id": "run_stale0001"})()
            with mock.patch.object(CLI.VH, "run_selection", side_effect=mutate):
                rc = CLI.cmd_prepare_review(args)
            self.assertEqual(rc, 0)
            self.assertFalse((w / "visual_hook" / "review" / "current.json").exists())
            self.assertTrue((w / "visual_hook" / "review" / "stale_run_stale0001.json").exists())


@unittest.skipUnless(HAS_FLASK and HAS_CV, "flask/cv2 חסרים")
class TestServerVisualHook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="vh_srv_"))
        os.environ["REL_WORK_ROOT"] = str(cls.root)
        spec = importlib.util.spec_from_file_location("review_server_vh", SYSDIR / "review-app" / "server.py")
        cls.srv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.srv)
        cls.srv.WORK = cls.root
        cls.client = cls.srv.app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def _fresh_candidate(self, w):
        """מועמד טרי כאילו עבודת התצוגה רצה: תוכנית תקפה + שני קבצי תצוגה."""
        plan = json.loads(json.dumps(__import__("test_visual_hook").base_plan(fc=300)))
        plan["plan_digest"] = VH.digest_plan(plan)
        for n in ("VISUAL_HOOK_PREVIEW.mp4", "VISUAL_HOOK_PREVIEW_SBS.mp4"):
            (w / n).write_bytes(n.encode())
        write(w / "visual_hook" / "review" / "current.json", {
            "schema_version": 1, "edit_token": VH.edit_token(w), "plan": plan,
            "report": {"why": ["shadow_suggestion"]},
            "preview": {"treatment": "VISUAL_HOOK_PREVIEW.mp4", "side_by_side": "VISUAL_HOOK_PREVIEW_SBS.mp4",
                        "sha256": {"treatment": VH.file_sha256(w / "VISUAL_HOOK_PREVIEW.mp4"),
                                   "side_by_side": VH.file_sha256(w / "VISUAL_HOOK_PREVIEW_SBS.mp4")}}})
        return plan

    def _proj(self, name):
        return mini_project(self.root / name)

    def _approve(self, name, **extra):
        with mock.patch.object(self.srv.runner_mod, "start_detached",
                               return_value={"ok": True, "run_id": "run_x", "already_running": False}):
            return self.client.post(f"/api/approve/{name}", json=dict({"content_type": "value"}, **extra))

    def test_get_default_is_off_and_no_change(self):
        self._proj("a1")
        j = self.client.get("/api/visual-hook/a1").get_json()
        self.assertEqual(j["mode"], "off")
        self.assertEqual(j["label_he"], "פתיחה חזותית: ללא שינוי")
        self.assertFalse(j["treatment_available"])

    def test_fresh_candidate_shows_subtle_line(self):
        w = self._proj("a2")
        plan = self._fresh_candidate(w)
        j = self.client.get("/api/visual-hook/a2").get_json()
        self.assertEqual(j["label_he"], "פתיחה חזותית: הדגשה עדינה")
        self.assertEqual(j["plan_digest"], plan["plan_digest"])
        self.assertNotIn("%", json.dumps(j, ensure_ascii=False))        # אין "ביטחון 87%"

    def test_approve_binds_visible_digest(self):
        w = self._proj("a3")
        plan = self._fresh_candidate(w)
        r = self._approve("a3", visual_hook_plan_digest=plan["plan_digest"], visual_hook_comparison_seen=True)
        self.assertEqual(r.status_code, 200)
        appr = json.loads((w / "APPROVAL.json").read_text(encoding="utf-8"))
        self.assertTrue(appr["visual_hook"]["bound"])
        pref = REG.ensure_manifest(w)["finish_prefs"]["visual_hook"]
        self.assertEqual(pref["approved_plan_digest"], plan["plan_digest"])
        self.assertTrue(VH.approved_plan_path(w, plan["plan_digest"]).exists())
        ev = [json.loads(x) for x in (w / "corrections.jsonl").read_text(encoding="utf-8").splitlines()
              if '"visual_hook"' in x]
        self.assertEqual([e["event"] for e in ev], ["hook_approved"])
        self._approve("a3", visual_hook_plan_digest=plan["plan_digest"], visual_hook_comparison_seen=True)
        ev2 = [x for x in (w / "corrections.jsonl").read_text(encoding="utf-8").splitlines() if '"hook_approved"' in x]
        self.assertEqual(len(ev2), 1)                                  # ניסיון חוזר לא סופר פעמיים

    def test_approve_without_fresh_preview_binds_nothing(self):
        w = self._proj("a4")
        plan = self._fresh_candidate(w)
        REG.set_finish_prefs(w, {"visual_hook": {"approved_plan_digest": plan["plan_digest"]}})
        e = json.loads((w / "edl.json").read_text(encoding="utf-8"))
        e["review"]["cuts"] = [[1.0, 2.0]]                               # עריכה אחרי התצוגה
        write(w / "edl.json", e)
        self._approve("a4", visual_hook_plan_digest=plan["plan_digest"])
        appr = json.loads((w / "APPROVAL.json").read_text(encoding="utf-8"))
        self.assertFalse(appr["visual_hook"]["bound"])
        self.assertNotIn("approved_plan_digest", REG.ensure_manifest(w)["finish_prefs"]["visual_hook"])

    def test_approve_before_any_preview_leaves_legacy_approval(self):
        w = self._proj("a5")
        self._approve("a5")
        appr = json.loads((w / "APPROVAL.json").read_text(encoding="utf-8"))
        self.assertNotIn("visual_hook", appr)

    def test_tampered_preview_is_not_bindable(self):
        w = self._proj("a6")
        plan = self._fresh_candidate(w)
        (w / "VISUAL_HOOK_PREVIEW.mp4").write_bytes(b"swapped")
        self._approve("a6", visual_hook_plan_digest=plan["plan_digest"])
        self.assertFalse(json.loads((w / "APPROVAL.json").read_text(encoding="utf-8"))["visual_hook"]["bound"])

    def test_two_tabs_stale_pref_version_409(self):
        w = self._proj("a7")
        self._fresh_candidate(w)
        j = self.client.get("/api/visual-hook/a7").get_json()
        r1 = self.client.post("/api/visual-hook/a7", json={"action": "disable", "pref_version": j["pref_version"]})
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post("/api/visual-hook/a7", json={"action": "select", "pref_version": j["pref_version"],
                                                          "expected_plan_digest": j["plan_digest"]})
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(r2.get_json()["code"], "STALE_PREFS")
        self.assertIs(REG.ensure_manifest(w)["finish_prefs"]["visual_hook"]["enabled"], False)

    def test_select_with_stale_digest_409(self):
        w = self._proj("a8")
        self._fresh_candidate(w)
        j = self.client.get("/api/visual-hook/a8").get_json()
        r = self.client.post("/api/visual-hook/a8", json={"action": "select", "pref_version": j["pref_version"],
                                                         "expected_plan_digest": "sha256:" + "5" * 64})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["code"], "HOOK_REVIEW_STALE")

    def test_edit_blocked_while_finishing(self):
        w = self._proj("a9")
        j = self.client.get("/api/visual-hook/a9").get_json()
        (w / RUNNER.LOCK_NAME).mkdir()
        write(w / RUNNER.LOCK_NAME / "meta.json", {"pid": os.getpid(), "run_id": "run_live"})
        try:
            r = self.client.post("/api/visual-hook/a9", json={"action": "disable", "pref_version": j["pref_version"]})
            self.assertEqual(r.status_code, 409)
            self.assertEqual(r.get_json()["code"], "BUSY_FINISHING")
            r2 = self.client.post("/api/visual-hook/a9/preview", json={})
            self.assertEqual(r2.status_code, 409)
        finally:
            shutil.rmtree(w / RUNNER.LOCK_NAME, ignore_errors=True)

    def test_bad_action_is_400(self):
        self._proj("a10")
        j = self.client.get("/api/visual-hook/a10").get_json()
        r = self.client.post("/api/visual-hook/a10", json={"action": "publish", "pref_version": j["pref_version"]})
        self.assertEqual(r.status_code, 400)

    def test_no_new_schedule_or_publish_route(self):
        rules = [str(r) for r in self.srv.app.url_map.iter_rules() if "visual-hook" in str(r)]
        self.assertTrue(rules)
        self.assertFalse(any(k in r for r in rules for k in ("schedule", "publish", "metricool")))


class TestArtifactsHookSidecars(unittest.TestCase):
    def _w(self, t, with_prov=True, applied=True):
        w = mini_project(Path(t) / "p")
        (w / "FINAL.mp4").write_bytes(os.urandom(2048))
        plan = {"recipe": "SMART_PUNCH_IN", "plan_digest": Z}
        write(w / "visual_hook_plan.json", plan)
        write(w / "visual_hook_report.json", {"applied": applied})
        write(w / "visual_hook_render.json", {"renderer": "v1"})
        write(w / "visual_hook_qa.json", {"pass": True})
        prov = {"edl_hash": "x"}
        if with_prov:
            prov["visual_hook"] = {"mode": "shadow", "applied": applied, "recipe": "SMART_PUNCH_IN",
                                   "plan_digest": Z, "sidecars": {n: VH.file_sha256(w / n) for n in
                                                                  ("visual_hook_plan.json", "visual_hook_report.json",
                                                                   "visual_hook_render.json", "visual_hook_qa.json")}}
        write(w / "FINAL_PROVENANCE.json", prov)
        return w

    def test_applied_hook_sidecars_frozen_and_verified(self):
        with tempfile.TemporaryDirectory() as t:
            w = self._w(t)
            a = ART.create_artifact(w)
            d = ART.artifact_dir(w, a["artifact_id"])
            for n in ART.HOOK_SIDECARS:
                self.assertTrue((d / n).exists(), n)
            self.assertTrue(ART.verify(w, a["artifact_id"])["ok"])
            os.chmod(d / "visual_hook_plan.json", 0o644)
            (d / "visual_hook_plan.json").write_text('{"recipe":"PAYOFF_PREVIEW"}', encoding="utf-8")
            v = ART.verify(w, a["artifact_id"])
            self.assertFalse(v["ok"])
            self.assertEqual(v["state"], "hook_sidecar_mismatch")

    def test_stale_sidecars_without_provenance_are_not_frozen(self):
        with tempfile.TemporaryDirectory() as t:
            w = self._w(t, with_prov=False)
            a = ART.create_artifact(w)
            d = ART.artifact_dir(w, a["artifact_id"])
            self.assertFalse(any((d / n).exists() for n in ART.HOOK_SIDECARS))
            self.assertNotIn("visual_hook", a)
            self.assertTrue(ART.verify(w, a["artifact_id"])["ok"])

    def test_sidecar_changed_after_run_is_not_frozen(self):
        with tempfile.TemporaryDirectory() as t:
            w = self._w(t)
            write(w / "visual_hook_plan.json", {"recipe": "NO_OP", "plan_digest": "sha256:" + "2" * 64})
            a = ART.create_artifact(w)
            self.assertFalse((ART.artifact_dir(w, a["artifact_id"]) / "visual_hook_plan.json").exists())

    def test_identical_media_dedup_does_not_mutate_old_sidecars(self):
        with tempfile.TemporaryDirectory() as t:
            w = self._w(t)
            a = ART.create_artifact(w)
            d = ART.artifact_dir(w, a["artifact_id"])
            snap = {n: (d / n).read_bytes() for n in ART.HOOK_SIDECARS}
            write(w / "visual_hook_report.json", {"applied": False, "changed": True})
            b = ART.create_artifact(w)
            self.assertEqual(a["artifact_id"], b["artifact_id"])
            self.assertEqual(snap, {n: (d / n).read_bytes() for n in ART.HOOK_SIDECARS})

    def test_legacy_artifact_without_hook_fields_valid(self):
        with tempfile.TemporaryDirectory() as t:
            w = mini_project(Path(t) / "p")
            (w / "FINAL.mp4").write_bytes(os.urandom(1024))
            a = ART.create_artifact(w)
            self.assertTrue(ART.verify(w, a["artifact_id"])["ok"])


class TestLearning(unittest.TestCase):
    def setUp(self):
        import learn_from_edits as L
        self.L = L

    def test_hook_events_do_not_become_edl_hook_or_calibration(self):
        code = self.L.classify({"type": "visual_hook", "event": "hook_disabled"})
        self.assertEqual(code, "RC_VISUAL_HOOK")
        self.assertIn(code, self.L.REPORT_ONLY)
        self.assertNotIn(code, self.L.CAL)
        self.assertEqual(self.L.classify({"type": "hook_move"}), "RC_HOOK")

    def test_dedup_weak_approval_and_render_failure(self):
        base = {"type": "visual_hook", "project_id": "prj_a", "content_type": "value", "brand": "rel",
                "plan_digest": Z, "actor": "harel"}
        evs = [dict(base, event="hook_approved", comparison_seen=False),
               dict(base, event="hook_approved", comparison_seen=False),          # retry
               dict(base, event="hook_approved", comparison_seen=True),
               dict(base, event="hook_render_failed", run_id="run_1"),
               dict(base, event="hook_disabled", project_id="prj_b")]
        s = self.L.summarize_hook_events(evs)["value/rel"]
        self.assertEqual(s["weak_positive"], 1)
        self.assertEqual(s["explicit_positive"], 1)
        self.assertEqual(s["render_failures"], 1)
        self.assertEqual(s["negative"], 1)
        self.assertEqual(s["explicit_preference_ratio"], 0.5)

    def test_shadow_proposal_never_mutates_policy(self):
        pol_before = (TOOLS / "visual_hook_policy.json").read_bytes()
        edl_before = (TOOLS / "edl-policy.json").read_bytes()
        with tempfile.TemporaryDirectory() as t:
            p = self.L.build_hook_proposal({"value/rel": {"explicit_positive": 3}}, out_dir=t)
            doc = json.loads(Path(p).read_text(encoding="utf-8"))
            self.assertEqual(doc["status"], "shadow")
            self.assertIsNone(doc["suggested_change"])
            self.assertFalse(doc["applies_to_frozen_plans"])
        self.assertEqual(pol_before, (TOOLS / "visual_hook_policy.json").read_bytes())
        self.assertEqual(edl_before, (TOOLS / "edl-policy.json").read_bytes())

    def test_frozen_plan_unaffected_by_policy_change(self):
        from test_visual_hook import base_plan
        p = base_plan()
        d = p["plan_digest"]
        with tempfile.TemporaryDirectory() as t:
            pol = json.loads(VH.POLICY_PATH.read_text(encoding="utf-8"))
            pol["shadow_weights"]["benefit"]["semantic_fit"] = 0.9
            pp = Path(t) / "pol.json"
            pp.write_text(json.dumps(pol), encoding="utf-8")
            self.assertNotEqual(VH.policy_digest(VH.load_policy(pp)), VH.policy_digest(VH.load_policy()))
        self.assertEqual(VH.digest_plan(p), d)
        self.assertEqual(VH.validate_plan_shape(p), [])


if __name__ == "__main__":
    unittest.main()
