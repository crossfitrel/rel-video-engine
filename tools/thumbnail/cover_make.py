#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cover_make.py — **שער הכניסה היחיד לכל קאבר** (v9.12, 2.8.26)
==============================================================

למה הקובץ הזה קיים
------------------
עד היום היו שלושה בוני-קאבר (`thumbnail_build.py`, `cover_build.py`,
`oshia-cover-creator/make_cover.py`), כל אחד עם ברירות מחדל משלו, וכל אחד קיבל
`--frame <כל PNG>` והאמין לקורא. שלוש התקלות שהראל דיווח עליהן ב-2.8.26 הן
שלוש פנים של אותו כשל מבני — **הכללים היו נוהל ולא שער**:

  1. פריים עם כתובית צרובה ("אז מה" מבצבץ מתחת לקופסה) — הקופסה היא 70%
     שקיפות ולעולם לא תסתיר טקסט צרוב. הכלל "מ-EXPORT נקי" היה כתוב בסקיל
     ולא נאכף בקוד.
  2. שורה אחת במקום שתיים — `--subtitle` היה **אופציונלי** בקוד בזמן שהקאנון
     אומר "תמיד 2 שורות".
  3. פריים עם עיניים חצי-עצומות ופה פתוח — `frame_select` ניקד גודל-פנים,
     חדות ובהירות בלבד; עיניים ומבט פשוט לא נמדדו.

מכאן: כל קאבר עובר דרך כאן, ושלושת הדברים נאכפים כשערים.

  G-COVER1  מקור נקי       חוסם   — `cover_guard.caption_signal` (סף נמדד)
  G-COVER2  שתי שורות      חוסם   — תת-כותרת חובה, בלי דלת אחורית
  G-COVER3  Studentit      חוסם   — התת-כותרת חייבת להיות בפונט המותג
  G-COVER4  איכות פריים    מדווח  — מנקד ובוחר את הטוב; מציג contact sheet
  G-COVER5  ראיית PNG      חוסם*  — cover_vision על הפלט (v9.29). *רק דגלים שנמדדו

‏G-COVER4 מדווח ולא חוסם בכוונה: לפעמים כל הפריימים בסרטון בינוניים, ופסילה
הייתה עוצרת עבודה בלי לשפר דבר. הוא כן **בוחר** — וזה ההבדל שמייצר את התוצאה.

שימוש:
    python3 cover_make.py --video EXPORT.mp4 --title "מה זה באמת" \
        --subtitle "להיות בעל מועדון" --brand personal --out thumbnail.png
"""
from __future__ import annotations
import argparse
import json
import os
import sys

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cover_guard                                    # noqa: E402
import thumbnail_build as tb                          # noqa: E402

BRAND_BOX = {
    "rel": (135, 29, 31),          # #871d1f — מועדון
    "personal": (0, 119, 182),     # #0077B6 — הראל חיון (מותג אישי)
}


def pick_frame(video, out_dir, step=0.35, skip_head=1.2, skip_tail=1.0, topn=9):
    """בוחר את הפריים הראוי ביותר לקאבר: איכות מנוקדת, כתובית פוסלת.

    מחזיר (best_path, best_report, candidates). כותב contact sheet לאימות
    ויזואלי — כי "התווית משקרת, הפריים לא".
    """
    os.makedirs(out_dir, exist_ok=True)
    cfg = cover_guard.load_calibration()
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = (total / fps) if fps else 0.0
    scored, rejected = [], 0
    t = skip_head
    while t < dur - skip_tail:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, fr = cap.read()
        if not ok:
            t += step
            continue
        cap_rep = cover_guard.caption_signal(fr, cfg)
        if not cap_rep["pass"]:
            rejected += 1
            t += step
            continue
        q = cover_guard.frame_quality(fr)
        scored.append((q["score"], t, fr, q, cap_rep))
        t += step
    cap.release()
    if not scored:
        raise SystemExit(
            f"❌ שער G-COVER1: כל {rejected} הפריימים שנדגמו מ-{os.path.basename(video)} "
            "מכילים כתובית צרובה.\n"
            "   זה אומר שהקובץ שהועבר אינו EXPORT הנקי אלא FINAL/MIXED.\n"
            "   קאבר נבנה רק מהקובץ שלפני צריבת הכתוביות.")

    scored.sort(key=lambda r: r[0], reverse=True)
    best_sc, best_t, best_fr, best_q, best_cap = scored[0]
    best_path = os.path.join(out_dir, "best.png")
    cv2.imwrite(best_path, best_fr)

    # גיליון מועמדים — מרוחקים ≥0.8ש זה מזה, עם הציון והנימוק על הפריים.
    import numpy as np
    chosen = []
    for sc, tt, fr, q, _ in scored:
        if all(abs(tt - c[0]) > 0.8 for c in chosen):
            chosen.append((tt, fr, sc, q))
        if len(chosen) >= topn:
            break
    cols = 3
    rows = (len(chosen) + cols - 1) // cols
    cw, ch = 300, 533
    sheet = np.full((max(1, rows) * ch, cols * cw, 3), 28, np.uint8)
    for i, (tt, fr, sc, q) in enumerate(chosen):
        r, c = divmod(i, cols)
        th = cv2.resize(fr, (cw, ch))
        tag = "OK" if (q.get("eyes_open") and not q.get("gaze_down")
                       and not q.get("mouth_open")) else "flag"
        col = (0, 220, 0) if tag == "OK" else (0, 165, 255)
        cv2.putText(th, f"{tt:.1f}s {sc:.2f} {tag}", (8, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, col, 2)
        sheet[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = th
    sheet_path = os.path.join(out_dir, "cover_candidates.jpg")
    cv2.imwrite(sheet_path, sheet)

    return best_path, {
        "t": round(best_t, 2), "quality": best_q, "caption_signal": best_cap,
        "sampled": len(scored) + rejected, "rejected_captioned": rejected,
        "candidates_sheet": sheet_path,
    }, chosen


def make(video=None, frame=None, title=None, subtitle=None, out="cover.png",
         brand="rel", band_center=tb.BAND_CENTER_Y, workdir=None, thumb_dir=None):
    # ── G-COVER2: שתי שורות. אין דלת אחורית, אין ברירת מחדל ריקה. ──────────
    if not title or not (subtitle or "").strip():
        raise SystemExit(
            "❌ שער G-COVER2: קאבר חייב **שתי שורות** — כותרת + תת-כותרת.\n"
            "   זה כלל קאנון (הראל, 1.8 ושוב 2.8). קאבר בשורה אחת לא יוצא מכאן.\n"
            "   פצל את המסר: כותרת = הקרס, תת-כותרת = ההמשך.")

    if frame is None:
        if not video:
            raise SystemExit("❌ נדרש --video (נקי) או --frame")
        thumb_dir = thumb_dir or os.path.join(os.path.dirname(out) or ".", "thumb")
        frame, pick_rep, _cands = pick_frame(video, thumb_dir)
    else:
        pick_rep = {"t": None, "quality": cover_guard.frame_quality(cv2.imread(frame))}

    # ── G-COVER1: הפריים עצמו נבדק שוב, גם כשהגיע מבחוץ. ───────────────────
    pick_rep["caption_guard"] = cover_guard.assert_clean_frame(frame)

    box = BRAND_BOX.get(brand)
    if box is None:
        raise SystemExit(f"❌ מותג לא מוכר: {brand} (rel | personal)")

    tb.build(frame, title, subtitle, out, band_center=band_center, box_color=box)

    # ── G-COVER3: לוודא שהתת-כותרת באמת יצאה ב-Studentit. ──────────────────
    if not tb.SUB_FONT_IS_STUDENTIT:
        raise SystemExit("❌ שער G-COVER3: פונט התת-כותרת אינו Studentit")

    # ── G-COVER5 (v9.29, 22.9.26): ראייה על ה-PNG שיצא, לא על הכוונה. ────────
    # G-COVER1..3 בודקים את הקלט לבונה; התקלות שהראל תפס (תת-כותרת הפוכה/
    # מקוטעת, תת-כותרת גדולה מהכותרת, כתובית מבצבצת) היו בפלט. cover_vision
    # מודד את הפיקסלים וחוסם רק דגלים שנמדדו נקיים (cover-vision-calibration).
    import cover_vision
    vis = cover_vision.analyze(out, title, subtitle, brand)
    rep = {"out": out, "brand": brand, "box_rgb": list(box),
           "title": title, "subtitle": subtitle,
           "sub_font": os.path.basename(tb.SUB_FONT),
           "lines": 2, "source_video": video, "frame": frame, **pick_rep,
           "vision": {k: vis.get(k) for k in ("flags", "blocking_hits", "threshold_source",
                                               "checks", "ok")},
           "ok": vis.get("ok") is not False}
    rp = os.path.join(os.path.dirname(out) or ".", "cover_report.json")
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1, default=str)
    if vis.get("ok") is False:
        raise SystemExit(
            "❌ שער G-COVER5 (ראייה על ה-PNG): " + ", ".join(vis.get("blocking_hits") or [])
            + f"\n   הקאבר נכתב ל-{out} לצורך בדיקה אבל לא מאושר. פירוט: {rp}")
    q = pick_rep.get("quality") or {}
    print(f"✅ קאבר: {out}")
    print(f"   מקור: {os.path.basename(video or frame)} · פריים t={pick_rep.get('t')}s")
    print(f"   שער כתובית: score={pick_rep['caption_guard']['score']} "
          f"< סף {pick_rep['caption_guard']['threshold']} ({pick_rep['caption_guard']['threshold_source']})")
    print(f"   איכות פריים: {q.get('why')} (ציון {q.get('score')})")
    print(f"   שתי שורות · תת-כותרת ב-{os.path.basename(tb.SUB_FONT)}")
    print(f"   ראיית PNG (G-COVER5): " + (", ".join(vis.get("flags") or []) or "אפס ממצאים")
          + f" · ספים {vis.get('threshold_source')}")
    if pick_rep.get("candidates_sheet"):
        print(f"   מועמדים לאימות: {pick_rep['candidates_sheet']}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", help="קובץ המקור הנקי (EXPORT.mp4) — מועדף")
    ap.add_argument("--frame", help="פריים מוכן (ייבדק גם הוא מול G-COVER1)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", required=True, help="חובה — קאבר הוא תמיד 2 שורות")
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand", default="rel", choices=["rel", "personal"])
    ap.add_argument("--band-center", type=float, default=tb.BAND_CENTER_Y)
    a = ap.parse_args()
    make(video=a.video, frame=a.frame, title=a.title, subtitle=a.subtitle,
         out=a.out, brand=a.brand, band_center=a.band_center)


if __name__ == "__main__":
    main()
