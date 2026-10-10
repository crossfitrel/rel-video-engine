#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_hook_e2e.py — הפקודות האמיתיות על עותקים בלבד (11.9.26).

לכל מקרה: שיבוט APFS של עותק ה-fixture לתיקייה חדשה ב-.e2e/visual-hook/runs/,
ואז run_finish.py → local_finish_pipeline.py אמיתי. בידוד מתופעות לוואי גלובליות:
  * ‎--music מפורש  → music-rotation.json (חוק 90 יום) לא מתעדכן.
  * ‎--no-notefix    → note_corrections --learn לא נוגע בלמידה הגלובלית.
  * בלי ‎--title     → אין קאבר (לא רלוונטי לפתיחה).
  * REL_WORK_ROOT=.e2e/visual-hook  → שום חיפוש לפי שם לא מגיע לפרויקט אמיתי.
תמלול האימות (G6b) כבוי כדי לחסוך ~30ש לריצה — מתועד בדוח, לא מוסתר.

שימוש: visual_hook_e2e.py --case case03 --scenario off_v1|shadow_v1|approved_v1|approved_v2|prep
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
SYSDIR = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from relvid.paths import work_root   # noqa: E402

E2E = work_root() / ".e2e" / "visual-hook"
PY = Path.home() / ".rel-whisper" / "bin" / "python"
MUSIC = SYSDIR / "brand-assets" / "music"


def clone_case(case: str, tag: str, drop_provenance=False) -> Path:
    src = E2E / case
    dst = E2E / "runs" / f"{case}_{tag}"
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["cp", "-c", "-R", "-p", str(src), str(dst)], capture_output=True)
    if r.returncode != 0:
        shutil.copytree(src, dst)
    for junk in ("visual_hook", "visual_hook_analysis.json", "visual_hook_candidates.json",
                 "visual_hook_plan.json", "visual_hook_report.json"):
        p = dst / junk
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    if drop_provenance:
        (dst / "FINAL_PROVENANCE.json").unlink(missing_ok=True)
    return dst


def music_track(case_dir: Path) -> str:
    m = json.loads((case_dir / "project_manifest.json").read_text(encoding="utf-8"))
    t = ((m.get("finish_prefs") or {}).get("music") or {}).get("track_auto")
    if t and (MUSIC / t).exists():
        return str(MUSIC / t)
    return str(sorted(MUSIC.glob("*.mp3"))[0])


def finish(W: Path, *extra, env_extra=None) -> dict:
    m = json.loads((W / "project_manifest.json").read_text(encoding="utf-8"))
    edl = json.loads((W / "edl.json").read_text(encoding="utf-8"))
    speed = float((edl.get("review") or {}).get("speed") or 1.0)
    cmd = [str(PY), str(TOOLS / "run_finish.py"), "--workdir", str(W),
           "--content-type", m.get("content_type") or "value", "--brand", m.get("brand") or "rel",
           "--music", music_track(W), "--no-notefix", "--no-verify-asr"]
    if abs(speed - 1.0) > 0.001:
        cmd += ["--speed", str(speed)]
    cmd += list(extra)
    env = dict(os.environ, REL_WORK_ROOT=str(E2E), PATH="/opt/homebrew/bin:" + os.environ.get("PATH", ""),
               REL_BROLL_USAGE_COMMIT="0", **(env_extra or {}))
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
    (W / "e2e_stdout.log").write_text(r.stdout + "\n---\n" + r.stderr, encoding="utf-8")
    fs = json.loads((W / "finish_status.json").read_text(encoding="utf-8")) if (W / "finish_status.json").exists() else {}
    return {"rc": r.returncode, "wall_sec": round(time.time() - t0, 1), "state": fs.get("state"),
            "detail": fs.get("detail"), "timings": fs.get("timings"), "cmd_tail": cmd[4:]}


def framemd5(p: Path, stream="v") -> list:
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(p), "-map", f"0:{stream}",
                        "-f", "framemd5", "-"], capture_output=True, text=True,
                       env=dict(os.environ, PATH="/opt/homebrew/bin:" + os.environ.get("PATH", "")))
    return [ln.split(",")[-1].strip() for ln in r.stdout.splitlines() if ln and not ln.startswith("#")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--scenario", required=True,
                    choices=("off_v1", "off_v2", "shadow_v1", "prep", "approved_v1", "approved_v2",
                             "fallback_v2", "stale_v1"))
    ap.add_argument("--plan", default=None)
    a = ap.parse_args()
    out = {"case": a.case, "scenario": a.scenario, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    if a.scenario == "prep":
        W = clone_case(a.case, "prep", drop_provenance=True)
        t0 = time.time()
        r = subprocess.run([str(PY), str(TOOLS / "visual_hook.py"), "prepare-review", "--workdir", str(W),
                            "--run-id", "run_e2eprep0001"], capture_output=True, text=True, timeout=3600,
                           env=dict(os.environ, REL_WORK_ROOT=str(E2E), REL_BROLL_USAGE_COMMIT="0",
                                    PATH="/opt/homebrew/bin:" + os.environ.get("PATH", "")))
        out.update(rc=r.returncode, wall_sec=round(time.time() - t0, 1), stdout=r.stdout[-600:], stderr=r.stderr[-600:])
        cur = W / "visual_hook" / "review" / "current.json"
        if cur.exists():
            doc = json.loads(cur.read_text(encoding="utf-8"))
            out.update(plan_digest=doc["plan"]["plan_digest"], recipe=doc["plan"]["recipe"],
                       context_source=doc["context_source"], input_digest=doc["input_digest"])
            (W / "approved_plan_for_e2e.json").write_text(json.dumps(doc["plan"], ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
        out["workdir"] = str(W)
    else:
        tag = a.scenario
        W = clone_case(a.case, tag, drop_provenance=True)
        extra, env_extra = [], None
        if a.scenario.endswith("v2"):
            extra += ["--render-engine", "v2"]
        if a.scenario.startswith("shadow"):
            extra += ["--visual-hook", "shadow"]
        if a.scenario.startswith(("approved", "fallback", "stale")):
            extra += ["--visual-hook", "shadow", "--visual-hook-plan", a.plan]
        if a.scenario == "fallback_v2":
            # כופה את "התקיעה הידועה" בכל סגמנט עם בירול ⇒ נפילה ל-v1. אותה תוכנית חייבת לשרוד.
            env_extra = {"REL_SEGMENT_SOFT_TIMEOUT": "0.01", "REL_SEGMENT_TIMEOUT": "0.01"}
        if a.scenario == "stale_v1":
            # עריכה אחרי התצוגה: קיצור הקטע האחרון ב-0.4ש ⇒ הקשר אחר ⇒ HOOK_REVIEW_STALE
            e = json.loads((W / "edl.json").read_text(encoding="utf-8"))
            k = e["keep_segments"][-1]
            k["end"] = round(float(k["end"]) - 0.4, 3)
            (W / "edl.json").write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
        out.update(finish(W, *extra, env_extra=env_extra))
        out["final_exists"] = (W / "FINAL.mp4").exists()
        rep_md = W / "FINISH_REPORT.md"
        if rep_md.exists():
            out["report_tail"] = [ln for ln in rep_md.read_text(encoding="utf-8").splitlines()
                                  if "Visual Hook" in ln or "נפילה" in ln or "HOOK_" in ln][:8]
        out["workdir"] = str(W)
        for n in ("visual_hook_report.json", "visual_hook_qa.json", "visual_hook_render.json",
                  "PREFLIGHT.json", "gate_blockers.json"):
            p = W / n
            if p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                out[n] = ({k: d.get(k) for k in ("applied", "mode", "recipe", "why", "label_he", "qa")}
                          if n == "visual_hook_report.json" else
                          {k: d.get(k) for k in ("pass", "hard_failures", "frames_checked", "median_err")}
                          if n == "visual_hook_qa.json" else
                          d.get("verdict") if n == "PREFLIGHT.json" else d)
        body = W / "EXPORT_TIGHT.mp4" if (W / "EXPORT_TIGHT.mp4").exists() else W / "EXPORT.mp4"
        vb = W / "VISUAL_BASE.mp4"
        if vb.exists():
            out["audio_md5_equal_body_vs_visual_base"] = framemd5(body, "a") == framemd5(vb, "a")
        if (W / "FINAL.mp4").exists():
            out["final_video_md5"] = __import__("hashlib").sha256("".join(framemd5(W / "FINAL.mp4")).encode()).hexdigest()[:16]
            out["final_frames"] = len(framemd5(W / "FINAL.mp4"))
        prov = W / "FINAL_PROVENANCE.json"
        if prov.exists():
            out["provenance_visual_hook"] = json.loads(prov.read_text(encoding="utf-8")).get("visual_hook")
        arts = sorted((W / "artifacts").glob("art_*/artifact.json")) if (W / "artifacts").exists() else []
        if arts:
            last = json.loads(arts[-1].read_text(encoding="utf-8"))
            out["artifact_visual_hook"] = last.get("visual_hook")
    res = E2E / "runs" / f"{a.case}_{a.scenario}.result.json"
    res.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
