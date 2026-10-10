#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
story_structure.py — Story Structure Engine (v7): ניתוח מבנה סיפורי של התמליל.
=============================================================================
מנוע המלצות בלבד: מסמן Hook / הבטחה / הקשר / ערך / הוכחה / CTA, חזרות,
משפטים שלא מקדמים, ו-Hook מאוחר. לא ממציא מסרים, טענות או CTA — רק מסמן
את מה שנאמר בפועל. הפלט מוצג באפליקציית הרוויו כהצעות.

שימוש:
  python3 story_structure.py --sentences sentences.json [--out story_report.json]
  (או --words whisper_raw.json — ייבנו משפטים לפי פערי 0.55ש)
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

CTA_PAT = re.compile(r"(לינק|קישור|ביו|תתקשרו|תשלחו|הודעה|בואו|מוזמנים|הירשמו|"
                     r"פרטים|תגובות|עקבו|שתפו|שמרו|ספרו לי)")
PROMISE_PAT = re.compile(r"(אני הולך|אני אספר|תגלו|תלמדו|בסרטון הזה|היום נדבר|"
                         r"אני רוצה לספר|שלושה דברים|טעות אחת|הסוד)")
PROOF_PAT = re.compile(r"(מחקר|נתונים|אחוז|לדוגמה|דוגמה|אצלנו במועדון|מתאמן ש|"
                       r"ראיתי|קרה לי|סיפור)")
HOOK_Q = re.compile(r"\?|למה |איך |מה הדבר|אם הייתם|תחשבו")


def sents_from_words(words, gap=0.55):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if not nxt or float(nxt["start"]) - float(w["end"]) >= gap:
            out.append({"text": " ".join(x["word"] for x in cur),
                        "start": float(cur[0]["start"]), "end": float(cur[-1]["end"])})
            cur = []
    return out


def norm(s):
    return re.sub(r"[^א-ת0-9a-z ]", "", str(s).lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences")
    ap.add_argument("--words")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.sentences and Path(a.sentences).exists():
        raw = json.loads(Path(a.sentences).read_text(encoding="utf-8"))
        sents = [s if isinstance(s, dict) else {"text": str(s)} for s in raw]
    elif a.words and Path(a.words).exists():
        sents = sents_from_words(json.loads(Path(a.words).read_text(encoding="utf-8")))
    else:
        print(json.dumps({"ok": False, "error": "צריך --sentences או --words"}))
        sys.exit(2)

    n = len(sents)
    beats, repeats, weak = [], [], []
    late_hook = None
    for i, s in enumerate(sents):
        txt = s.get("text", "")
        start = s.get("start")
        dur = round((s.get("end") or 0) - (s.get("start") or 0), 1) if s.get("end") else None
        tags = []
        if i == 0:
            tags.append("hook")
        if PROMISE_PAT.search(txt):
            tags.append("promise")
        if PROOF_PAT.search(txt):
            tags.append("proof")
        if CTA_PAT.search(txt) and i >= n - 3:
            tags.append("cta")
        if i > 0 and HOOK_Q.search(txt) and i <= n // 2 and len(txt.split()) >= 5 \
                and late_hook is None and i > 1:
            late_hook = {"index": i, "start": start, "text": txt[:90],
                         "suggestion": "Hook פוטנציאלי שנאמר מאוחר — שקול 'קבע כפתיחה' באפליקציה"}
        if not tags and 0 < i < n - 1:
            tags.append("value")
        # חזרות
        for j in range(max(0, i - 6), i):
            ratio = difflib.SequenceMatcher(a=norm(txt), b=norm(sents[j].get("text", "")),
                                            autojunk=False).ratio()
            if ratio > 0.75 and len(txt.split()) >= 4:
                repeats.append({"index": i, "similar_to": j, "ratio": round(ratio, 2),
                                "start": start, "text": txt[:80]})
                break
        # משפט חלש: קצר מאוד, בלי תוכן (מילות קישור בלבד)
        if 0 < i < n - 1 and len(txt.split()) <= 3 and not CTA_PAT.search(txt):
            weak.append({"index": i, "start": start, "text": txt,
                         "note": "משפט קצר שלא מקדם — לבדיקה (לא לחתוך אוטומטית)"})
        beats.append({"index": i, "start": start, "dur": dur, "tags": tags,
                      "text": txt[:100]})

    has_cta = any("cta" in b["tags"] for b in beats)
    report = {"sentences": n, "beats": beats, "repeats": repeats,
              "weak_candidates": weak, "late_hook": late_hook,
              "cta_detected": has_cta,
              "advisory": "מנוע המלצות בלבד — שום דבר כאן לא נחתך אוטומטית"}
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    print(json.dumps({"ok": True, "sentences": n, "repeats": len(repeats),
                      "late_hook": bool(late_hook), "cta": has_cta}, ensure_ascii=False))


if __name__ == "__main__":
    main()
