#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_hook.py — CLI דק ל-Visual Hook Engine (11.9.26). אין כאן לוגיקה עסקית:
הכול ב-relvid/visual_hook.py (החלטה) וב-relvid/hook_render.py (ביצוע).

  analyze        --workdir W [--body PATH] [--words PATH]
  plan           --workdir W --mode shadow|auto --output PATH [--select CANDIDATE_ID]
  preview        --workdir W --plan PATH --render-engine v1|v2 --output PATH [--seconds 10] [--side-by-side]
  validate       --workdir W --plan PATH                       (קריאה בלבד)
  prepare-review --workdir W [--run-id R]                      (עבודת job_kind=hook_preview של האפליקציה)

כללים שנאכפים כאן:
  * אף פקודה לא כותבת FINAL/PENDING/MIXED/artifacts ולא מפרסמת.
  * פקודה שכותבת לתיקיית העבודה בודקת את נעילת הגימור (ריצה חיה ⇒ exit 3).
  * preview כותב רק ‎.mp4 בתוך visual_hook/ או ‎.e2e, או בשם VISUAL_HOOK_PREVIEW*.
קודי יציאה: 0 הצלחה · 1 שגיאה/תוכנית לא תקפה · 2 HOOK_REVIEW_STALE · 3 נעול.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from relvid import visual_hook as VH                  # noqa: E402
from relvid import hook_render as HR                  # noqa: E402

FORBIDDEN_OUT = re.compile(r"^(FINAL|FINAL_PENDING|MIXED|EXPORT|INPUT|master_v2)(\b|[._])", re.I)


def _busy(W: Path):
    try:
        from relvid import runner as runner_mod
        return runner_mod.current_lock(W)
    except Exception:
        return None


def _safe_output(W: Path, out: Path, suffix: str) -> Path:
    out = out if out.is_absolute() else (Path.cwd() / out)
    out = out.resolve()
    if out.suffix.lower() != suffix:
        raise VH.HookError("HOOK_BAD_OUTPUT", f"הפלט חייב להיות {suffix}")
    if FORBIDDEN_OUT.match(out.name) or "artifacts" in out.parts:
        raise VH.HookError("HOOK_BAD_OUTPUT", f"שם/מיקום פלט אסור: {out.name}")
    inside_hook = str(out).startswith(str((W / VH.HOOK_DIR).resolve()))
    in_e2e = ".e2e" in out.parts
    named = out.parent == W.resolve() and out.name.startswith(("VISUAL_HOOK_PREVIEW", "visual_hook_"))
    if not (inside_hook or in_e2e or named):
        raise VH.HookError("HOOK_BAD_OUTPUT", "פלט מותר רק תחת visual_hook/, ‎.e2e או בשם VISUAL_HOOK_PREVIEW*/visual_hook_*")
    return out


def cmd_analyze(a) -> int:
    W = Path(a.workdir).resolve()
    if _busy(W):
        print("⛔ גימור פעיל בפרויקט — לא כותבים לתיקיית העבודה")
        return 3
    kw = {}
    if a.body:
        kw["body"] = a.body
    if a.words:
        kw["words_file"] = a.words
    ctx = VH.build_context(W, **kw)
    ana = VH.analyze(ctx)
    VH.atomic_write_json(W / VH.FILES["analysis"], {k: v for k, v in ana.items() if k != "cache_key"})
    m = ana["measurements"]
    print(f"✅ ניתוח: {ctx['project_id']} · {ana['timeline']['frame_count']} פריימים · "
          f"פתיח מלא={ctx['intro']['present']} · מילים תואמות={ctx['words_provenance']['ok']} · "
          f"עוגן={((ana['hook'] or {}).get('anchor') or {}).get('word')} · "
          f"חיתוכים={m.get('hard_cuts')} · כניסה מכוונת={m.get('intentional_entrance')}")
    print(json.dumps({"input_digest": ctx["input_digest"], "unknowns": ana["unknowns"]}, ensure_ascii=False))
    return 0


def cmd_plan(a) -> int:
    W = Path(a.workdir).resolve()
    if _busy(W):
        print("⛔ גימור פעיל בפרויקט — לא כותבים לתיקיית העבודה")
        return 3
    out = _safe_output(W, Path(a.output), ".json")
    prefs = {"selected_candidate_id": a.select} if a.select else None
    res = VH.run_selection(W, mode=a.mode, prefs=prefs)
    plan = res["plan"]
    if a.select and plan.get("candidate_id") != a.select:
        print(f"❌ המועמד {a.select} אינו זכאי/קיים — נבחר {plan['recipe']}")
        return 1
    VH.atomic_write_json(out, plan)
    r = res["report"]
    print(f"✅ {r['label_he'] if r['applied'] else r['suggestion_label_he'] + (' (הצעה בצל)' if a.mode == 'shadow' else '')} · "
          f"מתכון {plan['recipe']} · {plan['plan_digest'][:19]} · סיבות: {', '.join(plan['selection']['reason_codes'])}")
    for c in res["candidates"]:
        if c["recipe"] in ("NO_OP", "SMART_PUNCH_IN"):
            print(f"   {c['candidate_id']} {c['recipe']:<15} זכאי={c['eligible']} "
                  f"סיבות={c['reason_codes']} ציון={(c['score'] or {}).get('net')}")
    return 0


def _load_plan(p) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception as e:
        raise VH.HookError("HOOK_PLAN_INVALID", f"קריאת התוכנית נכשלה: {e}")


def cmd_validate(a) -> int:
    W = Path(a.workdir).resolve()
    plan = _load_plan(a.plan)
    ctx = VH.build_context(W)
    errs = VH.validate_plan(plan, ctx)
    if not errs:
        print(f"✅ תוכנית תקפה מול ההקשר הנוכחי · {plan['recipe']} · {plan['plan_digest'][:19]}")
        return 0
    for e in errs:
        print(f"❌ {e}")
    return 2 if VH.stale_code(errs) else 1


def cmd_preview(a) -> int:
    W = Path(a.workdir).resolve()
    if _busy(W):
        print("⛔ גימור פעיל בפרויקט — לא כותבים לתיקיית העבודה")
        return 3
    out = _safe_output(W, Path(a.output), ".mp4")
    plan = _load_plan(a.plan)
    ctx = VH.build_context(W)
    errs = VH.validate_plan(plan, ctx)
    if errs:
        for e in errs:
            print(f"❌ {e}")
        return 2 if VH.stale_code(errs) else 1
    if a.render_engine == "v1":
        info = HR.render_preview(ctx["body_path"], plan, out, seconds=a.seconds,
                                 side_by_side=a.side_by_side)
    else:
        info = preview_v2(W, plan, out, seconds=a.seconds)
    print(f"✅ תצוגה מקדימה (לא לפרסום): {out.name} · {info.get('frames')} פריימים · {a.render_engine}")
    return 0


def preview_v2(W: Path, plan: dict, out: Path, seconds=10.0) -> dict:
    """אותו IR דרך מנוע v2, במטמון נפרד (לא נוגע ב-.rendercache של הפרויקט)."""
    from relvid import render as RENDER
    tl = RENDER.build_timeline(W, hook_plan=plan)
    pdir = W / VH.HOOK_DIR / "preview_v2"
    pdir.mkdir(parents=True, exist_ok=True)
    tl.workdir = pdir
    master = pdir / f"master_{plan['plan_digest'][7:19]}.mkv"
    rs = RENDER.render(tl, master)
    if not rs.get("ok"):
        raise VH.HookError("HOOK_RENDER_FAILED", str(rs.get("error"))[:400])
    n = int(round(seconds * 30))
    tmp = out.with_name(out.stem + ".tmp.mp4")
    r = subprocess.run([VH.ffbin(), "-nostdin", "-y", "-loglevel", "error", "-i", str(master),
                        "-frames:v", str(n), "-t", f"{n / 30:.4f}", "-c:v", "libx264", "-crf", "20",
                        "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                        "-movflags", "+faststart", str(tmp)], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise VH.HookError("HOOK_PREVIEW_FAILED", r.stderr[-400:])
    os.replace(tmp, out)
    return {"frames": n, "master": str(master), "affected_segments":
            (tl.meta.get("visual_hook") or {}).get("affected_segments")}


# ═══════════════════════════════════════════════════════ prepare-review
COPY_FOR_PREP = ("edl.json", "whisper_raw.json", "words_corrected.json", "transcript_fix.json",
                 "edited.txt", "correct_transcript.txt", "comments.json", "sentences.json",
                 "project_manifest.json", "broll_plan.json", "illustration_plan.json",
                 "segment_sources.json", "intent_card.md", "brief.json", "brief.txt",
                 "candidates.json")


def context_reusable(W: Path) -> tuple[bool, str]:
    """ההקשר בתיקיית העבודה כבר מייצג את ה-EDL הנוכחי? (אז אין צורך בהכנה מחדש)"""
    from relvid import read_json, sha256_json
    prov = read_json(W / "FINAL_PROVENANCE.json", {}) or {}
    edl = read_json(W / "edl.json", {}) or {}
    if not prov or prov.get("edl_hash") != sha256_json(edl):
        return False, "ה-EDL השתנה מאז הגימור האחרון"
    if (read_json(W / "tight_keeps.json", None) or None) != (prov.get("tight_keeps") or None):
        return False, "tight_keeps אינו תואם לגימור האחרון"
    wf = W / "words_final.json"
    body = VH.resolve_body(W)
    if not wf.exists() or not body.exists():
        return False, "חסר גוף נקי או words_final.json"
    for src in ("edited.txt", "correct_transcript.txt", "comments.json"):
        p = W / src
        if p.exists() and p.stat().st_mtime > wf.stat().st_mtime + 1:
            return False, f"{src} חדש מהמילים הסופיות — נדרשת הכנה"
    return True, "ההקשר בתיקייה תואם ל-EDL הנוכחי"


def _prep_copy(W: Path, token: str) -> Path:
    prep = W / VH.HOOK_DIR / "prep" / re.sub(r"[^0-9a-z]", "", token.split(":")[-1])[:16]
    if prep.exists():
        shutil.rmtree(prep, ignore_errors=True)
    prep.mkdir(parents=True)
    os.symlink(W / "INPUT.mp4", prep / "INPUT.mp4")
    for n in COPY_FOR_PREP:
        if (W / n).exists():
            shutil.copy2(W / n, prep / n)
    ss = VH._jload(W / "segment_sources.json", {}) or {}
    for ov in ss.get("overrides") or []:
        src = Path(str(ov.get("src", "")))
        if src.name and not src.is_absolute() and (W / src).exists() and not (prep / src).exists():
            os.symlink(W / src, prep / src)
    return prep


def cmd_prepare_review(a) -> int:
    from relvid import runner as runner_mod, read_json, new_id, now_ts
    W = Path(a.workdir).resolve()
    run_id = a.run_id or new_id("run")
    rec = read_json(runner_mod.run_record_path(W, run_id), {}) or {
        "run_id": run_id, "project": W.name, "started_at": now_ts(),
        "log": f"runs/{run_id}.log"}
    rec["job_kind"] = "hook_preview"
    try:
        runner_mod.acquire_lock(W, run_id)
    except runner_mod.Locked as e:
        rec.update(status="skipped_already_running", detail=f"נעול ע\"י {e.meta}", finished_at=now_ts())
        runner_mod.save_run(W, rec)
        print("⛔ ריצה פעילה כבר קיימת — תצוגת פתיחה לא הופעלה")
        return 3
    status_path = W / VH.HOOK_DIR / "review" / "status.json"
    try:
        rec["status"] = "running"
        runner_mod.save_run(W, rec)
        VH.atomic_write_json(status_path, {"state": "running", "run_id": run_id, "started": now_ts()})
        token = VH.edit_token(W)
        ok, why = context_reusable(W)
        ctx_dir = W
        if not ok:
            prep = _prep_copy(W, token)
            mani = read_json(W / "project_manifest.json", {}) or {}
            appr = read_json(W / "APPROVAL.json", {}) or {}
            edl = read_json(W / "edl.json", {}) or {}
            speed = float(((edl.get("review") or {}).get("speed")) or 1.0)
            cmd = [sys.executable, str(HERE / "local_finish_pipeline.py"), "--workdir", str(prep),
                   "--content-type", mani.get("content_type") or appr.get("content_type") or "value",
                   "--brand", mani.get("brand") or appr.get("brand") or "rel",
                   "--visual-hook", "shadow", "--prepare-visual-hook-review", "--no-verify-asr"]
            if abs(speed - 1.0) > 0.001:
                cmd += ["--speed", str(round(speed, 3))]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                               env=dict(os.environ, REL_RUN_ID=run_id))
            if r.returncode != 0:
                raise VH.HookError("HOOK_PREP_FAILED", (r.stdout or "")[-300:] + (r.stderr or "")[-300:])
            ctx_dir = prep
        res = VH.run_selection(ctx_dir, mode="shadow", write=False)
        best = res["selected"]
        plan = VH.make_plan(res["context"], res["analysis"], best,
                            {"actor": "harel", "reason_codes": ["operator_selected"]}) \
            if best["recipe"] != "NO_OP" else res["plan"]
        rdir = W / VH.HOOK_DIR / "review"
        prev = {}
        if plan["recipe"] != "NO_OP":
            HR.render_preview(res["context"]["body_path"], plan, W / "VISUAL_HOOK_PREVIEW.mp4")
            HR.render_preview(res["context"]["body_path"], plan, W / "VISUAL_HOOK_PREVIEW_SBS.mp4",
                              side_by_side=True)
            prev = {"treatment": "VISUAL_HOOK_PREVIEW.mp4", "side_by_side": "VISUAL_HOOK_PREVIEW_SBS.mp4",
                    "sha256": {"treatment": VH.file_sha256(W / "VISUAL_HOOK_PREVIEW.mp4"),
                               "side_by_side": VH.file_sha256(W / "VISUAL_HOOK_PREVIEW_SBS.mp4")}}
        doc = {"schema_version": 1, "run_id": run_id, "created_at": now_ts(),
               "edit_token": token, "context_source": "workdir" if ctx_dir == W else "prep_copy",
               "context_note": why, "input_digest": res["context"]["input_digest"],
               "plan": plan, "report": res["report"], "preview": prev}
        if VH.edit_token(W) != token:
            VH.atomic_write_json(rdir / f"stale_{run_id}.json", doc)
            VH.atomic_write_json(status_path, {"state": "stale", "run_id": run_id, "finished": now_ts()})
            rec.update(status="stale", detail="הציר השתנה בזמן ההכנה — התצוגה נזרקה")
        else:
            VH.atomic_write_json(rdir / "current.json", doc)
            VH.atomic_write_json(status_path, {"state": "done", "run_id": run_id, "finished": now_ts()})
            rec.update(status="done", detail=res["report"]["suggestion_label_he"])
        if ctx_dir != W:
            shutil.rmtree(ctx_dir, ignore_errors=True)
        print(f"✅ {rec['detail']}")
        return 0
    except Exception as e:
        rec.update(status="failed", detail=str(e)[:400])
        VH.atomic_write_json(status_path, {"state": "failed", "run_id": run_id, "error": str(e)[:400],
                                           "finished": now_ts()})
        print(f"❌ {e}")
        return 1
    finally:
        # אין output_hash ואין artifact לעבודת תצוגה — גם כש-FINAL ישן קיים בתיקייה
        rec["output_hash"] = None
        rec["artifact_id"] = None
        rec["finished_at"] = now_ts()
        runner_mod.save_run(W, rec)
        runner_mod.release_lock(W)


def main() -> int:
    ap = argparse.ArgumentParser(description="Visual Hook Engine CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyze")
    p.add_argument("--workdir", required=True)
    p.add_argument("--body")
    p.add_argument("--words")
    p = sub.add_parser("plan")
    p.add_argument("--workdir", required=True)
    p.add_argument("--mode", choices=("shadow", "auto"), default="shadow")
    p.add_argument("--output", required=True)
    p.add_argument("--select", default=None)
    p = sub.add_parser("preview")
    p.add_argument("--workdir", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--render-engine", choices=("v1", "v2"), default="v1")
    p.add_argument("--output", required=True)
    p.add_argument("--seconds", type=float, default=10.0)
    p.add_argument("--side-by-side", action="store_true")
    p = sub.add_parser("validate")
    p.add_argument("--workdir", required=True)
    p.add_argument("--plan", required=True)
    p = sub.add_parser("prepare-review")
    p.add_argument("--workdir", required=True)
    p.add_argument("--run-id", default=None)
    a = ap.parse_args()
    try:
        return {"analyze": cmd_analyze, "plan": cmd_plan, "preview": cmd_preview,
                "validate": cmd_validate, "prepare-review": cmd_prepare_review}[a.cmd](a)
    except VH.HookError as e:
        print(f"❌ {e.code}: {e.detail}")
        return 2 if e.code == "HOOK_REVIEW_STALE" else 1


if __name__ == "__main__":
    sys.exit(main())
