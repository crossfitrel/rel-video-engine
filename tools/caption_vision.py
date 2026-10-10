#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
caption_vision.py — V7: הכתוביות נבדקות על הפיקסלים של ה-FINAL (v9.29, 22.9.26)
================================================================================

למה זה נולד
-----------
‏`V7_captions_readable` היה `manual` "לנצח": השער היחיד שמסתכל על הכתוביות
**כפי שהן נראות** היה עין אנושית על contact sheets. כל שאר שערי הכתוביות
(G6/G6b/G9/caption_safety) בודקים את **המילים** — לא את מה שנצרב. ולכן
התקלות שהראל תפס בעין עברו כל שער: היפוך RTL כפול (raqm + get_display,
24.7.26), פונט שמשבש גליפים, כתובית שנחתכת בקצה, כתובית כפולה.

הרעיון שהופך את זה לאוטומטי: **הרינדור דטרמיניסטי.** יודעים בדיוק איזו
מילה אמורה להיות על המסך בכל רגע (words_final → group_cues), באיזה פונט,
גודל, מתאר ומיקום (captions_overlay.band_box/_draw — אותו קוד שצורב).
אז לכל cue שנדגם:

  1. חולצים את הפריים מה-FINAL באמצע ה-cue (כולל היסט פתיח קבוע).
  2. מבודדים את פיקסלי הכתובית: לבן **צמוד** למתאר בצבע המותג — אותו סיגנל
     שנמדד ב-cover_guard (כמעט לא קיים בצילום טבעי).
  3. משווים למסכה של הרינדור הצפוי (F-score עם סבולת 3px) — ולמסכה של
     אותה מילה **הפוכה** (מחרוזת הפוכה ב-raqm = בדיוק תקלת ההיפוך הכפול).

מה נמדד לכל cue
----------------
  f_ok        התאמה לרינדור הנכון (0-1)
  f_rev       התאמה לרינדור ההפוך
  reversed    f_rev גבוה מ-f_ok בפער ובסף נמדד        → היפוך RTL
  missing     כמעט אין פיקסלי כתובית באזור הצפוי       → כתובית חסרה/זזה בזמן
  garbled     יש פיקסלי כתובית אבל f_ok נמוך מהסף      → גליפים משובשים/פונט אחר/מילה אחרת
  extra_ink   פיקסלי כתובית מחוץ לאזור הצפוי            → כתובית כפולה/טקסט צרוב במקור
  clipped     הרינדור הצפוי חורג מרוחב הפריים           → מילה נחתכת בקצה
  face        פנים (Haar) חותכות את מלבן הכתובית        → כתובית על הפנים
  punct       '.' ',' '…' בטקסט                        → הפרת קאנון
  tofu        תו שאין לו גליף בפונט (cmap)              → ריבוע/גליף שבור
  brand       צבע המתאר שנמצא ≠ מותג המניפסט            → הפרת פרופיל מותג אטומי

מה חוסם ומה מדווח — לפי מדידה (עקרון 1)
-----------------------------------------
הספים נגזרו ב---calibrate על 16 הסרטונים שהראל אישר (reference_profile) +
הזרקת כשל על רקעים אמיתיים מאותם סרטונים (EXPORT). שער חוסם רק כשההפרדה
נמדדה נקייה: reversed/garbled/missing/tofu. face/clipped/extra_ink/brand —
מדווחים (אי אפשר לשנות את המציאות בפריים, או שהסף עוד לא נמדד).
הקובץ `caption-vision-calibration.json` הוא מקור הספים; בלעדיו הכל מדווח.

הפלט: `CAPTION_VISION.json` + `caption_vision_sheet.jpg` (הגרועים ביותר:
פריים מול צפוי) — הגיליון הוא מה ש-Claude קורא ב-Read כשיש ממצא.

שימוש
-----
  python3 caption_vision.py --workdir W                      # FINAL.mp4 + words_final.json
  python3 caption_vision.py --workdir W --video FINAL_PENDING.mp4 --strict
  python3 caption_vision.py --calibrate W1 W2 ...             # כותב caption-vision-calibration.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent            # tools/
APPDIR = HERE.parent / "captions-app"
for _p in (str(HERE), str(APPDIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import captions_overlay as co                      # noqa: E402  אותו קוד שצורב
from captions_build import group_cues, load_words  # noqa: E402

CALIB = HERE / "caption-vision-calibration.json"

# פרמטרי הבידוד — אותם ערכים של cover_guard (נמדדו שם על 19 זוגות EXPORT/FINAL).
BRIGHT_V, BRIGHT_S = 200, 50
STROKE_TOL = 46
NEAR_PX = 4
TOL_PX = 3            # סבולת יישור בין פריים לרינדור (קידוד/סקייל)
REGION_PAD = 14       # אזור ההשוואה סביב שתי ההשערות

DEFAULTS = {
    # ברירות מחדל שמרניות — **לא חוסמות**. רק קובץ הכיול מקדם לחוסם.
    "f_ok_min": 0.55,           # מידע (סבולת 3px) — לא מפריד שיבוש מתקין (נמדד)
    "f1_min": 0.45,             # f_ok1 (סבולת 1px) מתחת לזה = garbled
    "rev_margin": 0.12,         # f_rev - f_ok מעל זה = reversed
    "missing_ink_ratio": 0.20,  # דיו באזור / שטח צפוי מתחת לזה = missing
    "extra_ink_ratio": 0.35,    # דיו מחוץ לאזור / שטח צפוי מעל זה = extra_ink
    "sym_iou": 0.75,            # רינדור נכון≈הפוך (מילה סימטרית) ⇒ לא מכריעים כיוון
    # v9.34: g1 = f_ok1 × r1 (recall בסבולת 1px). None = לא נמדד ⇒ אין דגל garbled_cue.
    # רקע אירוע עמוס (אדום-לבן) מוסיף דיו זר ⇒ מוריד precision, לא recall; גליף
    # שגוי מוריד recall. רקע לבן מוריד גם recall (2 cues תקינים בדרג-לי, נבדק בעין) —
    # ולכן חוסם רק ב-≥3 cues. נמדד על כל ה-cues של 50 FINAL חיים (גל 6).
    "g1_max": None,
    "source": "default_unmeasured",
    "blocking": [],
}


def load_calibration() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CALIB.read_text(encoding="utf-8")).get("params", {}))
    except Exception:
        pass
    return cfg


# ═══════════════════════════════════════════════════════════════════════
# גיאומטריה — משוחזרת מאותו קוד שצורב (captions_overlay.burn / relvid.render)
# ═══════════════════════════════════════════════════════════════════════
def geometry(cues, W, H, brand):
    prof = (co.BRAND_PROFILES.get(co.BRAND_ALIASES.get(brand, brand))
            or co.BRAND_PROFILES["club"])
    scale = H / 1920.0
    fontsize = max(28, round(120 * scale))
    stroke = max(3, round(7 * scale))
    marginv = max(40, round(430 * scale))
    font = ImageFont.truetype(str(prof["font"]), fontsize)
    y0, band_h = co.band_box(cues, W, H, font, stroke, marginv)
    return {"font": font, "font_path": str(prof["font"]), "stroke": stroke,
            "y0": int(y0), "band_h": int(band_h),
            "baseline": (H - marginv) - int(y0), "outline": prof["outline"]}


def render_mask(text, g, W, direction="rtl", font=None):
    """מסכת הדיו הצפויה (מילוי+מתאר) ברצועה, ו-bbox שלה.

    direction="reversed" = תקלת ההיפוך הכפול (get_display על גבי raqm): raqm
    מקבל מחרוזת שכבר הופכה ומהפך אותה שוב ⇒ הרצף החזותי הפוך. נמדד 22.9.26:
    direction="ltr" **לא** משחזר את התקלה — ב-raqm הוא רק כיוון הפסקה, ורצף
    אותיות עבריות עדיין מסודר מימין לשמאל (69/69 cues יצאו זהים לנכון)."""
    if direction == "reversed":
        text, direction = text[::-1], "rtl"
    img = Image.new("RGBA", (W, g["band_h"]), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font or g["font"]
    kw = {"direction": direction} if co.RAQM else {}
    t = text if co.RAQM else (co._bidi_fallback(text) if direction == "rtl" else text)
    d.text((W // 2, g["baseline"]), t, font=f, fill=(255, 255, 255, 255), anchor="ms",
           stroke_width=g["stroke"], stroke_fill=tuple(g["outline"]), **kw)
    arr = np.asarray(img)
    a = arr[..., 3] > 100
    # מילוי הגליף (לבן פנימי, בלי המתאר) — הצורה שמבדילה מילה מהיפוכה.
    # המתאר העבה של 7px מאחד כמעט כל מילה לכתם דומה, ולכן כיוון נמדד על המילוי.
    fill = a & (arr[..., 0] > 200) & (arr[..., 1] > 200) & (arr[..., 2] > 200)
    try:
        bb = d.textbbox((W // 2, g["baseline"]), t, font=f, anchor="ms",
                        stroke_width=g["stroke"], **kw)
    except Exception:
        bb = (0, 0, W, g["band_h"])
    return a, bb, fill


def ink_mask(band_bgr, outlines_rgb):
    """פיקסלי כתובית בפריים: לבן צמוד-מתאר ∪ מתאר צמוד-לבן, לכל צבע מותג."""
    hsv = cv2.cvtColor(band_bgr, cv2.COLOR_BGR2HSV)
    white = (hsv[..., 2] >= BRIGHT_V) & (hsv[..., 1] <= BRIGHT_S)
    f = band_bgr.astype(np.int16)
    k = np.ones((NEAR_PX * 2 + 1, NEAR_PX * 2 + 1), np.uint8)
    near_w = cv2.dilate(white.astype(np.uint8), k) > 0
    out = {}
    for name, rgb in outlines_rgb.items():
        bgr = np.array([rgb[2], rgb[1], rgb[0]], np.int16)
        stroke = np.abs(f - bgr).sum(axis=2) <= STROKE_TOL * 3
        near_s = cv2.dilate(stroke.astype(np.uint8), k) > 0
        out[name] = (white & near_s) | (stroke & near_w)
        out[name + ":fill"] = white & near_s
    return out


def _dil(m, px):
    k = np.ones((px * 2 + 1, px * 2 + 1), np.uint8)
    return cv2.dilate(m.astype(np.uint8), k) > 0


def fscore(obs, exp, region, tol=TOL_PX):
    p, r = prec_recall(obs, exp, region, tol)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def prec_recall(obs, exp, region, tol=TOL_PX):
    """precision = כמה מהדיו בפריים מוסבר ע"י הרינדור; recall = כמה מהרינדור נמצא."""
    o = obs & region
    no, ne = int(o.sum()), int(exp.sum())
    if no == 0 or ne == 0:
        return 0.0, 0.0
    p = float((o & _dil(exp, tol)).sum()) / no
    r = float((exp & _dil(o, tol)).sum()) / ne
    return p, r


def iou(a, b):
    u = int((a | b).sum())
    return 0.0 if u == 0 else float((a & b).sum()) / u


def score_cue(band_bgr, text, g, W, outline_name, obs_all, cfg, H=None):
    """השוואת פריים אחד לרינדור הצפוי ולרינדור ההפוך. מחזיר dict מדדים."""
    a_ok, bb, w_ok = render_mask(text, g, W, "rtl")
    a_rev, _, w_rev = render_mask(text, g, W, "reversed")
    region = _dil(a_ok | a_rev, REGION_PAD)
    obs = obs_all[outline_name]
    obs_w = obs_all[outline_name + ":fill"]
    exp_area = max(1, int(a_ok.sum()))
    # f_ok/f_rev על מילוי הגליף: הצורה שנושאת את הזהות והסדר של האותיות
    f_ok = fscore(obs_w, w_ok, region)
    f_rev = fscore(obs_w, w_rev, region)
    p1, r1 = prec_recall(obs_w, w_ok, region, tol=1)   # סבולת צרה — מדד משני לשיבוש
    f_ok1 = 0.0 if p1 + r1 == 0 else 2 * p1 * r1 / (p1 + r1)
    ink_in = int((obs & region).sum()) / exp_area
    ink_out = int((obs & ~_dil(region, 6)).sum()) / exp_area
    sym = iou(w_ok, w_rev) >= cfg["sym_iou"]
    return {"f_ok": round(f_ok, 3), "f_rev": round(f_rev, 3), "f_ok1": round(f_ok1, 3),
            "r1": round(r1, 3), "g1": round(f_ok1 * r1, 3),
            "ink_in": round(ink_in, 3), "ink_out": round(ink_out, 3),
            "symmetric": bool(sym), "bbox": [int(x) for x in bb]}


def classify(m, text, W, cfg, tofu_chars):
    flags = []
    if m["ink_in"] < cfg["missing_ink_ratio"]:
        flags.append("missing")
    else:
        if (not m["symmetric"] and m["f_rev"] - m["f_ok"] > cfg["rev_margin"]):
            flags.append("reversed")
        elif m.get("f_ok1", 1.0) < cfg.get("f1_min", DEFAULTS["f1_min"]):
            # שיבוש נמדד בסבולת 1px: בסבולת 3px כתובית "ריבועים" (tofu) קיבלה
            # 0.73 מול מינימום 0.70 בכתוביות מאושרות — אין הפרדה. ב-1px יש.
            flags.append("garbled")
        g1max = cfg.get("g1_max")
        if g1max is not None and m.get("g1", 1.0) < g1max:
            # v9.34 (גל 6): כלל פר-cue שמחזיק גם על רקעי אירוע — נמדד על כל ה-cues
            # של 50 FINAL חיים (13 Throwdown); חוסם ב-≥3 cues (min_hits) בלי תנאי אחוז.
            flags.append("garbled_cue")
    if m["ink_out"] > cfg["extra_ink_ratio"]:
        flags.append("extra_ink")
    x0, _, x1, _ = m["bbox"]
    if x0 < 4 or x1 > W - 4:
        flags.append("clipped")
    if re.search(r"[.,…]", text):
        flags.append("punct")
    if tofu_chars:
        flags.append("tofu")
    return flags


def font_cmap(path):
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(path, fontNumber=0, lazy=True)
        cov = set()
        for tb in t["cmap"].tables:
            cov |= {chr(c) for c in tb.cmap.keys()}
        return cov
    except Exception:
        return None


_FACE = None


def faces(bgr):
    global _FACE
    if _FACE is None:
        p = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        _FACE = cv2.CascadeClassifier(p) if os.path.exists(p) else False
    if _FACE is False:
        return None                         # 'לא נמדד' ≠ 'אין פנים' (עקרון 11)
    s = 0.33
    small = cv2.resize(bgr, None, fx=s, fy=s)
    gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
    r = _FACE.detectMultiScale(gray, 1.1, 8, minSize=(40, 40))
    return [tuple(int(v / s) for v in f) for f in (r if len(r) else [])]


_EYE = None


def eyes_in(bgr, box):
    """כמה עיניים (Haar) ב-60% העליונים של תיבת הפנים. None = אין מסווג (לא נמדד).

    v9.34 (גל 6): Haar-פנים לבדו סימן 35 פגיעות ב-3,656 cues מ-50 FINAL חיים — ובעין
    (face_sheet_*.jpg) רק 4 מהן היו פנים אמיתיות מתחת לכתובית (סלפי); השאר ידיים,
    ברכיים, חולצה. דרישת ≥2 עיניים בתיבה: 4/4 אמיתיות נשמרו, 0/31 שגויות."""
    global _EYE
    if _EYE is None:
        p = os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml")
        _EYE = cv2.CascadeClassifier(p) if os.path.exists(p) else False
    if _EYE is False:
        return None
    fx, fy, fw, fh = box
    roi = bgr[max(0, fy):fy + int(fh * 0.6), max(0, fx):fx + fw]
    if roi.size == 0:
        return 0
    s = 160.0 / max(1, fw)
    roi = cv2.equalizeHist(cv2.resize(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), None, fx=s, fy=s))
    return len(_EYE.detectMultiScale(roi, 1.1, 6, minSize=(14, 14)))


# ═══════════════════════════════════════════════════════════════════════
# קלט הפרויקט
# ═══════════════════════════════════════════════════════════════════════
def project_inputs(W_dir: Path, video=None, words=None, brand=None):
    W_dir = Path(W_dir)
    video = Path(video) if video else W_dir / "FINAL.mp4"
    words = Path(words) if words else W_dir / "words_final.json"
    man = {}
    try:
        man = json.loads((W_dir / "project_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    brand = brand or man.get("brand") or "rel"
    intro = None                       # None = לא רשום (לא "אפס") ⇒ ייאמד מהפיקסלים
    try:
        prov = json.loads((W_dir / "FINAL_PROVENANCE.json").read_text(encoding="utf-8"))
        if "intro_offset_sec" in prov:
            intro = float(prov.get("intro_offset_sec") or 0.0)
    except Exception:
        pass
    return video, words, brand, intro


def sample_frames(video: Path, times: list[float]):
    """קריאה סדרתית (grab) — מהירה ומדויקת לפריים, בלי seek לא-אמין."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    want = {}
    for i, t in enumerate(times):
        fi = int(round(t * fps))
        if 0 <= fi < max(n, 1) or n == 0:
            want.setdefault(fi, []).append(i)
    out = [None] * len(times)
    fi, last = 0, max(want) if want else -1
    while fi <= last:
        if not cap.grab():
            break
        if fi in want:
            ok, fr = cap.retrieve()
            if ok:
                for i in want[fi]:
                    out[i] = fr
        fi += 1
    cap.release()
    return out, fps


def ink_series(video: Path, g, step=3):
    """כמות דיו-כתובית ברצועה לאורך הסרטון (כל step פריימים)."""
    outlines = {"club": co.BRAND_PROFILES["club"]["outline"][:3],
                "personal": co.BRAND_PROFILES["personal"]["outline"][:3]}
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    ts, vals, fi = [], [], 0
    while cap.grab():
        if fi % step == 0:
            ok, fr = cap.retrieve()
            if ok:
                band = fr[g["y0"]:g["y0"] + g["band_h"]]
                m = ink_mask(band, outlines)
                vals.append(max(int(m["club"].sum()), int(m["personal"].sum())))
                ts.append(fi / fps)
        fi += 1
    cap.release()
    return np.array(ts), np.array(vals, float)


def estimate_offset(video: Path, cues, g, max_off=20.0):
    """היסט ציר המילים מול ה-FINAL, כשהוא לא רשום ב-FINAL_PROVENANCE (FINAL
    ידני/ישן — למשל 'manual-intro-reattach' של מאסל מן, 1.8.26, לפני v9.19).
    קורלציה בין "יש כתובית" לפי המילים לבין "יש דיו" בפיקסלים. מדווח את
    האיכות — היסט שנאמד אינו עובדה, וזה נרשם בדוח."""
    ts, v = ink_series(video, g)
    if len(v) < 10 or v.max() <= 0:
        return 0.0, 0.0
    on = (v > 0.25 * np.percentile(v[v > 0], 75)).astype(float) if (v > 0).any() else v
    dt = float(np.median(np.diff(ts))) if len(ts) > 1 else 0.1
    best, best_c = 0.0, -1.0
    for k in range(0, int(max_off / dt) + 1):
        off = k * dt
        exp = np.zeros_like(on)
        for c in cues:
            exp[(ts >= c["start"] + off) & (ts < c["end"] + off)] = 1.0
        if exp.sum() == 0:
            continue
        agree = float(((exp == 1) & (on == 1)).sum()) / exp.sum()
        agree -= 0.5 * float(((exp == 0) & (on == 1)).sum()) / max(1.0, (exp == 0).sum())
        if agree > best_c:
            best, best_c = off, agree
    return round(best, 3), round(best_c, 3)


def analyze(W_dir, video=None, words=None, brand=None, max_cues=0, cfg=None,
            sheet=True, write=True, intro_offset=None):
    cfg = cfg or load_calibration()
    W_dir = Path(W_dir)
    video, words, brand, intro = project_inputs(W_dir, video, words, brand)
    forced = intro_offset is not None
    if forced:                                   # הצינור יודע את intro_sec בוודאות
        intro = float(intro_offset)
    if not video.exists() or not words.exists():
        return {"ok": None, "measured": False,
                "why": f"חסר קלט: {video.name if not video.exists() else words.name}"}
    cues = group_cues(load_words(str(words)))
    cap = cv2.VideoCapture(str(video))
    Wv = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); Hv = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    g = geometry(cues, Wv, Hv, brand)
    cmap = font_cmap(g["font_path"])
    offset_source = "pipeline" if forced else "provenance"
    offset_quality = None
    if intro is None:
        intro, offset_quality = estimate_offset(video, cues, g)
        offset_source = "estimated"
    # דגימה: כל cue באורך ≥2 פריימים; max_cues>0 = דגימה אחידה
    idx = [i for i, c in enumerate(cues) if c["end"] - c["start"] >= 0.07]
    if max_cues and len(idx) > max_cues:
        step = len(idx) / float(max_cues)
        idx = [idx[int(k * step)] for k in range(max_cues)]
    times = [intro + (cues[i]["start"] + cues[i]["end"]) / 2.0 for i in idx]
    frames, fps = sample_frames(video, times)
    outlines = {"club": co.BRAND_PROFILES["club"]["outline"][:3],
                "personal": co.BRAND_PROFILES["personal"]["outline"][:3]}
    want_outline = "personal" if co.BRAND_ALIASES.get(brand, brand) == "personal" else "club"
    rows, brand_votes = [], {"club": 0, "personal": 0}
    for i, t, fr in zip(idx, times, frames):
        c = cues[i]
        if fr is None:
            rows.append({"i": i, "t": round(t, 2), "text": c["text"], "flags": ["no_frame"]})
            continue
        band = fr[g["y0"]:g["y0"] + g["band_h"]]
        obs_all = ink_mask(band, outlines)
        # איזה מתאר באמת נצרב — פרופיל מותג אטומי. המדידה נעשית מול המתאר
        # שנמצא בפריים (אחרת כתובית תקינה בצבע השני נראית "חסרה"), והפער מול
        # המניפסט מדווח בנפרד כ-brand.
        other = "club" if want_outline == "personal" else "personal"
        used = want_outline
        if int(obs_all[other].sum()) > 2 * max(1, int(obs_all[want_outline].sum())):
            used = other
        brand_votes[used] += 1
        m = score_cue(band, c["text"], g, Wv, used, obs_all, cfg)
        tofu = sorted({ch for ch in c["text"] if cmap is not None
                       and ch not in cmap and not ch.isspace()})
        flags = classify(m, c["text"], Wv, cfg, tofu)
        fc = faces(fr)
        if fc is None:
            m["face"] = None
        else:
            x0, y0b, x1, y1b = m["bbox"]
            cy0, cy1 = g["y0"] + y0b, g["y0"] + y1b
            hit = [f for f in fc if f[0] < x1 and f[0] + f[2] > x0
                   and f[1] < cy1 and f[1] + f[3] > cy0]
            ne = [eyes_in(fr, f) for f in hit]
            if any(n is None for n in ne):
                verified = hit                  # אין מסווג עיניים ⇒ ההתנהגות הישנה, מסומן
                m["face_eye_check"] = None
            else:
                verified = [f for f, n in zip(hit, ne) if n >= 2]
                m["face_eye_check"] = True
            m["face_raw"] = bool(hit)
            m["face"] = bool(verified)
            if verified:
                flags.append("face")
        rows.append({"i": i, "t": round(t, 2), "text": c["text"], **m,
                     "tofu": tofu, "flags": flags})
    measured = [r for r in rows if "f_ok" in r]
    brand_found = max(brand_votes, key=brand_votes.get) if measured else None
    counts: dict[str, int] = {}
    for r in rows:
        for f in r["flags"]:
            counts[f] = counts.get(f, 0) + 1
    blocking = set(cfg.get("blocking") or [])
    # min_hits/min_frac (נמדד בסריקת 40 FINAL חיים, 22.9.26): תקלה אמיתית פוגעת
    # בהרבה cues (היפוך כפול = כולם; ציר מילים שגוי = רצף). cue בודד שחוצה סף
    # על פריים עמוס (רחבת Throwdown, אדום-לבן ברקע) הוא רעש — עולה ל-preflight
    # כ-HIGH ולא עוצר גימור. garbled הוצא מהחסימה: 5 חיוביים-שגויים בסרטון אחד
    # של אירוע, נבדקו בעין — הכתובית תקינה.
    min_hits = cfg.get("min_hits") or {}
    min_frac = cfg.get("min_frac") or {}
    nm = max(1, sum(1 for r in rows if "f_ok" in r))
    block_hits = {k: v for k, v in counts.items()
                  if k in blocking and v >= int(min_hits.get(k, 1))
                  and v >= float(min_frac.get(k, 0.0)) * nm}
    fok = [r["f_ok"] for r in measured]
    doc = {
        "video": str(video), "words": str(words), "brand": brand,
        "brand_found": brand_found,
        "brand_mismatch": bool(brand_found and brand_found != want_outline
                               and brand_votes[brand_found] > len(measured) * 0.6),
        "intro_offset_sec": intro, "offset_source": offset_source,
        "offset_quality": offset_quality,
        "n_cues": len(cues), "n_sampled": len(rows),
        "n_measured": len(measured), "measured": bool(measured),
        "f_ok_median": round(statistics.median(fok), 3) if fok else None,
        "f_ok_min": round(min(fok), 3) if fok else None,
        "counts": counts, "blocking_flags": sorted(blocking),
        "blocking_hits": block_hits, "threshold_source": cfg.get("source"),
        "raqm": bool(co.RAQM),
        "ok": (not block_hits) if measured else None,
        "cues": rows,
    }
    if doc["brand_mismatch"]:
        counts["brand"] = brand_votes.get(brand_found, 0)
    if write:
        (W_dir / "CAPTION_VISION.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    if sheet and measured:
        doc["sheet"] = str(write_sheet(W_dir, video, rows, g, Wv, frames, idx))
        if write:
            (W_dir / "CAPTION_VISION.json").write_text(
                json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def write_sheet(W_dir, video, rows, g, Wv, frames, idx, n=10):
    """גיליון הגרועים: שורה = הפריים ברצועה (למעלה) מול הרינדור הצפוי (למטה).
    זה מה ש-Claude קורא ב-Read כשיש ממצא — הראיה, לא התווית."""
    by_i = {i: fr for i, fr in zip(idx, frames)}
    ms = [r for r in rows if "f_ok" in r]
    ms.sort(key=lambda r: (0 if r["flags"] else 1, r["f_ok"]))
    pick = ms[:n]
    sw = 540
    tiles = []
    for r in pick:
        fr = by_i.get(r["i"])
        if fr is None:
            continue
        band = fr[g["y0"]:g["y0"] + g["band_h"]]
        a_ok, _, w_ok = render_mask(r["text"], g, Wv, "rtl")
        exp = np.full_like(band, 70)
        ol = g["outline"]
        exp[a_ok] = (ol[2], ol[1], ol[0])
        exp[w_ok] = (255, 255, 255)
        pair = np.vstack([band, exp])
        s = sw / float(pair.shape[1])
        pair = cv2.resize(pair, (sw, max(1, int(pair.shape[0] * s))))
        lab = f"t={r['t']}s f={r['f_ok']} rev={r['f_rev']} {','.join(r['flags']) or 'ok'}"
        hdr = np.full((22, sw, 3), 20, np.uint8)
        cv2.putText(hdr, lab, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (80, 80, 255) if r["flags"] else (80, 220, 80), 1)
        tiles.append(np.vstack([hdr, pair]))
    if not tiles:
        return None
    out = W_dir / "caption_vision_sheet.jpg"
    cv2.imwrite(str(out), np.vstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out


# ═══════════════════════════════════════════════════════════════════════
# --calibrate — חיובי אמיתי (FINAL מאושר) מול שליליים מוזרקים על רקע אמיתי
# ═══════════════════════════════════════════════════════════════════════
def _composite(bg_band, text, g, W, direction="rtl", font=None, dx=0):
    img = Image.new("RGBA", (W, g["band_h"]), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if direction == "reversed":
        text, direction = text[::-1], "rtl"
    kw = {"direction": direction} if co.RAQM else {}
    d.text((W // 2 + dx, g["baseline"]), text, font=font or g["font"],
           fill=(255, 255, 255, 255), anchor="ms", stroke_width=g["stroke"],
           stroke_fill=tuple(g["outline"]), **kw)
    ov = np.asarray(img).astype(np.float32)
    al = ov[..., 3:4] / 255.0
    rgb = ov[..., :3][..., ::-1]
    out = (bg_band.astype(np.float32) * (1 - al) + rgb * al).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])  # ≈ קידוד המסירה
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)


def calibrate(workdirs, per_video=40, alt_font=None):
    base = dict(DEFAULTS)
    pos, neg = {"f_ok": [], "margin": [], "ink_in": [], "ink_out": []}, {}
    syn_ok = []
    used = []
    alt_font = alt_font or str(HERE / "thumbnail" / "fonts" / "PloniBold.otf")
    for spec in workdirs:
        # "DIR" או "DIR::words.json" — כשה-FINAL נצרב מקובץ מילים אחר מ-words_final.json
        # (נמדד: טיפ-אחד-HSPU נצרב מ-words_final3.json; מול words_final.json חציון 0.61)
        wd, _, wfile = str(spec).partition("::")
        wd = Path(wd)
        video, words, brand, intro = project_inputs(wd, words=(wd / wfile) if wfile else None)
        clean = wd / "EXPORT.mp4"
        if not video.exists() or not words.exists():
            continue
        doc = analyze(wd, words=words, cfg=base, max_cues=per_video, sheet=False, write=False)
        for r in doc["cues"]:
            if "f_ok" not in r:
                continue
            pos["f_ok"].append(r["f_ok"]); pos["ink_in"].append(r["ink_in"])
            pos.setdefault("f_ok1", []).append(r["f_ok1"])
            pos["ink_out"].append(r["ink_out"])
            if not r["symmetric"]:
                pos["margin"].append(r["f_rev"] - r["f_ok"])
        used.append(wd.name)
        if not clean.exists():
            continue
        # שליליים: אותם cues, על רקע נקי מאותו סרטון (EXPORT לפני כתוביות)
        cues = group_cues(load_words(str(words)))
        cap = cv2.VideoCapture(str(clean))
        Ws = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); Hs = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if not Ws or abs(Ws / float(Hs) - 1080 / 1920.0) > 0.02:
            continue                                   # רק מקור אנכי 9:16
        Wv, Hv = 1080, 1920                            # הרקע מוקטן לממדי המסירה
        g = geometry(cues, Wv, Hv, brand)
        want = "personal" if co.BRAND_ALIASES.get(brand, brand) == "personal" else "club"
        idx = [i for i, c in enumerate(cues) if c["end"] - c["start"] >= 0.07][:per_video]
        frames, _ = sample_frames(clean, [(cues[i]["start"] + cues[i]["end"]) / 2 for i in idx])
        altf = ImageFont.truetype(alt_font, g["font"].size) if os.path.exists(alt_font) else None
        outlines = {"club": co.BRAND_PROFILES["club"]["outline"][:3],
                    "personal": co.BRAND_PROFILES["personal"]["outline"][:3]}
        for k, (i, fr) in enumerate(zip(idx, frames)):
            if fr is None:
                continue
            if fr.shape[1] != Wv:
                fr = cv2.resize(fr, (Wv, Hv), interpolation=cv2.INTER_AREA)
            bg = fr[g["y0"]:g["y0"] + g["band_h"]]
            text = cues[i]["text"]
            other = cues[idx[(k + 7) % len(idx)]]["text"]
            letters = text.replace(" ", "")
            scr = (text[1:] + text[0]) if len(letters) >= 3 else None     # שבירת shaping
            variants = {
                "synthetic_ok": _composite(bg, text, g, Wv),
                "reversed": _composite(bg, text, g, Wv, "reversed"),
                "tofu": _composite(bg, "\u25a1" * max(1, len(letters)), g, Wv),
                "scrambled": _composite(bg, scr, g, Wv) if scr and scr != text else None,
                "wrong_word": _composite(bg, other, g, Wv) if other != text else None,
                "wrong_font": _composite(bg, text, g, Wv, font=altf) if altf else None,
                "missing": cv2.imdecode(cv2.imencode(".jpg", bg)[1], cv2.IMREAD_COLOR),
                "doubled": _composite(_composite(bg, text, g, Wv), other, g, Wv, dx=-260),
            }
            for name, band in variants.items():
                if band is None:
                    continue
                m = score_cue(band, text, g, Wv, want, ink_mask(band, outlines), base)
                if name == "synthetic_ok":
                    syn_ok.append(m["f_ok"])
                    continue
                if name == "reversed" and m["symmetric"]:
                    continue
                neg.setdefault(name, []).append(m)

    def q(v, p):
        if not v:
            return None
        v = sorted(v)
        return round(v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))], 3)

    # הספים: באמצע הפער בין הזנב של החיוביים לזנב של השליליים.
    pos_f_p01 = q(pos["f_ok"], 0.01)
    neg_garb = [m["f_ok"] for n in ("tofu",) for m in neg.get(n, [])
                if m["ink_in"] >= base["missing_ink_ratio"]]
    neg_rev_margin = [m["f_rev"] - m["f_ok"] for m in neg.get("reversed", [])]
    pos_f_min = min(pos["f_ok"]) if pos["f_ok"] else None
    garb_p95 = q(neg_garb, 0.95)
    f_ok_min = (round((pos_f_min + garb_p95) / 2, 3)
                if pos_f_min is not None and garb_p95 is not None and pos_f_min > garb_p95
                else base["f_ok_min"])
    pos_f1_min = min(pos["f_ok1"]) if pos.get("f_ok1") else None
    garb1 = [q([m["f_ok1"] for m in neg.get(n, []) if m["ink_in"] >= base["missing_ink_ratio"]], 0.95)
             for n in ("tofu", "scrambled", "wrong_word")]
    garb1 = [g for g in garb1 if g is not None]
    f1_min = (round((pos_f1_min + max(garb1)) / 2, 3)
              if pos_f1_min is not None and garb1 and pos_f1_min > max(garb1)
              else base["f1_min"])
    pos_margin_max = max(pos["margin"]) if pos["margin"] else None
    neg_margin_p05 = q(neg_rev_margin, 0.05)
    rev_margin = (round((pos_margin_max + neg_margin_p05) / 2, 3)
                  if pos_margin_max is not None and neg_margin_p05 is not None
                  and neg_margin_p05 > pos_margin_max else base["rev_margin"])
    pos_ink_min = min(pos["ink_in"]) if pos["ink_in"] else None
    miss_ink_p95 = q([m["ink_in"] for m in neg.get("missing", [])], 0.95)
    missing_ratio = (round((pos_ink_min + miss_ink_p95) / 2, 3)
                     if pos_ink_min is not None and miss_ink_p95 is not None
                     and pos_ink_min > miss_ink_p95 else base["missing_ink_ratio"])
    pos_out_max = max(pos["ink_out"]) if pos["ink_out"] else None
    dbl_p05 = q([m["ink_out"] for m in neg.get("doubled", [])], 0.05)
    extra_ratio = (round((pos_out_max + dbl_p05) / 2, 3)
                   if pos_out_max is not None and dbl_p05 is not None and dbl_p05 > pos_out_max
                   else base["extra_ink_ratio"])
    params = {"f_ok_min": f_ok_min, "f1_min": f1_min, "rev_margin": rev_margin,
              "missing_ink_ratio": missing_ratio, "extra_ink_ratio": extra_ratio,
              "sym_iou": base["sym_iou"], "source": "measured"}

    # שיעורי שגיאה בספים שנבחרו — ההצדקה (או אי-ההצדקה) לחסום
    def rate(vals, pred):
        return round(sum(1 for v in vals if pred(v)) / len(vals), 4) if vals else None
    ev = {
        "videos": used, "n_pos": len(pos["f_ok"]), "synthetic_ok_median": q(syn_ok, 0.5),
        "pos_f_ok": {"p01": pos_f_p01, "p50": q(pos["f_ok"], 0.5), "min": q(pos["f_ok"], 0)},
        "neg_tofu_f_ok_p95": garb_p95,
        "pos_rev_margin_max": round(pos_margin_max, 3) if pos_margin_max is not None else None,
        "neg_rev_margin_p05": neg_margin_p05,
        "pos_ink_in_min": round(pos_ink_min, 3) if pos_ink_min is not None else None,
        "neg_missing_ink_p95": miss_ink_p95,
        "pos_ink_out_max": round(pos_out_max, 3) if pos_out_max is not None else None,
        "neg_doubled_ink_out_p05": dbl_p05,
        "pos_false_garbled": rate(pos["f_ok1"], lambda v: v < f1_min),
        "pos_f1_min": pos_f1_min, "neg_garbled_f1_p95_max": max(garb1) if garb1 else None,
        "pos_false_reversed": rate(pos["margin"], lambda v: v > rev_margin),
        "pos_false_missing": rate(pos["ink_in"], lambda v: v < missing_ratio),
        "pos_false_extra": rate(pos["ink_out"], lambda v: v > extra_ratio),
        "neg": {},
    }
    ev["pos_f_ok1"] = {"min": q(pos.get("f_ok1", []), 0), "p01": q(pos.get("f_ok1", []), 0.01)}
    ev["neg_quantiles"] = {n: {"f_ok_p50": q([m["f_ok"] for m in ms], 0.5),
                               "f_ok_p95": q([m["f_ok"] for m in ms], 0.95),
                               "f_ok1_p50": q([m["f_ok1"] for m in ms], 0.5),
                               "f_ok1_p95": q([m["f_ok1"] for m in ms], 0.95)}
                           for n, ms in neg.items()}
    for name, ms in neg.items():
        if name == "reversed":
            caught = rate(ms, lambda m: m["f_rev"] - m["f_ok"] > rev_margin
                          and m["ink_in"] >= missing_ratio)
        elif name == "missing":
            caught = rate(ms, lambda m: m["ink_in"] < missing_ratio)
        elif name == "doubled":
            caught = rate(ms, lambda m: m["ink_out"] > extra_ratio or m["f_ok"] < f_ok_min)
        else:
            caught = rate(ms, lambda m: m["f_ok1"] < f1_min or m["ink_in"] < missing_ratio
                          or (m["f_rev"] - m["f_ok"] > rev_margin))
        ev["neg"][name] = {"n": len(ms), "caught": caught}
    # קידום לחוסם: חיובי-שגוי 0 על המאושרים וגם תפיסה ≥95% בהזרקה
    blocking = []
    for flag, fp, negnames in (("reversed", ev["pos_false_reversed"], ("reversed",)),
                               ("missing", ev["pos_false_missing"], ("missing",)),
                               ("garbled", ev["pos_false_garbled"], ("tofu", "scrambled"))):
        cs = [(ev["neg"].get(n) or {}).get("caught") for n in negnames]
        if fp == 0 and cs and all(c is not None and c >= 0.95 for c in cs):
            blocking.append(flag)
    # tofu (תו בלי גליף ב-cmap) — דטרמיניסטי מקובץ הפונט, אפס חיובי-שגוי מהגדרה,
    # ותמיד שגוי על המסך. חוסם בלי תלות בכיול הפיקסלים.
    blocking.append("tofu")
    # garbled: 0/1,225 חיובי-שגוי על המאושרים, אבל 5 חיוביים-שגויים בסרטון אירוע
    # אחד בסריקה החיה (22.9.26, נבדק בעין) ⇒ מדווח. ההפרדה בכיול לא מחזיקה
    # מחוץ להתפלגות של המאושרים.
    # garbled חוסם רק כתקלה **שיטתית** (≥25% מה-cues): בסריקה החיה (40 FINAL, 22.9.26)
    # החיובי-השגוי המקסימלי היה 5/94 (5.3%, רקע אירוע עמוס — נבדק בעין), ותקלה אמיתית
    # (קניות-v2, פונט כתוביות ישן) סימנה 59/120 (49%). cue בודד = HIGH ב-P20, לא חסימה.
    # garbled_cue (v9.34, גל 6): הסף נגזר מסריקה על **כל** ה-cues של ה-FINAL החיים
    # (_opus55_wave6/w6_v7_analyze3.py), לא מ-16 המאושרים בלבד — ולכן --calibrate
    # שומר אותו מהקובץ הקיים ולא ממציא אותו מחדש.
    try:
        _prev_doc = json.loads(CALIB.read_text(encoding="utf-8"))
        prev, prev_ev = _prev_doc.get("params", {}), _prev_doc.get("evidence", {})
    except Exception:
        prev, prev_ev = {}, {}
    if prev.get("g1_max") is not None:
        params["g1_max"] = prev["g1_max"]
        for k in ("pos_false_garbled_cue", "garbled_cue_w6"):
            if k in prev_ev:
                ev[k] = prev_ev[k]
        if "garbled_cue" in (prev.get("blocking") or []):
            blocking.append("garbled_cue")
    params["blocking"] = blocking
    params["min_hits"] = {"reversed": 3, "missing": 2, "garbled": 3, "garbled_cue": 3}
    params["min_frac"] = {"reversed": 0.2, "garbled": 0.25}
    params["blocking_rule"] = "חיובי-שגוי 0 על המאושרים ותפיסה ≥95% בהזרקת כשל"
    doc = {"params": params, "evidence": ev,
           "_readme": "ספי caption_vision — נמדדו על FINAL מאושרים (חיוביים) מול "
                      "הזרקת כשל על רקע EXPORT אמיתי מאותם סרטונים (שליליים). "
                      "רק דגל ב-blocking חוסם."}
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir")
    ap.add_argument("--video")
    ap.add_argument("--words")
    ap.add_argument("--brand")
    ap.add_argument("--max-cues", type=int, default=0)
    ap.add_argument("--intro-offset", type=float, default=None,
                    help="היסט פתיח קבוע (שניות). בלי — מ-FINAL_PROVENANCE או נאמד מהפיקסלים")
    ap.add_argument("--strict", action="store_true", help="exit 1 על דגל חוסם")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--calibrate", nargs="+", metavar="WORKDIR")
    ap.add_argument("--per-video", type=int, default=40)
    ap.add_argument("--write-calibration", action="store_true")
    a = ap.parse_args()
    if a.calibrate:
        doc = calibrate(a.calibrate, per_video=a.per_video)
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        if a.write_calibration:
            CALIB.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"✅ נכתב {CALIB.name}")
        return 0
    if not a.workdir:
        ap.error("צריך --workdir או --calibrate")
    doc = analyze(a.workdir, a.video, a.words, a.brand, a.max_cues,
                  intro_offset=a.intro_offset)
    if a.json:
        print(json.dumps({k: v for k, v in doc.items() if k != "cues"}, ensure_ascii=False, indent=1))
    else:
        if doc.get("measured") is False:
            print(f"— V7 כתוביות: לא נמדד ({doc.get('why')})")
            return 0
        icon = "✅" if doc["ok"] else "🔴"
        c = doc["counts"]
        print(f"{icon} V7 כתוביות: {doc['n_measured']}/{doc['n_cues']} cues נמדדו על הפיקסלים · "
              f"f_ok חציון {doc['f_ok_median']} · "
              + (" · ".join(f"{k} {v}" for k, v in sorted(c.items())) or "אפס ממצאים")
              + f" · ספים: {doc['threshold_source']}")
        if doc.get("sheet"):
            print(f"   גיליון: {doc['sheet']}")
        for r in [r for r in doc["cues"] if r["flags"]][:8]:
            print(f"   ⚠️ t={r['t']}ש '{r['text']}' {','.join(r['flags'])} "
                  f"(f={r.get('f_ok')} rev={r.get('f_rev')})")
    return (0 if doc.get("ok") in (True, None) else 1) if a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
