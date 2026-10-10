#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cover_vision.py — שער ראייה על הקאבר **המרונדר** (v9.29, 22.9.26)
=================================================================

למה זה נולד
-----------
שערי G-COVER1..4 בודקים את מה שנכנס לבונה (פריים נקי, subtitle לא ריק, שם
הפונט) — לא את ה-PNG שיצא. ולכן כל תקלת קאבר שהראל דיווח עליה הייתה תקלה
שהבונה "לא התכוון" אליה: Studentit שמוציא תת-כותרת הפוכה/מקוטעת גם עם raqm
(feedback_studentit_garbles_hebrew_despite_raqm), Dana Yad שמצייר גליפים לא
קריאים, תת-כותרת גדולה מהכותרת (126px מול 80px, 23.7.26), כתובית צרובה
שמבצבצת מתחת לקופסה (2.8.26), ושלושה בונים שונים עם ברירות מחדל שונות.
הכוונה עברה; ה-PNG היה פגום.

מה נמדד — על הפיקסלים, בלי להאמין לבונה
-----------------------------------------
  CV1 box        קופסת מותג ברוחב מלא נמצאה, וצבעה = המותג (#871d1f / #0077B6)
  CV2 two_lines  בדיוק שתי שורות טקסט בתוך הקופסה (G-COVER2, נמדד ולא מוצהר)
  CV3 title_big  הכותרת גדולה מהתת-כותרת — בגובה הדיו בפועל (כלל של אוריה)
  CV4 no_leak    אין כתובית צרובה (לבן צמוד מתאר-מותג) מחוץ לקופסה
  CV5 order      לכל שורה: הדיו תואם פריסה ידנית תו-אחר-תו מימין לשמאל בפונט
                 המותג **יותר** מאשר את הפריסה ההפוכה, ובציון מעל הסף.
                 הפריסה הידנית לא עוברת דרך raqm/shaping — ולכן היא ייחוס
                 עצמאי לשבירת shaping (Studentit) או היפוך כפול. לא מעגלי.
  CV6 tofu       כל תו בכותרת/תת-כותרת קיים ב-cmap של הפונט שמצייר אותו

מה חוסם — רק מה שנמדד נקי (עקרון 1)
------------------------------------
הספים ב-cover-vision-calibration.json, נגזרים ב---calibrate על הקאברים
שנבנו ב-cover_make (36, ‏2.8-22.9.26) + הזרקת כשל (שורה הפוכה, שורה
מעורבבת, שורה אחת, תת-כותרת גדולה, כתובית צרובה מתחת לקופסה). חוסם רק
דגל עם חיובי-שגוי 0 ותפיסה ≥95%. השאר מדווח. בלי קובץ כיול — הכל מדווח.

שימוש
-----
  python3 cover_vision.py --png thumbnail.png --title "..." --subtitle "..." --brand rel
  python3 cover_vision.py --workdir W        # thumbnail.png + cover_report.json
  python3 cover_vision.py --calibrate W1 W2 ... [--write-calibration]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import thumbnail_build as tb                           # noqa: E402  פונטים/כיסוי בלבד
import cover_guard                                     # noqa: E402

CALIB = HERE / "cover-vision-calibration.json"
BRANDS = {"rel": (135, 29, 31), "personal": (0, 119, 182)}
ALPHA = 0.70
TOL = 3

DEFAULTS = {
    "box_row_frac": 0.85,     # שורה = קופסה כשרוב הפיקסלים הלא-לבנים עקביים עם בלנד 70%
    "white_min": 225,         # דיו טקסט לבן
    "line_gap": 4,            # שורות ריקות שמפרידות בין שורות טקסט
    "order_min": 0.55,        # F מול פריסה ידנית מתחת לזה = משובש
    "order_margin": 0.08,     # F_rev - F מעל זה = הפוך
    "size_ratio_min": 1.0,    # גובה-דיו כותרת / תת-כותרת
    "leak_threshold": None,   # None = cover_guard threshold
    # v9.34 (גל 6): ייחוס ברמת מילה לכותרת (Assistant). None = לא נמדד ⇒ אין דגל.
    # מילה מעורבבת אחת בכותרת של 3-4 מילים מדוללת בשורה (תפיסה 0/33 ברמת שורה);
    # ברמת מילה: מאושרים ≥0.991 מול מעורבבים ≤0.909. בתת-כותרת (Studentit, כתב-יד)
    # נמדד ונפל — מאושרים עד 0.375 — ולכן אין ייחוס מילה לתת-כותרת.
    "title_word_min": None,
    "source": "default_unmeasured",
    "blocking": [],
}


def load_calibration():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CALIB.read_text(encoding="utf-8")).get("params", {}))
    except Exception:
        pass
    return cfg


# ═══════════════════════════════════════════════════════════════════════
def find_box(rgb, cfg):
    """שורות הקופסה: פיקסל = 0.7·מותג + 0.3·רקע ⇒ כל ערוץ בטווח [0.7b, 0.7b+76.5].
    מחזיר (top, bot, brand, frac_profile)."""
    H, W, _ = rgb.shape
    f = rgb.astype(np.float32)
    white = (f.min(axis=2) >= cfg["white_min"])
    best = None
    for name, b in BRANDS.items():
        lo = np.array(b, np.float32) * ALPHA - 3
        hi = lo + 255 * (1 - ALPHA) + 6
        ok = ((f >= lo) & (f <= hi)).all(axis=2)
        denom = np.maximum(1, (~white).sum(axis=1))
        frac = (ok & ~white).sum(axis=1) / denom
        rows = frac >= cfg["box_row_frac"]
        # סגירה חד-ממדית: שורת דיו צפופה (ראש אותיות, anti-alias) לא שוברת את
        # הקופסה לשניים. נמדד 22.9.26 על "על הלוח": בלי זה נמצאה רק חצי קופסה.
        rows = cv2.morphologyEx(rows.astype(np.uint8).reshape(-1, 1), cv2.MORPH_CLOSE,
                                np.ones((25, 1), np.uint8)).ravel() > 0
        # הרצף הארוך ביותר
        run, start, bl = 0, 0, (0, 0)
        for y, r in enumerate(rows):
            if r:
                if run == 0:
                    start = y
                run += 1
                if run > bl[1] - bl[0]:
                    bl = (start, y + 1)
            else:
                run = 0
        if best is None or (bl[1] - bl[0]) > (best[1] - best[0]):
            best = (bl[0], bl[1], name)
    return best


def text_lines(rgb, top, bot, cfg):
    """שורות טקסט לבן בתוך הקופסה — לפי היטל אופקי."""
    band = rgb[top:bot].astype(np.int16)
    white = (band.min(axis=2) >= cfg["white_min"]) & \
            ((band.max(axis=2) - band.min(axis=2)) <= 40)
    prof = white.sum(axis=1)
    on = prof >= 3
    lines, y, n = [], 0, len(on)
    while y < n:
        if on[y]:
            s = y
            gap = 0
            while y < n and (on[y] or gap < cfg["line_gap"]):
                gap = 0 if on[y] else gap + 1
                y += 1
            e = y - gap
            if e - s >= 6:
                lines.append((top + s, top + e))
        else:
            y += 1
    return lines, white


def core_height(mask):
    """גובה 'הגוף' של שורה: שורות שבהן הדיו ≥25% מהשיא (מנטרל עולים/יורדים)."""
    p = mask.sum(axis=1)
    if p.max() == 0:
        return 0
    return int((p >= 0.25 * p.max()).sum())


def _fonts_for(kind, size):
    if kind == "title":
        return [(ImageFont.truetype(tb.TITLE_FONT, size), tb.font_coverage(tb.TITLE_FONT))]
    out = [(ImageFont.truetype(tb.SUB_FONT, size), tb.font_coverage(tb.SUB_FONT))]
    for p in (tb.SUB_FONT_TIER2, tb.SUB_FONT_FALLBACK):
        if os.path.exists(p):
            out.append((ImageFont.truetype(p, size), tb.font_coverage(p)))
    return out


def manual_layout(text, kind, size=200, reverse=False):
    """פריסה ידנית תו-אחר-תו, בלי shaping: מימין לשמאל (או הפוך), כל תו
    בפונט הראשון שמכיל אותו. רצפי לטינית/ספרות נשמרים משמאל-לימין בתוכם."""
    fonts = _fonts_for(kind, size)
    # רצפים: לטינית/ספרות (LTR, כרצף) מול כל השאר — עברית, רווח ופיסוק ניטרלי
    # זורמים RTL תו-תו. (נמדד 22.9.26: כשהפסיק נספר כרצף LTR, "שירלי, באמצע
    # התחרות" קיבל פסיק בצד הלא-נכון בייחוס, והקאבר התקין סומן כמשובש.)
    runs, cur, cur_he = [], "", None
    for ch in text:
        he = not (ch.isascii() and ch.isalnum())
        if cur_he is None or he == cur_he or ch == " ":
            cur += ch
            cur_he = he if cur_he is None or ch != " " else cur_he
        else:
            runs.append((cur, cur_he)); cur, cur_he = ch, he
    if cur:
        runs.append((cur, cur_he))
    pieces = []
    for t, he in runs:
        units = list(t) if he else [t]
        for u in units:
            f = next((fo for fo, cov in fonts if cov is None or all(c in cov or c == " " for c in u)),
                     fonts[-1][0])
            pieces.append((u, f))
    widths = [max(1, int(round(f.getlength(u)))) for u, f in pieces]
    Wt = sum(widths) + 20
    img = Image.new("L", (Wt, int(size * 1.8)), 0)
    d = ImageDraw.Draw(img)
    order = list(zip(pieces, widths))
    if not reverse:
        x = Wt - 10
        for (u, f), w in order:
            x -= w
            d.text((x, int(size * 1.2)), u, font=f, fill=255, anchor="ls")
    else:
        x = 10
        for (u, f), w in order:
            d.text((x, int(size * 1.2)), u, font=f, fill=255, anchor="ls")
            x += w
    return np.asarray(img) > 127


def manual_layout_words(text, kind, size=200):
    """כמו manual_layout (RTL, בלי shaping), ומחזיר גם טווח x לכל מילה."""
    fonts = _fonts_for(kind, size)
    runs, cur, cur_he = [], "", None
    for ch in text:
        he = not (ch.isascii() and ch.isalnum())
        if cur_he is None or he == cur_he or ch == " ":
            cur += ch
            cur_he = he if cur_he is None or ch != " " else cur_he
        else:
            runs.append((cur, cur_he)); cur, cur_he = ch, he
    if cur:
        runs.append((cur, cur_he))
    pieces, wi = [], 0
    for t, he in runs:
        # רווח שנדבק לסוף רצף LTR ("17 ") הוא גבול מילה — בלי הפיצול, 'אמרת 17 דקות'
        # קיבל 2 טווחים ל-3 מילים ונשאר בלי ייחוס (נמדד על 33 הקאברים, גל 6)
        core = t.rstrip(" ")
        units = list(t) if he else ([core] if core else []) + [" "] * (len(t) - len(core))
        for u in units:
            if u == " ":
                wi += 1
            f = next((fo for fo, cov in fonts if cov is None or all(c in cov or c == " " for c in u)),
                     fonts[-1][0])
            pieces.append((u, f, wi))
    widths = [max(1, int(round(f.getlength(u)))) for u, f, _ in pieces]
    Wt = sum(widths) + 20
    img = Image.new("L", (Wt, int(size * 1.8)), 0)
    d = ImageDraw.Draw(img)
    spans, x = {}, Wt - 10
    for (u, f, w_i), w in zip(pieces, widths):
        x -= w
        d.text((x, int(size * 1.2)), u, font=f, fill=255, anchor="ls")
        if u != " ":
            a, b = spans.get(w_i, (x, x + w))
            spans[w_i] = (min(a, x), max(b, x + w))
    return np.asarray(img) > 127, [spans[k] for k in sorted(spans)]


def word_scores(obs, text, kind):
    """F לכל מילה: גבולות המילים מהפריסה הידנית, מוקרנים יחסית על bbox הדיו בפועל
    (מילה מעורבבת שומרת על רוחבה, ולכן הגבולות נשמרים). מחזיר [(מילה, F)]; מילה
    עם אות/ספרה לטינית מדולגת (רצף LTR — נמדד 0.797 על '17' תקין)."""
    ref, spans = manual_layout_words(text, kind)
    words = text.split(" ")
    ys, xs = np.where(ref)
    oy, ox = np.where(obs)
    if not len(xs) or not len(ox) or len(spans) != len(words):
        return []
    rx0, rx1, ox0, ox1 = xs.min(), xs.max() + 1, ox.min(), ox.max() + 1
    sc = (ox1 - ox0) / float(rx1 - rx0)
    out = []
    for w, (a, b) in zip(words, spans):
        a, b = max(a, rx0), min(b, rx1)
        if b - a < 4 or any(c.isascii() and c.isalnum() for c in w):
            continue
        ra, rb = int(a) - 2, int(b) + 2
        oa, ob = int(ox0 + (a - rx0) * sc) - 2, int(ox0 + (b - rx0) * sc) + 2
        r_sl = np.zeros_like(ref); r_sl[:, max(0, ra):rb] = ref[:, max(0, ra):rb]
        o_sl = np.zeros_like(obs); o_sl[:, max(0, oa):ob] = obs[:, max(0, oa):ob]
        out.append((w, round(fscore(o_sl, r_sl), 3)))
    return out


def _crop(m):
    ys, xs = np.where(m)
    if len(ys) == 0:
        return None
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _dil(m, px):
    return cv2.dilate(m.astype(np.uint8), np.ones((2 * px + 1, 2 * px + 1), np.uint8)) > 0


def fscore(obs, ref):
    """שני המסכות חתוכות ל-bbox; ref מוקטן לממדי obs. הסבולת יחסית לגובה
    השורה: Studentit הוא קו דק של כתב-יד, וסבולת קבועה של 3px ענישה אותו
    על עובי-קו ולא על צורה (נראה בעין על 4 קאברים תקינים, 22.9.26)."""
    o, r = _crop(obs), _crop(ref)
    if o is None or r is None:
        return 0.0
    r = cv2.resize(r.astype(np.uint8) * 255, (o.shape[1], o.shape[0]),
                   interpolation=cv2.INTER_AREA) > 127
    no, nr = int(o.sum()), int(r.sum())
    if not no or not nr:
        return 0.0
    tol = max(TOL, int(round(0.03 * o.shape[0])))
    p = float((o & _dil(r, tol)).sum()) / no
    q = float((r & _dil(o, tol)).sum()) / nr
    return 0.0 if p + q == 0 else 2 * p * q / (p + q)


def leak_score(bgr, top, bot):
    """cover_guard.caption_signal על הפריים כשהקופסה (±12px) מושחרת —
    כך הטקסט הלבן על הקופסה האדומה לא נספר ככתובית."""
    img = bgr.copy()
    img[max(0, top - 12):bot + 12] = 0
    return cover_guard.caption_signal(img)


def analyze(png, title=None, subtitle=None, brand=None, cfg=None):
    cfg = cfg or load_calibration()
    bgr = cv2.imread(str(png))
    if bgr is None:
        return {"ok": None, "measured": False, "why": f"לא נקרא: {png}"}
    rgb = bgr[..., ::-1]
    H, W, _ = rgb.shape
    res = {"png": str(png), "size": [W, H], "checks": {}, "flags": []}
    top, bot, found = find_box(rgb, cfg)
    ch = res["checks"]
    ch["CV1_box"] = {"top": int(top), "bot": int(bot), "brand_found": found,
                     "brand_expected": brand, "height": int(bot - top),
                     "pass": (bot - top) >= 0.05 * H and (brand is None or found == brand)}
    if (bot - top) < 0.05 * H:
        res["flags"].append("no_box")
        res["ok"] = False if "no_box" in cfg["blocking"] else None
        return res
    if brand and found != brand:
        res["flags"].append("box_brand")
    lines, white = text_lines(rgb, top, bot, cfg)
    ch["CV2_two_lines"] = {"n_lines": len(lines), "lines": lines, "pass": len(lines) == 2}
    if len(lines) != 2:
        res["flags"].append("line_count")
    if len(lines) >= 2:
        m1 = white[lines[0][0] - top:lines[0][1] - top]
        m2 = white[lines[1][0] - top:lines[1][1] - top]
        h1, h2 = core_height(m1), core_height(m2)
        core_ratio = round(h1 / float(max(1, h2)), 3)
        # גודל הגופן בפועל, נאמד מרוחב הדיו מול פריסה ידנית באותו פונט —
        # בלתי תלוי בבונה. גובה-הדיו לבדו מטעה: Studentit (כתב-יד) גבוה ודק,
        # ולכן בקאבר "גאה בצוות" יחס הגבהים יצא 0.98 כשהכותרת גדולה בעליל.
        ratio, pts = None, None
        if title and subtitle:
            def pt(txt, kind, m):
                c = _crop(m); r = _crop(manual_layout(txt, kind, size=200))
                return None if c is None or r is None else 200.0 * c.shape[1] / r.shape[1]
            p1, p2 = pt(title, "title", m1), pt(subtitle, "sub", m2)
            if p1 and p2:
                pts = [round(p1, 1), round(p2, 1)]
                ratio = round(p1 / p2, 3)
        ch["CV3_title_big"] = {"title_core_px": h1, "sub_core_px": h2,
                               "core_ratio": core_ratio, "pt_est": pts, "ratio": ratio,
                               "threshold": cfg["size_ratio_min"],
                               "pass": None if ratio is None else ratio > cfg["size_ratio_min"]}
        if ratio is not None and ratio <= cfg["size_ratio_min"]:
            res["flags"].append("title_not_bigger")
        if title and subtitle:
            ords = []
            for kind, txt, m in (("title", title, m1), ("sub", subtitle, m2)):
                f_ok = fscore(m, manual_layout(txt, kind))
                f_rev = fscore(m, manual_layout(txt, kind, reverse=True))
                ords.append({"line": kind, "f_ok": round(f_ok, 3), "f_rev": round(f_rev, 3)})
                if f_rev - f_ok > cfg["order_margin"]:
                    res["flags"].append(f"reversed_{kind}")
                elif f_ok < cfg["order_min"]:
                    res["flags"].append(f"garbled_{kind}")
            ch["CV5_order"] = {"lines": ords, "min": cfg["order_min"],
                               "margin": cfg["order_margin"]}
            # v9.34: ייחוס ברמת מילה — כותרת בלבד (בתת-כותרת Studentit נמדד ונפל)
            ws = word_scores(m1, title, "title")
            wmin = min((s for _, s in ws), default=None)
            ch["CV5_order"]["title_words"] = ws
            ch["CV5_order"]["title_word_min"] = cfg.get("title_word_min")
            if (cfg.get("title_word_min") is not None and wmin is not None
                    and wmin < cfg["title_word_min"]
                    and not any(f.startswith("reversed_title") for f in res["flags"])):
                res["flags"].append("garbled_word_title")
    lk = leak_score(bgr, top, bot)
    thr = cfg["leak_threshold"] if cfg.get("leak_threshold") is not None else lk.get("threshold")
    ch["CV4_no_leak"] = {"score": lk["score"], "threshold": thr,
                         "row_ratio": lk.get("peak_row_ratio"), "pass": lk["score"] < thr}
    if lk["score"] >= thr:
        res["flags"].append("caption_leak")
    tofu = {}
    if title:
        cov = tb.font_coverage(tb.TITLE_FONT)
        miss = sorted({c for c in title if cov is not None and c not in cov and not c.isspace()})
        if miss:
            tofu["title"] = miss
    if subtitle:
        covs = [tb.font_coverage(p) for p in (tb.SUB_FONT, tb.SUB_FONT_TIER2, tb.SUB_FONT_FALLBACK)
                if os.path.exists(p)]
        miss = sorted({c for c in subtitle if not c.isspace()
                       and all(cv is not None and c not in cv for cv in covs)})
        if miss:
            tofu["subtitle"] = miss
    ch["CV6_tofu"] = {"missing": tofu, "pass": not tofu}
    if tofu:
        res["flags"].append("tofu")
    block = [f for f in res["flags"]
             if f in cfg["blocking"] or f.rsplit("_", 1)[0] in cfg["blocking"]]
    res.update({"blocking_flags": cfg["blocking"], "blocking_hits": block,
                "threshold_source": cfg["source"], "measured": True,
                "ok": not block})
    return res


def from_workdir(W, cfg=None):
    W = Path(W)
    rep = {}
    try:
        rep = json.loads((W / "cover_report.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    png = Path(rep.get("out") or W / "thumbnail.png")
    if not png.exists():
        png = W / "thumbnail.png"
    b = rep.get("brand")
    return analyze(png, rep.get("title"), rep.get("subtitle"), b, cfg)


# ═══════════════════════════════════════════════════════════════════════
# --calibrate: קאברים אמיתיים (חיוביים) מול הזרקת כשל שנבנית בבונה עצמו
# ═══════════════════════════════════════════════════════════════════════
def _inject(W, kind, tmp):
    """בונה קאבר פגום מאותו פריים ואותו טקסט, דרך הבונה הקנוני — כך השליליים
    נראים בדיוק כמו תקלה אמיתית ולא כמו ציור סינתטי."""
    rep = json.loads((Path(W) / "cover_report.json").read_text(encoding="utf-8"))
    frame, t, s, b = rep.get("frame"), rep["title"], rep["subtitle"], rep.get("brand", "rel")
    if not frame or not os.path.exists(frame):
        return None
    box = BRANDS.get(b)
    out = os.path.join(tmp, f"{kind}.png")
    import contextlib, io
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            if kind == "reversed":
                tb.build(frame, t[::-1], s[::-1], out, box_color=box)
                return out, t, s, b
            if kind == "scrambled":
                sc = lambda x: " ".join(w[1:] + w[0] if len(w) > 2 else w for w in x.split(" "))
                tb.build(frame, sc(t), sc(s), out, box_color=box)
                return out, t, s, b
            if kind == "scr_word_title":
                # v9.34: מילה אחת בלבד בכותרת (הראשונה עם 3+ אותיות) — הכשל הקשה
                ws, done = t.split(" "), False
                for i, w in enumerate(ws):
                    if len(w) > 2 and not done and not any(c.isascii() and c.isalnum() for c in w):
                        ws[i], done = w[1:] + w[0], True
                if not done:
                    return None
                tb.build(frame, " ".join(ws), s, out, box_color=box)
                return out, t, s, b
            if kind == "sub_bigger":
                # כותרת קטנה ותת-כותרת פי 1.6 ממנה — תקלת 23.7.26 (126px מול 80px)
                # tb.build מתעלם מ-sub_ratio (משתמש ב-SUB_RATIO הגלובלי) — דורסים את הקבוע
                old_r = tb.SUB_RATIO
                tb.SUB_RATIO = 1.6
                try:
                    tb.build(frame, t, s, out, box_color=box, title_start=90)
                finally:
                    tb.SUB_RATIO = old_r
                return out, t, s, b
            if kind == "one_line":
                tb.build(frame, t + " " + s, "‏", out, box_color=box)
                return out, t, s, b
            if kind == "leak":
                tb.build(frame, t, s, out, box_color=box)
                im = Image.open(out).convert("RGBA")
                sys.path.insert(0, str(HERE.parent.parent / "captions-app"))
                import captions_overlay as co
                f = ImageFont.truetype(str(co.BRAND_PROFILES["club"]["font"]), 120)
                lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
                ImageDraw.Draw(lay).text((im.size[0] // 2, int(im.size[1] * 0.93)), "אז מה",
                                         font=f, fill=(255, 255, 255, 255), anchor="ms",
                                         direction="rtl", stroke_width=7,
                                         stroke_fill=co.BRAND_PROFILES["club"]["outline"])
                Image.alpha_composite(im, lay).convert("RGB").save(out)
                return out, t, s, b
    except SystemExit:
        return None
    return None


def calibrate(workdirs):
    import tempfile
    base = dict(DEFAULTS)
    pos, negs = [], {}
    tmp = tempfile.mkdtemp(prefix="cv_cal_")
    for W in workdirs:
        W = Path(W)
        if not (W / "thumbnail.png").exists():
            continue
        r = from_workdir(W, base)
        if r.get("measured"):
            pos.append({"w": W.name, "canon": (W / "cover_report.json").exists(), **_summ(r)})
        if (W / "cover_report.json").exists():
            for kind in ("reversed", "scrambled", "sub_bigger", "one_line", "leak", "scr_word_title"):
                inj = _inject(W, kind, tmp)
                if inj:
                    rr = analyze(inj[0], inj[1], inj[2], inj[3], base)
                    negs.setdefault(kind, []).append({"w": W.name, **_summ(rr)})

    def vals(rows, key):
        return [r[key] for r in rows if r.get(key) is not None]
    with_text = [p for p in pos if p.get("f_ok_min") is not None]
    ev = {"n_pos": len(pos), "n_pos_with_text": len(with_text),
          "pos_line_count": sorted({p["n_lines"] for p in pos if p["canon"]}),
          "pre_canon_line_count": sorted({p["n_lines"] for p in pos if not p["canon"]}),
          "pos_ratio_min": min(vals(pos, "ratio")) if vals(pos, "ratio") else None,
          "pos_f_ok_min": min(vals(with_text, "f_ok_min")) if with_text else None,
          "pos_rev_margin_max": max(vals(with_text, "rev_margin")) if with_text else None,
          "pos_leak_max": max(vals(pos, "leak")) if pos else None,
          "pos_flags": {p["w"]: p["flags"] for p in pos if p["flags"]},
          "neg": {}}
    rev_neg = vals(negs.get("reversed", []), "rev_margin")
    scr_neg = vals(negs.get("scrambled", []), "f_ok_min")
    p = dict(base)
    if ev["pos_rev_margin_max"] is not None and rev_neg and min(rev_neg) > ev["pos_rev_margin_max"]:
        p["order_margin"] = round((ev["pos_rev_margin_max"] + min(rev_neg)) / 2, 3)
    if ev["pos_f_ok_min"] is not None and scr_neg and max(scr_neg) < ev["pos_f_ok_min"]:
        p["order_min"] = round((ev["pos_f_ok_min"] + max(scr_neg)) / 2, 3)
    tw_pos = vals(with_text, "title_word_min")
    tw_neg = vals(negs.get("scr_word_title", []), "title_word_min")
    ev["pos_title_word_min"] = min(tw_pos) if tw_pos else None
    ev["neg_scr_word_title_max"] = max(tw_neg) if tw_neg else None
    if tw_pos and tw_neg and max(tw_neg) < min(tw_pos):
        p["title_word_min"] = round((min(tw_pos) + max(tw_neg)) / 2, 3)
    ratios_bad = vals(negs.get("sub_bigger", []), "ratio")
    if ev["pos_ratio_min"] is not None and ratios_bad and max(ratios_bad) < ev["pos_ratio_min"]:
        p["size_ratio_min"] = round(max(1.0, (ev["pos_ratio_min"] + max(ratios_bad)) / 2), 3)
    p["source"] = "measured"
    # שיעורים בספים הסופיים
    blocking = []
    fin = dict(p); fin["blocking"] = []
    pos_final = []
    for W in workdirs:
        W = Path(W)
        # חיובי-שגוי נמדד רק על קאברים שנבנו תחת הקאנון הנוכחי (cover_make,
        # מ-2.8.26). קאברים ישנים יותר (שורה אחת, לפני G-COVER2) — מידע בלבד.
        if (W / "thumbnail.png").exists() and (W / "cover_report.json").exists():
            pos_final.append(from_workdir(W, fin))
    def fp_rate(pred):
        m = [r for r in pos_final if r.get("measured")]
        return round(sum(1 for r in m if pred(r)) / len(m), 4) if m else None
    targets = {
        "reversed": ("reversed", lambda r: any(f.startswith("reversed") for f in r["flags"])),
        "garbled": ("scrambled", lambda r: any(f.startswith(("garbled", "reversed")) for f in r["flags"])),
        "title_not_bigger": ("sub_bigger", lambda r: "title_not_bigger" in r["flags"]),
        "line_count": ("one_line", lambda r: "line_count" in r["flags"]),
        "caption_leak": ("leak", lambda r: "caption_leak" in r["flags"]),
        # השליליים נותחו בכיול הבסיס (בלי סף מילה) ⇒ התפיסה נמדדת על הערך, בסף הסופי
        "garbled_word": ("scr_word_title", lambda r: r.get("title_word_min") is not None
                         and p.get("title_word_min") is not None
                         and r["title_word_min"] < p["title_word_min"]),
    }
    for flag, (negname, pred) in targets.items():
        fpr = fp_rate(lambda r, f=flag: any(x == f or x.startswith(f + "_") for x in r["flags"]))
        rows = []
        for n in negs.get(negname, []):
            rows.append(n)
        caught = (round(sum(1 for n in rows if pred(n)) / len(rows), 4) if rows else None)
        ev["neg"][negname] = {"n": len(rows), "caught": caught, "pos_false_rate": fpr}
        if fpr == 0 and caught is not None and caught >= 0.95:
            blocking.append(flag)
    p["blocking"] = blocking
    p["blocking_rule"] = "חיובי-שגוי 0 על קאברים שנבנו ב-cover_make ותפיסה ≥95% בהזרקה"
    # שליליים — שמירת flags לשחזור ההחלטה
    for k, rows in negs.items():
        for n in rows:
            pass
    return {"params": p, "evidence": ev,
            "_readme": "ספי cover_vision — חיוביים: thumbnail.png של פרויקטים שנבנו ב-cover_make; "
                       "שליליים: אותו פריים ואותו טקסט דרך הבונה הקנוני עם כשל מוזרק."}


def _summ(r):
    ch = r.get("checks", {})
    o = (ch.get("CV5_order") or {}).get("lines") or []
    return {"flags": r.get("flags", []),
            "n_lines": (ch.get("CV2_two_lines") or {}).get("n_lines"),
            "ratio": (ch.get("CV3_title_big") or {}).get("ratio"),
            "f_ok_min": min((x["f_ok"] for x in o), default=None),
            "rev_margin": max((x["f_rev"] - x["f_ok"] for x in o), default=None),
            "title_word_min": min((s for _, s in (ch.get("CV5_order") or {}).get("title_words") or []),
                                  default=None),
            "leak": (ch.get("CV4_no_leak") or {}).get("score")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png"); ap.add_argument("--title"); ap.add_argument("--subtitle")
    ap.add_argument("--brand", choices=["rel", "personal"])
    ap.add_argument("--workdir")
    ap.add_argument("--out", help="כתיבת COVER_VISION.json")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--calibrate", nargs="+")
    ap.add_argument("--write-calibration", action="store_true")
    a = ap.parse_args()
    if a.calibrate:
        doc = calibrate(a.calibrate)
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        if a.write_calibration:
            CALIB.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    if a.workdir:
        r = from_workdir(a.workdir)
        out = a.out or os.path.join(a.workdir, "COVER_VISION.json")
    elif a.png:
        r = analyze(a.png, a.title, a.subtitle, a.brand)
        out = a.out
    else:
        ap.error("--png או --workdir")
    if out:
        Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    icon = {True: "✅", False: "🔴", None: "—"}[r.get("ok")]
    ch = r.get("checks", {})
    print(f"{icon} ראיית קאבר: " + (" · ".join(r.get("flags", [])) or "אפס ממצאים")
          + f" · שורות {(ch.get('CV2_two_lines') or {}).get('n_lines')}"
          + f" · יחס כותרת/תת {(ch.get('CV3_title_big') or {}).get('ratio')}"
          + f" · ספים: {r.get('threshold_source')}")
    for ln in (ch.get("CV5_order") or {}).get("lines", []):
        print(f"   {ln['line']}: f_ok={ln['f_ok']} f_rev={ln['f_rev']}")
    return (0 if r.get("ok") in (True, None) else 1) if a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
