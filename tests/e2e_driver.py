#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
e2e_driver.py — E2E על עותקי בדיקה (לא נוגע בפרויקטים אמיתיים ולא ב-Monday/Metricool).
מכסה: comment→queue→claim→resolve, stale task, revision flow, אישור כפול=ריצה אחת.
  python3 tests/e2e_driver.py בדיקת-מערכת-אחת
"""
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
sys.path.insert(0, str(SYSDIR / "tools"))
BASE = "http://127.0.0.1:5112"
NAME = sys.argv[1] if len(sys.argv) > 1 else "בדיקת-מערכת-אחת"
ENC = urllib.parse.quote(NAME)
W = SYSDIR / "_work" / NAME
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)[:140]))
    print(f"{'✅' if ok else '❌'} {name} {detail}")


def api(path, body=None):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def cli(*args):
    r = subprocess.run(["python3", str(SYSDIR / "tools" / "review_cli.py")] + list(args),
                       capture_output=True, text=True, timeout=120)
    try:
        return r.returncode, json.loads(r.stdout.strip())
    except Exception:
        return r.returncode, {"raw": r.stdout[-200:] + r.stderr[-200:]}


# 1. פרויקט נראה ב-API
proj = api(f"/api/project/{ENC}")
check("project_visible", proj.get("name") == NAME, f"total={proj.get('total')}")

# 2. הערה בטיימקוד → תור קלאוד
c = api(f"/api/comments/{ENC}", {"text": "E2E: בדוק את הפתיחה", "time_start": 3.5,
                                 "category": "edit", "priority": "high", "queue": True})
cid = c["comment"]["comment_id"]
check("comment_created", c.get("ok") and c["comment"]["status"] == "queued_for_claude", cid)

# 3. review_cli tasks רואה אותה
rc, tasks = cli("tasks", "--json")
check("cli_tasks_shows", any(t.get("task_id") == cid for t in tasks if isinstance(t, dict)),
      f"{len(tasks)} tasks in queue")

# 4. claim
rc, claim = cli("claim", cid, "--json")
check("cli_claim", rc == 0 and claim.get("ok"),
      f"snippet={ (claim.get('task') or {}).get('transcript_snippet','')[:40] }")

# 5. עריכה (דרך API save — יוצרת revision) → resolve
edl = json.loads((W / "edl.json").read_text(encoding="utf-8"))
cuts = (edl.get("review") or {}).get("cuts", [])
tA = round(float(edl["total_dur"]) * 0.82, 2)
body = {"cuts": cuts + [{"start": tA, "end": round(tA + 0.5, 2), "reason": "E2E cut",
                         "source": "harel", "confidence": "harel", "active": True}],
        "hook_move": (edl.get("review") or {}).get("hook_move"),
        "actions": [{"type": "add_cut", "cut": {"start": tA, "end": tA + 0.5,
                                                "reason": "E2E cut"}}],
        "actor": "claude", "summary": "E2E תיקון לפי הערה"}
sv = api(f"/api/save/{ENC}", body)
rev = sv.get("revision_id")
check("save_creates_revision", bool(rev), rev)
rc, res = cli("resolve", cid, "--revision", rev, "--summary", "E2E תוקן", "--json")
check("cli_resolve", rc == 0 and res.get("ok"))
com = api(f"/api/project/{ENC}")["comments"]
check("resolved_status", any(x["comment_id"] == cid and x["status"] == "resolved"
                             and x["resolved_revision_id"] == rev for x in com))

# 6. resolve בלי revision נדחה
c2 = api(f"/api/comments/{ENC}", {"text": "E2E שנייה", "queue": True})
cid2 = c2["comment"]["comment_id"]
rc, bad = cli("resolve", cid2, "--summary", "בלי revision", "--json")
check("resolve_requires_revision", rc != 0)

# 7. stale task: משנים EDL *באמת* (cut שונה) אחרי יצירת ההערה → claim נעצר
body2 = dict(body, summary="שינוי שהופך את ההערה ל-stale", actions=[])
tB = round(float(edl["total_dur"]) * 0.9, 2)
body2["cuts"] = body["cuts"] + [{"start": tB, "end": round(tB + 0.4, 2),
                                 "reason": "E2E stale", "source": "harel",
                                 "confidence": "harel", "active": True}]
sv2 = api(f"/api/save/{ENC}", body2)
rc, st = cli("claim", cid2, "--json")
check("stale_task_blocked", rc == 4 and st.get("stale"))
rc, st2 = cli("claim", cid2, "--force", "--json")
check("stale_force_works", rc == 0 and st2.get("ok"))
cli("fail", cid2, "--reason", "E2E — מוחזר לתור", "--json")

# 8. undo/redo/restore
revs = api(f"/api/revisions/{ENC}")
n_before = len(revs["revisions"])
u = api(f"/api/undo/{ENC}", {})
check("undo", u.get("ok"))
r2 = api(f"/api/redo/{ENC}", {})
check("redo", r2.get("ok"))
first = revs["revisions"][0]["revision_id"]
rest = api(f"/api/restore/{ENC}", {"revision_id": first})
check("restore_nondestructive", rest.get("ok") and
      len(api(f"/api/revisions/{ENC}")["revisions"]) == n_before + 1)

# 9. אישור כפול = ריצה אחת
a1 = api(f"/api/approve/{ENC}", {"content_type": "value", "brand": "personal"})
a2 = api(f"/api/approve/{ENC}", {"content_type": "value", "brand": "personal"})
one_started = a1.get("run_id") and (a2.get("already_running") or a2.get("run_id") == a1.get("run_id"))
check("double_approve_single_run", one_started,
      f"run1={a1.get('run_id')} run2_already={a2.get('already_running')}")

print("\n== ממתין לריצת הגימור (עד 20 דק) ==")
final_state = None
for i in range(240):
    time.sleep(5)
    s = api(f"/api/status/{ENC}")
    if s.get("state") in ("done", "failed"):
        final_state = s
        break
check("pipeline_finished", final_state is not None,
      (final_state or {}).get("state"))
if final_state:
    if final_state["state"] == "done":
        check("final_exists_after_qa", (W / "FINAL.mp4").exists())
        check("no_pending_left", not (W / "FINAL_PENDING.mp4").exists())
        check("qa_pass", (json.loads((W / "qa_report.json").read_text(encoding="utf-8"))).get("pass"))
    else:
        # כשל gate צפוי אפשרי (עריכת E2E) — העיקר: אין FINAL חלקי
        check("no_partial_final", not (W / "FINAL.mp4").exists(),
              f"failed: {final_state.get('detail')}")
    time.sleep(8)   # ה-wrapper משחרר את הנעילה עד 2ש אחרי סיום הפייפליין
    check("lock_released", not (W / ".finish.lock").exists())
    runs = sorted((W / "runs").glob("run_*.json"))
    check("run_record_exists", len(runs) >= 1, f"{len(runs)} runs")

    # 10. resume: אחרי כשל — אישור נוסף מדלג על recut+whisper
    if final_state["state"] == "failed":
        a3 = api(f"/api/approve/{ENC}", {"content_type": "value", "brand": "personal"})
        check("resume_offered", bool(a3.get("resume")), a3.get("resume"))
        for i in range(120):
            time.sleep(5)
            s = api(f"/api/status/{ENC}")
            if s.get("state") in ("done", "failed"):
                break
        fs = json.loads((W / "finish_status.json").read_text(encoding="utf-8"))
        skipped = [x for x in fs.get("steps_done", []) if "דולג" in (x.get("detail") or "")]
        check("resume_skipped_heavy_steps", len(skipped) >= 2,
              f"{[x['step'] for x in skipped]}")
        time.sleep(8)
        check("lock_released_after_resume", not (W / ".finish.lock").exists())

ok = all(r[1] for r in results)
print(f"\n{'✅ E2E PASS' if ok else '❌ E2E FAIL'} — {sum(1 for r in results if r[1])}/{len(results)}")
sys.exit(0 if ok else 1)
