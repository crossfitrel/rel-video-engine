#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runner — Job Runner v7: ריצות גימור idempotent עם נעילה, run_id ו-resume.
========================================================================
* lock אחד לכל פרויקט (.finish.lock — תיקייה, os.mkdir אטומי + בדיקת pid חי).
* לחיצה כפולה על "אשר" → הריצה הקיימת מזוהה ולא מופעלת שוב.
* כל ריצה: runs/run_<id>.json עם revision, hashes, פקודה, סטטוס, לוג נפרד.
* resume: אם ריצה קודמת נפלה אחרי recut/whisper וה-EDL לא השתנה — הריצה
  הבאה מדלגת על השלבים הכבדים (--no-recut --skip-whisper).
* FINAL.mp4 נכתב רק אחרי QA PASS (הפייפליין כותב FINAL_PENDING עד אז),
  ו-FINAL מאושר קודם מגובה ל-FINAL_prev_<ts>.mp4 — לא נדרס.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import (SYSDIR, TOOLS, atomic_write_json, new_id, now_ts, pid_alive,
               read_json, sha256_file, sha256_json)
from . import revisions as rev_mod

LOCK_NAME = ".finish.lock"
RUNS_DIR = "runs"
PIPELINE_VERSION_TAG = "v7.0"


class Locked(Exception):
    def __init__(self, meta):
        self.meta = meta
        super().__init__(f"ריצה פעילה: {meta}")


def _lock_dir(workdir):
    return Path(workdir) / LOCK_NAME


def acquire_lock(workdir, run_id):
    """נעילה אטומית. אימוץ: אם הנעילה נוצרה מראש ע"י ה-spawner עבור אותו run_id
    (סגירת חלון ה-race של אישור-כפול) — תהליך הריצה מאמץ אותה עם ה-pid שלו."""
    ld = _lock_dir(workdir)
    try:
        ld.mkdir()
    except FileExistsError:
        meta = read_json(ld / "meta.json", {}) or {}
        if meta.get("run_id") == run_id:
            pass                                   # הנעילה שלי (נוצרה ב-spawn) — אימוץ
        elif pid_alive(meta.get("pid")):
            raise Locked(meta)
        else:
            # נעילה יתומה (התהליך מת) — משחררים בבטחה
            shutil.rmtree(ld, ignore_errors=True)
            ld.mkdir()
    atomic_write_json(ld / "meta.json",
                      {"pid": os.getpid(), "run_id": run_id, "started": now_ts()})


def release_lock(workdir):
    shutil.rmtree(_lock_dir(workdir), ignore_errors=True)


def current_lock(workdir):
    meta = read_json(_lock_dir(workdir) / "meta.json")
    if meta and pid_alive(meta.get("pid")):
        return meta
    return None


def _runs_dir(workdir):
    d = Path(workdir) / RUNS_DIR
    d.mkdir(exist_ok=True)
    return d


def run_record_path(workdir, run_id):
    return _runs_dir(workdir) / f"{run_id}.json"


def list_runs(workdir):
    out = []
    for p in sorted(_runs_dir(workdir).glob("run_*.json")):
        r = read_json(p)
        if r:
            out.append(r)
    return out


def last_run(workdir):
    runs = list_runs(workdir)
    return runs[-1] if runs else None


def save_run(workdir, rec):
    rec["updated_at"] = now_ts()
    atomic_write_json(run_record_path(workdir, rec["run_id"]), rec)


def resume_flags(workdir):
    """אם הריצה האחרונה נכשלה אחרי recut+whisper וה-EDL לא השתנה — מדלגים.
    ריצה שקרסה (record נשאר 'running' אבל אין נעילה חיה) נחשבת גם היא כושלת."""
    w = Path(workdir)
    prev = last_run(w)
    crashed = (prev and prev.get("status") == "running"
               and current_lock(w) is None)
    if not prev or (prev.get("status") != "failed" and not crashed):
        return [], None
    edl = read_json(w / "edl.json", {}) or {}
    if prev.get("edl_hash") != sha256_json(edl):
        return [], "EDL השתנה מאז הריצה הקודמת — ריצה מלאה"
    fs = read_json(w / "finish_status.json", {}) or {}
    done = {s.get("step") for s in fs.get("steps_done", [])}
    flags = []
    if "recut" in done and (w / "EXPORT.mp4").exists():
        flags.append("--no-recut")
    if "whisper" in done and (w / "whisper_export.json").exists():
        flags.append("--skip-whisper")
    return flags, (f"resume מ-run קודם ({prev['run_id']}): מדלג על "
                   + ", ".join(flags) if flags else None)


def build_command(workdir, body, pybin, extra_flags=None):
    w = Path(workdir)
    # v10.1: אישור מעמוד הרוויו בענן משחזר בדיוק את הגימור שייצר את הגרסה שהראל ראה
    if body.get("replay_last"):
        last = read_json(w / "LAST_FINISH_ARGS.json", {}) or {}
        if last.get("args"):
            cmd = [str(pybin), str(TOOLS / "run_finish.py"), "--workdir", str(w)] + list(last["args"])
            for f in (extra_flags or []):
                cmd.append(f)
            return cmd
    cmd = [str(pybin), str(TOOLS / "run_finish.py"), "--workdir", str(w),
           "--content-type", body.get("content_type", "value"),
           "--brand", body.get("brand", "rel")]
    if body.get("title"):
        cmd += ["--title", body["title"]]
        if body.get("subtitle"):
            cmd += ["--subtitle", body["subtitle"]]
    if body.get("music_lufs"):
        cmd += ["--music-lufs", str(body["music_lufs"])]
    try:
        _speed = float(body.get("speed", 1.0) or 1.0)
    except (TypeError, ValueError):
        _speed = 1.0
    if abs(_speed - 1.0) > 0.001:
        cmd += ["--speed", str(round(_speed, 3))]
    if body.get("visual_hook_mode") in ("off", "shadow", "auto"):
        # v9.23 — מצב פתיחה חזותית מפורש מהקורא. העדפת האפליקציה במניפסט עדיין
        # גוברת בתוך הצנרת; כאן רק מעבירים את מה שנתבקש, בלי ברירת מחדל חדשה.
        cmd += ["--visual-hook", body["visual_hook_mode"]]
    if body.get("refinish"):
        # v7.4 — גימור מהיר מהאפליקציה: רק שכבות הגימור (reconcile/בירול/מוזיקה/
        # כתוביות/loudness/QA), בלי recut/whisper/tighten. speed לא נשלח — כבר אפוי
        # ב-EXPORT_TIGHT מהריצה המלאה.
        cmd.append("--refinish")
    for f in (extra_flags or []):
        cmd.append(f)
    return cmd


def _tool_env():
    """v9.22 (L50b): השרת עולה בלי /opt/homebrew/bin ב-PATH — הריצה שהוא מפעיל
    יורשת סביבה שבה ffmpeg חסר. מקדימים את נתיבי Homebrew לתהליך הבן."""
    env = dict(os.environ)
    cur = env.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin").split(os.pathsep)
    add = [d for d in ("/opt/homebrew/bin", "/usr/local/bin") if os.path.isdir(d) and d not in cur]
    env["PATH"] = os.pathsep.join(add + cur)
    return env


_spawn_mutex = threading.Lock()      # שני POST /approve מקבילים באותו שרת


def build_hook_preview_command(workdir, pybin, run_id):
    """job_kind=hook_preview — אותה נעילה ואותו מנגנון סטטוס/ביטול, פקודה אחרת:
    CLI שמכין מועמד פתיחה חזותית ועוצר. אין FINAL, אין קאבר, אין artifact."""
    return [str(pybin), str(TOOLS / "visual_hook.py"), "prepare-review",
            "--workdir", str(Path(workdir)), "--run-id", run_id]


def start_detached(workdir, body, pybin, job_kind="finish"):
    """נקודת הכניסה של כפתור 'אשר': idempotent. מחזיר run קיים אם רץ.
    סגירת ה-race: הבדיקה+יצירת הנעילה+ה-spawn רצים תחת mutex, והנעילה נוצרת
    כאן (בשם ה-run) עוד לפני שהתהליך עלה — הבן מאמץ אותה ב-acquire_lock."""
    w = Path(workdir)
    with _spawn_mutex:
        live = current_lock(w)
        if live:
            return {"ok": True, "already_running": True, "run_id": live.get("run_id")}
        # נעילת-הכנה: אם קיימת נעילה עם meta אך בלי pid חי — ייתכן ריצה שרק
        # נולדה (הבן עוד לא כתב pid). מזהים לפי started טרי.
        stale_meta = read_json(_lock_dir(w) / "meta.json", {}) or {}
        if stale_meta and stale_meta.get("spawning"):
            # ריצה בהולדתה — אלא אם ה-spawn נתקע (מעל 120ש בלי שהבן אימץ)
            try:
                age = time.time() - time.mktime(
                    time.strptime(stale_meta.get("started", ""), "%Y-%m-%d %H:%M:%S"))
            except Exception:
                age = 9999
            if age < 120:
                return {"ok": True, "already_running": True,
                        "run_id": stale_meta.get("run_id")}
            shutil.rmtree(_lock_dir(w), ignore_errors=True)
        run_id = new_id("run")
        _lock_dir(w).mkdir(exist_ok=True)
        atomic_write_json(_lock_dir(w) / "meta.json",
                          {"pid": None, "spawning": True, "run_id": run_id,
                           "started": now_ts()})
    flags, resume_note = ([], None) if job_kind == "hook_preview" else resume_flags(w)
    edl = read_json(w / "edl.json", {}) or {}
    rec = {
        "run_id": run_id,
        "project": w.name,
        "revision_id": rev_mod.head(w),
        "pipeline_version": PIPELINE_VERSION_TAG,
        "status": "starting",
        "stage": None,
        "started_at": now_ts(),
        "finished_at": None,
        "command": None,
        "edl_hash": sha256_json(edl),
        "input_hash": sha256_file(w / "INPUT.mp4"),
        "output_hash": None,
        "resume": resume_note,
        "retry_count": sum(1 for r in list_runs(w) if r.get("status") == "failed"),
        "log": f"{RUNS_DIR}/{run_id}.log",
        "job_kind": job_kind,
        "params": {k: body.get(k) for k in
                   ("content_type", "brand", "title", "subtitle", "music_lufs", "speed",
                    "refinish", "visual_hook_mode")},
    }
    save_run(w, rec)
    if job_kind == "hook_preview":
        cmd = build_hook_preview_command(w, pybin, run_id)
    else:
        cmd = build_command(w, body, pybin, ["--run-id", run_id] + flags)
    rec["command"] = cmd
    save_run(w, rec)
    logf = open(_runs_dir(w) / f"{run_id}.log", "a")
    subprocess.Popen(["nohup"] + cmd, stdout=logf, stderr=logf,
                     cwd=str(SYSDIR), start_new_session=True, env=_tool_env())
    return {"ok": True, "already_running": False, "run_id": run_id,
            "resume": resume_note, "job_kind": job_kind}


def cancel(workdir):
    """ביטול בטוח: הורג את תהליך הריצה אם חי, מסמן את הריצה cancelled."""
    w = Path(workdir)
    meta = read_json(_lock_dir(w) / "meta.json")
    if not meta:
        return {"ok": False, "error": "אין ריצה פעילה"}
    pid = meta.get("pid")
    if pid_alive(pid):
        try:
            os.killpg(os.getpgid(pid), 15)
        except Exception:
            try:
                os.kill(pid, 15)
            except Exception:
                pass
        time.sleep(1)
    rec = read_json(run_record_path(w, meta.get("run_id", "")), {}) or {}
    if rec:
        rec["status"] = "cancelled"
        rec["finished_at"] = now_ts()
        save_run(w, rec)
    release_lock(w)
    return {"ok": True, "cancelled": meta.get("run_id")}
