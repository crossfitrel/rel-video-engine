#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relvid.visual_hook — Visual Hook Engine (MVP: NO_OP + SMART_PUNCH_IN), 11.9.26.

═══════════════════════════════════════════════════════════════════════════
מה זה ומה זה לא
═══════════════════════════════════════════════════════════════════════════
בוחר *אם* ואיך לחזק את 0-10 השניות הראשונות **בתמונה בלבד**, מתוך הצילום
האמיתי. אינו נוגע בדיבור, ב-EDL, במשך, בכתוביות, במוזיקה או בפרסום.
NO_OP היא החלטה עריכתית מוצלחת — לא כישלון.

ההפרדה כאן נוקשה:
  * **החלטה** (המודול הזה) — הקשר, ניתוח, מועמדים, בחירה, תוכנית קפואה.
  * **ביצוע** (`relvid/hook_render.py`) — מהדר את אותה תוכנית ל-v1 ול-v2.
אף מנוע רינדור לא מקבל החלטה עריכתית; שניהם צורכים `visual_hook_plan.json`.

מקור האפיון: handoff/visual-hook-engine/ (CLAUDE_OPUS_HANDOFF.md +
VISUAL_HOOK_ARCHITECTURE.md). ברירת מחדל off; auto בלי קוהורט מאושר = NO_OP.

עקרונות שנאכפים בקוד (ולא רק כתובים):
  1. ספק ⇒ NO_OP. גלאי פנים אינו אימות זהות; תנועה אינה ראיה לתמורה.
  2. digest סמנטי: אין חותמות זמן, נתיבים משתנים או מוזיקה בקלט ה-digest.
  3. אותו קלט ⇒ אותה תוכנית. אין אקראיות ואין שעון בבחירה.
  4. פרמטרים = דאטה מוקלד שנבדק, לעולם לא מחרוזת פילטר/HTML מבחוץ.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
TOOLS = PKG_DIR.parent
SYSDIR = TOOLS.parent

SCHEMA_VERSION = 1
ANALYSIS_VERSION = 2
FPS = 30
MODES = ("off", "shadow", "auto")
REGISTRY_PATH = TOOLS / "visual_hook_registry.json"
POLICY_PATH = TOOLS / "visual_hook_policy.json"
HOOK_DIR = "visual_hook"
FILES = {
    "analysis": "visual_hook_analysis.json",
    "candidates": "visual_hook_candidates.json",
    "plan": "visual_hook_plan.json",
    "render": "visual_hook_render.json",
    "report": "visual_hook_report.json",
    "qa": "visual_hook_qa.json",
    "preview": "VISUAL_HOOK_PREVIEW.mp4",
}
IDENTITY = [0.0, 0.0, 1.0, 1.0]
LABEL_HE = {"NO_OP": "פתיחה חזותית: ללא שינוי", "SMART_PUNCH_IN": "פתיחה חזותית: הדגשה עדינה"}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")
STOPWORDS_HE = {
    "של", "את", "על", "זה", "לא", "אם", "יש", "הוא", "היא", "אני", "אתם", "אתן",
    "שלכם", "שלכן", "כל", "מה", "גם", "רק", "עם", "או", "כי", "אבל", "אז", "כמו",
    "יותר", "הם", "הן", "אנחנו", "שלי", "לכם", "להם", "זו", "הזה", "הזאת", "אחד",
    "אחת", "בו", "בה", "לו", "לה", "שם", "פה", "כאן", "היה", "הייתה", "להיות",
    "אין", "עוד", "כבר", "איך", "למה", "מי", "כך", "ככה", "אותו", "אותה", "שלנו",
}


class HookError(Exception):
    """שגיאה עם קוד יציב — האפליקציה והצנרת מסתעפות לפי code, לא לפי טקסט."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


# ═══════════════════════════════════════════════════════════ קנוניזציה
def _normalize(o):
    if isinstance(o, bool) or o is None or isinstance(o, str):
        return o
    if isinstance(o, int):
        return o
    if isinstance(o, float):
        if not math.isfinite(o):
            raise HookError("HOOK_NONFINITE", f"ערך לא-סופי בקלט digest: {o}")
        r = round(o, 6)
        return int(r) if r == int(r) and abs(r) < 1e15 else r
    if isinstance(o, dict):
        return {str(k): _normalize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_normalize(v) for v in o]
    raise HookError("HOOK_BAD_TYPE", f"טיפוס לא נתמך ב-digest: {type(o).__name__}")


def canonical_json(obj) -> str:
    return json.dumps(_normalize(obj), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(obj) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


_FILE_HASH_CACHE: dict = {}


def file_sha256(path) -> str | None:
    """hash תוכן **מלא** (לא quick). מטמון בזיכרון לפי (נתיב, גודל, mtime_ns)."""
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return None
    key = (str(p.resolve()), st.st_size, st.st_mtime_ns)
    if key in _FILE_HASH_CACHE:
        return _FILE_HASH_CACHE[key]
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    _FILE_HASH_CACHE[key] = "sha256:" + h.hexdigest()
    return _FILE_HASH_CACHE[key]


def _jload(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, allow_nan=False),
                   encoding="utf-8")
    os.replace(tmp, path)


def now_ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def edit_token(workdir) -> str:
    """טוקן **תוכן** של מה שקובע את הקשר הפתיחה: חיתוכים (review+keep_segments),
    טקסט מתוקן והערות (notefix משנה מילים). בכוונה **לא** head ה-revision כמו
    `edl_token` של השרת: לחיצה על "אשר" שומרת קודם (doSave) ויוצרת revision
    חדש גם בלי שום שינוי — טוקן מבוסס-head היה הופך כל תצוגה ל"מיושנת" ברגע
    האישור, והטיפול לעולם לא היה נקשר. (ל-lost-update בין טאבים יש pref_version.)"""
    w = Path(workdir)
    edl = _jload(w / "edl.json", {}) or {}
    parts = {"review": edl.get("review"), "keep_segments": edl.get("keep_segments")}
    for n in ("edited.txt", "correct_transcript.txt", "comments.json", "words_corrected.json"):
        p = w / n
        parts[n] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return "tok_" + digest(parts)[7:23]


# ═══════════════════════════════════════════════════════════ רשומה ומדיניות
def load_registry(path=None) -> dict:
    doc = _jload(path or REGISTRY_PATH)
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise HookError("HOOK_REGISTRY_INVALID", "רשומת המתכונים חסרה או בגרסה לא נתמכת")
    out = {}
    for r in doc.get("recipes") or []:
        rid = r.get("id")
        if not rid or rid in out:
            raise HookError("HOOK_REGISTRY_INVALID", f"מזהה מתכון חסר/כפול: {rid}")
        if r.get("status") not in ("mvp", "pilot_pending_policy", "deferred", "excluded"):
            raise HookError("HOOK_REGISTRY_INVALID", f"{rid}: status לא מוכר")
        if not isinstance(r.get("version"), int) or r["version"] < 1:
            raise HookError("HOOK_REGISTRY_INVALID", f"{rid}: version לא תקין")
        out[rid] = r
    if "NO_OP" not in out:
        raise HookError("HOOK_REGISTRY_INVALID", "NO_OP חייב להיות ברשומה")
    # כל שרשרת fallback מסתיימת ב-NO_OP ואינה מעגלית
    for rid in out:
        seen, cur = set(), rid
        while cur != "NO_OP":
            if cur in seen or cur not in out:
                raise HookError("HOOK_REGISTRY_INVALID", f"{rid}: שרשרת fallback שבורה/מעגלית")
            seen.add(cur)
            fb = out[cur].get("fallbacks") or []
            if not fb:
                raise HookError("HOOK_REGISTRY_INVALID", f"{cur}: אין fallback שמגיע ל-NO_OP")
            cur = fb[-1] if "NO_OP" in fb else fb[0]
    return out


def recipe_runnable(registry: dict, rid: str) -> bool:
    r = registry.get(rid) or {}
    return r.get("status") == "mvp" and bool(r.get("implemented"))


def load_policy(path=None) -> dict:
    pol = _jload(path or POLICY_PATH)
    if not isinstance(pol, dict) or pol.get("version") != 1:
        raise HookError("HOOK_POLICY_INVALID", "מדיניות Visual Hook חסרה או בגרסה לא נתמכת")
    if pol.get("default_mode") not in MODES:
        raise HookError("HOOK_POLICY_INVALID", "default_mode לא חוקי")
    return pol


def policy_digest(policy: dict) -> str:
    return digest({k: v for k, v in policy.items() if not k.startswith("_")})


# ═══════════════════════════════════════════════════════════ מדיה
def ffbin(name="ffmpeg") -> str:
    """נתיב מוחלט (לקח L50/L50b: שרת/תהליך בלי Homebrew ב-PATH)."""
    p = shutil.which(name)
    if p:
        return p
    for d in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        if Path(d, name).exists():
            return str(Path(d, name))
    return name


def _run(cmd, timeout=600, binary=False):
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True,
                              text=not binary, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess([str(c) for c in cmd], 124,
                                           e.stdout or (b"" if binary else ""),
                                           (e.stderr or (b"" if binary else "")))


def probe_video(path) -> dict:
    r = _run([ffbin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_packets",
              "-show_entries",
              "stream=width,height,r_frame_rate,nb_read_packets,pix_fmt,color_primaries,"
              "color_transfer,color_space,color_range:format=duration",
              "-of", "json", str(path)], timeout=120)
    try:
        doc = json.loads(r.stdout or "{}")
        s = (doc.get("streams") or [{}])[0]
        num, den = (s.get("r_frame_rate") or "0/1").split("/")
        return {"width": int(s.get("width") or 0), "height": int(s.get("height") or 0),
                "fps_num": int(num), "fps_den": int(den) or 1,
                "frame_count": int(s.get("nb_read_packets") or 0),
                "duration": round(float((doc.get("format") or {}).get("duration") or 0), 3),
                "pix_fmt": s.get("pix_fmt"),
                "color": {"primaries": s.get("color_primaries"), "trc": s.get("color_transfer"),
                          "space": s.get("color_space"), "range": s.get("color_range")}}
    except Exception:
        return {"width": 0, "height": 0, "fps_num": 0, "fps_den": 1, "frame_count": 0,
                "duration": 0.0, "pix_fmt": None, "color": {}}


def resolve_body(workdir) -> Path:
    """הגוף הנקי הסופי כפי שהצנרת פותרת אותו: EXPORT_TIGHT כשההידוק הפיק קובץ,
    אחרת EXPORT (במסלול --director ה-TIGHT **הוא** ה-EXPORT)."""
    w = Path(workdir)
    t = w / "EXPORT_TIGHT.mp4"
    return t if t.exists() else (w / "EXPORT.mp4")


def load_words(path) -> list:
    ws = _jload(path, []) or []
    out = []
    for i, x in enumerate(ws):
        try:
            s, e = float(x["start"]), float(x["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(s) and math.isfinite(e)):
            continue
        out.append({"id": i, "word": str(x.get("word", "")), "start": s, "end": e})
    return out


def _strip(word: str) -> str:
    return re.sub(r"[^\w֐-׿]", "", word or "")


def words_provenance(words: list, body: dict) -> dict:
    """האם קובץ המילים שייך לדור המדיה הזה. משך בלבד אינו הוכחה — אבל מילים
    שחורגות מהגוף, או שנגמרות הרבה לפניו, הן בוודאות דור אחר."""
    reasons = []
    dur = float(body.get("duration") or 0.0)
    if not words:
        reasons.append("no_words")
    else:
        starts = [w["start"] for w in words]
        if any(b < a - 1e-6 for a, b in zip(starts, starts[1:])):
            reasons.append("non_monotonic_words")
        if words[0]["start"] < -0.05:
            reasons.append("negative_word_time")
        last = max(w["end"] for w in words)
        if dur and last > dur + 0.35:
            reasons.append("words_exceed_body")
        if dur and last < dur * 0.8:
            reasons.append("words_end_early")
    return {"ok": not reasons, "reasons": reasons,
            "last_word_end": round(max((w["end"] for w in words), default=0.0), 3),
            "body_duration": dur}


def resolve_intro(workdir, manifest: dict, title: str = "") -> dict:
    """פתיח מלא נפתר **לפני** הבחירה, באותה לוגיקה של הצנרת (שדה נעוץ במניפסט,
    ואחרת כותרת/נושא/שם). `full_intro == null` לבדו אינו ראיה שאין פתיח."""
    w = Path(workdir)
    pin = (manifest.get("full_intro") or {}).get("id")
    if pin:
        fid, src = pin, "manifest"
    else:
        fid, src = None, None
        try:
            import sys
            if str(TOOLS) not in sys.path:
                sys.path.insert(0, str(TOOLS))
            import fixed_intro as fi_mod
            fid, _ph = fi_mod.detect_full_intro(manifest.get("name"), manifest.get("topic"),
                                                title or "", w.name)
            src = "title" if fid else None
        except Exception:
            fid, src = None, "detector_unavailable"
    intro_frames = 0
    if fid:
        try:
            import fixed_intro as fi_mod
            ap, _rec = fi_mod.full_intro_asset(fid)
            if ap and Path(ap).exists():
                intro_frames = int(round(float(probe_video(ap)["duration"]) * FPS))
        except Exception:
            intro_frames = 0
    return {"present": bool(fid), "id": fid, "source": src, "intro_frames": intro_frames}


def reservations_for(workdir, broll_items, frame_count: int, words: list | None = None) -> list:
    """שכבות מוגנות על ציר body_final: בירול (ידני/קיים/מפורש), המחשות, אפקט פורמט."""
    out = []
    for it in broll_items or []:
        try:
            s0 = float(it.get("insert_at", 0))
            e0 = float(it.get("insert_end", s0 + float(it.get("clip_len", 2.8))))
        except (TypeError, ValueError):
            continue
        a, b = max(0, int(math.floor(s0 * FPS))), min(frame_count, int(math.ceil(e0 * FPS)))
        if b > a:
            out.append({"kind": "broll", "start_frame": a, "end_frame": b,
                        "ref": Path(str(it.get("path") or it.get("file") or "")).name})
    ill = _jload(Path(workdir) / "illustration_plan.json", {}) or {}
    for it in (ill.get("picks") or ill.get("plan") or []):
        try:
            s0, e0 = float(it.get("start")), float(it.get("end"))
        except (TypeError, ValueError):
            continue
        out.append({"kind": "illustration", "start_frame": int(math.floor(s0 * FPS)),
                    "end_frame": int(math.ceil(e0 * FPS)), "ref": str(it.get("id", ""))})
    if words:
        try:
            import sys
            if str(TOOLS) not in sys.path:
                sys.path.insert(0, str(TOOLS))
            import fixed_intro as fx_mod
            hits = fx_mod.detect([{"word": w["word"], "start": w["start"], "end": w["end"]}
                                  for w in words])
            for h in hits[:1]:
                e = float(h["end"])
                out.append({"kind": "format_effect", "start_frame": max(0, int((e - 1.0) * FPS)),
                            "end_frame": int((e + 2.0) * FPS), "ref": h.get("format_id", "")})
        except Exception:
            pass
    out.sort(key=lambda r: (r["start_frame"], r["end_frame"], r["kind"], r["ref"]))
    return out


def broll_items_from_workdir(workdir, manifest: dict, broll_plan_file=None) -> tuple[list, str]:
    """אותו סדר עדיפויות כמו הצנרת: ידני מהאפליקציה > תוכנית מפורשת > broll_plan.json."""
    prefs = (manifest.get("finish_prefs") or {}).get("broll") or {}
    if prefs.get("mode") == "off":
        return [], "prefs_off"
    if prefs.get("mode") == "manual":
        return [dict(it, insert_end=float(it.get("insert_at", 0)) + float(it.get("clip_len", 2.8))
                     if it.get("insert_end") is None else it.get("insert_end"))
                for it in (prefs.get("items") or [])], "manual"
    pf = Path(broll_plan_file) if broll_plan_file else (Path(workdir) / "broll_plan.json")
    plan = _jload(pf, {}) or {}
    return list(plan.get("plan") or []), ("plan_file" if plan.get("plan") else "none")


def measured_speed(workdir, body_probe: dict) -> float:
    """כמו render.build_timeline: היחס בין סכום tight_keeps למשך הגוף הוא ההאצה."""
    w = Path(workdir)
    tight = _jload(w / "tight_keeps.json", None)
    edl = _jload(w / "edl.json", {}) or {}
    try:
        if tight:
            from . import sync as sync_mod
            keeps = sync_mod.tight_keeps_in_source(edl, tight)
        else:
            keeps = edl.get("keep_segments") or []
        total = sum(float(k["end"]) - float(k["start"]) for k in keeps)
        d = float(body_probe.get("duration") or 0)
        if d > 0.5 and total > 0:
            ratio = total / d
            return round(ratio, 4) if abs(ratio - 1.0) > 0.01 else 1.0
    except Exception:
        pass
    return 1.0


# ═══════════════════════════════════════════════════════════ הקשר
def build_context(workdir, *, body=None, words_file=None, broll_items=None,
                  broll_plan_file=None, brand=None, content_type=None, title="",
                  intro=None, policy=None, manifest=None) -> dict:
    """ההקשר הסמנטי הקפוא של גוף סופי אחד. `input_digest` הוא הזהות שלו:
    מקור (תוכן מלא) + מיפוי (EDL/הידוק/האצה) + מילים + שכבות מוגנות + פתיח.
    **לא** כולל את הבייטים של EXPORT (קידוד חוזר אינו שינוי סמנטי) ולא
    מוזיקה/חותמות זמן."""
    w = Path(workdir).resolve()
    policy = policy or load_policy()
    manifest = manifest if manifest is not None else (_jload(w / "project_manifest.json", {}) or {})
    body_path = Path(body) if body else resolve_body(w)
    if not body_path.exists():
        raise HookError("HOOK_NO_BODY", f"אין גוף נקי לניתוח: {body_path.name}")
    bprobe = probe_video(body_path)
    wf = Path(words_file) if words_file else (w / "words_final.json")
    words = load_words(wf)
    prov = words_provenance(words, bprobe)
    align = words_audio_alignment(body_path, words) if words else None
    prov["alignment"] = align
    if align and align.get("misaligned"):
        prov["ok"] = False
        prov["reasons"].append("words_audio_offset")
    if broll_items is None:
        broll_items, broll_src = broll_items_from_workdir(w, manifest, broll_plan_file)
    else:
        broll_src = "explicit"
    intro = intro if intro is not None else resolve_intro(w, manifest, title)
    fc = int(bprobe["frame_count"])
    resv = reservations_for(w, broll_items, fc, words)
    edl = _jload(w / "edl.json", {}) or {}
    seg_src = w / "segment_sources.json"
    inp = w / "INPUT.mp4"
    speed = measured_speed(w, bprobe)
    project_id = str(manifest.get("project_id") or "")
    semantic = {
        "schema": SCHEMA_VERSION,
        "project_id": project_id,
        "source": {"input_sha256": file_sha256(inp) if inp.exists() else None,
                   "segment_sources": digest(_jload(seg_src, {})) if seg_src.exists() else None},
        "mapping": {"keep_segments": edl.get("keep_segments") or [],
                    "review": edl.get("review") or {},
                    "tight_keeps": _jload(w / "tight_keeps.json", None),
                    "speed": speed},
        "words": [[x["word"], round(x["start"], 3), round(x["end"], 3)] for x in words],
        "body": {"frame_count": fc, "width": bprobe["width"], "height": bprobe["height"],
                 "fps": [bprobe["fps_num"], bprobe["fps_den"]]},
        "brand": brand or manifest.get("brand") or "rel",
        "content_type": content_type or manifest.get("content_type") or "value",
        # השכבות המוגנות **אינן** חלק מ-input_digest: יש להן reservation_digest משלהן,
        # ושינוי שלהן מחוץ לחלון הפתיחה (למשל רוטציית בירול שבחרה קליפ אחר ב-20ש)
        # אינו משנה את התמונה שאושרה. חפיפה לחלון — כן (ראה validate_plan).
        "intro": {"present": intro["present"], "id": intro["id"],
                  "intro_frames": intro["intro_frames"]},
        "analysis_version": ANALYSIS_VERSION,
        "renderer_abi": (policy.get("renderer") or {}).get("abi"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "workdir": str(w),
        "body_path": str(body_path),
        "body_probe": bprobe,
        "words_file": str(wf),
        "words": words,
        "words_provenance": prov,
        "broll_source": broll_src,
        "reservations": resv,
        "reservation_digest": digest(resv),
        "intro": intro,
        "brand": semantic["brand"],
        "content_type": semantic["content_type"],
        "speed": speed,
        "input_digest": digest(semantic),
        "policy_digest": policy_digest(policy),
    }


# ═══════════════════════════════════════════════════════════ ניתוח
def _decode_gray(path, n_frames, w, h, select_every=1):
    vf = f"scale={w}:{h}:flags=area,format=gray"
    cmd = [ffbin(), "-nostdin", "-loglevel", "error", "-i", str(path)]
    if select_every > 1:
        vf = f"select=not(mod(n\\,{select_every})),{vf}"
        cmd += ["-vf", vf, "-fps_mode", "passthrough"]
    else:
        cmd += ["-vf", vf]
    cmd += ["-frames:v", str(int(math.ceil(n_frames / select_every))), "-f", "rawvideo", "-"]
    r = _run(cmd, timeout=600, binary=True)
    if r.returncode != 0:
        return None
    import numpy as np
    buf = np.frombuffer(r.stdout, dtype=np.uint8)
    k = buf.size // (w * h)
    return buf[:k * w * h].reshape(k, h, w) if k else None


def words_audio_alignment(body, words: list, secs: float = 12.0) -> dict | None:
    """זהות מילים↔מדיה מהאודיו עצמו: האם גבולות המילים יושבים על אנרגיית דיבור,
    ובאיזה היסט הם יושבים הכי טוב. מילים מדור עריכה אחר זזות — וזה נמדד כאן
    במקום להניח. (משך הקובץ לבדו אינו הוכחה.)"""
    import numpy as np
    ws = [x for x in words if x["end"] <= secs]
    if len(ws) < 4:
        return None
    r = _run([ffbin(), "-nostdin", "-loglevel", "error", "-i", str(body), "-t", f"{secs}",
              "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], timeout=120, binary=True)
    if r.returncode != 0 or not r.stdout:
        return None
    a = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float64)
    hop = 320                                        # 20ms
    n = a.size // hop
    if n < 50:
        return None
    rms = np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-9)
    db = 20 * np.log10(rms / 32768.0 + 1e-12)
    floor = float(np.percentile(db, 10))
    speech = db > max(floor + 10.0, -50.0)

    def score(off):
        vals = []
        for x in ws:
            i0, i1 = int((x["start"] + off) / 0.02), int(math.ceil((x["end"] + off) / 0.02))
            i0, i1 = max(0, i0), min(n, max(i1, i0 + 1))
            if i1 > i0:
                vals.append(float(speech[i0:i1].mean()))
        return sum(vals) / len(vals) if vals else 0.0

    offs = [round(o * 0.05, 2) for o in range(-10, 11)]
    scores = {o: score(o) for o in offs}
    best = max(offs, key=lambda o: (round(scores[o], 3), -abs(o)))
    s0 = scores[0.0]
    misaligned = abs(best) >= 0.2 and scores[best] - s0 > 0.15
    return {"score_at_0": round(s0, 3), "best_offset_sec": best, "best_score": round(scores[best], 3),
            "n_words": len(ws), "misaligned": bool(misaligned)}


def hook_quote(workdir, words: list, max_sec=6.0) -> dict:
    """משפט הפתיחה המדובר — מ-sentences_tight.json כשקיים, אחרת לפי פיסוק/פאוזה."""
    if not words:
        return {"word_ids": [], "quote": "", "start": None, "end": None, "source": "none"}
    end_t = None
    st = _jload(Path(workdir) / "sentences_tight.json", None)
    if isinstance(st, list) and st:
        try:
            end_t = float(st[0]["end"])
            src = "sentences_tight"
        except (KeyError, TypeError, ValueError):
            end_t = None
    if end_t is None:
        src = "punctuation"
        for i, x in enumerate(words):
            nxt = words[i + 1]["start"] if i + 1 < len(words) else None
            if re.search(r"[.?!]$", x["word"].strip()) or (nxt is not None and nxt - x["end"] > 0.5):
                end_t = x["end"]
                break
        if end_t is None:
            end_t = words[-1]["end"]
    end_t = min(end_t, words[0]["start"] + max_sec)
    sel = [x for x in words if x["start"] < end_t - 1e-6]
    return {"word_ids": [x["id"] for x in sel],
            "quote": " ".join(x["word"] for x in sel).strip(),
            "start": round(sel[0]["start"], 3) if sel else None,
            "end": round(sel[-1]["end"], 3) if sel else None, "source": src}


def choose_anchor(quote: dict, words: list, policy: dict) -> dict | None:
    lo, hi = (policy.get("crop_envelope") or {}).get("anchor_window_sec", [1.0, 5.0])
    byid = {x["id"]: x for x in words}
    cands = []
    for wid in quote.get("word_ids") or []:
        x = byid.get(wid)
        if not x or not (lo <= x["start"] <= hi):
            continue
        core = _strip(x["word"])
        if len(core) < 3 or core in STOPWORDS_HE:
            continue
        cands.append((-len(core), -(x["end"] - x["start"]), x["start"], x["id"], x))
    if not cands:
        return None
    cands.sort()
    x = cands[0][-1]
    return {"word_id": x["id"], "word": x["word"], "start": round(x["start"], 3),
            "end": round(x["end"], 3),
            "why": "המילה הארוכה ביותר במשפט הפתיחה בחלון 1-5ש (עדות: supported, לא סמנטיקה מאומתת)"}


def analyze(context: dict, policy: dict | None = None, *, use_cache=True) -> dict:
    """מדידות מקומיות דטרמיניסטיות על 0-10ש של הגוף הנקי. שום מודל ושום רשת."""
    policy = policy or load_policy()
    w = Path(context["workdir"])
    body = Path(context["body_path"])
    st = body.stat()
    cache_key = digest({"input": context["input_digest"], "v": ANALYSIS_VERSION,
                        "body": [st.st_size, st.st_mtime_ns]})
    cache_file = w / HOOK_DIR / "analysis_cache" / f"{cache_key[7:23]}.json"
    if use_cache and cache_file.exists():
        cached = _jload(cache_file)
        if cached and cached.get("cache_key") == cache_key:
            return cached
    fc = int(context["body_probe"]["frame_count"])
    win = min(int(policy.get("analysis_window_frames", 300)), fc)
    heur = policy.get("eligibility_heuristics") or {}
    unknowns, evidence = [], []
    meas = {"window_frames": win}
    faces_per_sample: list = []
    motion_boxes: list = []
    cuts: list = []
    mad: list = []
    cam = {"scale_drift_max": None, "pan_px_max": None}
    try:
        import numpy as np
        small = _decode_gray(body, win, 180, 320)
        if small is None or len(small) < 2:
            unknowns.append({"what": "motion", "why": "פענוח הגוף נכשל"})
        else:
            f = small.astype(np.int16)
            diff = np.abs(f[1:] - f[:-1])
            mad = [0.0] + [round(float(d.mean()), 3) for d in diff]
            med = float(np.median(mad[1:])) if len(mad) > 1 else 0.0
            # חיתוכים קשים: קפיצת MAD + היסטוגרמה שונה
            for i in range(1, len(small)):
                if mad[i] < max(float(heur.get("cut_mad_floor", 28.0)), 6.0 * med):
                    continue
                h1 = np.histogram(small[i - 1], bins=32, range=(0, 256))[0].astype(float)
                h2 = np.histogram(small[i], bins=32, range=(0, 256))[0].astype(float)
                c = float(np.corrcoef(h1, h2)[0, 1]) if h1.std() and h2.std() else 1.0
                if c < float(heur.get("cut_hist_corr_max", 0.6)):
                    cuts.append(i)
            # מעטפת תנועה לכל חצי שנייה (15 פריימים)
            for b0 in range(0, len(small), 15):
                seg = diff[max(0, b0 - 1):min(len(diff), b0 + 14)]
                if not len(seg):
                    motion_boxes.append(None)
                    continue
                m = (seg > 16).any(axis=0)
                ys, xs = np.nonzero(m)
                if xs.size < 0.002 * m.size:
                    motion_boxes.append(None)
                    continue
                x0, x1 = np.percentile(xs, [2, 98])
                y0, y1 = np.percentile(ys, [2, 98])
                motion_boxes.append([round(float(x0) / 180, 4), round(float(y0) / 320, 4),
                                     round(float(x1 - x0) / 180, 4), round(float(y1 - y0) / 320, 4)])
            meas["motion_mad"] = mad
            meas["motion_mad_median"] = round(med, 3)
            meas["hard_cuts"] = cuts
            meas["motion_boxes_15f"] = motion_boxes
            try:
                import cv2
                # מצלמה ≠ גוף. הסקייל נאמד **ישירות** בין פריים לפריים שלוש שניות אחריו
                # (לא סכום צעדים — צבירת רעש), ורק מנקודות על רקע שלא זז בכל הטווח.
                # דחיפת מצלמה אמיתית מזיזה את כל הפריים ⇒ אין רקע סטטי ⇒ "לא ניתן לאמת"
                # ⇒ NO_OP. חצובה + אדם שזז ⇒ רקע סטטי שופע ⇒ סקייל ≈ 0.
                spans, unreliable, skipped = [], 0, 0
                pans = []
                # תפר EDL (קפיצת תמונה באותו פריים) שובר התאמה ישירה בין שני צדדיו —
                # טווח שחוצה תפר מדולג, לא נספר "לא אמין". אם אין טווחי 3ש נקיים
                # מספיקים, עוברים לטווחי 1.5ש (הסקייל מוכפל ל-3ש שקולות).
                seam = [i for i in range(1, len(mad)) if mad[i] > max(8.0, 5.0 * med)]
                plan_spans = [(i, 90) for i in range(0, len(small) - 90, 15)
                              if not any(i < x <= i + 90 for x in seam)]
                if len(plan_spans) < 3:
                    plan_spans = [(i, 45) for i in range(0, len(small) - 45, 15)
                                  if not any(i < x <= i + 45 for x in seam)]
                skipped = len(range(0, max(0, len(small) - 90), 15)) - len(plan_spans)
                for i, L in plan_spans:
                    a, b = small[i], small[i + L]
                    stack = small[i:i + L + 1:5].astype(np.int16)
                    static = (np.abs(stack - stack[0]).max(axis=0) < 20).astype(np.uint8) * 255
                    static = cv2.erode(static, np.ones((5, 5), np.uint8))
                    pts = cv2.goodFeaturesToTrack(a, maxCorners=300, qualityLevel=0.01, minDistance=4,
                                                  mask=static)
                    if pts is None or len(pts) < 15:
                        unreliable += 1
                        continue
                    nxt, stt, _err = cv2.calcOpticalFlowPyrLK(a, b, pts, None, winSize=(21, 21), maxLevel=3)
                    good = (stt.reshape(-1) == 1) if stt is not None else np.zeros(len(pts), bool)
                    if int(good.sum()) < 15:
                        unreliable += 1
                        continue
                    M, inl = cv2.estimateAffinePartial2D(pts[good], nxt[good], method=cv2.RANSAC,
                                                         ransacReprojThreshold=1.0)
                    if M is None or inl is None or int(inl.sum()) < 12:
                        unreliable += 1
                        continue
                    spans.append(abs(math.log(max(1e-6, math.hypot(M[0, 0], M[1, 0])))) * (90.0 / L))
                    pans.append(math.hypot(M[0, 2], M[1, 2]))
                n_sp = len(spans) + unreliable
                reliable = n_sp > 0 and unreliable <= n_sp // 3
                cam = {"scale_drift_max": round(float(max(spans)), 4) if (spans and reliable) else None,
                       "pan_px_max": round(float(max(pans)), 3) if pans else None,
                       "method": "direct_3s_static_background", "spans": len(spans),
                       "unreliable_spans": unreliable, "seam_skipped_spans": skipped,
                       "seams": seam[:20]}
            except ImportError:
                unknowns.append({"what": "camera_motion", "why": "OpenCV לא זמין"})
        # פנים — כל 5 פריימים, 540×960
        try:
            import cv2
            big = _decode_gray(body, win, 540, 960, select_every=5)
            if big is None:
                unknowns.append({"what": "faces", "why": "פענוח לדגימת פנים נכשל"})
            else:
                front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
                prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
                min_px = max(24, int(float(heur.get("min_face_height_frac", 0.06)) * 960))
                for k, g in enumerate(big):
                    boxes = []
                    for casc in (front, prof):
                        if casc.empty():
                            continue
                        for (x, y, bw, bh) in casc.detectMultiScale(g, scaleFactor=1.1, minNeighbors=6,
                                                                     minSize=(min_px, min_px)):
                            boxes.append([x / 540, y / 960, bw / 540, bh / 960])
                    faces_per_sample.append({"frame": k * 5, "boxes": _merge_boxes(boxes)})
        except ImportError:
            unknowns.append({"what": "faces", "why": "OpenCV לא זמין — אין אימות גבולות נושא"})
    except ImportError:
        unknowns.append({"what": "all", "why": "numpy לא זמין"})
    meas["camera"] = cam
    meas["faces"] = faces_per_sample
    nf = [len(s["boxes"]) for s in faces_per_sample]
    meas["multi_face_ratio_opening"] = round(sum(1 for k in nf if k >= 2) / len(nf), 4) if nf else None
    align = (context.get("words_provenance") or {}).get("alignment")
    meas["words_audio_alignment"] = align
    if align is None:
        unknowns.append({"what": "words_audio_alignment", "why": "פחות מ-4 מילים ב-12ש או פענוח אודיו נכשל"})
    # פתיח ויזואלי / כניסה מכוונת
    absent_f = int(float(heur.get("entrance_face_absent_sec", 0.5)) * FPS)
    first_face = next((s["frame"] for s in faces_per_sample if s["boxes"]), None)
    meas["first_face_frame"] = first_face
    meas["intentional_entrance"] = bool(first_face is not None and first_face > absent_f
                                        and first_face <= 3 * FPS)
    words = context.get("words") or []
    quote = hook_quote(w, words)
    anchor = choose_anchor(quote, words, policy) if context["words_provenance"]["ok"] else None
    if quote["word_ids"]:
        evidence.append({"kind": "transcript", "detail": "משפט פתיחה מדובר מהקובץ שנבדק מול משך הגוף",
                         "word_ids": quote["word_ids"][:40]})
    if not context["words_provenance"]["ok"]:
        unknowns.append({"what": "transcript_provenance",
                         "why": "קובץ המילים אינו תואם לגוף: " + ",".join(context["words_provenance"]["reasons"])})
    out = {
        "schema_version": SCHEMA_VERSION,
        "project_id": context["project_id"],
        "input_digest": context["input_digest"],
        "analysis_version": ANALYSIS_VERSION,
        "cache_key": cache_key,
        "timeline": {"axis": "body_final", "fps_num": FPS, "fps_den": 1,
                     "frame_count": fc, "intro_frames": int(context["intro"]["intro_frames"] or 0)},
        "hook": {**quote, "anchor": anchor,
                 "promise": None, "payoff": None, "emotion": None,
                 "semantic_note": "promise/payoff/emotion לא מוסקים מקומית — אין מודל בפריסת MVP"},
        "content_type": context["content_type"],
        "brand": context["brand"],
        "intro": context["intro"],
        "measurements": meas,
        "reservations": context["reservations"],
        "evidence": evidence,
        "unknowns": unknowns,
    }
    try:
        atomic_write_json(cache_file, out)
    except OSError:
        pass
    return out


def _iou(a, b):
    ax1, ay1, bx1, by1 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax1, bx1) - max(a[0], b[0]))
    ih = max(0.0, min(ay1, by1) - max(a[1], b[1]))
    inter = iw * ih
    u = a[2] * a[3] + b[2] * b[3] - inter
    return inter / u if u > 0 else 0.0


def _merge_boxes(boxes):
    boxes = sorted(boxes, key=lambda b: -b[2] * b[3])
    out = []
    for b in boxes:
        if all(_iou(b, o) < 0.3 for o in out):
            out.append([round(float(v), 4) for v in b])
    return sorted(out, key=lambda b: (b[0], b[1]))


# ═══════════════════════════════════════════════════════════ מועמדים
def crop_rect(scale: float, cx: float, cy: float) -> list:
    wv = 1.0 / scale
    x = min(max(cx - wv / 2, 0.0), 1.0 - wv)
    y = min(max(cy - wv / 2, 0.0), 1.0 - wv)
    return [round(x, 6), round(y, 6), round(wv, 6), round(wv, 6)]


def smoothstep(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def rect_at(cue: dict, frame: int) -> list:
    """מקור אמת פייתוני לאינטרפולציה — הבדיקות משוות אליו את הפיקסלים."""
    kfs = cue["keyframes"]
    if frame < kfs[0]["frame"] or frame >= cue["end_frame"]:
        return list(IDENTITY)
    for a, b in zip(kfs, kfs[1:]):
        if a["frame"] <= frame < b["frame"]:
            s = smoothstep((frame - a["frame"]) / (b["frame"] - a["frame"]))
            return [ra + (rb - ra) * s for ra, rb in zip(a["rect"], b["rect"])]
    return list(kfs[-1]["rect"])


def _head_box(face):
    x, y, w_, h_ = face
    return [x - 0.25 * w_, y - 0.45 * h_, w_ * 1.5, h_ * 1.75]


def _contained(box, rect, margin):
    x, y, w_, h_ = rect
    return (box[0] >= x + margin * w_ and box[1] >= y + margin * h_ and
            box[0] + box[2] <= x + w_ - margin * w_ and box[1] + box[3] <= y + h_ - margin * h_)


def _crop_candidate(context, analysis, policy, registry) -> dict:
    """מועמד SMART_PUNCH_IN. **כל** הבדיקות רצות ומדווחות (גם אחרי כשל), כדי
    שהדוח יסביר את ה-NO_OP במלואו — לא רק את הסיבה הראשונה שנתקלנו בה."""
    env = policy.get("crop_envelope") or {}
    heur = policy.get("eligibility_heuristics") or {}
    fc = int(analysis["timeline"]["frame_count"])
    meas = analysis["measurements"]
    checks, reasons = [], []

    def check(name, ok, reason_code, detail):
        checks.append({"check": name, "pass": bool(ok), "reason_code": None if ok else reason_code,
                       "detail": detail})
        if not ok and reason_code not in reasons:
            reasons.append(reason_code)
        return ok

    check("recipe_released", recipe_runnable(registry, "SMART_PUNCH_IN"), "policy_disallowed",
          "SMART_PUNCH_IN במצב mvp ומיושם ברשומה")
    check("no_full_intro", not context["intro"]["present"], "fixed_intro_present",
          f"פתיח מלא: {context['intro'].get('id') or 'אין'} ({context['intro'].get('source')})")
    bp = context["body_probe"]
    check("timeline_supported", (bp["width"], bp["height"], bp["fps_num"], bp["fps_den"]) == (1080, 1920, 30, 1),
          "unsupported_timeline", f"{bp['width']}×{bp['height']}@{bp['fps_num']}/{bp['fps_den']}")
    al = context["words_provenance"].get("alignment") or {}
    check("transcript_provenance", context["words_provenance"]["ok"], "stale_transcript",
          (",".join(context["words_provenance"]["reasons"]) or "המילים תואמות את משך הגוף") +
          (f" · יישור לאודיו: היסט מיטבי {al.get('best_offset_sec')}ש (ציון {al.get('score_at_0')}→{al.get('best_score')})"
           if al else " · יישור לאודיו: לא נמדד"))
    anchor = (analysis.get("hook") or {}).get("anchor")
    check("verbal_anchor", anchor is not None, "no_verbal_anchor",
          f"מילת עוגן: {anchor['word']} @ {anchor['start']}ש" if anchor else "אין מילת תוכן במשפט הפתיחה בחלון 1-5ש")
    check("no_intentional_entrance", not meas.get("intentional_entrance"), "intentional_entrance",
          f"פנים ראשונות בפריים {meas.get('first_face_frame')}")
    mfr = meas.get("multi_face_ratio_opening")
    check("no_multi_person_opening", mfr is not None and mfr < float(heur.get("multi_face_ratio", 0.3)),
          "multi_person", f"יותר מפנים אחת ב-{mfr} מהדגימות ב-0-10ש (כולל פנים מודפסות — ספק ⇒ NO_OP)")

    ramp_in = int(env.get("ramp_in_frames", 15))
    ramp_out = int(env.get("ramp_out_frames", 15))
    if anchor:
        peak_f = int(round(anchor["start"] * FPS))
        start = peak_f - ramp_in
        hook_end = float((analysis.get("hook") or {}).get("end") or anchor["end"])
        want_hold = int(round((min(hook_end, anchor["end"] + 1.5) + 0.3 - anchor["start"]) * FPS))
        hold = max(int(env.get("min_hold_frames", 24)), min(int(env.get("max_hold_frames", 45)), want_hold))
        # שכבה מוגנת שמתחילה אחרי השיא תוחמת את ה-cue: מקצרים את ההחזקה (עד 6
        # פריימים) ולא דוחפים את הבירול. לא נכנס ⇒ reservation_conflict.
        nxt = [r["start_frame"] for r in context["reservations"] if r["start_frame"] > peak_f]
        latest_end = min([min(fc, int(policy.get("analysis_window_frames", 300)))] + nxt)
        hold = min(hold, latest_end - 1 - ramp_out - peak_f)
        if hold < 6:
            hold = max(int(env.get("min_hold_frames", 24)), 6)
        end = peak_f + hold + ramp_out + 1
    else:
        # אין עוגן ⇒ אין cue. חלון דיווח בלבד (1-5ש) כדי שהדוח יסביר גם תנועה/פנים.
        start, end, peak_f, hold = 30, 150, None, 0
    limit = min(fc, int(policy.get("analysis_window_frames", 300)))
    if anchor:
        check("cue_bounds", start >= 15 and end <= limit, "unsupported_timeline",
              f"חלון [{start},{end}) מול גבול {limit}")
        resv = [r for r in context["reservations"] if r["end_frame"] > start and r["start_frame"] < end]
        check("no_reservation_overlap", not resv, "reservation_conflict",
              "חופף ל-" + ", ".join(f"{r['kind']}[{r['start_frame']},{r['end_frame']})" for r in resv)
              if resv else "אין חפיפה לשכבה מוגנת")
    cuts_in = [c for c in meas.get("hard_cuts") or [] if start < c < end]
    check("no_hard_cut_in_window", not cuts_in, "competing_cut",
          f"חיתוכים קשים בחלון: {cuts_in}" if cuts_in else "אין חיתוך קשה בחלון")
    faces = [x for x in meas.get("faces") or [] if start <= x["frame"] < end]
    n = len(faces)
    single = sum(1 for x in faces if len(x["boxes"]) == 1)
    multi = sum(1 for x in faces if len(x["boxes"]) >= 2)
    ratio = single / n if n else 0.0
    check("subject_known", n > 0 and ratio >= float(heur.get("min_single_face_ratio", 0.7)),
          "semantic_unknown", f"פנים יחידות ב-{single}/{n} דגימות בחלון (גלאי פנים אינו אימות זהות)")
    check("single_person_in_window", n == 0 or multi / n < float(heur.get("multi_face_ratio", 0.3)),
          "multi_person", f"יותר מפנים אחת ב-{multi}/{n} דגימות בחלון")
    mads = (meas.get("motion_mad") or [])[start:end]
    wmot = float(sorted(mads)[len(mads) // 2]) if mads else None
    check("no_strong_motion", wmot is not None and wmot <= float(heur.get("max_window_motion_mad", 14.0)),
          "strong_motion", f"MAD חציוני בחלון {wmot:.2f}" if wmot is not None else "תנועה לא נמדדה")
    drift = (meas.get("camera") or {}).get("scale_drift_max")
    cam_m = meas.get("camera") or {}
    check("no_existing_camera_push", drift is not None and drift <= float(heur.get("max_camera_scale_drift", 0.025)),
          "existing_camera_motion",
          (f"סקייל מצלמה מרבי {drift} בין פריימים 3ש זה מזה, מרקע סטטי ({cam_m.get('spans')} טווחים)"
           if drift is not None else
           f"לא ניתן לאמת מצלמה סטטית — אין מספיק רקע שלא זז ({cam_m.get('unreliable_spans')} טווחים לא אמינים) "
           f"⇒ מתייחסים כתנועה קיימת"))
    base = {"candidate_id": None, "recipe": "SMART_PUNCH_IN",
            "recipe_version": (registry.get("SMART_PUNCH_IN") or {}).get("version", 1),
            "eligible": False, "checks": checks, "reason_codes": reasons,
            "evidence_grade": "unknown", "cues": [], "assets": [], "params": {},
            "features": {}, "score": None}
    if reasons or not anchor or not faces:
        if not reasons:
            reasons.append("semantic_unknown")
        return _finish_candidate(base)

    # גבולות מוגנים: ראש (מפנים) + מעטפת תנועה, לכל דגימה בחלון
    prot = [_head_box(fb) for x in faces for fb in x["boxes"]]
    mboxes = meas.get("motion_boxes_15f") or []
    for bi in range(start // 15, min(len(mboxes), (end + 14) // 15)):
        if mboxes[bi]:
            prot.append(mboxes[bi])
    margin = float(env.get("margin_frac", 0.03))
    centers = sorted((fb[0] + fb[2] / 2, fb[1] + fb[3] / 2) for x in faces for fb in x["boxes"])
    fcx = sorted(c[0] for c in centers)[len(centers) // 2]
    fcy = sorted(c[1] for c in centers)[len(centers) // 2]
    chosen = None
    for scale in env.get("peak_scale_candidates", [1.06, 1.04]):
        for (cx, cy, tag) in ((0.5, 0.5, "center"), (0.5, fcy, "face_vertical"), (fcx, fcy, "face")):
            rect = crop_rect(float(scale), cx, cy)
            if all(_contained(bx, rect, margin) for bx in prot):
                slack = min(min(bx[0] - rect[0], bx[1] - rect[1],
                                rect[0] + rect[2] - (bx[0] + bx[2]), rect[1] + rect[3] - (bx[1] + bx[3]))
                            for bx in prot) if prot else 0.0
                chosen = (float(scale), rect, tag, slack)
                break
        if chosen:
            break
    check("crop_containment", chosen is not None, "unsafe_crop",
          f"ראש+מעטפת תנועה בתוך המסגרת עם שוליים {margin}" if chosen else
          "אין מסגרת במעטפת האודישן שמכילה את הראש ואת מעטפת התנועה")
    if not chosen:
        return _finish_candidate(base)
    scale, rect, tag, slack = chosen
    kfs = [{"frame": start, "rect": list(IDENTITY)},
           {"frame": start + ramp_in, "rect": rect}]
    if end - 1 - ramp_out > start + ramp_in:
        kfs.append({"frame": end - 1 - ramp_out, "rect": rect})
    kfs.append({"frame": end - 1, "rect": list(IDENTITY)})
    cue = {"id": "cue_1", "kind": "crop", "start_frame": start, "end_frame": end,
           "interpolation": "smoothstep", "keyframes": kfs}
    maxm = float(heur.get("max_window_motion_mad", 14.0))
    feats = {
        "semantic_fit": 0.6, "hook_reinforcement": round(1 - min(1.0, wmot / maxm), 4),
        "visual_fit": round(min(1.0, max(0.0, slack) / 0.08), 4), "authenticity": 0.9,
        "asset_readiness": 1.0,
        "distraction": round((scale - 1.0) / 0.08, 4),
        "collision_uncertainty": round(1 - ratio, 4), "render_complexity": 0.2,
        "existing_motion_redundancy": round(min(1.0, wmot / maxm), 4),
    }
    wts = policy.get("shadow_weights") or {}
    ben = sum(float(v) * feats[k] for k, v in (wts.get("benefit") or {}).items())
    cost = sum(float(v) * feats[k] for k, v in (wts.get("cost") or {}).items())
    base.update({"eligible": True, "evidence_grade": "supported", "cues": [cue],
                 "params": {"peak_scale": scale, "center": tag, "ramp_in_frames": ramp_in,
                            "hold_frames": max(0, end - 1 - ramp_out - (start + ramp_in)),
                            "ramp_out_frames": ramp_out, "anchor_word_id": anchor["word_id"]},
                 "features": feats,
                 "score": {"benefit": round(ben, 4), "cost": round(cost, 4),
                           "net": round(ben - cost, 4), "calibrated": False}})
    return _finish_candidate(base)


def _finish_candidate(c: dict) -> dict:
    c["candidate_id"] = "cand_" + digest({"recipe": c["recipe"], "v": c["recipe_version"],
                                          "cues": c["cues"], "eligible": c["eligible"]})[7:19]
    return c


def discover(context: dict, analysis: dict, registry=None, policy=None) -> list:
    registry = registry or load_registry()
    policy = policy or load_policy()
    noop_reasons = []
    if context["intro"]["present"]:
        noop_reasons.append("fixed_intro_present")
    if analysis["measurements"].get("intentional_entrance"):
        noop_reasons.append("intentional_entrance")
    noop = _finish_candidate({"candidate_id": None, "recipe": "NO_OP", "recipe_version": 1,
                              "eligible": True, "checks": [], "reason_codes": noop_reasons,
                              "evidence_grade": "verified", "cues": [], "assets": [],
                              "params": {}, "features": {},
                              "score": {"benefit": 0.0, "cost": 0.0, "net": 0.0,
                                        "baseline": True, "calibrated": False}})
    crop = _crop_candidate(context, analysis, policy, registry)
    if not crop["eligible"]:
        # ה-NO_OP מסביר את עצמו: למה לא נגענו (כל סיבות הפסילה של מועמד החיתוך)
        noop["reason_codes"] = sorted(set(noop_reasons) | set(crop["reason_codes"]))
    cands = [noop, crop]
    # רשומת המתכונים שאינם משוחררים — מדווחים, לעולם לא זכאים
    for rid, r in sorted(registry.items()):
        if rid in ("NO_OP", "SMART_PUNCH_IN"):
            continue
        cands.append(_finish_candidate({"candidate_id": None, "recipe": rid,
                                        "recipe_version": r["version"], "eligible": False,
                                        "checks": [{"check": "recipe_released", "pass": False,
                                                    "reason_code": "policy_disallowed",
                                                    "detail": f"status={r['status']}"}],
                                        "reason_codes": ["policy_disallowed"],
                                        "evidence_grade": "unknown", "cues": [], "assets": [],
                                        "params": {}, "features": {}, "score": None}))
    return cands


# ═══════════════════════════════════════════════════════════ בחירה
def select(context: dict, candidates: list, prefs: dict | None, mode: str, policy=None) -> tuple[dict, dict]:
    """מחזיר (מועמד נבחר, selection). סדר: כיבוי מפורש > בחירה מאושרת של הראל >
    shadow (הצעה בלבד) > auto (רק קוהורט מאושר). שובר שוויון: פחות התערבות."""
    policy = policy or load_policy()
    prefs = prefs or {}
    registry = load_registry()
    noop = next(c for c in candidates if c["recipe"] == "NO_OP")
    # ציון גבוה אינו היתר: רק מתכון משוחרר (mvp+implemented) יכול להיבחר
    eligible = [c for c in candidates if c["eligible"] and c["recipe"] != "NO_OP"
                and recipe_runnable(registry, c["recipe"])]
    eligible.sort(key=lambda c: (-(c["score"] or {}).get("net", -9), len(c["cues"]), c["candidate_id"]))
    if prefs.get("enabled") is False:
        return noop, {"actor": "harel", "reason_codes": ["explicit_disabled"]}
    want = prefs.get("selected_candidate_id")
    if want:
        hit = next((c for c in candidates if c["candidate_id"] == want), None)
        if hit and hit["eligible"] and recipe_runnable(registry, hit["recipe"]):
            return hit, {"actor": "harel", "reason_codes": ["operator_selected"]}
        return noop, {"actor": "auto", "reason_codes": ["selected_candidate_unavailable"]}
    best = eligible[0] if eligible else None
    if mode == "shadow":
        if best and (best["score"] or {}).get("net", 0) > 0:
            return best, {"actor": "auto", "reason_codes": ["shadow_suggestion"]}
        return noop, {"actor": "auto", "reason_codes": (noop["reason_codes"] or
                                                        (["no_eligible_candidate"] if not best else ["already_effective"]))}
    if mode == "auto":
        cohort = {"content_type": context["content_type"], "brand": context["brand"]}
        allowed = any(all(cohort.get(k) == v for k, v in coh.items())
                      for coh in (policy.get("auto_cohorts") or []))
        margin = policy.get("auto_min_margin")
        if best and allowed and margin is not None and (best["score"] or {}).get("net", 0) >= float(margin):
            return best, {"actor": "auto", "reason_codes": ["auto_cohort_approved"]}
        why = "auto_cohort_not_approved" if best else (noop["reason_codes"][0] if noop["reason_codes"] else "no_eligible_candidate")
        return noop, {"actor": "auto", "reason_codes": [why]}
    return noop, {"actor": "auto", "reason_codes": ["policy_disallowed"]}


# ═══════════════════════════════════════════════════════════ תוכנית
PLAN_KEYS = {"schema_version", "project_id", "input_digest", "policy_digest",
             "reservation_digest", "recipe", "recipe_version", "timeline", "audio_mode",
             "evidence", "assets", "cues", "declared_transitions", "selection",
             "candidate_id", "plan_digest"}


def make_plan(context: dict, analysis: dict, candidate: dict, selection: dict) -> dict:
    hook = analysis.get("hook") or {}
    plan = {
        "schema_version": SCHEMA_VERSION,
        "project_id": context["project_id"],
        "input_digest": context["input_digest"],
        "policy_digest": context["policy_digest"],
        "reservation_digest": context["reservation_digest"],
        "recipe": candidate["recipe"],
        "recipe_version": int(candidate["recipe_version"]),
        "candidate_id": candidate["candidate_id"],
        "timeline": dict(analysis["timeline"]),
        "audio_mode": "preserve",
        "evidence": {"word_ids": list(hook.get("word_ids") or []),
                     "quote": hook.get("quote") or "",
                     "grade": candidate["evidence_grade"],
                     "reviewed_subjects": []},
        "assets": list(candidate["assets"]),
        "cues": [dict(c) for c in candidate["cues"]],
        "declared_transitions": [],
        "selection": {"actor": selection["actor"],
                      "reason_codes": sorted(set(selection["reason_codes"]) | set(candidate["reason_codes"]))
                      if candidate["recipe"] == "NO_OP" else list(selection["reason_codes"])},
    }
    plan["plan_digest"] = digest_plan(plan)
    return plan


def digest_plan(plan: dict) -> str:
    return digest({k: v for k, v in plan.items() if k != "plan_digest"})


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def validate_plan_shape(plan, registry=None) -> list:
    """בדיקת צורה מלאה, בלי תלות בחבילת jsonschema. מחזיר רשימת שגיאות."""
    errs = []
    registry = registry or load_registry()
    if not isinstance(plan, dict):
        return ["plan אינו אובייקט"]
    try:
        canonical_json(plan)
    except HookError as e:
        errs.append(e.detail)
    except (TypeError, ValueError) as e:
        errs.append(f"JSON לא קנוני: {e}")
    extra = set(plan) - PLAN_KEYS
    if extra:
        errs.append(f"מפתחות לא מוכרים: {sorted(extra)}")
    if plan.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version לא נתמך: {plan.get('schema_version')}")
    if not isinstance(plan.get("project_id"), str) or not PROJECT_ID_RE.match(plan.get("project_id") or ""):
        errs.append("project_id חסר/לא חוקי")
    for k in ("input_digest", "policy_digest", "reservation_digest"):
        if not isinstance(plan.get(k), str) or not DIGEST_RE.match(plan.get(k)):
            errs.append(f"{k} אינו sha256 קנוני")
    rid = plan.get("recipe")
    if rid not in registry:
        errs.append(f"מתכון לא מוכר: {rid}")
    elif not recipe_runnable(registry, rid):
        errs.append(f"מתכון לא משוחרר: {rid} ({registry[rid]['status']})")
    elif plan.get("recipe_version") != registry[rid]["version"]:
        errs.append(f"recipe_version לא נתמך: {plan.get('recipe_version')}")
    tl = plan.get("timeline")
    if not isinstance(tl, dict):
        errs.append("timeline חסר")
        tl = {}
    else:
        if set(tl) != {"axis", "fps_num", "fps_den", "frame_count", "intro_frames"}:
            errs.append("timeline: מפתחות לא תקינים")
        if tl.get("axis") != "body_final":
            errs.append("timeline.axis חייב להיות body_final")
        if tl.get("fps_num") != 30 or tl.get("fps_den") != 1:
            errs.append("timeline: רק 30/1 נתמך")
        if not _is_int(tl.get("frame_count")) or tl.get("frame_count") <= 0:
            errs.append("timeline.frame_count חייב להיות שלם חיובי")
        if not _is_int(tl.get("intro_frames")) or tl.get("intro_frames") < 0:
            errs.append("timeline.intro_frames חייב להיות שלם ≥0")
    if plan.get("audio_mode") != "preserve":
        errs.append("audio_mode חייב להיות preserve — המנוע משנה תמונה בלבד")
    ev = plan.get("evidence")
    if not isinstance(ev, dict) or set(ev) != {"word_ids", "quote", "grade", "reviewed_subjects"}:
        errs.append("evidence: מבנה לא תקין")
    else:
        wid = ev.get("word_ids")
        if not isinstance(wid, list) or not all(_is_int(x) and x >= 0 for x in wid) \
                or wid != sorted(set(wid)):
            errs.append("evidence.word_ids: רשימת שלמים עולה וייחודית")
        if not isinstance(ev.get("quote"), str):
            errs.append("evidence.quote חייב להיות מחרוזת")
        if ev.get("grade") not in ("verified", "supported", "unknown"):
            errs.append("evidence.grade לא חוקי")
        if not isinstance(ev.get("reviewed_subjects"), list) or \
                not all(isinstance(x, str) for x in ev.get("reviewed_subjects")):
            errs.append("evidence.reviewed_subjects: רשימת מחרוזות")
    assets = plan.get("assets")
    if not isinstance(assets, list):
        errs.append("assets חייב להיות רשימה")
        assets = []
    for a in assets:
        if not isinstance(a, dict) or set(a) != {"id", "sha256", "approved_root_relative_path",
                                                 "source_frame_range", "role"}:
            errs.append("asset: מבנה לא תקין")
            continue
        p = str(a.get("approved_root_relative_path") or "")
        if not p or p.startswith("/") or ".." in Path(p).parts or "\\" in p:
            errs.append(f"asset {a.get('id')}: נתיב לא חוקי")
        if not isinstance(a.get("sha256"), str) or not DIGEST_RE.match(a["sha256"]):
            errs.append(f"asset {a.get('id')}: checksum לא חוקי")
    cues = plan.get("cues")
    if not isinstance(cues, list):
        errs.append("cues חייב להיות רשימה")
        cues = []
    trans = plan.get("declared_transitions")
    if not isinstance(trans, list):
        errs.append("declared_transitions חייב להיות רשימה")
        trans = []
    sel = plan.get("selection")
    if not isinstance(sel, dict) or sel.get("actor") not in ("auto", "harel") or \
            not isinstance(sel.get("reason_codes"), list) or \
            not all(isinstance(x, str) and re.match(r"^[a-z_]+$", x) for x in sel.get("reason_codes")):
        errs.append("selection: actor/reason_codes לא תקינים")
    if rid == "NO_OP":
        if assets or cues or trans:
            errs.append("NO_OP מחייב assets/cues/declared_transitions ריקים")
    elif rid == "SMART_PUNCH_IN":
        if assets:
            errs.append("SMART_PUNCH_IN אינו צורך נכסים — רק הגוף הנקי")
        if trans:
            errs.append("SMART_PUNCH_IN אינו מצהיר מעברים")
        if len(cues) != 1:
            errs.append("SMART_PUNCH_IN: בדיוק cue אחד (אין אקסנט ב-MVP)")
        pmax = float(((registry.get("SMART_PUNCH_IN") or {}).get("params") or {})
                     .get("peak_scale", {}).get("max", 1.08))
        wmax = int(((registry.get("SMART_PUNCH_IN") or {}).get("params") or {})
                   .get("window_end_frame", {}).get("max", 300))
        for c in cues:
            errs += _validate_crop_cue(c, tl.get("frame_count") if _is_int(tl.get("frame_count")) else 0,
                                       pmax, wmax)
    return errs


def _validate_crop_cue(c, frame_count, pmax, wmax) -> list:
    errs = []
    if not isinstance(c, dict) or set(c) != {"id", "kind", "start_frame", "end_frame",
                                             "interpolation", "keyframes"}:
        return ["cue: מבנה לא תקין"]
    if c.get("kind") != "crop" or c.get("interpolation") != "smoothstep":
        errs.append("cue: רק crop עם smoothstep")
    s, e = c.get("start_frame"), c.get("end_frame")
    if not (_is_int(s) and _is_int(e) and 0 <= s < e <= frame_count and e <= wmax):
        errs.append(f"cue: טווח [{s},{e}) לא חוקי (frame_count={frame_count}, חלון ≤{wmax})")
        return errs
    kfs = c.get("keyframes")
    if not isinstance(kfs, list) or len(kfs) < 3:
        return errs + ["cue: לפחות 3 keyframes"]
    prev = None
    for k in kfs:
        if not isinstance(k, dict) or set(k) != {"frame", "rect"} or not _is_int(k.get("frame")):
            errs.append("keyframe: מבנה לא תקין")
            continue
        f, r = k["frame"], k["rect"]
        if prev is not None and f <= prev:
            errs.append("keyframes: חייבים להיות עולים ממש")
        prev = f
        if not (s <= f < e):
            errs.append(f"keyframe {f} מחוץ ל-[{s},{e})")
        if not isinstance(r, list) or len(r) != 4 or not all(_num(v) for v in r):
            errs.append(f"keyframe {f}: rect לא סופי/לא תקין")
            continue
        x, y, w_, h_ = (float(v) for v in r)
        if not (0 < w_ <= 1 and 0 < h_ <= 1):
            errs.append(f"keyframe {f}: w/h מחוץ ל-(0,1]")
        if abs(w_ - h_) > 1e-6:
            errs.append(f"keyframe {f}: יחס גובה-רוחב לא נשמר (w≠h)")
        if x < -1e-9 or y < -1e-9 or x + w_ > 1 + 1e-9 or y + h_ > 1 + 1e-9:
            errs.append(f"keyframe {f}: rect חורג מהפריים")
        if w_ > 0 and 1.0 / w_ > pmax + 1e-6:
            errs.append(f"keyframe {f}: scale {1/w_:.4f} מעל {pmax}")
    if kfs and isinstance(kfs[0], dict):
        if kfs[0].get("frame") != s or [float(v) for v in kfs[0].get("rect", [])] != IDENTITY:
            errs.append("keyframe ראשון חייב להיות זהות ב-start_frame")
        if kfs[-1].get("frame") != e - 1 or [float(v) for v in kfs[-1].get("rect", [])] != IDENTITY:
            errs.append("keyframe אחרון חייב להיות זהות ב-end_frame-1")
    return errs


def validate_plan(plan: dict, context: dict | None = None, registry=None) -> list:
    """צורה + סמנטיקה מול ההקשר הנוכחי. digest של הקלט שאינו תואם ⇒ HOOK_REVIEW_STALE."""
    errs = validate_plan_shape(plan, registry)
    if errs:
        return errs
    if plan.get("plan_digest") and plan["plan_digest"] != digest_plan(plan):
        errs.append("plan_digest אינו תואם לתוכן — התוכנית שונתה אחרי הקפאה")
    if context is None:
        return errs
    if plan["project_id"] != context["project_id"]:
        errs.append("project_id אינו תואם לפרויקט")
    if plan["input_digest"] != context["input_digest"]:
        errs.append("HOOK_REVIEW_STALE: הקשר הגוף/המילים/המיפוי השתנה מאז שהתוכנית נבחרה")
    if plan["reservation_digest"] != context["reservation_digest"]:
        near = [r for c in plan["cues"] for r in context["reservations"]
                if r["end_frame"] > c["start_frame"] - 15 and r["start_frame"] < c["end_frame"] + 15]
        if near:
            errs.append("HOOK_REVIEW_STALE: שכבה מוגנת (בירול/המחשה/אפקט) השתנתה בתוך חלון הפתיחה")
    if plan["timeline"]["frame_count"] != context["body_probe"]["frame_count"]:
        errs.append("frame_count אינו תואם לגוף בפועל")
    ids = {w["id"]: w for w in context.get("words") or []}
    wid = plan["evidence"]["word_ids"]
    if any(i not in ids for i in wid):
        errs.append("evidence.word_ids מפנה למילים שאינן בקובץ המילים הנוכחי")
    elif wid and " ".join(ids[i]["word"] for i in wid).strip() != plan["evidence"]["quote"]:
        errs.append("evidence.quote אינו תואם למילים בפועל")
    if plan["recipe"] != "NO_OP":
        if not context["words_provenance"]["ok"]:
            errs.append("טיפול דורש מילים מאומתות-דור; המילים אינן תואמות לגוף")
        for c in plan["cues"]:
            for r in context["reservations"]:
                if r["end_frame"] > c["start_frame"] and r["start_frame"] < c["end_frame"]:
                    errs.append(f"cue חופף לשכבה מוגנת {r['kind']}")
        if context["intro"]["present"]:
            errs.append("פתיח מלא קיים — ברירת המחדל האוטומטית היא NO_OP")
    return errs


def stale_code(errors: list) -> str | None:
    return "HOOK_REVIEW_STALE" if any(str(e).startswith("HOOK_REVIEW_STALE") for e in errors) else None


# ═══════════════════════════════════════════════════════════ דוח ותזמור
def build_report(context, analysis, candidates, selected, selection, plan, *, mode, applied,
                 approval=None) -> dict:
    alt = [c for c in candidates if c["eligible"] and c["recipe"] != "NO_OP"
           and c["candidate_id"] != selected["candidate_id"]]
    crop = next((c for c in candidates if c["recipe"] == "SMART_PUNCH_IN"), None)
    why = []
    if selected["recipe"] == "NO_OP":
        codes = plan["selection"]["reason_codes"]
        why = [f"{c}" for c in codes]
    else:
        why = plan["selection"]["reason_codes"] + [f"anchor:{(analysis['hook'].get('anchor') or {}).get('word')}"]
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": context["project_id"],
        "mode": mode,
        "applied": bool(applied),
        "shadow": mode == "shadow",
        "label_he": LABEL_HE.get(plan["recipe"] if applied else "NO_OP", LABEL_HE["NO_OP"]),
        "suggestion_label_he": LABEL_HE.get(selected["recipe"]),
        "recipe": plan["recipe"],
        "candidate_id": plan.get("candidate_id"),
        "plan_digest": plan["plan_digest"],
        "input_digest": context["input_digest"],
        "why": why,
        "crop_checks": (crop or {}).get("checks"),
        "candidates": [{"candidate_id": c["candidate_id"], "recipe": c["recipe"],
                        "eligible": c["eligible"], "reason_codes": c["reason_codes"],
                        "evidence_grade": c["evidence_grade"], "score": c["score"]}
                       for c in candidates],
        "has_alternative": bool(alt),
        "unknowns": analysis.get("unknowns"),
        "intro": context["intro"],
        "timeline": plan["timeline"],
        "qa": None,
        "approval": approval,
        "preflight_note": ("NO_OP היא החלטה תקינה — הפתיחה נשארת כפי שצולמה"
                           if plan["recipe"] == "NO_OP" else
                           "הדגשה עדינה אחת בתמונה בלבד; הדיבור, הכתוביות והמשך לא השתנו. "
                           "ההעדפה האסתטית נקבעת בהשוואה של הראל — אין טענת שיפור שימור שנמדדה"),
        "claims_retention_uplift": False,
    }


def run_selection(workdir, *, mode="shadow", prefs=None, context_kwargs=None, write=True,
                  namespace=None) -> dict:
    """ניתוח → מועמדים → בחירה → תוכנית → דוח. כותב קבצי workdir (או ל-namespace)."""
    registry = load_registry()
    policy = load_policy()
    ctx = build_context(workdir, policy=policy, **(context_kwargs or {}))
    analysis = analyze(ctx, policy)
    cands = discover(ctx, analysis, registry, policy)
    selected, selection = select(ctx, cands, prefs, mode, policy)
    plan = make_plan(ctx, analysis, selected, selection)
    errs = validate_plan(plan, ctx, registry)
    if errs:
        raise HookError("HOOK_PLAN_INVALID", "; ".join(errs))
    applied = mode != "shadow" and plan["recipe"] != "NO_OP"
    report = build_report(ctx, analysis, cands, selected, selection, plan, mode=mode, applied=applied)
    candidates_doc = {"schema_version": SCHEMA_VERSION, "project_id": ctx["project_id"],
                      "input_digest": ctx["input_digest"], "policy_digest": ctx["policy_digest"],
                      "candidates": cands,
                      "plans": {c["candidate_id"]: make_plan(ctx, analysis, c,
                                                             {"actor": "harel", "reason_codes": ["operator_selected"]})
                                for c in cands if c["eligible"]}}
    if write:
        root = Path(namespace) if namespace else Path(workdir)
        ana = {k: v for k, v in analysis.items() if k != "cache_key"}
        atomic_write_json(root / FILES["analysis"], ana)
        atomic_write_json(root / FILES["candidates"], candidates_doc)
        atomic_write_json(root / FILES["plan"], plan)
        atomic_write_json(root / FILES["report"], report)
    return {"context": ctx, "analysis": analysis, "candidates": cands, "candidates_doc": candidates_doc,
            "selected": selected, "selection": selection, "plan": plan, "report": report}


# ═══════════════════════════════════════════════════════════ חיבור לגימור
def approved_plan_path(workdir, plan_digest: str | None) -> Path | None:
    if not plan_digest or not DIGEST_RE.match(str(plan_digest)):
        return None
    return Path(workdir) / HOOK_DIR / "approved" / f"{plan_digest[7:23]}.json"


def finish_resolve(workdir, *, mode: str, pref: dict | None, body, words_file, broll_items,
                   brand, content_type, title="", plan_path=None) -> dict:
    """נקודת הכניסה של local_finish_pipeline. מחזיר מצב שהצנרת צורכת בלי לקבל
    החלטות עריכה משלה:
      applied=False ⇒ הגימור ממשיך בדיוק במסלול הישן.
      error=(code, detail) ⇒ תוכנית שאושרה אינה תקפה יותר — הצנרת עוצרת את
      המועמד (הגרסה המאושרת האחרונה נשמרת). לעולם לא NO_OP שקט אחרי אישור.
    תוכנית מאושרת (מהאפליקציה או --visual-hook-plan) גוברת על הבחירה; כיבוי
    מפורש (enabled=false) גובר על הכול."""
    pref = dict(pref or {})
    registry, policy = load_registry(), load_policy()
    W = Path(workdir)
    ctx = build_context(W, body=body, words_file=words_file, broll_items=broll_items, brand=brand,
                        content_type=content_type, title=title, policy=policy)
    analysis = analyze(ctx, policy)
    cands = discover(ctx, analysis, registry, policy)
    approval = None
    src = Path(plan_path) if plan_path else approved_plan_path(W, pref.get("approved_plan_digest"))
    error = None
    if pref.get("enabled") is False:
        selected, selection = select(ctx, cands, {"enabled": False}, mode, policy)
        plan = make_plan(ctx, analysis, selected, selection)
        applied = False
    elif src is not None:
        try:
            plan = json.loads(Path(src).read_text(encoding="utf-8"))
        except Exception as e:
            plan = None
            error = ("HOOK_ASSET_MISSING", f"התוכנית המאושרת אינה קריאה ({Path(src).name}): {e}")
        if plan is not None:
            errs = validate_plan(plan, ctx, registry)
            if plan_path is None and plan.get("plan_digest") != pref.get("approved_plan_digest"):
                errs.append("HOOK_REVIEW_STALE: התוכנית בקובץ אינה זו שאושרה")
            if errs:
                error = (stale_code(errs) or "HOOK_PLAN_INVALID", "; ".join(errs))
        approval = {"source": "cli_plan" if plan_path else "app_approval",
                    "approved_plan_digest": (plan or {}).get("plan_digest") if plan_path
                    else pref.get("approved_plan_digest"),
                    "comparison_seen": pref.get("comparison_seen")}
        if error:
            # מועמד מתוקן לתצוגה הבאה — לא מוחל
            selected, selection = select(ctx, cands, {}, "shadow", policy)
            revised = make_plan(ctx, analysis, selected, selection)
            report = build_report(ctx, analysis, cands, selected, selection, revised, mode=mode,
                                  applied=False, approval=dict(approval, error=error[0]))
            atomic_write_json(W / FILES["report"], report)
            atomic_write_json(W / FILES["candidates"], {"schema_version": SCHEMA_VERSION,
                                                        "project_id": ctx["project_id"],
                                                        "input_digest": ctx["input_digest"],
                                                        "candidates": cands})
            return {"mode": mode, "applied": False, "plan": revised, "report": report,
                    "context": ctx, "error": error, "approved_digest": approval["approved_plan_digest"]}
        selected = next((c for c in cands if c["candidate_id"] == plan.get("candidate_id")), None) or \
            {"candidate_id": plan.get("candidate_id"), "recipe": plan["recipe"], "eligible": True,
             "reason_codes": [], "evidence_grade": plan["evidence"]["grade"], "cues": plan["cues"],
             "score": None}
        selection = plan["selection"]
        applied = plan["recipe"] != "NO_OP" and mode != "off"
    else:
        selected, selection = select(ctx, cands, {}, mode, policy)
        plan = make_plan(ctx, analysis, selected, selection)
        applied = mode == "auto" and plan["recipe"] != "NO_OP"
    report = build_report(ctx, analysis, cands, selected, selection, plan, mode=mode,
                          applied=applied, approval=approval)
    atomic_write_json(W / FILES["analysis"], {k: v for k, v in analysis.items() if k != "cache_key"})
    atomic_write_json(W / FILES["candidates"], {"schema_version": SCHEMA_VERSION,
                                                "project_id": ctx["project_id"],
                                                "input_digest": ctx["input_digest"],
                                                "candidates": cands})
    atomic_write_json(W / FILES["plan"], plan)
    atomic_write_json(W / FILES["report"], report)
    return {"mode": mode, "applied": applied, "plan": plan, "report": report, "context": ctx,
            "error": None, "approved_digest": (approval or {}).get("approved_plan_digest")}
