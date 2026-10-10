#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hook_fx.py — ארגז העריכה של ההוק (v9.46, 8.10.26).

הראל 8.10.26: "הרעיון של ארגז הכלים הוא ... ברמת העריכה שלנו. אפקטים, אנימציה שמשתלבת בתוך ההוק,
מעברים ויזואליים, צלילים". זו השכבה הזו: תנועות עריכה על 0-4 השניות הראשונות, אחרי בירול/פתיח קבוע
ולפני MG, מוזיקה וכתוביות (כך שהטקסט של ה-MG והכתוביות לא מזדומים יחד עם התמונה).

תנועות (כולן שומרות על אורך הציר — אף מילה לא זזה, הכתוביות נשארות מסונכרנות):
  snap_zoom      זום חד לנקודה/לפנים (ease-out-expo), החזקה, שחרור או חזרה בחיתוך
  push_in        זום איטי רציף (Ken Burns) לאורך ההוק
  shake          רעידת מצלמה דועכת (על מכה/נחיתה)
  impact_freeze  עצירת פריים על רגע השיא (+זום עדין, רעידה, פלאש אופציונלי) — הפריימים שאחריו מוחלפים
  speed_ramp     האטה סביב רגע השיא ותפיסה מהירה אחריו (רק בלי דיבור בחלון)
  whip           מעבר whip בחיתוך: טשטוש תנועה + הזזה, A יוצא B נכנס
  zoom_through   מעבר זום-בלר בחיתוך
  flash          פלאש לבן קצר בחיתוך (שכבה, לא תיקון צבע — 2-4 פריימים)
סאונד: צלילי Mixkit (tools/motion/sfx/hook/catalog.json) מיושרים לפי השיא (riser — לפי הסוף),
עוצמה יחסית לדיבור של הסרטון · music_drop (שקט פתאומי במוזיקה, נצרך ע"י audio_mix --mute) ·
boost_orig/duck_orig על הסאונד המקורי.

התוכנית: HOOK_PLAN.json["edit"] = {"moves":[...], "sfx":[...], "music_drop":[[a,b]], "boost_orig":{...}}.
פקודות:
  check  --workdir W [--base V]           שערים לפני רינדור (HFX1-HFX6, HFX10)
  render --workdir W --base IN --out OUT [--words F] [--lossless] [--vh-applied]
  sheet  --workdir W --before IN --after OUT    HOOK_FX_SHEET.jpg (חוק הראייה — לפתוח ב-Read)
  demo   --src VIDEO --plan EDIT.json --out DIR [--secs 8]   לפני/אחרי מסרטון קיים (עותק בלבד)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
SFX_DIR = HERE / "motion" / "sfx" / "hook"

MAX_WIN = 4.0                    # שכבת ההוק בלבד — שום תנועה אחרי 4ש
MOVE_TYPES = ("snap_zoom", "push_in", "shake", "impact_freeze", "speed_ramp", "whip", "zoom_through", "flash")
TIME_ALTERING = {"impact_freeze", "speed_ramp"}
TRANSITIONS = {"whip", "zoom_through", "flash"}
GEOMETRIC = {"snap_zoom", "push_in", "shake", "impact_freeze", "whip", "zoom_through"}
SPATIAL_MG = {"spotlight", "then_now", "telestrator", "callout", "forearm", "angle", "tripod"}
MAX_MOVES = 2                    # "רגע בינוני גרוע מאפס" — לכל היותר שתי תנועות בהוק
LIM = {("snap_zoom", "scale"): (1.05, 1.35), ("push_in", "scale"): (1.02, 1.12), ("shake", "amp"): (0.003, 0.025),
       ("impact_freeze", "hold"): (0.12, 0.6), ("speed_ramp", "slow"): (0.25, 0.6), ("whip", "dur"): (0.12, 0.36),
       ("zoom_through", "dur"): (0.12, 0.4), ("flash", "dur"): (0.05, 0.15), ("snap_zoom", "in"): (0.06, 0.4)}
CUT_TOL = 0.12
SFX_ROLES = ("impact", "swish", "zoom", "riser", "rewind", "scratch", "shutter")
REL_DB = {"impact": -7.0, "swish": -10.0, "zoom": -10.0, "riser": -12.0, "rewind": -10.0, "scratch": -9.0,
          "shutter": -11.0}       # LU מתחת לדיבור של הסרטון (מדידה, לא גיין קבוע)
AUTO_SFX = {"whip": "swish", "zoom_through": "zoom", "impact_freeze": "impact", "speed_ramp": "impact"}
SFX_PRIO = {"impact": 3, "scratch": 3, "swish": 2, "zoom": 2, "rewind": 2, "shutter": 1, "riser": 0}
SFX_MIN_GAP, SFX_MAX = 0.35, 3


# ─────────────────────────── עזר ───────────────────────────

def sh(cmd, timeout=3600, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout,
                          stdin=subprocess.DEVNULL, **kw)


def gate(name, ok, level, detail, **extra):
    return {"gate": name, "ok": bool(ok), "level": level, "detail": detail, **extra}


def ease_out_expo(u):
    return 1.0 if u >= 1 else 1 - 2 ** (-10 * u)


def ease_in_out(u):
    u = min(max(u, 0.0), 1.0)
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def ease_in(u):
    u = min(max(u, 0.0), 1.0)
    return u ** 3


def probe(video) -> dict:
    r = sh([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=width,height,r_frame_rate,pix_fmt,nb_frames,color_range,color_space,color_transfer,color_primaries"
            ":format=duration", "-of", "json", video])
    d = json.loads(r.stdout or "{}")
    st = (d.get("streams") or [{}])[0]
    num, den = (st.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1)
    dur = float((d.get("format") or {}).get("duration") or 0)
    pf = st.get("pix_fmt") or "yuv420p"
    return {"w": int(st["width"]), "h": int(st["height"]), "fps": fps, "dur": dur, "pix_fmt": pf,
            "deep": "10" in pf, "color": {k: st.get(k) for k in ("color_range", "color_space", "color_transfer",
                                                                 "color_primaries")}}


def ctags(info: dict) -> list[str]:
    tags = []
    for opt, key in (("-colorspace", "color_space"), ("-color_trc", "color_transfer"),
                     ("-color_primaries", "color_primaries"), ("-color_range", "color_range")):
        v = info["color"].get(key)
        if v and v != "unknown":
            tags += [opt, v]
    return tags


def has_audio(video) -> bool:
    r = sh([FFPROBE, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", video])
    return bool((r.stdout or b"").strip())


def adur(video) -> float:
    r = sh([FFPROBE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of",
            "csv=p=0", video])
    try:
        return float(r.stdout.decode().strip())
    except Exception:
        return 0.0


def lufs(path, t0=None, t1=None) -> float:
    cmd = [FFMPEG, "-nostdin"]
    if t0 is not None:
        cmd += ["-ss", f"{t0:.3f}"]
    cmd += ["-i", path]
    if t1 is not None:
        cmd += ["-t", f"{max(0.5, t1 - (t0 or 0)):.3f}"]
    cmd += ["-vn", "-af", "ebur128", "-f", "null", "-"]
    r = sh(cmd)
    import re
    v = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr.decode(errors="ignore"))
    return float(v[-1]) if v else -70.0


def setparams(info: dict) -> str:
    """פילטר שמקבע את תכונות הצבע של הבסיס על כל ענף — בלי זה ffmpeg ממיר צבע אוטומטית
    כשהחלון (ffv1) והמשך הבסיס נבדלים בתגיות (נמדד 8.10.26: ΔUV 6.4 על בסיס HLG)."""
    c = info["color"]
    kv = []
    for k, opt in (("color_primaries", "color_primaries"), ("color_transfer", "color_trc"),
                   ("color_space", "colorspace"), ("color_range", "range")):
        v = c.get(k)
        if v and v != "unknown":
            kv.append(f"{opt}={v}")
    return ("setparams=" + ":".join(kv)) if kv else "null"


def load_words(W: Path | None, words_path=None) -> list[dict]:
    cands = [Path(words_path)] if words_path else []
    if W:
        cands += [W / n for n in ("words_final.json", "whisper_export_tight.json", "words.json")]
    for p in cands:
        if p and p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            return d if isinstance(d, list) else (d.get("words") or [])
    return []


def load_edit(W: Path | None, plan_path=None) -> dict:
    if plan_path:
        d = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        return d.get("edit", d)
    p = W / "HOOK_PLAN.json" if W else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("edit") or {}
    return {}


def edit_digest(edit: dict) -> str:
    return hashlib.sha1(json.dumps(edit, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def media_stamp(p: Path) -> dict:
    st = Path(p).stat()
    return {"size": st.st_size, "mtime": int(st.st_mtime)}


def sfx_catalog() -> dict:
    p = SFX_DIR / "catalog.json"
    if not p.exists():
        return {"items": []}
    return json.loads(p.read_text(encoding="utf-8"))


# ─────────────────────────── קריאת פריימים ───────────────────────────

def read_frames(video, n: int, info: dict) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """n הפריימים הראשונים כ-(Y,U,V) בפורמט המקורי — בלי המרת צבע (yuv420p / yuv420p10le)."""
    w, h = info["w"], info["h"]
    pf = "yuv420p10le" if info["deep"] else "yuv420p"
    dt = np.uint16 if info["deep"] else np.uint8
    bpp = 2 if info["deep"] else 1
    fsz = (w * h + 2 * (w // 2) * (h // 2)) * bpp
    p = subprocess.Popen([FFMPEG, "-nostdin", "-loglevel", "error", "-i", str(video), "-frames:v", str(n),
                          "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", pf, "-"], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    out = []
    for _ in range(n):
        buf = p.stdout.read(fsz)
        if len(buf) < fsz:
            break
        a = np.frombuffer(buf, dtype=dt)
        y = a[:w * h].reshape(h, w)
        u = a[w * h:w * h + (w // 2) * (h // 2)].reshape(h // 2, w // 2)
        v = a[w * h + (w // 2) * (h // 2):].reshape(h // 2, w // 2)
        out.append((y, u, v))
    p.stdout.close()
    p.wait()
    return out


def detect_cuts(frames, fps: float, mad_floor=28.0, corr_max=0.6) -> list[float]:
    """חיתוכים בחלון (ספי visual_hook_policy: cut_mad_floor / cut_hist_corr_max)."""
    import cv2
    cuts, prev, ph = [], None, None
    for k, (y, _, _) in enumerate(frames):
        s = y[::8, ::8].astype(np.float32)
        if s.max() > 255:
            s = s / 4.0
        hst = cv2.calcHist([s.astype(np.uint8)], [0], None, [32], [0, 256])
        cv2.normalize(hst, hst)
        if prev is not None:
            mad = float(np.abs(s - prev).mean())
            corr = float(cv2.compareHist(hst, ph, cv2.HISTCMP_CORREL))
            if mad > mad_floor and corr < corr_max:
                cuts.append(round(k / fps, 3))
        prev, ph = s, hst
    return cuts


# ─────────────────────────── תכנון לפי פריים ───────────────────────────

def M_scale(s, px, py):
    return np.array([[s, 0, (1 - s) * px], [0, s, (1 - s) * py], [0, 0, 1.0]])


def M_trans(dx, dy):
    return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1.0]])


def norm_moves(edit: dict) -> list[dict]:
    out = []
    for i, m in enumerate(edit.get("moves") or []):
        m = dict(m)
        m.setdefault("id", f"m{i}")
        t = m.get("type")
        if t == "snap_zoom":
            m.setdefault("in", 0.14); m.setdefault("hold", 0.8); m.setdefault("out", 0.25); m.setdefault("scale", 1.15)
            m["start"], m["end"] = float(m["at"]), float(m["at"]) + m["in"] + m["hold"] + m["out"]
        elif t == "push_in":
            m.setdefault("scale", 1.06)
            m["start"], m["end"] = float(m.get("from", 0.0)), float(m.get("to", 2.5))
        elif t == "shake":
            m.setdefault("dur", 0.35); m.setdefault("amp", 0.012)
            m["start"], m["end"] = float(m["at"]), float(m["at"]) + m["dur"]
        elif t == "impact_freeze":
            m.setdefault("hold", 0.35); m.setdefault("punch", 1.05); m.setdefault("shake", 0.0)
            m["start"], m["end"] = float(m["at"]), float(m["at"]) + m["hold"]
        elif t == "speed_ramp":
            m.setdefault("slow", 0.35); m.setdefault("slow_dur", 0.6)
            m["start"], m["end"] = float(m.get("from", 0.0)), float(m["to"])
        elif t in ("whip", "zoom_through"):
            m.setdefault("dur", 0.24)
            m["start"], m["end"] = float(m["at"]) - m["dur"] / 2, float(m["at"]) + m["dur"] / 2
        elif t == "flash":
            m.setdefault("dur", 0.1); m.setdefault("peak", 0.6)
            m["start"], m["end"] = float(m["at"]) - m["dur"] / 2, float(m["at"]) + m["dur"] / 2
        out.append(m)
    return out


def ramp_map(m: dict, fps: float) -> tuple[dict[int, float], float]:
    """speed_ramp: S(t) — זמן מקור לכל זמן פלט בחלון [a,b]. איטי סביב c, ואז תפיסה. S(a)=a, S(b)=b."""
    a, b, c = m["start"], m["end"], float(m["impact"])
    slow, sd = float(m["slow"]), float(m["slow_dur"])
    t1 = max(a, c - 0.5 * slow * sd)               # תחילת ההאטה (פלט = מקור עד כאן)
    t2 = t1 + sd                                     # סוף ההאטה בזמן פלט
    s2 = t1 + slow * sd                              # מקור בסוף ההאטה
    if t2 >= b:
        raise ValueError("speed_ramp: slow_dur ארוך מהחלון")
    fast = (b - s2) / (b - t2)
    ts = np.linspace(a, b, 400)
    v = np.ones_like(ts)
    v[(ts >= t1) & (ts < t2)] = slow
    v[ts >= t2] = fast
    k = max(3, int(0.06 * 400 / max(b - a, 1e-6)))   # החלקה ~60ms
    v = np.convolve(np.pad(v, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), "valid")
    S = a + np.concatenate([[0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(ts))])
    S = a + (S - a) * (b - a) / (S[-1] - a)          # נרמול: S(b)=b בדיוק
    mp = {}
    for f in range(int(round(a * fps)), int(round(b * fps))):
        mp[f] = float(np.interp(f / fps, ts, S)) * fps
    disp_c = float(np.interp(c, S, ts))               # מתי רגע השיא מוצג בפועל
    return mp, disp_c


def plan_frames(moves: list[dict], n: int, info: dict, cuts: list[float], faces_focus=None):
    """לכל פריים פלט: מקור (float), רשימת מטריצות (דגימות מושן-בלר), ואלפא פלאש."""
    fps, W, H = info["fps"], info["w"], info["h"]
    src = np.arange(n, dtype=float)
    base_M = [np.eye(3) for _ in range(n)]
    blur = [None] * n
    flash = np.zeros(n)
    disp = {}

    def focus_px(m):
        f = m.get("focus") or [0.5, 0.4]
        if f == "face":
            f = faces_focus or [0.5, 0.38]
        return float(f[0]) * W, float(f[1]) * H

    for m in moves:                                  # 1) זמן
        if m["type"] == "speed_ramp":
            mp, dc = ramp_map(m, fps)
            for f, s in mp.items():
                if f < n:
                    src[f] = s
            disp[m["id"]] = dc
        elif m["type"] == "impact_freeze":
            f0, f1 = int(round(m["start"] * fps)), int(round(m["end"] * fps))
            for f in range(f0, min(f1, n)):
                src[f] = src[f0] if f0 < n else f0
            disp[m["id"]] = m["start"]
    for m in moves:                                  # 2) גיאומטריה
        t = m["type"]
        for f in range(n):
            tt = f / fps
            if t == "snap_zoom":
                px, py = focus_px(m)
                a, i_, h_, o_ = m["start"], m["in"], m["hold"], m["out"]
                if tt < a or tt >= a + i_ + h_ + o_:        # out=0 ⇒ חזרה חדה (punch-cut) בסוף ההחזקה
                    continue
                if tt < a + i_:
                    s = 1 + (m["scale"] - 1) * ease_out_expo((tt - a) / i_)
                elif tt < a + i_ + h_:
                    s = m["scale"]
                else:
                    s = m["scale"] - (m["scale"] - 1) * ease_in_out((tt - a - i_ - h_) / o_)
                base_M[f] = base_M[f] @ M_scale(s, px, py)
            elif t == "push_in" and m["start"] <= tt < m["end"]:
                px, py = focus_px(m)
                u = (tt - m["start"]) / (m["end"] - m["start"])
                base_M[f] = base_M[f] @ M_scale(1 + (m["scale"] - 1) * ease_in_out(u), px, py)
            elif t == "shake" and m["start"] <= tt < m["end"]:
                u = tt - m["start"]
                amp = m["amp"] * W * math.exp(-u / (m["dur"] / 2.5))
                base_M[f] = base_M[f] @ M_trans(amp * math.sin(2 * math.pi * 17 * u),
                                                0.7 * amp * math.sin(2 * math.pi * 23 * u + 1.3))
            elif t == "impact_freeze" and m["start"] <= tt < m["end"]:
                u = (tt - m["start"]) / (m["end"] - m["start"])
                px, py = focus_px(m)
                base_M[f] = base_M[f] @ M_scale(1 + (m["punch"] - 1) * ease_out_expo(u * 1.5), px, py)
                if m.get("shake"):
                    v = tt - m["start"]
                    amp = m["shake"] * W * math.exp(-v / 0.12)
                    base_M[f] = base_M[f] @ M_trans(amp * math.sin(2 * math.pi * 19 * v), 0.6 * amp * math.sin(2 * math.pi * 27 * v))
                if m.get("flash") and tt - m["start"] < 2.5 / fps:
                    flash[f] = max(flash[f], 0.55 * (1 - (tt - m["start"]) * fps / 2.5))
            elif t in ("whip", "zoom_through") and m["start"] <= tt < m["end"]:
                c, half = float(m["at"]), m["dur"] / 2
                if tt < c:
                    u = (tt - (c - half)) / half; side = "out"
                else:
                    u = (tt - c) / half; side = "in"
                samples = []
                for j in range(11):
                    du = (j - 5) / 10 / max(1, half * fps)        # פיזור תוך-פריים
                    uu = min(max(u + du, 0), 1)
                    if t == "whip":
                        d = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[m.get("dir", "left")]
                        mag = float(m.get("dist", 0.16))
                        k_ = ease_in(uu) if side == "out" else (1 - ease_out_expo(uu))
                        sign = 1 if side == "out" else -1
                        samples.append(M_trans(sign * d[0] * mag * W * k_, sign * d[1] * mag * H * k_))
                    else:
                        amt = float(m.get("amount", 0.45))
                        k_ = ease_in(uu) if side == "out" else (1 - ease_out_expo(uu))
                        samples.append(M_scale(1 + amt * k_, W / 2, H / 2))
                blur[f] = samples
            elif t == "flash" and m["start"] <= tt < m["end"]:
                u = abs(tt - float(m["at"])) / (m["dur"] / 2)
                flash[f] = max(flash[f], m["peak"] * max(0.0, 1 - u))
    return src, base_M, blur, flash, disp


def cover(M: np.ndarray, W: int, H: int) -> np.ndarray:
    """מוסיף זום מינימלי סביב המרכז כך שכל הפלט נלקח מתוך התמונה (בלי שוליים)."""
    Minv = np.linalg.inv(M)
    s = 1.0
    for _ in range(60):
        T = Minv @ np.linalg.inv(M_scale(s, W / 2, H / 2))
        pts = T @ np.array([[0, W, 0, W], [0, 0, H, H], [1, 1, 1, 1.0]])
        if pts[0].min() >= -0.5 and pts[0].max() <= W + 0.5 and pts[1].min() >= -0.5 and pts[1].max() <= H + 0.5:
            return M_scale(s, W / 2, H / 2) @ M
        s += 0.005
    return M_scale(s, W / 2, H / 2) @ M


def warp(plane: np.ndarray, M: np.ndarray, chroma: bool, interp):
    import cv2
    A = M[:2].copy()
    if chroma:
        A[:, 2] /= 2.0
    h, w = plane.shape
    return cv2.warpAffine(plane, A, (w, h), flags=interp, borderMode=cv2.BORDER_REFLECT101)


def render_frames(frames, src, base_M, blur, flash, info):
    import cv2
    W, H, deep = info["w"], info["h"], info["deep"]
    top = 1023 if deep else 255
    mid = 512 if deep else 128
    out, changed = [], []
    n = len(frames)
    for f in range(n):
        s = src[f]
        k0 = int(math.floor(s)); fr = s - k0
        k0 = min(max(k0, 0), n - 1); k1 = min(k0 + 1, n - 1)
        if fr < 1e-3 or k0 == k1:
            Y, U, V = frames[k0]
        else:                                          # בלנד בין פריימים בהאטה
            a, b = frames[k0], frames[k1]
            Y, U, V = [(x.astype(np.float32) * (1 - fr) + y.astype(np.float32) * fr) for x, y in zip(a, b)]
            Y, U, V = [p.round().astype(a[0].dtype) for p in (Y, U, V)]
        ident = (abs(s - f) < 1e-3) and np.allclose(base_M[f], np.eye(3)) and blur[f] is None and flash[f] <= 0
        if ident:
            out.append(frames[f]); changed.append(False); continue
        mats = [cover(base_M[f] @ b_, W, H) for b_ in blur[f]] if blur[f] else [cover(base_M[f], W, H)]
        planes = []
        for pi, P in enumerate((Y, U, V)):
            if len(mats) == 1 and np.allclose(mats[0], np.eye(3)):
                acc = P
            elif len(mats) == 1:
                acc = warp(P, mats[0], pi > 0, cv2.INTER_LANCZOS4)
            else:
                acc = np.zeros(P.shape, np.float32)
                for Mm in mats:
                    acc += warp(P, Mm, pi > 0, cv2.INTER_LINEAR).astype(np.float32)
                acc = (acc / len(mats)).round().astype(P.dtype)
            planes.append(acc)
        if flash[f] > 0:
            a_ = float(flash[f])
            Yf = planes[0].astype(np.float32); Yf += a_ * (top * (940 / 1023 if deep else 235 / 255) - Yf)
            planes[0] = Yf.round().astype(planes[0].dtype)
            for i in (1, 2):
                Cf = planes[i].astype(np.float32); Cf += a_ * (mid - Cf)
                planes[i] = Cf.round().astype(planes[i].dtype)
        out.append(tuple(planes)); changed.append(True)
    return out, changed


# ─────────────────────────── סאונד ───────────────────────────

def pick_variant(role: str, seed: str, idx: int, cat: dict) -> dict | None:
    items = [x for x in cat.get("items", []) if x["role"] == role]
    if not items:
        return None
    h = int(hashlib.sha1(f"{seed}:{role}".encode()).hexdigest(), 16)
    return items[(h + idx) % len(items)]


def plan_sfx(edit: dict, moves: list[dict], disp: dict, seed: str) -> tuple[list[dict], list[str]]:
    raw = []
    for x in edit.get("sfx") or []:
        raw.append({"at": float(x["at"]), "kind": x["kind"], "gain": float(x.get("gain", 0)), "key": x.get("key"),
                    "why": "plan"})
    for m in moves:
        k = AUTO_SFX.get(m["type"])
        if not k or m.get("no_sfx"):
            continue
        at = disp.get(m["id"], float(m.get("at", m["start"])))
        if not any(abs(r["at"] - at) < SFX_MIN_GAP and r["kind"] != "riser" for r in raw):
            raw.append({"at": at, "kind": k, "gain": float(m.get("sfx_gain", 0)), "key": None, "why": f"auto:{m['type']}"})
    raw.sort(key=lambda r: r["at"])
    kept, dropped = [], []
    for r in raw:
        if r["kind"] != "riser":
            clash = [k for k in kept if k["kind"] != "riser" and abs(k["at"] - r["at"]) < SFX_MIN_GAP]
            if clash:
                c = clash[0]
                if SFX_PRIO.get(r["kind"], 0) > SFX_PRIO.get(c["kind"], 0):
                    kept.remove(c); dropped.append(f"{c['kind']}@{c['at']:.2f}")
                else:
                    dropped.append(f"{r['kind']}@{r['at']:.2f}"); continue
        kept.append(r)
    while len([k for k in kept if k["at"] <= MAX_WIN]) > SFX_MAX:
        low = min(kept, key=lambda k: SFX_PRIO.get(k["kind"], 0))
        kept.remove(low); dropped.append(f"{low['kind']}@{low['at']:.2f}")
    return kept, dropped


def build_audio_filter(sfx_items, ref_lufs: float, edit: dict, moves: list[dict], disp: dict, seed: str):
    cat = sfx_catalog()
    inputs, chains, placed = [], [], []
    for i, r in enumerate(sfx_items):
        it = None
        if r.get("key"):
            it = next((x for x in cat.get("items", []) if x["key"] == r["key"]), None)
        it = it or pick_variant(r["kind"], seed, i, cat)
        if not it:
            continue
        path = SFX_DIR / it["file"]
        lead = it["dur"] if it.get("align") == "end" else it["peak_at"]
        start = r["at"] - lead
        trim = max(0.0, -start)
        start = max(0.0, start)
        gain = min(6.0, (ref_lufs + REL_DB.get(r["kind"], -12.0) + r.get("gain", 0.0)) - it["lufs"])
        idx = len(inputs) // 2 + 1          # inputs = ["-i", f, "-i", f…] — זוגות
        inputs += ["-i", str(path)]
        ms = int(round(start * 1000))
        chains.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start={trim:.3f},asetpts=N/SR/TB,"
                      f"volume={gain:.2f}dB,adelay={ms}|{ms}[s{i}]")
        placed.append({"at": round(r["at"], 3), "kind": r["kind"], "key": it["key"], "gain_db": round(gain, 1),
                       "file_start": round(start, 3), "why": r["why"]})
    vol = []
    b = edit.get("boost_orig")
    if b:
        vol.append(f"volume=enable='between(t,{float(b['from']):.3f},{float(b['to']):.3f})':volume={float(b.get('db', 3)):.1f}dB")
    for m in moves:
        if m["type"] == "speed_ramp" and m.get("duck_orig", True):
            vol.append(f"volume=enable='between(t,{m['start']:.3f},{m['end']:.3f})':volume={float(m.get('duck_db', -9)):.1f}dB")
        if m["type"] == "impact_freeze" and m.get("duck_orig"):
            vol.append(f"volume=enable='between(t,{m['start']:.3f},{m['end']:.3f})':volume={float(m.get('duck_db', -9)):.1f}dB")
    base_chain = "[0:a]aresample=48000,aformat=channel_layouts=stereo" + ("," + ",".join(vol) if vol else "") + "[a0]"
    labels = ["[a0]"] + [f"[s{i}]" for i in range(len(chains))]
    fc = ";".join([base_chain] + chains)
    fc += (f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first[a]" if chains
           else ";[a0]anull[a]")
    return inputs, fc, placed


def music_mute(edit: dict, moves: list[dict]) -> list[list[float]]:
    out = [[float(a), float(b)] for a, b in (edit.get("music_drop") or [])]
    for m in moves:
        if m["type"] == "impact_freeze" and m.get("silence"):
            out.append([m["start"], m["end"] + 0.05])
    return [[round(a, 3), round(b, 3)] for a, b in sorted(out)]


# ─────────────────────────── שערים ───────────────────────────

def gate_window(moves) -> dict:
    bad = [f"{m['id']}:{m['type']} {m['start']:.2f}-{m['end']:.2f}" for m in moves
           if m["start"] < -1e-6 or m["end"] > MAX_WIN + 1e-6]
    return gate("HFX1_window", not bad, "blocking", "; ".join(bad) or f"כל התנועות בתוך 0-{MAX_WIN:.0f}ש")


def gate_dosage(moves) -> dict:
    vis = [m for m in moves]
    return gate("HFX2_dosage", len(vis) <= MAX_MOVES, "blocking",
                f"{len(vis)} תנועות (מקס {MAX_MOVES}; רעידה/פלאש בתוך impact_freeze לא נספרים)")


def gate_speech(moves, words) -> dict:
    if not words:
        return gate("HFX3_speech_sync", True, "reporting", "לא נמדד: אין מילים", measured=False)
    bad = []
    for m in moves:
        if m["type"] not in TIME_ALTERING or m.get("voice_off_camera"):
            continue
        a, b = m["start"], m["end"]
        hit = [w["word"] for w in words if float(w["start"]) < b and float(w["end"]) > a]
        if hit:
            bad.append(f"{m['type']} {a:.2f}-{b:.2f} על דיבור: {' '.join(hit[:4])}")
    return gate("HFX3_speech_sync", not bad, "blocking", "; ".join(bad) or "אין עצירה/האטה על דיבור (אין פער שפתיים)")


def gate_ranges(moves) -> dict:
    """טווחי LIM — נקבעו בדמואים (פודיום: 1.18 חתך מצח), לא מסרטונים מאושרים ⇒ מדווח, לא חוסם.
    הבמאי רואה את זה בגיליון; כיול מפסיקות הראל (E16)."""
    bad = []
    for m in moves:
        for (t, k), (lo, hi) in LIM.items():
            if m["type"] == t and k in m and not (lo <= float(m[k]) <= hi):
                bad.append(f"{t}.{k}={m[k]} מחוץ ל-[{lo},{hi}]")
    return gate("HFX4b_ranges", not bad, "reporting", "; ".join(bad) or "פרמטרים בטווח הדמואים")


def gate_bounds(moves) -> dict:
    """תקינות פיזית בלבד: סוג מוכר, רמפה שאפשר לבנות."""
    bad = []
    for m in moves:
        if m["type"] not in MOVE_TYPES:
            bad.append(f"{m['id']}: סוג לא מוכר {m['type']}"); continue
        if m["type"] == "speed_ramp":
            if "impact" not in m:
                bad.append("speed_ramp בלי impact")
            else:
                try:
                    ramp_map(m, 30.0)
                except Exception as e:      # noqa: BLE001
                    bad.append(str(e))
    return gate("HFX4_bounds", not bad, "blocking", "; ".join(bad) or "תנועות תקינות")


def gate_faces(moves, info, faces) -> dict:
    zooms = [m for m in moves if m["type"] in ("snap_zoom", "push_in", "impact_freeze")]
    if not zooms:
        return gate("HFX5_faces", True, "blocking", "אין זום")
    if faces is None:
        return gate("HFX5_faces", True, "reporting", "לא נמדד: זיהוי פנים לא זמין", measured=False)
    bad = []
    for m in zooms:
        s = float(m.get("scale", m.get("punch", 1.0)))
        f = m.get("focus") or [0.5, 0.4]
        if f == "face":
            continue                                   # ממוקד על הפנים עצמן
        px, py = float(f[0]), float(f[1])
        x0, x1 = px - px / s, px + (1 - px) / s
        y0, y1 = py - py / s, py + (1 - py) / s
        for b in faces.get(m["id"], []):
            if b[0] < x0 - 0.01 or b[2] > x1 + 0.01 or b[1] < y0 - 0.01 or b[3] > y1 + 0.01:
                bad.append(f"{m['id']}: פנים נחתכות בזום ×{s} (focus {px:.2f},{py:.2f})")
                break
    return gate("HFX5_faces", not bad, "blocking", "; ".join(bad) or "הפנים נשארות בפריים בכל זום", measured=True)


def gate_cuts(moves, cuts) -> dict:
    bad = []
    for m in moves:
        if m["type"] in TRANSITIONS and not m.get("force"):
            at = float(m["at"])
            near = [c for c in cuts if abs(c - at) <= CUT_TOL]
            if not near:
                bad.append(f"{m['type']}@{at:.2f} בלי חיתוך (חיתוכים: {cuts[:6]})")
            else:
                m["at"] = near[0]                        # הצמדה לחיתוך האמיתי
                half = (m.get("dur") or 0.1) / 2
                m["start"], m["end"] = near[0] - half, near[0] + half
    return gate("HFX6_cut_anchor", not bad, "blocking", "; ".join(bad) or "מעברים יושבים על חיתוכים אמיתיים",
                cuts=cuts)


def gate_conflict(moves, W: Path | None, vh_applied: bool) -> dict:
    # פריז בלי פאנץ׳/רעד לא מזיז פיקסלים — מותר מעל טלסטרייטור (פירוק טכני)
    geo = [m for m in moves if m["type"] in GEOMETRIC
           and not (m["type"] == "impact_freeze" and float(m.get("punch", 1.0)) <= 1.0 and not float(m.get("shake", 0) or 0))]
    bad = []
    if geo and vh_applied:
        bad.append("Visual Hook Engine (punch-in) כבר הוחל — מגבר אחד")
    mp = (W / "motion_plan.json") if W else None
    if geo and mp and mp.exists():
        try:
            evs = json.loads(mp.read_text(encoding="utf-8")).get("events") or []
        except Exception:
            evs = []
        for ev in evs:
            if ev.get("type") in SPATIAL_MG:
                es, ee = float(ev.get("start", 0)), float(ev.get("end", ev.get("start", 0)))
                for m in geo:
                    if es < m["end"] and ee > m["start"]:
                        bad.append(f"MG {ev.get('type')} {es:.2f}-{ee:.2f} חופף ל-{m['type']} (הנקודה תזוז)")
    return gate("HFX10_conflict", not bad, "blocking", "; ".join(bad) or "אין התנגשות עם MG מרחבי / punch-in")


def faces_for(video, moves, info) -> tuple[dict | None, list | None]:
    """פנים בזמן כל זום (haar של motion_build). focus='face' ⇐ מרכז הפנים הגדולות."""
    try:
        sys.path.insert(0, str(HERE))
        import motion_build as MB
    except Exception:
        return None, None
    res, ff = {}, None
    for m in moves:
        if m["type"] in ("snap_zoom", "push_in", "impact_freeze"):
            t = float(m.get("at", m["start"]))
            faces, meth = MB.haar_at(video, max(0.0, min(t + 0.2, info["dur"] - 0.05)))
            if faces is None:
                return None, None
            res[m["id"]] = faces
            if m.get("focus") == "face" and faces:
                b = max(faces, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
                ff = [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]
    return res, ff


def pre_gates(moves, words, info, cuts, faces, W, vh_applied) -> list[dict]:
    return [gate_window(moves), gate_dosage([m for m in moves]), gate_speech(moves, words), gate_bounds(moves), gate_ranges(moves),
            gate_faces(moves, info, faces), gate_cuts(moves, cuts), gate_conflict(moves, W, vh_applied)]


# ─────────────────────────── רינדור ───────────────────────────

def render(base: Path, out: Path, edit: dict, W: Path | None = None, words=None, lossless=False,
           vh_applied=False, seed="") -> dict:
    t0 = time.time()
    info = probe(base)
    moves = norm_moves(edit)
    win_end = min(MAX_WIN + 0.2, max([m["end"] for m in moves] + [0.0]) + 0.1)
    n = max(1, int(round(win_end * info["fps"])))
    frames = read_frames(base, n, info) if moves else []
    n = len(frames)
    cuts = detect_cuts(frames, info["fps"]) if frames else []
    faces, ffocus = faces_for(base, moves, info) if moves else ({}, None)
    gates = pre_gates(moves, words or [], info, cuts, faces, W, vh_applied)
    rep = {"version": "9.46", "base": Path(base).name, "base_stamp": media_stamp(base), "edit_digest": edit_digest(edit),
           "window": round(n / info["fps"], 3) if n else 0, "cuts": cuts, "moves": moves, "gates": gates}
    if any(g["level"] == "blocking" and not g["ok"] for g in gates):
        rep["ok"] = False
        return rep
    src, base_M, blur, flash, disp = plan_frames(moves, n, info, cuts, ffocus) if moves else (None, None, None, None, {})
    seed = seed or (W.name if W else Path(base).stem)
    sfx_items, sfx_dropped = plan_sfx(edit, moves, disp, seed)
    tmp_dir = (W or Path(out).parent)
    win_file = tmp_dir / "_hook_fx_win.mkv"
    changed = []
    if moves:
        outf, changed = render_frames(frames, src, base_M, blur, flash, info)
        pf = "yuv420p10le" if info["deep"] else "yuv420p"
        enc = subprocess.Popen([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", pf,
                                "-s", f"{info['w']}x{info['h']}", "-r", f"{info['fps']:.6f}", "-i", "-",
                                "-c:v", "ffv1", "-level", "3", *ctags(info), str(win_file)], stdin=subprocess.PIPE)
        for (y, u, v) in outf:
            enc.stdin.write(np.ascontiguousarray(y).tobytes())
            enc.stdin.write(np.ascontiguousarray(u).tobytes())
            enc.stdin.write(np.ascontiguousarray(v).tobytes())
        enc.stdin.close()
        enc.wait()
    ref = lufs(base) if has_audio(base) else -20.0
    a_inputs, afc, placed = build_audio_filter(sfx_items, ref, edit, moves, disp, seed)
    tags = ctags(info)
    sp_ = setparams(info)
    pf = "yuv420p10le" if info["deep"] else "yuv420p"
    venc = (["-c:v", "ffv1", "-level", "3"] if lossless else
            ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", pf]) + tags
    if moves:
        inputs = ["-i", str(base), *a_inputs, "-i", str(win_file)]
        wi = 1 + len(a_inputs) // 2
        # ציר פריימים קשיח: שני הענפים מקבלים pts=N/fps לפני trim/concat — אחרת ffmpeg משכפל/מפיל פריים
        # בתפר ושאר הסרטון זז 1-3 פריימים (נמדד 8.10.26: הזזה +1 ב-HSPU, +3→+2 בפודיום).
        fr_ = f"{info['fps']:.6f}"
        vf = (f"[{wi}:v]setpts=N/({fr_}*TB),{sp_}[w];"
              f"[0:v]setpts=N/({fr_}*TB),trim=start_frame={n},setpts=PTS-STARTPTS,{sp_}[r];"
              f"[w][r]concat=n=2:v=1:a=0,{sp_}[v]")
    else:
        inputs = ["-i", str(base), *a_inputs]
        vf = f"[0:v]null[v]"
    if has_audio(base):
        fc = vf + ";" + afc
        amap = ["-map", "[a]", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
    else:
        fc, amap = vf, []
    vmap = ["-map", "[v]"]
    if not moves:                 # סאונד בלבד — הווידאו מועתק כמו שהוא (אפס דור קידוד)
        fc, vmap, venc = afc, ["-map", "0:v"], ["-c:v", "copy"]
    cmd = [FFMPEG, "-nostdin", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, *vmap, *amap,
           "-fps_mode", "passthrough", *venc, str(out)]
    r = sh(cmd)
    win_file.unlink(missing_ok=True)
    if r.returncode != 0:
        rep["ok"] = False
        rep["error"] = r.stderr.decode(errors="ignore")[-600:]
        return rep
    post = post_gates(base, out, info, changed, flash if moves else None)
    rep.update({"ok": all(g["ok"] or g["level"] != "blocking" for g in post),
                "sfx": placed, "sfx_dropped": sfx_dropped, "music_mute": music_mute(edit, moves),
                "display_times": {k: round(v, 3) for k, v in disp.items()}, "ref_lufs": round(ref, 1),
                "out": Path(out).name, "out_stamp": media_stamp(out), "secs": round(time.time() - t0, 1)})
    rep["gates"] = gates + post
    return rep


def post_gates(base, out, info, changed, flash) -> list[dict]:
    o = probe(out)
    gs = []
    dv = abs(o["dur"] - info["dur"])
    da = abs(adur(out) - adur(base)) if has_audio(base) else 0.0
    gs.append(gate("HFX8_duration", dv < 1.5 / info["fps"] + 0.02 and da < 0.05, "blocking",
                   f"וידאו Δ{dv:.3f}ש · אודיו Δ{da:.3f}ש (תנועות שומרות על הציר)"))
    keys = ("color_space", "color_transfer", "color_primaries", "color_range")
    diff = [f"{k}: {info['color'].get(k)}→{o['color'].get(k)}" for k in keys
            if (info["color"].get(k) or "unknown") != (o["color"].get(k) or "unknown")]
    # השוואת ממוצע UV בפריימים שלא שונו (מחוץ לחלון) — חותמת "לא נוגעים בצבע"
    n = len(changed)
    probe_frames = min(n + 30, int(info["dur"] * info["fps"]) - 1)
    try:
        a = read_frames(base, probe_frames, info)
        b = read_frames(out, probe_frames, o)
        idx = [k for k in range(min(len(a), len(b))) if k >= n or not changed[k]]
        dU = max((abs(float(a[k][1].mean()) - float(b[k][1].mean())) for k in idx[-10:]), default=0.0)
        dV = max((abs(float(a[k][2].mean()) - float(b[k][2].mean())) for k in idx[-10:]), default=0.0)
        # יישור: פריים מחוץ לחלון חייב להיות *אותו* פריים (MAD-Y קטן) — הזזה של פריים = כתוביות זזות
        tail = idx[-8:]
        mad0 = max((float(np.abs(a[k][0][::4, ::4].astype(np.int32) - b[k][0][::4, ::4].astype(np.int32)).mean())
                    for k in tail), default=0.0)
        fl = [k for k in range(n) if changed[k] and (flash is None or flash[k] <= 0)]
        dUe = max((abs(float(a[k][1].mean()) - float(b[k][1].mean())) for k in fl[:20]), default=0.0)
        scale = 4.0 if info["deep"] else 1.0
        ok_c = not diff and dU < 2.0 * scale and dV < 2.0 * scale and dUe < 3.0 * scale   # 2.0 = רעש קידוד; המרת צבע אוטומטית נמדדה 6.4
        gs.append(gate("HFX8b_frame_align", mad0 < 3.0 * scale, "blocking",
                       f"MAD-Y בפריימים שאחרי החלון {mad0:.2f} (מעל 3 = הציר זז בפריים)"))
        gs.append(gate("HFX9_color", ok_c, "blocking",
                       ("; ".join(diff) + " " if diff else "") +
                       f"ΔUV מחוץ לחלון {max(dU, dV):.2f} · בתנועות {dUe:.2f} (גיאומטריה בלבד)"))
    except Exception as e:      # noqa: BLE001
        gs.append(gate("HFX9_color", not diff, "blocking", "; ".join(diff) or f"תגיות זהות; ΔUV לא נמדד ({e})",
                       measured=False))
    return gs


# ─────────────────────────── גיליון ───────────────────────────

def _grab(video, times):
    import cv2
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    want = {int(round(t * fps)): t for t in times}
    out, k = {}, 0
    last = max(want) if want else 0
    while k <= last:
        ok, fr = cap.read()
        if not ok:
            break
        if k in want:
            out[want[k]] = fr
        k += 1
    cap.release()
    return out


def _wave(video, secs, width, height):
    import cv2
    r = sh([FFMPEG, "-nostdin", "-loglevel", "error", "-i", str(video), "-t", f"{secs:.2f}", "-vn", "-ac", "1",
            "-ar", "8000", "-f", "s16le", "-"])
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768 if r.stdout else np.zeros(1)
    img = np.full((height, width, 3), 24, np.uint8)
    if len(x) > 1:
        bins = np.array_split(np.abs(x), width)
        for i, b in enumerate(bins):
            v = float(b.max()) if len(b) else 0
            hh = int(v * (height / 2 - 2))
            cv2.line(img, (i, height // 2 - hh), (i, height // 2 + hh), (200, 200, 200), 1)
    return img


def sheet(before: Path, after: Path, out: Path, rep: dict | None = None, secs=3.2, step=0.2) -> Path:
    """לפני (שורות עליונות) / אחרי (תחתונות), כל 0.2ש ב-0-3.2ש, + גל קול של האחרי עם סמני צלילים."""
    import cv2
    times = [round(i * step, 2) for i in range(int(secs / step))]
    A, B = _grab(before, times), _grab(after, times)
    tw, th, cols = 180, 320, 8
    rows = math.ceil(len(times) / cols)
    pad = 26
    Hh = (th + pad) * rows * 2 + 140
    img = np.full((Hh + 40, tw * cols, 3), 16, np.uint8)
    for gi, (lab, G) in enumerate((("BEFORE", A), ("AFTER", B))):
        y0 = gi * (th + pad) * rows
        for i, t in enumerate(times):
            r_, c_ = divmod(i, cols)
            x, y = c_ * tw, y0 + r_ * (th + pad) + pad
            fr = G.get(t)
            if fr is not None:
                img[y:y + th, x:x + tw] = cv2.resize(fr, (tw, th), interpolation=cv2.INTER_AREA)
            cv2.putText(img, f"{lab} {t:.2f}s", (x + 4, y - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (230, 230, 230), 1)
    wy = (th + pad) * rows * 2 + 10
    wv = _wave(after, secs, tw * cols, 110)
    img[wy:wy + 110] = wv
    if rep:
        for s in rep.get("sfx", []):
            x = int(s["at"] / secs * tw * cols)
            cv2.line(img, (x, wy), (x, wy + 110), (0, 90, 255), 2)
            cv2.putText(img, s["kind"], (x + 3, wy + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 140, 255), 1)
        for m in rep.get("moves", []):
            x0 = int(m["start"] / secs * tw * cols); x1 = int(min(m["end"], secs) / secs * tw * cols)
            cv2.rectangle(img, (x0, wy + 112), (max(x0 + 2, x1), wy + 126), (60, 180, 60), -1)
            cv2.putText(img, m["type"], (x0 + 2, wy + 140), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120, 230, 120), 1)
        for a_, b_ in rep.get("music_mute", []):
            x0 = int(a_ / secs * tw * cols); x1 = int(b_ / secs * tw * cols)
            cv2.rectangle(img, (x0, wy + 100), (x1, wy + 108), (200, 60, 200), -1)
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return out


# ─────────────────────────── CLI ───────────────────────────

def cmd_check(a) -> int:
    W = Path(a.workdir)
    edit = load_edit(W, a.plan)
    moves = norm_moves(edit)
    words = load_words(W, a.words)
    cuts, faces, info = [], None, None
    if a.base:
        info = probe(a.base)
        n = int(round(min(MAX_WIN + 0.2, max([m["end"] for m in moves] + [0]) + 0.1) * info["fps"]))
        cuts = detect_cuts(read_frames(a.base, n, info), info["fps"]) if n else []
        faces, _ = faces_for(a.base, moves, info)
    gs = pre_gates(moves, words, info or {"w": 1080, "h": 1920, "fps": 30}, cuts, faces, W, a.vh_applied)
    if not a.base:
        gs = [g if g["gate"] != "HFX6_cut_anchor" else gate("HFX6_cut_anchor", True, "reporting",
                                                             "לא נמדד: בלי --base", measured=False) for g in gs]
    print(json.dumps({"ok": all(g["ok"] or g["level"] != "blocking" for g in gs), "cuts": cuts, "gates": gs},
                     ensure_ascii=False, indent=1))
    return 0 if all(g["ok"] or g["level"] != "blocking" for g in gs) else 2


def cmd_render(a) -> int:
    W = Path(a.workdir) if a.workdir else None
    edit = load_edit(W, a.plan)
    words = load_words(W, a.words)
    rep = render(Path(a.base), Path(a.out), edit, W=W, words=words, lossless=a.lossless, vh_applied=a.vh_applied)
    rp = (W or Path(a.out).parent) / "HOOK_FX_REPORT.json"
    if a.plan:      # תוכנית נגזרת (למשל v2 בלי תנועות) — שומרים את חתימת המקור ל-P22
        try:
            rep["orig_edit_digest"] = json.loads(Path(a.plan).read_text(encoding="utf-8")).get("orig_digest")
        except Exception:
            pass
    if rep.get("ok") and not a.no_sheet:
        sp = (W or Path(a.out).parent) / "HOOK_FX_SHEET.jpg"
        sheet(Path(a.base), Path(a.out), sp, rep)
        rep["sheet"] = sp.name
    rp.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [g["gate"] + ": " + g["detail"] for g in rep.get("gates", []) if g["level"] == "blocking" and not g["ok"]]
    print(json.dumps({"ok": rep.get("ok"), "blocking": bad, "sfx": rep.get("sfx"), "music_mute": rep.get("music_mute"),
                      "secs": rep.get("secs"), "error": rep.get("error")}, ensure_ascii=False))
    return 0 if rep.get("ok") else 2


def cmd_sheet(a) -> int:
    W = Path(a.workdir)
    rp = W / "HOOK_FX_REPORT.json"
    rep = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else None
    print(sheet(Path(a.before), Path(a.after), W / "HOOK_FX_SHEET.jpg", rep))
    return 0


def cmd_demo(a) -> int:
    """לפני/אחרי על N השניות הראשונות של סרטון קיים — עותק בלבד, לא נוגע במקור."""
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    clip = out / "before.mp4"
    sh([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-i", a.src, "-t", f"{a.secs:.2f}", "-c:v", "libx264",
        "-crf", "14", "-preset", "medium", "-c:a", "aac", "-b:a", "320k", clip])
    edit = load_edit(None, a.plan)
    words = load_words(None, a.words) if a.words else []
    rep = render(clip, out / "after.mp4", edit, W=None, words=words, seed=Path(a.src).stem)
    (out / "HOOK_FX_REPORT.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    if rep.get("ok"):
        sheet(clip, out / "after.mp4", out / "HOOK_FX_SHEET.jpg", rep)
        compare(clip, out / "after.mp4", out / "compare.mp4")
    print(json.dumps({"ok": rep.get("ok"), "gates": [g for g in rep["gates"] if not g["ok"]], "sfx": rep.get("sfx")},
                     ensure_ascii=False))
    return 0 if rep.get("ok") else 2


def compare(before: Path, after: Path, out: Path) -> Path:
    """לפני | אחרי זה לצד זה (540×960 כל צד), אודיו של האחרי."""
    fc = ("[0:v]scale=540:960,drawbox=x=0:y=0:w=540:h=44:color=black@0.55:t=fill,"
          "drawtext=text='BEFORE':x=12:y=10:fontsize=26:fontcolor=white[l];"
          "[1:v]scale=540:960,drawbox=x=0:y=0:w=540:h=44:color=black@0.55:t=fill,"
          "drawtext=text='AFTER':x=12:y=10:fontsize=26:fontcolor=white[r];[l][r]hstack=inputs=2[v]")
    r = sh([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-i", before, "-i", after, "-filter_complex", fc,
            "-map", "[v]", "-map", "1:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", out])
    if r.returncode != 0:          # בלי drawtext (ffmpeg בלי freetype)
        fc2 = "[0:v]scale=540:960[l];[1:v]scale=540:960[r];[l][r]hstack=inputs=2[v]"
        sh([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-i", before, "-i", after, "-filter_complex", fc2,
            "-map", "[v]", "-map", "1:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", out])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("check"); c.add_argument("--workdir", required=True); c.add_argument("--base")
    c.add_argument("--plan"); c.add_argument("--words"); c.add_argument("--vh-applied", action="store_true")
    c.set_defaults(fn=cmd_check)
    r = sp.add_parser("render"); r.add_argument("--workdir"); r.add_argument("--base", required=True)
    r.add_argument("--out", required=True); r.add_argument("--plan"); r.add_argument("--words")
    r.add_argument("--lossless", action="store_true"); r.add_argument("--vh-applied", action="store_true")
    r.add_argument("--no-sheet", action="store_true"); r.set_defaults(fn=cmd_render)
    s = sp.add_parser("sheet"); s.add_argument("--workdir", required=True); s.add_argument("--before", required=True)
    s.add_argument("--after", required=True); s.set_defaults(fn=cmd_sheet)
    d = sp.add_parser("demo"); d.add_argument("--src", required=True); d.add_argument("--plan", required=True)
    d.add_argument("--out", required=True); d.add_argument("--secs", type=float, default=8.0); d.add_argument("--words")
    d.set_defaults(fn=cmd_demo)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
