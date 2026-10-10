#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relvid.hook_render — מהדר אחד לתוכנית Visual Hook, לשני המנועים (11.9.26).

למה perspective ולא zoompan/crop+scale
--------------------------------------
* `zoompan` מעגל את x/y לפיקסלים שלמים ⇒ רעד בזום איטי (הסיכון "robotic").
* `crop` מקבע w/h באתחול — אי אפשר לזום ממנו בפריים-לפריים.
* `scale:eval=frame` משנה גודל פריים באמצע גרף — שביר.
* `perspective:eval=frame` ממפה ארבע פינות מקור (תת-פיקסל, cubic) לפריים פלט
  בגודל קבוע, עם תמיכת timeline (`enable`). מחוץ ל-cue הפילטר **כבוי**, כלומר
  הפריים עובר ללא נגיעה (נמדד 11.9.26: הפרש 0 בדיוק מחוץ לחלון, סימטריה
  מלאה סביב ה-keyframe, ECC מול טרנספורם הייחוס 0.99986).

הביטויים נבנים **כאן** מתבנית קבועה ומספרים מאומתים — אף פעם לא מחרוזת
שהגיעה מבחוץ. v1 מחיל אותם על הגוף הנקי (visual_base); v2 מחיל אותם בתוך
שרשרת ה-[base] של הסגמנט, לפני בירול וכתוביות, **בלי overlay** (overlay
בגרף הוא מפעיל התקיעה הידועה — FFMPEG-STALL.md).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

from . import visual_hook as VH

ABI = "vh-crop-perspective-1"


# ═══════════════════════════════════════════════════════════ IR
def _fmt(v: float) -> str:
    s = f"{float(v):.6f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def _piece(kfs_local, comp: int, var: str) -> str:
    """ביטוי smoothstep רציף-למקוטעין על keyframes בזמן מקומי. מחוץ לטווח —
    הערך של ה-keyframe הקרוב (הראשון והאחרון הם זהות בתוכנית תקפה)."""
    # comp: 0=x · 1=y · 2=x+w · 3=y+h
    pick = (lambda r: r[0], lambda r: r[1], lambda r: r[0] + r[2], lambda r: r[1] + r[3])[comp]
    vals = [(p, pick(r)) for p, r in kfs_local]
    expr = _fmt(vals[-1][1])
    for (p0, v0), (p1, v1) in reversed(list(zip(vals, vals[1:]))):
        if abs(v1 - v0) < 1e-12:
            seg = _fmt(v0)
        else:
            u = f"(({var}-{_fmt(p0)})/{_fmt(p1 - p0)})"
            seg = f"({_fmt(v0)}+({_fmt(v1 - v0)})*{u}*{u}*(3-2*{u}))"
        expr = f"if(lt({var},{_fmt(p1)}),{seg},{expr})"
    return f"if(lt({var},{_fmt(vals[0][0])}),{_fmt(vals[0][1])},{expr})"


def perspective_filter(cue: dict, *, frame_offset: float = 0.0, frame_scale: float = 1.0,
                       interpolation: str = "cubic") -> str:
    """cue על ציר body_final ⇒ פילטר על ציר פריימים מקומי p = (F - offset) * scale.
    v1: offset=0, scale=1. v2: offset=תחילת הסגמנט בפריימים סופיים, scale=speed
    (הבסיס בסגמנט הוא לפני-האצה ב-30fps). ההמרה קורית **פעם אחת**, כאן."""
    var = "(in-1)"
    kl = [((k["frame"] - frame_offset) * frame_scale, [float(v) for v in k["rect"]])
          for k in cue["keyframes"]]
    X = _piece(kl, 0, var)
    Y = _piece(kl, 1, var)
    XW = _piece(kl, 2, var)
    YH = _piece(kl, 3, var)
    # עיגול ל-6 ספרות לפני floor/ceil: 40×1.15 הוא 45.99999999999999 בנקודה צפה
    lo = max(0, int(math.floor(round((cue["start_frame"] - frame_offset) * frame_scale, 6))))
    hi = int(math.ceil(round((cue["end_frame"] - 1 - frame_offset) * frame_scale, 6)))
    q = lambda e, d: f"'({e})*{d}'"                    # noqa: E731 — ציטוט filtergraph
    return (f"perspective=x0={q(X, 'W')}:y0={q(Y, 'H')}:x1={q(XW, 'W')}:y1={q(Y, 'H')}"
            f":x2={q(X, 'W')}:y2={q(YH, 'H')}:x3={q(XW, 'W')}:y3={q(YH, 'H')}"
            f":interpolation={interpolation}:sense=source:eval=frame"
            f":enable='between(n,{lo},{hi})'")


def compile_for_segment(plan: dict, seg_start_frame: int, seg_n_frames: int, speed: float) -> list:
    """IR לסגמנט אחד: רק cues שחותכים את טווח הפריימים הסופי שלו. סגמנט שאינו
    נחתך מקבל רשימה ריקה — ולכן מפתח המטמון שלו לא משתנה בכלל."""
    out = []
    if not plan or plan.get("recipe") in (None, "NO_OP"):
        return out
    a, b = int(seg_start_frame), int(seg_start_frame) + int(seg_n_frames)
    for c in plan.get("cues") or []:
        if c["end_frame"] <= a or c["start_frame"] >= b:
            continue
        flt = perspective_filter(c, frame_offset=a, frame_scale=float(speed))
        frag = {"abi": ABI, "plan_digest": plan["plan_digest"], "cue": c,
                "seg_start_frame": a, "speed": round(float(speed), 4)}
        out.append({"cue_id": c["id"], "filter": flt, "fragment": frag,
                    "fragment_digest": VH.digest(frag),
                    "global_frames": [max(a, c["start_frame"]), min(b, c["end_frame"])]})
    return out


# ═══════════════════════════════════════════════════════════ v1
def _audio_md5(path) -> str | None:
    r = subprocess.run([VH.ffbin(), "-nostdin", "-loglevel", "error", "-i", str(path),
                        "-map", "0:a:0?", "-c", "copy", "-f", "md5", "-"],
                       capture_output=True, text=True, timeout=300)
    s = (r.stdout or "").strip()
    return s if r.returncode == 0 and s.startswith("MD5=") else None


def _decoded_frames(path) -> int:
    return int(VH.probe_video(path).get("frame_count") or 0)


def render_v1(body_path, plan: dict, out_path, *, crf: int = 18, preset: str = "medium",
              first_frames: int | None = None) -> dict:
    """הגוף הנקי ⇒ visual_base עם אותו אודיו (stream copy) ואותו מספר פריימים.
    NO_OP מחזיר את הנתיב המקורי בלי שום קידוד. כשל ⇒ HookError (לעולם לא NO_OP
    שקט אחרי אישור)."""
    body_path, out_path = Path(body_path), Path(out_path)
    base_receipt = {"schema_version": 1, "plan_digest": plan["plan_digest"], "renderer": "v1",
                    "abi": ABI, "recipe": plan["recipe"]}
    if plan["recipe"] == "NO_OP":
        return dict(base_receipt, applied=False, output={"path": str(body_path), "encoded": False},
                    diagnostics={"note": "NO_OP — אפס קידוד"})
    if not body_path.exists():
        raise VH.HookError("HOOK_ASSET_MISSING", f"הגוף הנקי חסר: {body_path}")
    probe = VH.probe_video(body_path)
    n = int(first_frames or plan["timeline"]["frame_count"])
    if not first_frames and probe["frame_count"] != plan["timeline"]["frame_count"]:
        raise VH.HookError("HOOK_TIMELINE_MISMATCH",
                           f"לגוף {probe['frame_count']} פריימים, בתוכנית {plan['timeline']['frame_count']}")
    chain = ",".join(perspective_filter(c) for c in plan["cues"])
    pix = probe.get("pix_fmt") if probe.get("pix_fmt") in ("yuv420p", "yuv420p10le") else "yuv420p"
    col = probe.get("color") or {}
    cmd = [VH.ffbin(), "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(body_path), "-filter_complex", f"[0:v]{chain}[v]",
           "-map", "[v]", "-map", "0:a?", "-c:a", "copy",
           "-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", pix,
           "-fps_mode", "passthrough"]
    # ⚠️ בלי ‎-frames:v ובלי ‎-r בגימור מלא. נמדד 11.9.26 (סקאלת-הבריאות): כשזרם
    # האודיו ארוך מהווידאו בכמה מאות ms, ‎-frames:v סוגר את כל הפלט כשהווידאו מגיע
    # לתקרה — וזנב האודיו נחתך. HOOK_AUDIO_CHANGED תפס את זה על הפקודה האמיתית.
    # הפילטר לא משנה מספר פריימים; הספירה נאכפת אחרי הקידוד (HOOK_FRAME_COUNT).
    if first_frames:
        cmd += ["-frames:v", str(n)]
    for opt, key in (("-color_primaries", "primaries"), ("-color_trc", "trc"),
                     ("-colorspace", "space"), ("-color_range", "range")):
        if col.get(key) and col.get(key) not in ("unknown", "reserved"):
            cmd += [opt, col[key]]
    if first_frames:
        cmd += ["-t", f"{n / 30:.5f}"]
    tmp = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)
    cmd += ["-movflags", "+faststart", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0 or not tmp.exists():
        raise VH.HookError("HOOK_RENDER_FAILED", (r.stderr or "")[-600:])
    got = _decoded_frames(tmp)
    if got != n:
        tmp.unlink(missing_ok=True)
        raise VH.HookError("HOOK_FRAME_COUNT", f"פוענחו {got} פריימים, נדרשו {n}")
    a_in, a_out = (_audio_md5(body_path), _audio_md5(tmp)) if not first_frames else (None, None)
    if not first_frames and a_in != a_out:
        tmp.unlink(missing_ok=True)
        raise VH.HookError("HOOK_AUDIO_CHANGED", "האודיו אחרי הטיפול אינו זהה-בייטים לגוף הנקי")
    os.replace(tmp, out_path)
    return dict(base_receipt, applied=True,
                input={"path": str(body_path), "sha256": VH.file_sha256(body_path)},
                output={"path": str(out_path), "sha256": VH.file_sha256(out_path),
                        "decoded_frames": got, "encoded": True},
                audio={"mode": "preserve", "input_md5": a_in, "output_md5": a_out,
                       "equal": a_in == a_out},
                encode={"crf": crf, "preset": preset, "pix_fmt": pix},
                emitted_transitions=[], filter_sha256=VH.digest(chain),
                diagnostics={"ffmpeg": _ffmpeg_version()})


def _ffmpeg_version() -> str:
    try:
        r = subprocess.run([VH.ffbin(), "-version"], capture_output=True, text=True, timeout=20)
        return (r.stdout or "").splitlines()[0][:80]
    except Exception:
        return "?"


def render_preview(body_path, plan: dict, out_path, *, seconds: float = 10.0,
                   side_by_side: bool = False) -> dict:
    """קטע השוואה 0-10ש (לא תוצר פרסום). אותו IR בדיוק כמו בגימור; קידוד קל יותר.
    side_by_side: מקור | טיפול, 540×960 כל צד, עם האודיו המקורי."""
    body_path, out_path = Path(body_path), Path(out_path)
    n = min(int(round(seconds * 30)), int(plan["timeline"]["frame_count"]))
    vf = ",".join(perspective_filter(c) for c in plan.get("cues") or []) or "null"
    if side_by_side:
        graph = (f"[0:v]split=2[o][t];[t]{vf}[tt];[o]scale=540:960:flags=lanczos[os];"
                 f"[tt]scale=540:960:flags=lanczos[ts];[os][ts]hstack=inputs=2[v]")
    else:
        graph = f"[0:v]{vf}[v]"
    tmp = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)
    cmd = [VH.ffbin(), "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(body_path), "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
           "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-frames:v", str(n), "-t", f"{n / 30:.4f}",
           "-movflags", "+faststart", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    if r.returncode != 0 or not tmp.exists():
        raise VH.HookError("HOOK_PREVIEW_FAILED", (r.stderr or "")[-600:])
    os.replace(tmp, out_path)
    return {"path": str(out_path), "frames": n, "side_by_side": side_by_side,
            "plan_digest": plan["plan_digest"], "publishable": False}


def caption_band(words_file, brand="rel") -> dict | None:
    """אותה גיאומטריית רצועה בדיוק כמו render.build_timeline (ומשם co.band_box),
    לשימוש מסכת ה-QA. כשל ⇒ None (ה-QA ממסך אז את כל האזור התחתון)."""
    try:
        import sys
        from . import render as RENDER
        for p in (str(RENDER.TOOLS), str(RENDER.APPDIR)):
            if p not in sys.path:
                sys.path.insert(0, p)
        from captions_build import group_cues, load_words
        import captions_overlay as co
        from PIL import ImageFont
        cues = group_cues(load_words(str(words_file)))
        if not cues:
            return None
        Hh, Ww = 1920, 1080
        fontsize, stroke, marginv = 120, 7, 430
        prof = (co.BRAND_PROFILES.get(co.BRAND_ALIASES.get(brand, brand)) or co.BRAND_PROFILES["club"])
        font = ImageFont.truetype(str(prof["font"]), fontsize)
        y0, h = co.band_box(cues, Ww, Hh, font, stroke, marginv)
        return {"y0": int(y0), "h": int(h)}
    except Exception:
        return None


def v2_receipt(plan: dict, tl_meta: dict, master_path) -> dict:
    """קבלת v2: התוכנית נצרבה בשרשרת הווידאו של הסגמנטים המושפעים בלבד.
    שרשרת האודיו לא נבנית מה-IR בכלל (render_segment בונה אותה מ-[0:a] בנפרד)."""
    vh = (tl_meta or {}).get("visual_hook") or {}
    return {"schema_version": 1, "plan_digest": plan["plan_digest"], "renderer": "v2", "abi": ABI,
            "recipe": plan["recipe"], "applied": plan["recipe"] != "NO_OP",
            "output": {"path": str(master_path), "sha256": VH.file_sha256(master_path),
                       "decoded_frames": VH.probe_video(master_path).get("frame_count"), "encoded": True},
            "affected_segments": vh.get("affected_segments"),
            "frames_v2": vh.get("frames_v2"), "frames_plan": vh.get("frames_plan"),
            "audio": {"mode": "preserve", "chain_unchanged": True},
            "emitted_transitions": [], "diagnostics": {"ffmpeg": _ffmpeg_version()}}
