#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""caption_lexicon_qa.py — שער G9: כל מילה שנצרבת היא מילה בעברית (V3, 30.7.26).

הראל: "הכתוביות לא טובות. מלאות בשגיאות כתיב. ולא בעברית תקינה."
נצרבו בפועל: "ועל כל צפוף" (בהוק), "הציעות", "בשוט הצהריים".

**מה השער בודק:** כל מילה ב-`words_final.json` — כלומר בדיוק מה שנצרב על
המסך — חייבת להיות אחת מאלה:
  · בלקסיקון (`he_lexicon`)
  · מילה שהמגיה תיקן בביטחון ≥0.80
  · מילה שהמגיה אישר במפורש

**מה חוסם:** מילה שאינה באף אחת מהשלוש, או מילה שהמגיה סימן `needs_manual`.
כתובית שגויה נשארת על המסך לנצח — לכן זה חוסם ולא מזהיר.

exit: 0 = עבר · 1 = חסום · 2 = שגיאת קלט

שימוש:
  python3 tools/caption_lexicon_qa.py --workdir W [--out caption_lexicon_report.json]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import he_lexicon as LEX                                      # noqa: E402


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def check(workdir):
    W = Path(workdir)
    words = jload(W / "words_final.json")
    if words is None:
        return {"ok": True, "skipped": "אין words_final.json"}, 0
    fix = jload(W / "transcript_fix.json", {}) or {}

    lex, _ = LEX.load()
    corrected = {LEX.norm(a["to"]) for a in (fix.get("applied") or [])}
    approved = {LEX.norm(a.get("w", "")) for a in (fix.get("approved") or [])}
    ran = bool(fix)

    # ⚠️ `needs_manual` נבדק **ברמת הריצה ולא ברמת הטוקן**.
    # שורש (30.7.26): המגיה סימן את i=3 שהמילה בו היא "כל" — ואז השער חסם את
    # כל חמשת המופעים של "כל" בסרטון, כולם תקינים. האינדקס של המגיה הוא על
    # ציר המקור, ו-`words_final` הוא אחרי החיתוך — אין ביניהם התאמה ישירה.
    # ההכרעה הנכונה פשוטה יותר: שאלת תמלול פתוחה אחת = הריצה לא מפרסמת.
    unresolved = [{"i": m.get("i"), "word": m.get("w", ""), "why": m.get("why", "")[:200]}
                  for m in (fix.get("needs_manual") or [])]

    bad = []
    for i, w in enumerate(words):
        k = LEX.norm(w.get("word", ""))
        if len(k) < 2:
            continue
        if k in lex or k in corrected or k in approved:
            continue
        bad.append({"i": i, "word": k, "t": round(float(w.get("start", 0)), 2)})

    rep = {
        "ok": not bad and not unresolved,
        "proofreader_ran": ran,
        "n_words": len(words),
        "lexicon_size": len(lex),
        "n_corrected": len(fix.get("applied") or []),
        "unknown": bad,
        "unresolved_questions": unresolved,
    }
    # `blocking` ו-`ok` הם שני דברים שונים בכוונה: `ok` אומר אם נמצאו ממצאים,
    # `blocking` אומר אם עוצרים. בלי המגיה אין למי לייחס אישור, ולכן המסלול
    # הישן (בלי --director) מדווח ולא חוסם — **אבל הדיווח חייב לשקף את המספר
    # האמיתי.** (30.7.26: הגרסה הראשונה הדפיסה "אפס מילים לא מוכרות" בזמן
    # שהחזיקה 9 — בדיוק המלכודת של "מוגדר ≠ עובד".)
    rep["blocking"] = bool((bad or unresolved) and ran)
    if not ran:
        rep["note"] = "לא רץ פאס הגהה — דיווח בלבד, לא חוסם"
    return rep, (1 if rep["blocking"] else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rep, code = check(a.workdir)
    out = Path(a.out) if a.out else Path(a.workdir) / "caption_lexicon_report.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    if rep.get("skipped"):
        print("⚠️ " + rep["skipped"])
        sys.exit(0)
    if rep["ok"]:
        print(f"✅ G9 לקסיקון: {rep['n_words']} מילים · {rep['n_corrected']} תוקנו · "
              f"אפס מילים לא מוכרות (לקסיקון {rep['lexicon_size']})")
    else:
        mark = "❌" if rep["blocking"] else "⚠️"
        tail = "" if rep["blocking"] else " — דיווח בלבד, לא רץ פאס הגהה"
        parts = []
        if rep["unknown"]:
            parts.append(f"{len(rep['unknown'])} מילים לא מוכרות")
        if rep["unresolved_questions"]:
            parts.append(f"{len(rep['unresolved_questions'])} שאלות תמלול פתוחות")
        print(f"{mark} G9 לקסיקון: " + " · ".join(parts) + f" (מתוך {rep['n_words']}){tail}")
        for x in rep["unknown"][:12]:
            print(f"   לא מוכרת · {x['t']:.2f}ש  {x['word']}")
        for x in rep["unresolved_questions"][:6]:
            print(f"   להכרעה · i={x['i']} '{x['word']}' — {x['why'][:90]}")
    sys.exit(code)


if __name__ == "__main__":
    main()
