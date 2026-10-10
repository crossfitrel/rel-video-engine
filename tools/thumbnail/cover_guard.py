#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cover_guard.py — שני הדברים שאי אפשר לסמוך עליהם בקאבר, נמדדים (v9.12, 2.8.26)
===============================================================================

שורש התקלה החוזרת ("למה אתה כל הזמן נופל בקאברים?"):
כל בוני-הקאבר קיבלו `--frame <כל PNG>` והאמינו למי שקרא להם. הכלל "קאבר תמיד
מ-EXPORT נקי" היה **נוהל**, לא שער. נוהל אפשר לשכוח; שער לא. ב-2.8.26 הקאבר
של "מה-זה-להיות-בעל-מועדון" יצא עם הכתובית הצרובה "אז מה" מבצבצת מתחת לקופסה
הכחולה — כי הקופסה היא 70% שקיפות ולעולם לא תסתיר טקסט צרוב שמתחתיה.

לכן שתי מדידות, שתיהן על הפיקסלים ולא על הכוונה:

1. `caption_signal(bgr)` — האם בפריים הזה יש **כתובית צרובה**.
   הכתובית שלנו היא גליף לבן עם מתאר צבעוני בערך ב-y=0.70-0.80. הסיגנל שמפריד
   אותה מקיר לבן/חולצה בהירה הוא לא הבהירות אלא **צפיפות הקצוות בתוך הלבן**:
   לגליף יש היקף עצום ביחס לשטח, לקיר אין. הסף לא נוחש — הוא נמדד על זוגות
   EXPORT (נקי) מול FINAL (צרוב) מהפרויקטים עצמם (`--calibrate`).

2. `frame_quality(bgr)` — האם הפריים **ראוי לקאבר**.
   ‏frame_select הישן ניקד גודל-פנים + חדות + בהירות בלבד, ולכן בחר בשמחה פריים
   עם עיניים חצי-עצומות ופה פתוח באמצע הברה. כאן נמדדים שלושה דברים נוספים:
   עיניים פקוחות (Haar בתוך ROI של החצי העליון של הפנים), מבט/ראש למטה
   (מיקום קו-העיניים בתוך הפנים), ופה פתוח (שונות אנכית בשליש התחתון).

עיקרון: **מדווח כשאי אפשר לתקן, חוסם כשהעלות אפס.**
כתובית צרובה בקאבר = פסול תמיד, בלי יתרון מקזז ⇒ נכשל-סגור.
איכות פריים = דירוג, לא פסילה ⇒ מנקד ובוחר את הטוב, ומדווח מה נבחר.
"""
from __future__ import annotations
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CALIB_PATH = os.path.join(HERE, "cover-guard-calibration.json")

# ברירות מחדל שמרניות — נדרסות ע"י קובץ הכיול אם קיים (וזה המצב הרצוי).
DEFAULTS = {
    "band_top": 0.60,          # תחום הסריקה לכתובית (יחס מגובה הפריים)
    "band_bot": 0.92,
    "win_rows": 40,            # חלון גלישה: גובה מינימלי של רצועת גליפים
    "bright_v": 200,           # ערך V מינימלי ל"לבן של גליף"
    "bright_s": 50,            # רוויה מקסימלית
    "stroke_dilate": 4,        # מרחק מקסימלי לבן↔מתאר (פיקסלים)
    "stroke_tol": 46,          # סבילות צבע למתאר המותג (מרחק BGR)
    # שני צבעי המתאר היחידים שהמערכת צורבת: מועדון #871d1f, אישי #0077B6.
    "stroke_colors_bgr": [[31, 29, 135], [182, 119, 0]],
    "threshold": 0.020,        # סף ההכרעה — **נמדד**, ראה --calibrate
    "threshold_source": "default_unmeasured",
}


def load_calibration():
    cfg = dict(DEFAULTS)
    try:
        with open(CALIB_PATH, encoding="utf-8") as fh:
            cfg.update(json.load(fh).get("params", {}))
    except Exception:
        pass
    return cfg


# ═══════════════════════════════════════════════════════════════════════
# 1. גלאי כתובית צרובה
# ═══════════════════════════════════════════════════════════════════════
def caption_signal(bgr, cfg=None):
    """מחזיר {'score', 'peak_row', 'pass'} — score גבוה = כתובית צרובה.

    ניסיון ראשון (2.8.26) היה "לבן ∩ ליד-קצה". הוא **נמדד ונפסל**: על 19 זוגות
    ‏EXPORT/FINAL אמיתיים הוא נתן 23% חסימות-שווא — כי רחבת אימון מלאה בציוד
    בהיר מייצרת בדיוק את אותו סיגנל. זו הסיבה שהוא לא בקוד.

    מה שכן מפריד: הכתובית שלנו היא **גליף לבן עטוף במתאר בצבע המותג** — ‎#871d1f
    למועדון, ‎#0077B6 לאישי. הצירוף "פיקסל לבן במרחק ≤4px מפיקסל בגוון המותג"
    כמעט לא קיים בצילום טבעי, וקיים בשפע בכל כתובית צרובה. זה הסיגנל שנמדד.
    """
    cfg = cfg or load_calibration()
    h, w = bgr.shape[:2]
    y0, y1 = int(h * cfg["band_top"]), int(h * cfg["band_bot"])
    roi = bgr[y0:y1]
    if roi.size == 0:
        return {"score": 0.0, "peak_row": None, "pass": True}

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    bright = (hsv[..., 2] >= cfg["bright_v"]) & (hsv[..., 1] <= cfg["bright_s"])

    f = roi.astype(np.int16)
    stroke = np.zeros(bright.shape, bool)
    for c in cfg["stroke_colors_bgr"]:
        d = np.abs(f - np.array(c, np.int16)).sum(axis=2)
        stroke |= d <= int(cfg["stroke_tol"]) * 3
    k = int(cfg["stroke_dilate"]) * 2 + 1
    near_stroke = cv2.dilate(stroke.astype(np.uint8), np.ones((k, k), np.uint8)) > 0

    glyph = bright & near_stroke
    per_row = glyph.sum(axis=1) / float(w)

    win = int(cfg["win_rows"])
    if len(per_row) < win:
        return {"score": float(per_row.mean()), "peak_row": None, "pass": True}
    kern = np.ones(win) / win
    smooth = np.convolve(per_row, kern, mode="valid")
    i = int(np.argmax(smooth))
    score = float(smooth[i])
    return {
        "score": round(score, 5),
        "peak_row": int(y0 + i + win // 2),
        "peak_row_ratio": round((y0 + i + win // 2) / float(h), 4),
        "threshold": cfg["threshold"],
        "threshold_source": cfg.get("threshold_source"),
        "pass": score < cfg["threshold"],
    }


def assert_clean_frame(path, cfg=None):
    """נכשל-סגור: פריים עם כתובית צרובה לא יהפוך לקאבר. מחזיר את הדוח."""
    bgr = cv2.imread(path)
    if bgr is None:
        raise SystemExit(f"❌ cover_guard: לא ניתן לקרוא פריים: {path}")
    rep = caption_signal(bgr, cfg)
    if not rep["pass"]:
        raise SystemExit(
            "❌ שער G-COVER1: הפריים מכיל כתובית צרובה "
            f"(score={rep['score']} ≥ סף {rep['threshold']}, "
            f"שורה ~{rep.get('peak_row_ratio')} מהגובה).\n"
            "   קאבר נבנה **רק** מ-EXPORT.mp4 הנקי — הקופסה היא 70% שקיפות\n"
            "   ולעולם לא תסתיר טקסט צרוב שמתחתיה.\n"
            f"   מקור הפריים: {path}")
    return rep


# ═══════════════════════════════════════════════════════════════════════
# 2. איכות פריים — מה ש-frame_select לא ראה
# ═══════════════════════════════════════════════════════════════════════
_CASCADES = {}


def _cascade(name):
    if name not in _CASCADES:
        _CASCADES[name] = cv2.CascadeClassifier(cv2.data.haarcascades + name)
    return _CASCADES[name]


def frame_quality(bgr):
    """מדדי ראוּיוּת לקאבר. מחזיר dict עם ציון 0-1 והנימוקים שמאחוריו."""
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = _cascade("haarcascade_frontalface_default.xml").detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=6,
        minSize=(int(w * 0.10), int(w * 0.10)))
    out = {"faces": len(faces), "eyes": 0, "eyes_open": None,
           "gaze_down": None, "mouth_open": None,
           "sharp": float(cv2.Laplacian(gray, cv2.CV_64F).var())}
    if len(faces) == 0:
        out["score"] = 0.0
        out["why"] = "אין פנים בפריים"
        return out

    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    out["face"] = [int(fx), int(fy), int(fw), int(fh)]
    face_gray = gray[fy:fy + fh, fx:fx + fw]

    # עיניים — Haar בחצי העליון של הפנים. שתי עיניים = פקוחות.
    upper = face_gray[: int(fh * 0.60)]
    eyes = _cascade("haarcascade_eye.xml").detectMultiScale(
        upper, scaleFactor=1.05, minNeighbors=5,
        minSize=(int(fw * 0.12), int(fh * 0.08)))
    out["eyes"] = len(eyes)
    out["eyes_open"] = len(eyes) >= 2

    # מבט/ראש למטה — קו העיניים יורד בתוך תיבת הפנים כשהראש מורכן.
    if len(eyes) > 0:
        eye_cy = float(np.mean([e[1] + e[3] / 2.0 for e in eyes])) / fh
        out["eye_line"] = round(eye_cy, 3)
        out["gaze_down"] = eye_cy > 0.42       # מרכז-עין תקין ~0.30-0.40
    # פה פתוח — שונות אנכית גבוהה בשליש התחתון של הפנים.
    lower = face_gray[int(fh * 0.62):, int(fw * 0.20):int(fw * 0.80)]
    if lower.size:
        col_var = float(np.mean(np.var(lower.astype(np.float32), axis=0)))
        out["mouth_var"] = round(col_var, 1)
        out["mouth_open"] = col_var > 900.0

    face_area = (fw * fh) / float(w * h)
    score = min(face_area * 100.0, 1.0) * 0.35
    score += min(out["sharp"] / 400.0, 1.0) * 0.15
    if out["eyes_open"]:
        score += 0.30
    if out["gaze_down"] is False:
        score += 0.10
    if out["mouth_open"] is False:
        score += 0.10
    out["score"] = round(score, 4)
    reasons = []
    if not out["eyes_open"]:
        reasons.append("עיניים לא מזוהות כפקוחות")
    if out["gaze_down"]:
        reasons.append("מבט/ראש למטה")
    if out["mouth_open"]:
        reasons.append("פה פתוח באמצע דיבור")
    out["why"] = " · ".join(reasons) if reasons else "פריים נקי — עיניים פקוחות, מבט קדימה"
    return out


# ═══════════════════════════════════════════════════════════════════════
# כיול — הסף נמדד על זוגות EXPORT/FINAL אמיתיים, לא נוחש
# ═══════════════════════════════════════════════════════════════════════
def _sample(video, n=14):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = total / fps if fps else 0
    out = []
    for i in range(n):
        t = dur * (0.10 + 0.80 * i / max(1, n - 1))
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, fr = cap.read()
        if ok:
            out.append(fr)
    cap.release()
    return out


def calibrate(work_root, out_path=CALIB_PATH):
    cfg = dict(DEFAULTS)
    clean, capped = [], []
    pairs = 0
    for name in sorted(os.listdir(work_root)):
        d = os.path.join(work_root, name)
        exp, fin = os.path.join(d, "EXPORT.mp4"), os.path.join(d, "FINAL.mp4")
        if not (os.path.isfile(exp) and os.path.isfile(fin)):
            continue
        pairs += 1
        clean += [caption_signal(f, cfg)["score"] for f in _sample(exp)]
        capped += [caption_signal(f, cfg)["score"] for f in _sample(fin)]
    if not clean or not capped:
        raise SystemExit("❌ אין זוגות EXPORT/FINAL לכיול")
    clean, capped = np.array(clean), np.array(capped)
    # סף = אמצע הפער בין האחוזון ה-98 של הנקיים לאחוזון ה-5 של הצרובים.
    hi_clean = float(np.percentile(clean, 98))
    lo_capped = float(np.percentile(capped, 5))
    thr = (hi_clean + lo_capped) / 2.0 if lo_capped > hi_clean else lo_capped * 0.9
    cfg["threshold"] = round(thr, 5)
    cfg["threshold_source"] = "measured"
    rep = {
        "params": cfg,
        "evidence": {
            "projects_with_pairs": pairs,
            "clean_frames": int(clean.size), "captioned_frames": int(capped.size),
            "clean_p50": round(float(np.percentile(clean, 50)), 5),
            "clean_p98": round(hi_clean, 5),
            "captioned_p05": round(lo_capped, 5),
            "captioned_p50": round(float(np.percentile(capped, 50)), 5),
            "separation": lo_capped > hi_clean,
            "false_block_rate": round(float((clean >= thr).mean()), 4),
            "miss_rate": round(float((capped < thr).mean()), 4),
        },
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return rep


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", help="בדיקת פריים בודד (PNG/JPG)")
    ap.add_argument("--quality", help="מדדי איכות לפריים בודד")
    ap.add_argument("--calibrate", metavar="WORK_ROOT", help="כיול הסף על זוגות EXPORT/FINAL")
    a = ap.parse_args()
    if a.calibrate:
        calibrate(a.calibrate)
    elif a.check:
        img = cv2.imread(a.check)
        print(json.dumps(caption_signal(img), ensure_ascii=False, indent=1))
    elif a.quality:
        img = cv2.imread(a.quality)
        print(json.dumps(frame_quality(img), ensure_ascii=False, indent=1))
    else:
        ap.print_help()
        sys.exit(2)
