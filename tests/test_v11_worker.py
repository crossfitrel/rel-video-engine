"""v11 (29.10.26) — הזרקת כשל לשכבות החדשות: worker, llm.py, video_api.
כל בדיקה מוכיחה שהשכבה נכשלת סגור: אין "בוצע" בלי שמירה מאומתת, אין "מוכן" בלי PREFLIGHT, אין Opus בלי הסלמה."""
import io, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cloud")); sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("WORKER_OFFLINE", "1")
import video_api as V  # noqa: E402
import llm  # noqa: E402
import worker as W  # noqa: E402


class LLMRouting(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(llm.route("transcript_sanity"), "haiku")
        self.assertEqual(llm.route("director"), "sonnet")
        self.assertEqual(llm.route("caption"), "sonnet")
        self.assertEqual(llm.route("unknown_task"), "sonnet")

    def test_opus_requires_escalation_reason(self):
        with mock.patch.object(V, "call") as c:
            with self.assertRaises(llm.LLMError):
                llm.ask("escalate", "x")
            c.assert_not_called()

    def test_server_refusal_raises(self):
        with mock.patch.object(V, "call", return_value={"ok": False, "error": "cap_reel"}):
            with self.assertRaises(llm.LLMError):
                llm.ask("caption", "x", project_id="p-1")


class UploadVerify(unittest.TestCase):
    def test_sha_mismatch_fails(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"real-bytes")
        calls = {"upload_url": {"ok": True, "signedUrl": "https://x/put"}, "signed_url": {"ok": True, "url": "https://x/get"}}

        class R(io.BytesIO):
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
        with mock.patch.object(V, "call", side_effect=lambda op, **k: calls[op]), \
             mock.patch("urllib.request.urlopen", side_effect=[R(b""), R(b"corrupted")]):
            with self.assertRaises(V.ApiError):
                V.upload(f.name, "p/x.mp4", "video/mp4")


class WorkerContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); W.WORK = Path(self.tmp.name)
        (W.WORK / "proj").mkdir()
        (W.WORK / "proj" / "project_manifest.json").write_text(json.dumps({"title": "t", "dept": "קרוספיט אריאל"}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_state_mismatch_is_not_done(self):
        with mock.patch.object(W, "sh", return_value=("", "", 0)), mock.patch.object(W, "_sha_saved", return_value=("a" * 64, "b" * 64)):
            with self.assertRaises(RuntimeError):
                W.save_state("proj", "finish")

    def test_preflight_not_ready_never_reaches_review(self):
        (W.WORK / "proj" / "PREFLIGHT.json").write_text(json.dumps({"verdict": {"ready_for_harel": False, "n_high": 1}, "findings": [{"check": "P1", "severity": "high", "detail": "x"}]}), encoding="utf-8")
        upserts = []
        with mock.patch.object(W, "sh", return_value=("", "", 0)), mock.patch.object(W, "save_state", return_value=(True, "x")), \
             mock.patch.object(W, "publish_review") as pub, \
             mock.patch.object(V, "call", side_effect=lambda op, **k: upserts.append((op, k)) or {"ok": True}):
            with self.assertRaises(W.Escalate):
                W.finish_full("p-1", "proj", "קרוספיט אריאל")
            pub.assert_not_called()
        states = [k["project"]["state"] for op, k in upserts if op == "project_upsert"]
        self.assertEqual(states, ["blocked"])
        self.assertFalse(any(op == "monday_status" for op, _ in upserts))

    def test_preflight_reads_verdict_block(self):
        (W.WORK / "proj" / "PREFLIGHT.json").write_text(json.dumps({"verdict": {"ready_for_harel": True, "out_dur": 40.6, "summary": "מוכן"}, "findings": []}), encoding="utf-8")
        pf = W.preflight(W.WORK / "proj")
        self.assertTrue(pf["ready_for_harel"]); self.assertEqual(pf["out_dur"], 40.6)

    def test_failed_job_sets_health_and_does_not_consume_action(self):
        sent = []
        def fake(op, **k):
            sent.append((op, k))
            if op == "job_claim":
                return {"ok": True, "job": {"id": "j1", "kind": "finish", "project_id": "p-1", "payload": {"action_id": "a1"}}, "project": {"id": "p-1", "workdir": "proj"}, "comments": []}
            return {"ok": True}
        with mock.patch.object(V, "call", side_effect=fake), mock.patch.dict(W.HANDLERS, {"finish": mock.Mock(side_effect=RuntimeError("boom"))}):
            rc = W.cmd_run(type("A", (), {"job_id": "j1"})())
        self.assertEqual(rc, 1)
        done = [k for op, k in sent if op == "job_done"][0]
        self.assertEqual(done["status"], "failed"); self.assertIsNone(done["consume_action"])
        self.assertTrue(any(op == "health_set" and k["value"] == "failed" for op, k in sent))

    def test_escalation_creates_claude_judge_job(self):
        sent = []
        def fake(op, **k):
            sent.append((op, k))
            if op == "job_claim":
                return {"ok": True, "job": {"id": "j2", "kind": "notes", "project_id": "p-1", "payload": {}}, "project": {"id": "p-1", "workdir": "proj"}, "comments": []}
            return {"ok": True}
        with mock.patch.object(V, "call", side_effect=fake), mock.patch.dict(W.HANDLERS, {"notes": mock.Mock(side_effect=W.Escalate("note_unmapped"))}):
            W.cmd_run(type("A", (), {"job_id": "j2"})())
        enq = [k for op, k in sent if op == "enqueue"]
        self.assertEqual(enq[0]["kind"], "judge"); self.assertEqual(enq[0]["runner"], "claude")


if __name__ == "__main__":
    unittest.main()


class TestVerifyIsSparse(__import__("unittest").TestCase):
    """L146 (1.11.26): אימות שמירה לעולם לא משבט את כל ענף libs — מילא את דיסק ה-runner, rc=128 בכל ג'וב."""
    def test_worker_uses_verify_project(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "cloud" / "worker.py").read_text(encoding="utf-8")
        body = src.split("def save_state", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"verify-project"', body)
        self.assertNotIn('"pull-project"', body)

    def test_verify_project_is_sparse_json_only(self):
        from pathlib import Path
        sh = (Path(__file__).resolve().parents[1] / "cloud" / "libs_git.sh").read_text(encoding="utf-8")
        block = sh.split("verify-project)", 1)[1].split(";;", 1)[0]
        self.assertIn("--filter=blob:none", block)
        self.assertIn("sparse-checkout set", block)
        self.assertIn("*.json", block)
