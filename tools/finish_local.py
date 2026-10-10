#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
finish_local.py — R.E.L Social Video Editing System
====================================================
שלב הגימור המקומי, מאוחד: QA Gate אפס-שקט → צריבת כתוביות → יישור loudness → מדידה.
תוצר: קובץ סופי **יחיד** מוכן להעלאה. (חוק 4.6: בלי כפילויות.)

למה כלי נפרד מ-captions_build: זה ה-orchestrator של הגימור. ה-gate חוסם צריבה
כשיש פערי שקט — הלקח מ-4.6: פרומפט לבדו לא נאכף, חייבים לאמת על המדיה.

=== QA Gate אפס-שקט (שני גלאים) ===
1. **דד-אייר מתזמוני המילים** (הגלאי העיקרי): מוזיקה ממלאת את האודיו, אז
   silencedetect לא תופס "שקט" בין קטעי דיבור. במקום זה: מילה שמשכה המוצג
   גדול מ-max_word_dur מכילה דד-אייר (הפער נבלע לתוך משך המילה הקודמת).
   span = [word.start + speech_est, word.end]. דיווח span ≥ min_gap.
2. **silencedetect על האודיו** (גיבוי): תופס שקט מוחלט אמיתי (אם אין מוזיקה).

אם ה-gate נכשל → exit code 3 + JSON של ה-spans (ל-orchestrator: refinement ל-agent).
עם --force → מתעלמים מה-gate (לטסטים / אישור ידני).

שימוש:
  # רק בדיקה
  python3 finish_local.py gate --words words.json [--video V.mp4]

  # גימור מלא (gate → כתוביות → loudnorm → מדידה)
  python3 finish_local.py run --video EXPORT.mp4 --words words.json --out FINAL.mp4
      [--loudnorm -14] [--max-word-dur 1.3] [--min-gap 0.5] [--force]
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAPTIONS = os.path.join(HERE, "captions_build.py")
AUDIO_MIX = os.path.join(HERE, "audio_mix.py")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def load_words(path):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for w in data:
        word = w.get("word", w.get("w", ""))
        s = float(w.get("start", w.get("s")))
        e = float(w.get("end", w.get("e")))
        if str(word).strip():
            out.append({"word": word, "start": s, "end": e})
    out.sort(key=lambda x: x["start"])
    return out


def deadair_from_words(words, max_word_dur=1.3, min_gap=0.5, speech_est=1.0):
    """מזהה דד-אייר: מילה עם משך מוצג גדול מ-max_word_dur מכילה פער שקט."""
    spans = []
    for w in words:
        dur = w["end"] - w["start"]
        if dur > max_word_dur:
            gap_start = round(w["start"] + min(speech_est, dur * 0.4), 2)
            gap = round(w["end"] - gap_start, 2)
            if gap >= min_gap:
                spans.append({"after_word": w["word"], "from": gap_start,
                              "to": round(w["end"], 2), "gap_sec": gap})
    return spans


def edge_silence(words, comp_dur=None, min_gap=0.4, intro_keep=0.0):
    """שקט בפתיחה/סיום — לא נבלע במשך מילה, אז deadair_from_words לא תופס.
    שקט פתיחה בריל = דד-אייר קלאסי (פותחים על ה-Hook). (לקח 7.6)
    intro_keep: פתיח ויזואלי מוגן במפורש (visual_opening_sec, לקח 19.7) — שקט עד
    לסף הזה לא נחשב דד-אייר; רק העודף שמעבר לו מדווח (מגן על החלטה מפורשת של הראל)."""
    spans = []
    if not words:
        return spans
    lead = round(float(words[0]["start"]), 2)
    excess = round(lead - max(0.0, intro_keep), 2)
    if excess >= min_gap:
        spans.append({"where": "פתיחה", "from": round(max(0.0, intro_keep), 2),
                      "to": lead, "gap_sec": excess})
    if comp_dur:
        trail = round(float(comp_dur) - float(words[-1]["end"]), 2)
        if trail >= min_gap:
            spans.append({"where": "סיום", "from": round(float(words[-1]["end"]), 2),
                          "to": round(float(comp_dur), 2), "gap_sec": trail})
    return spans


def silencedetect(video, noise=-35, d=0.5):
    """גלאי גיבוי — שקט מוחלט אמיתי (אם אין מוזיקה)."""
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video,
             "-af", f"silencedetect=noise={noise}dB:d={d}", "-f", "null", "-"])
    spans = []
    starts = re.findall(r"silence_start:\s*([0-9.]+)", r.stderr)
    durs = re.findall(r"silence_duration:\s*([0-9.]+)", r.stderr)
    for st, du in zip(starts, durs):
        spans.append({"from": round(float(st), 2), "gap_sec": round(float(du), 2)})
    return spans


def cmd_gate(args):
    words = load_words(args.words)
    da = deadair_from_words(words, args.max_word_dur, args.min_gap)
    edges = edge_silence(words, args.comp_dur, min_gap=getattr(args, "edge_block", 0.4),
                          intro_keep=getattr(args, "intro_keep", 0.0))
    sd = silencedetect(args.video, d=args.min_gap) if args.video else []
    # לקח 19.7 (v6): ספאן -35dB קצר הוא לרוב נשימה/פאוזה טבעית מעל סף הדיבור (-40) —
    # חיתוכו פוגע בדיבור. חוסמים רק חורים אמיתיים (>= audio_block); השאר אזהרה.
    intro_keep = getattr(args, "intro_keep", 0.0) or 0.0
    sd_adj = []
    for s in sd:
        span_to = s["from"] + s["gap_sec"]
        if intro_keep > 0 and s["from"] < intro_keep:
            # חופף לפתיח המוגן — סופרים רק את מה שחורג ממנו (לקח 19.7)
            eff = round(span_to - intro_keep, 2)
            if eff <= 0:
                continue
            sd_adj.append({"from": round(intro_keep, 2), "gap_sec": eff})
        else:
            sd_adj.append(s)
    sd_block = [s for s in sd_adj if s["gap_sec"] >= args.audio_block]
    sd_warn = [s for s in sd_adj if s["gap_sec"] < args.audio_block]
    report = {"edge_silence_spans": edges, "dead_air_spans": da,
              "audio_silence_spans": sd_block, "audio_silence_warnings": sd_warn}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if da or sd_block or edges:
        n = len(da) + len(sd_block) + len(edges)
        print(f"\n🚫 QA GATE נכשל: {n} פערי שקט חוסמים. "
              f"התיקון באפליקציית הרוויו (v6).", file=sys.stderr)
        return 3
    if sd_warn:
        print(f"\n⚠️  {len(sd_warn)} פאוזות שקטות קצרות (לא חוסם).", file=sys.stderr)
    print("\n✅ QA GATE עבר: אפס דד-אייר.", file=sys.stderr)
    return 0


def measure_i(path):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
             "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
    blocks = re.findall(r"\{[^{}]*\}", r.stderr, re.DOTALL)
    return float(json.loads(blocks[-1])["input_i"]) if blocks else None


def cmd_run(args):
    # --- 1. QA Gate ---
    words = load_words(args.words)
    da = deadair_from_words(words, args.max_word_dur, args.min_gap)
    edges = edge_silence(words, args.comp_dur, min_gap=0.4)
    da = edges + da
    if da and not args.force:
        print(json.dumps({"silence_spans": da}, ensure_ascii=False, indent=2))
        print(f"\n🚫 QA GATE נכשל: {len(da)} פערי דד-אייר/שקט-קצוות. הצריבה נעצרה. "
              f"סגור את הפערים באפליקציית הרוויו (gate_fail.json מכיל טיימקודים), "
              f"ונסה שוב (או --force לעקיפה).", file=sys.stderr)
        return 3
    if da:
        print(f"⚠️  --force: ממשיך למרות {len(da)} פערי דד-אייר.", file=sys.stderr)

    # --- 2. כתוביות (ASS) ---
    ass = args.out + ".ass"
    rc = run(["python3", CAPTIONS, "build", "--words", args.words, "--out", ass])
    if rc.returncode != 0:
        print(rc.stderr, file=sys.stderr)
        return 1

    # --- 3. צריבה + יישור loudness (מעבר אחד) ---
    measured = measure_i(args.video)
    limit = 10 ** (-1.0 / 20)   # -1 dBTP
    fontsdir = os.path.join(HERE, "..", "brand-assets")

    def encode(gain_db):
        af = f"volume={gain_db}dB,alimiter=limit={limit:.3f}:attack=5:release=60:level=disabled"
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", args.video,
               "-vf", f"subtitles={ass}:fontsdir={fontsdir}",
               "-af", af,
               "-c:v", "libx264", "-crf", str(args.crf), "-preset", "veryfast",
               "-c:a", "aac", "-b:a", "192k", args.out]
        return run(cmd)

    gain_db = round(args.loudnorm - measured, 2) if measured is not None else 0.0
    r = encode(gain_db)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        return 1
    out_i = measure_i(args.out)

    # --- תיקון עקביות: ה-limiter עלול למשוך את ה-integrated מתחת ליעד.
    #     אם סטינו >0.5dB — לתקן את הגיין פעם אחת ולקודד מחדש. (לקח 7.6)
    if out_i is not None and abs(out_i - args.loudnorm) > 0.5:
        gain_db = round(gain_db + (args.loudnorm - out_i), 2)
        r = encode(gain_db)
        if r.returncode == 0:
            out_i = measure_i(args.out)

    # --- 4. מדידת QA ---
    print(f"✅ {args.out}")
    print(f"   קלט: {measured:.2f} LUFS → גיין {gain_db:+.2f}dB → פלט: {out_i:.2f} LUFS (יעד {args.loudnorm})")
    print(f"   כתוביות: {ass}")
    return 0


def main():
    p = argparse.ArgumentParser(description="R.E.L local finishing — QA gate + captions + loudness")
    sub = p.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("gate", help="QA Gate אפס-שקט בלבד")
    pg.add_argument("--words", required=True)
    pg.add_argument("--video", default=None)
    pg.add_argument("--max-word-dur", type=float, default=1.3)
    pg.add_argument("--min-gap", type=float, default=0.5)
    pg.add_argument("--comp-dur", type=float, default=None, help="משך הקומפוזיציה (לזיהוי שקט סיום)")
    pg.add_argument("--audio-block", type=float, default=0.6,
                    help="ספאן silencedetect חוסם מאורך זה (קצר יותר=אזהרה). כויל 1.5→0.9→0.6 ב-20.7.26: "
                         "הראל 'כמה שפחות שקט ככה טוב' — beat מכוון (punch/CTA ב-edl-policy.json) "
                         "כוילו יחד ל-≤0.55/0.35 כדי להישאר מתחת לסף ולא להיכשל תמיד.")
    pg.add_argument("--intro-keep", type=float, default=0.0,
                    help="פתיח ויזואלי מוגן (visual_opening_sec, לקח 19.7) — שקט עד לסף זה בפתיחה לא נחשב דד-אייר")
    pg.add_argument("--edge-block", type=float, default=0.4,
                    help="סף gate ל-edge_silence (שקט קצוות פתיחה/סיום, אחרי המילה האחרונה/לפני הראשונה). "
                         "ברירת מחדל 0.4ש. הרפיה זמנית (0.6-1.0) בטוחה מעצם ההגדרה — הפער נמדד תמיד "
                         "אחרי המילה האחרונה שזוהתה, אז אין סיכון לחיתוך דיבור (21.7).")
    pg.set_defaults(func=cmd_gate)

    pr = sub.add_parser("run", help="גימור מלא")
    pr.add_argument("--video", required=True)
    pr.add_argument("--words", required=True)
    pr.add_argument("--out", required=True)
    pr.add_argument("--loudnorm", type=float, default=-14.0)
    pr.add_argument("--max-word-dur", type=float, default=1.3)
    pr.add_argument("--min-gap", type=float, default=0.5)
    pr.add_argument("--comp-dur", type=float, default=None, help="משך הקומפוזיציה (לזיהוי שקט סיום)")
    pr.add_argument("--crf", type=int, default=20)
    pr.add_argument("--force", action="store_true")
    pr.set_defaults(func=cmd_run)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
