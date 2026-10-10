#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
captions_qa.py — R.E.L Social Video Editing System
==================================================
מודד אובייקטיבית את סנכרון הכתוביות מול האודיו, מול ground-truth של תזמון
מילים אמיתי (faster-whisper / align_words.py). מחזיר:
  - drift לכל מילה (חתום: + = מאחר, - = מקדים)
  - ממוצע drift חתום  → מזהה היסט גלובלי ומציע תיקון --delay מדויק
  - אחוז מילים בתוך סף (0.10 / 0.15 / 0.20s)
  - SYNC SCORE (% בתוך 0.15s) + PASS/FAIL
  - 10 המילים הכי חורגות (לאיתור בעיות מקומיות)

זהו ה-QA GATE: כתוביות לא נשלחות לפני SCORE טוב. "מוגדר ≠ עובד" — מודדים.

שימוש:
  python captions_qa.py CAPTION_words.json GROUNDTRUTH_whisper.json [--pass 90] [--tol 0.15]

CAPTION_words.json     — התזמון שנבדק (פלט align_reconcile/transcript_to_words; שדה word/start)
GROUNDTRUTH_whisper.json — תזמון אמיתי מהאודיו (פלט align_words.py)
"""
import sys, json, re, argparse, difflib, statistics

NIQQUD = re.compile(r"[֑-ׇ]")
def norm(w):
    w = NIQQUD.sub("", str(w))
    return re.sub(r"[^א-ת0-9A-Za-z]", "", w)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caption"); ap.add_argument("truth")
    ap.add_argument("--pass", dest="passpct", type=float, default=90.0)
    ap.add_argument("--tol", type=float, default=0.15)
    a = ap.parse_args()

    cap = json.load(open(a.caption, encoding="utf-8"))
    tru = json.load(open(a.truth, encoding="utf-8"))
    ctok = [norm(x["word"]) for x in cap]
    ttok = [norm(x["word"]) for x in tru]
    sm = difflib.SequenceMatcher(a=ctok, b=ttok, autojunk=False)

    drifts = []          # signed: caption.start - truth.start
    rows = []            # (word, cap_start, tru_start, drift)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                cs = float(cap[i1 + k]["start"]); ts = float(tru[j1 + k]["start"])
                d = cs - ts
                drifts.append(d)
                rows.append((cap[i1 + k]["word"], cs, ts, d))

    if not drifts:
        # 25.9.26 — סרטון בלי דיבור: אפס כתוביות ואמת-קרקע כמעט ריקה (≤3 מילים = הזיית ASR) → לא רלוונטי.
        if not ctok and len([t for t in ttok if t]) <= 3:
            print("QA PASS: no-speech video — 0 caption words, truth ≤3 words (ASR noise)"); sys.exit(0)
        print("QA ERROR: no matched words between caption and ground-truth"); sys.exit(2)

    n = len(drifts); absd = [abs(d) for d in drifts]
    mean_signed = statistics.mean(drifts)
    mean_abs = statistics.mean(absd)
    med_abs = statistics.median(absd)
    mx = max(absd)
    within = lambda t: 100.0 * sum(1 for x in absd if x <= t) / n
    w10, w15, w20 = within(0.10), within(0.15), within(0.20)
    score = within(a.tol)
    matched_pct = 100.0 * n / max(1, len(cap))

    worst = sorted(rows, key=lambda r: -abs(r[3]))[:10]
    print(f"=== CAPTIONS QA  ({a.caption.split('/')[-1]}) ===")
    print(f"matched words: {n}/{len(cap)} ({matched_pct:.0f}% of caption aligned to audio truth)")
    print(f"mean signed drift: {mean_signed:+.3f}s   (>0=late, <0=early)")
    print(f"   -> suggested delay correction: {-mean_signed:+.2f}s")
    print(f"mean |drift|: {mean_abs:.3f}s | median: {med_abs:.3f}s | max: {mx:.3f}s")
    print(f"within 0.10s: {w10:.0f}%   within 0.15s: {w15:.0f}%   within 0.20s: {w20:.0f}%")
    print(f"SYNC SCORE (<= {a.tol}s): {score:.0f}%   -> {'PASS' if score>=a.passpct and matched_pct>=70 else 'FAIL'}")
    print("worst offenders:")
    for w, cs, ts, d in worst:
        print(f"   {d:+.2f}s  '{w}'  (caption {cs:.2f} vs audio {ts:.2f})")
    summary = {"n": n, "matched_pct": round(matched_pct,1), "mean_signed": round(mean_signed,3),
               "median_signed": round(statistics.median(drifts),3),  # 28.9.26: עמיד להתאמות-שווא (TD26)
               "suggest_delay": round(-mean_signed,2), "mean_abs": round(mean_abs,3),
               "max_abs": round(mx,3), "within_0.15": round(w15,1), "score": round(score,1),
               "pass": bool(score>=a.passpct and matched_pct>=70)}
    print("JSON " + json.dumps(summary, ensure_ascii=False))
    sys.exit(0 if summary["pass"] else 1)

if __name__ == "__main__":
    main()
