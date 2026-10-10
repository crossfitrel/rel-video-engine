#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
align_reconcile.py — R.E.L Social Video Editing System
======================================================
ממזג תזמון-אמיתי (faster-whisper, align_words.py) עם הטקסט המתוקן.
התוצאה: words.json עם **טקסט מדויק** (מהתיקון של הראל באפליקציית הרוויו)
+ **תזמון אמיתי** (מהאודיו).

למה: whisper נותן תזמון מצוין אבל הטקסט העברי שלו לא תמיד מדויק (למשל "עוריות"
ייתכן ש-whisper יכתוב "אוריות"). הטקסט המתוקן (edited.txt מהאפליקציה) נותן את
הטקסט הנכון אבל בלי תזמון מילה-מילה. אנחנו לוקחים את הטוב משניהם: difflib מיישר
את שתי סדרות-המילים, מילים תואמות מקבלות את הזמן האמיתי של whisper, ופערים
מתמלאים באינטרפולציה ליניארית קצרה בין עוגנים אמיתיים סמוכים.

שימוש:
  python align_reconcile.py WHISPER_WORDS.json CORRECTED_TRANSCRIPT.txt OUT_words.json \
      [--delay 0.0] [--end 999] [--min-word 0.12]

קלט whisper: [{"word","start","end","prob"}...]  (פלט align_words.py)
קלט מתוקן: txt חופשי; שורות [h:mm:ss] ו-"Speaker:" מנוקות אוטומטית (תאימות לאחור).
פלט: [{"word","start","end","prob","src"}...] בסדר הדיבור, הטקסט המתוקן, תזמון אמיתי.
       src = "match" (זמן אמיתי) / "interp" (אינטרפולציה).
"""
import sys, json, re, argparse

NIQQUD = re.compile(r"[֑-ׇ]")

def norm(w):
    w = NIQQUD.sub("", str(w))
    w = re.sub(r"[^א-ת0-9A-Za-z]", "", w)  # Hebrew letters + alnum only
    return w

def load_corrected_words(path):
    txt = open(path, encoding="utf-8").read()
    txt = re.sub(r"Speaker\s*\d*\s*:", " ", txt)
    txt = re.sub(r"\[\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\]", " ", txt)
    return [w for w in re.split(r"\s+", txt) if w and re.search(r"\w", w)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("whisper"); ap.add_argument("corrected"); ap.add_argument("out")
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=99999.0)
    ap.add_argument("--min-word", type=float, default=0.12)
    a = ap.parse_args()

    import difflib
    wh = json.load(open(a.whisper, encoding="utf-8"))
    dwords = load_corrected_words(a.corrected)
    if not wh or not dwords:
        # 25.9.26 — סרטון בלי דיבור (מונטאז'): אין מילים → אפס כתוביות, לא קריסה.
        json.dump([], open(a.out, "w", encoding="utf-8"))
        print(f"OK 0 words -> {a.out}  | no-speech"); return
    wtok = [norm(x["word"]) for x in wh]
    dtok = [norm(x) for x in dwords]

    times = [None] * len(dwords)
    probs = [0.0] * len(dwords)
    src = ["interp"] * len(dwords)
    sm = difflib.SequenceMatcher(a=dtok, b=wtok, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = [wh[j1 + k]["start"], wh[j1 + k]["end"]]
                probs[i1 + k] = wh[j1 + k].get("prob", 0.0)
                src[i1 + k] = "match"
        elif tag == "replace":
            di, dj = i2 - i1, j2 - j1
            if dj > 0:
                # ── v7.9 (הראל 26.7.26: "יש חלק שהכתוביות מאחרות") ──────────────
                # שורש האיחור: הגרסה הקודמת פרשה את המילים המתוקנות **אחיד** על
                # blk_s..blk_e — כלומר (א) התעלמה מאורך המילה, ו-(ב) זרקה את
                # גבולות-המילים האמיתיים של whisper *בתוך* הבלוק. בבלוק החלפה
                # ארוך (נמדד באופן-ג'ים: 7 מילים על 1.76ש, כולן בדיוק 0.251ש)
                # הפריסה האחידה מתנתקת מקצב הדיבור האמיתי והכתובית "מאחרת"
                # באמצע הבלוק גם כשההתחלה והסוף מדויקים.
                # התיקון: מיפוי פיסתי-לינארי לפי **מצטבר תווים** — כל מילה
                # מתוקנת ממופה לזמן דרך עוגני-הזמן האמיתיים של מילות whisper
                # בבלוק. לקח 19.7 ("אינטרפולציה משוקללת לפי אורך מילה") היה
                # מיושם רק בענף interp; מעכשיו הוא חל גם כאן.
                blk = wh[j1:j2]
                a_len = [max(1, len(norm(x["word"]))) for x in blk]
                a_cum = [0]
                for L in a_len:
                    a_cum.append(a_cum[-1] + L)
                a_tot = a_cum[-1]

                def t_at(frac):
                    """זמן אמיתי בנקודה frac (0..1) של הבלוק, לפי עוגני whisper."""
                    pos = frac * a_tot
                    for wi in range(len(blk)):
                        if pos <= a_cum[wi + 1] or wi == len(blk) - 1:
                            inner = (pos - a_cum[wi]) / max(1e-6, a_len[wi])
                            inner = min(max(inner, 0.0), 1.0)
                            s0, e0 = float(blk[wi]["start"]), float(blk[wi]["end"])
                            return s0 + (e0 - s0) * inner
                    return float(blk[-1]["end"])

                d_len = [max(1, len(norm(dwords[i1 + k]))) for k in range(di)]
                d_cum = [0]
                for L in d_len:
                    d_cum.append(d_cum[-1] + L)
                d_tot = d_cum[-1]
                for k in range(di):
                    st = t_at(d_cum[k] / d_tot)
                    en = t_at(d_cum[k + 1] / d_tot)
                    times[i1 + k] = [st, max(en, st + a.min_word)]
                    probs[i1 + k] = wh[min(j1 + k, j2 - 1)].get("prob", 0.0)
                    src[i1 + k] = "replace"
        # 'delete' (descript words not in whisper) -> stay None -> interpolate

    # interpolate None spans between known anchors
    n = len(times)
    i = 0
    first_known = next((t for t in times if t), None)
    last_known = next((t for t in reversed(times) if t), None)
    if first_known is None:
        # אין אף עוגן (whisper שיבש קשה) — לא קורסים: מיפוי פוזיציוני של תזמוני whisper
        # על מילות הטקסט הנכון לפי יחס אינדקסים. מסומן src="positional" לשקיפות ב-QA.
        for k in range(len(dwords)):
            jj = min(len(wh) - 1, int(k * len(wh) / max(1, len(dwords))))
            times[k] = [wh[jj]["start"], wh[jj]["end"]]
            probs[k] = wh[jj].get("prob", 0.0)
            src[k] = "positional"
        first_known = times[0]
        last_known = times[-1]
    while i < n:
        if times[i] is not None:
            i += 1; continue
        p = i - 1
        ps = times[p][1] if p >= 0 and times[p] else first_known[0]
        q = i
        while q < n and times[q] is None:
            q += 1
        qs = times[q][0] if q < n and times[q] else (last_known[1] if last_known else ps + 0.3)
        m = q - i  # number of None in [i, q)
        span = max(0.0, qs - ps)
        # אינטרפולציה משוקללת לפי אורך מילה (לקח הראל 19.7 — סנכרון רגעי):
        # מילה ארוכה מקבלת חלק גדול יותר מהמרווח — קירוב טוב יותר מחלוקה שווה.
        wts = [max(1, len(norm(dwords[i + r]))) for r in range(m)]
        tot_w = sum(wts) + 1
        acc_w = 0
        for r in range(m):
            st = ps + span * acc_w / tot_w
            acc_w += wts[r]
            en = ps + span * acc_w / tot_w
            times[i + r] = [round(st, 3), round(max(en, st + a.min_word), 3)]
        i = q

    out = []
    for w, t, pr, s in zip(dwords, times, probs, src):
        st = round(min(max(0.0, t[0] + a.delay), a.end), 3)
        en = round(min(max(st + a.min_word, t[1] + a.delay), a.end), 3)
        out.append({"word": w, "start": st, "end": en, "prob": round(pr, 3), "src": s})
    out.sort(key=lambda x: x["start"])

    # ── de-collide + מונוטוניות (לקח "מילים נעלמות" 22.6/30.6, עכשיו מובנה) ──
    # ריצות של מילים עם תזמון זהה/כמעט-זהה (תוצר interp) נפרשות שווה עד העוגן הבא;
    # אחר-כך אכיפת עלייה קפדנית של starts — התנאי שמונע מ-group_cues לאפס cues.
    n = len(out)
    i = 0
    while i < n:
        j = i + 1
        while j < n and out[j]["start"] - out[i]["start"] < 0.03:
            j += 1
        if j - i > 1:
            base = out[i]["start"]
            span_end = out[j]["start"] if j < n else max(out[j - 1]["end"], base + a.min_word * (j - i))
            span_end = max(span_end, base + a.min_word * (j - i))
            step = (span_end - base) / (j - i)
            for k in range(i, j):
                st = base + step * (k - i)
                out[k]["start"] = round(st, 3)
                out[k]["end"] = round(min(st + max(a.min_word, step), a.end), 3)
                if out[k]["src"] == "interp":
                    out[k]["src"] = "spread"
        i = j
    for k in range(1, n):
        if out[k]["start"] <= out[k - 1]["start"]:
            out[k]["start"] = round(out[k - 1]["start"] + 0.02, 3)
        if out[k]["end"] < out[k]["start"] + a.min_word:
            out[k]["end"] = round(out[k]["start"] + a.min_word, 3)

    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nm = sum(1 for s in src if s == "match")
    pct = 100 * nm // max(1, len(out))
    print(f"OK {len(out)} words -> {a.out}  | matched(real-time)={nm}/{len(out)} "
          f"({pct}%), interp/replace={len(out)-nm}")

    # ── v7.9 — נראות דריפט: ריצות של מילים לא-מעוגנות ברצף ─────────────────
    # "הכתוביות מאחרות" חזר כי אף מדד לא חשף את זה. רצף ארוך של מילים בלי
    # עוגן-זמן אמיתי הוא בדיוק המקום שבו נוצר איחור מורגש — מדווח מפורשות.
    drift = []
    run_s = None
    for k, o in enumerate(out):
        if o["src"] != "match":
            if run_s is None:
                run_s = k
        else:
            if run_s is not None and k - run_s >= 4:
                drift.append({"words": k - run_s, "from": out[run_s]["start"],
                              "to": out[k - 1]["end"],
                              "text": " ".join(x["word"] for x in out[run_s:k])[:60]})
            run_s = None
    if run_s is not None and len(out) - run_s >= 4:
        drift.append({"words": len(out) - run_s, "from": out[run_s]["start"],
                      "to": out[-1]["end"],
                      "text": " ".join(x["word"] for x in out[run_s:])[:60]})
    for d in drift:
        print(f"⚠️  דריפט אפשרי: {d['words']} מילים בלי עוגן "
              f"{d['from']:.2f}-{d['to']:.2f}ש — \"{d['text']}\"")
    print(json.dumps({"words": len(out), "match_pct": pct,
                      "positional_fallback": "positional" in src,
                      "drift_runs": drift}, ensure_ascii=False))

if __name__ == "__main__":
    main()
