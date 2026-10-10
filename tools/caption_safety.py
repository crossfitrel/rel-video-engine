#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
caption_safety.py — Caption Safety Engine (v7): בדיקות בטיחות על כתוביות לפני צריבה.
==================================================================================
משלים את captions_qa (סנכרון): כאן בודקים את התוכן והסגנון —
RTL, סדר מילים מונוטוני, משכי cues, חפיפות, פערים חריגים, פיסוק אסור,
זמינות פונט, צבע מתאר לפי מותג. דוח בלבד, לא משנה קבצים.

שימוש:
  python3 caption_safety.py --words words_final.json [--brand rel] [--dur 60] [--out r.json]
exit 0 = אין FAIL (אזהרות מותרות) · exit 1 = FAIL
"""
import argparse
import json, os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
sys.path.insert(0, str(HERE))
try:
    import gate_registry as GR
except Exception:                   # pragma: no cover
    GR = None
FONT = SYSDIR / "brand-assets" / "Assistant-ExtraBold.ttf"
BRAND_OUTLINE = {"rel": "#871d1f", "personal": "#0077B6", "oshia": "#0077B6"}

MIN_CUE = 0.10      # cue קצר מזה לא נקרא
MAX_CUE = 2.6       # מילה בודדת ארוכה מזה = תזמון חשוד
MAX_GAP = 1.2       # פער בין cues בזמן דיבור רציף — חריג (יתכן דד-אייר)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--brand", default="rel")
    ap.add_argument("--dur", type=float, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    words = json.loads(Path(a.words).read_text(encoding="utf-8"))
    issues, warns = [], []

    if not words:
        # 25.9.26 — סרטון בלי דיבור (מונטאז'): words ריק כי reconcile קבע no-speech.
        # רק אם הוחלט במפורש no-speech (סימון ב-words_final ריק + דגל) — אחרת נשאר כשל.
        if os.environ.get("REL_NO_SPEECH") == "1":
            print(json.dumps({"ok": True, "note": "no-speech — אין כתוביות"})); sys.exit(0)
        print(json.dumps({"ok": False, "error": "אין מילים"}))
        sys.exit(1)

    heb = re.compile(r"[א-ת]")
    prev_end = None
    for i, w in enumerate(words):
        word, s, e = str(w.get("word", "")), float(w["start"]), float(w["end"])
        # הצורב מנקה [.,…] ב-clean_token — כאן בודקים רק מה ששורד את הניקוי.
        # v8.6: הבדיקה כפי שהייתה כתובה הייתה טאוטולוגיה — היא הסירה [.,…] ואז
        # חיפשה [.,…] בתוצאה, כלומר לא יכלה להיכשל אף פעם (נמדד: 205 מילים עם
        # פיסוק גולמי ב-2,139 מילים אמיתיות, ואפס דגלים). החוק עצמו כן נאכף,
        # אבל בזמן הצריבה (captions_build.clean_token) ולא ע"י שער.
        # מה שכן צריך שער: (א) tripwire אם הניקוי עצמו ייסדק בעתיד — שאותו
        # בודקים על ה-cleaned מול קבוצה מפורשת; (ב) פיסוק ש**שורד** את הניקוי
        # ולכן באמת נצרב על המסך. ‎? ו-! מותרים בקאנון; מקף וגרש/גרשיים
        # לגיטימיים בעברית (עוד-פעם, ד״ר, ג׳ירפה) ולכן מותרים.
        cleaned = re.sub(r"[.,…]+", "", word)
        if re.search(r"[.,…]", cleaned):        # tripwire — הניקוי נסדק
            issues.append({"i": i, "t": s, "type": "forbidden_punct", "word": word})
        elif re.search(r"[;]", cleaned):        # נקודה-פסיק לא נצרבת אף פעם בעברית מדוברת
            issues.append({"i": i, "t": s, "type": "forbidden_punct_survives",
                           "word": word, "detail": "נקודה-פסיק נצרבת על המסך"})
        elif re.search(r"[:()\[\]{}]", cleaned):
            warns.append({"i": i, "t": s, "type": "punct_survives_burn",
                          "word": word, "detail": "פיסוק ששורד את clean_token ויוצג"})
        if re.search(r"[.,…]", word) and not re.search(r"[.,…]", cleaned):
            warns.append({"i": i, "t": s, "type": "raw_punct_cleaned_at_burn",
                          "word": word})
        if e - s < MIN_CUE:
            warns.append({"i": i, "t": s, "type": "cue_too_short",
                          "dur": round(e - s, 3), "word": word})
        if e - s > MAX_CUE:
            warns.append({"i": i, "t": s, "type": "cue_too_long",
                          "dur": round(e - s, 2), "word": word})
        if prev_end is not None:
            if s < prev_end - 0.1:
                # חפיפה אמיתית. ≤0.1ש = רעש תזמון שהצורב (group_cues) מיישר — אזהרה.
                issues.append({"i": i, "t": s, "type": "overlap",
                               "overlap": round(prev_end - s, 3), "word": word})
            elif s < prev_end - 0.001:
                warns.append({"i": i, "t": s, "type": "tiny_overlap",
                              "overlap": round(prev_end - s, 3), "word": word})
            elif s - prev_end > MAX_GAP:
                warns.append({"i": i, "t": s, "type": "large_gap",
                              "gap": round(s - prev_end, 2), "word": word})
        prev_end = e
        # תו ערבי בטקסט עברי (לקח 20.7 — אותיות מתחלפות חזותית)
        if re.search(r"[؀-ۿ]", word):
            issues.append({"i": i, "t": s, "type": "arabic_char", "word": word})

    # מונוטוניות
    starts = [float(w["start"]) for w in words]
    if any(b < a2 for a2, b in zip(starts, starts[1:])):
        issues.append({"type": "non_monotonic_order"})

    # פונט + מותג
    font_ok = FONT.exists()
    if not font_ok:
        issues.append({"type": "font_missing", "path": str(FONT)})
    outline = BRAND_OUTLINE.get(a.brand)
    if not outline:
        warns.append({"type": "unknown_brand", "brand": a.brand})

    # כיסוי: המילה האחרונה מול משך הסרטון
    if a.dur:
        tail = a.dur - float(words[-1]["end"])
        if tail > 2.0:
            warns.append({"type": "captions_end_early", "tail_sec": round(tail, 1)})

    # הנימוק נכנס לדוח כדאטה — מי שקורא את הדוח רואה גם על מה השער מגן
    # ומה קורה במקום חסימה. הטמעה במקום אחד ולא בכל append: סוג הליקוי הוא
    # המפתח, וההסבר שייך לסוג ולא למופע.
    if GR:
        for rec in issues + warns:
            if rec.get("type"):
                rec["why"] = GR.annotate("caption_safety", rec["type"])

    report = {"words": len(words), "brand": a.brand, "outline": outline,
              "font": str(FONT), "font_ok": font_ok,
              "fails": issues, "warnings": warns,
              "result": "FAIL" if issues else ("PASS_WITH_WARNINGS" if warns else "PASS")}
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    print(json.dumps({"result": report["result"], "fails": len(issues),
                      "warnings": len(warns)}, ensure_ascii=False))
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
