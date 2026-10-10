#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcript_to_words.py — R.E.L Social Video Editing System
==========================================================
ממיר תמלול עם טיימקודים [h:mm:ss] ל-words.json (פורמט captions_build/finish_local),
עם **תזמון מילים מקורב** — לשימוש כשאין word-timestamps מדויקים
(אין קרדיטי Descript ל-agent, ו-whisper לא ניתן להתקנה בסביבה).

עיקרון: הטקסט **מדויק** (מהתמלול של Descript), התזמון **מקורב** — בכל מקטע
[t_i → t_{i+1}] המילים מפוזרות פרופורציונלית לאורך המילה (chars). מתאים לכתוביות
מילה-מילה כ"גרסה ראשונה"; אפשר לכוונן ידנית ב-CapCut אם מילה בודדת מקדימה/מאחרת.

קלט: קובץ txt עם שורות "[h:mm:ss] טקסט..." (פלט export_transcript עם timecodes).
שימוש:
  python3 transcript_to_words.py --transcript t.txt --end 59.78 --out words.json
"""
import argparse, json, re, sys


def parse_ts(s):
    p = [float(x) for x in s.split(":")]
    while len(p) < 3:
        p = [0.0] + p
    return p[0] * 3600 + p[1] * 60 + p[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--end", type=float, required=True, help="משך הקומפוזיציה (שניות)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-word", type=float, default=0.18, help="משך מינימלי למילה")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="היסט גלובלי (שניות) לכל הכתוביות — חיובי=מאחר (מתקן 'מוקדם מדי')")
    a = ap.parse_args()

    txt = open(a.transcript, encoding="utf-8").read()
    txt = re.sub(r"Speaker\s*\d*\s*:", " ", txt)   # הסרת תוויות דובר
    segs = re.findall(r"\[(\d{1,2}:\d{2}:\d{2}(?:\.\d+)?)\]\s*([^\[]*)", txt)
    phrases = []
    for ts, body in segs:
        body = body.replace("--", " ").replace("—", " ").strip()
        words = [w for w in re.split(r"\s+", body) if w and re.search(r"\w", w)]  # סינון טוקנים שהם רק פיסוק
        phrases.append((parse_ts(ts), words))

    # תת-שנייה: כשכמה עוגנים חולקים אותה שנייה שלמה (frequency_seconds<1, הטיימקוד מוצג בשלמים),
    # לפזר אותם באופן שווה בתוך השנייה כדי לשחזר את הדיוק (למשל 2 עוגנים -> N.0, N.5).
    i = 0
    while i < len(phrases):
        j = i
        while j < len(phrases) and phrases[j][0] == phrases[i][0]:
            j += 1
        k = j - i
        if k > 1:
            base = phrases[i][0]
            for m in range(k):
                phrases[i + m] = (round(base + m / k, 3), phrases[i + m][1])
        i = j

    out = []
    for i, (t, words) in enumerate(phrases):
        if not words:
            continue
        t_next = phrases[i + 1][0] if i + 1 < len(phrases) else a.end
        span = max(0.2, t_next - t)
        lens = [max(1, len(re.sub(r"[^\w]", "", w))) for w in words]
        total = sum(lens) or 1
        cur = t
        for w, l in zip(words, lens):
            dur = max(a.min_word, span * l / total)
            end = min(cur + dur, t_next)
            out.append({"word": w, "start": round(cur, 2), "end": round(end, 2)})
            cur = end
    if a.delay:
        for w in out:
            w["start"] = round(min(max(0.0, w["start"] + a.delay), a.end), 2)
            w["end"] = round(min(w["end"] + a.delay, a.end), 2)
    out.sort(key=lambda x: x["start"])
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(out)} words -> {a.out}")


if __name__ == "__main__":
    main()
