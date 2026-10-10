#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
captions_build.py — R.E.L Social Video Editing System
======================================================
מחולל כתוביות "2 מילים קופצות" בעברית, בסטייל המותג, וצריבה מקומית ב-ffmpeg.

למה מקומית: Descript לא תומך RTL בכתוביות (חוק קשיח v1.3). libass כן —
אומת 4.6.2026 עם Assistant-ExtraBold (פריימים נבדקו ויזואלית: RTL תקין).

סטייל מותג (ברירת מחדל):
  פונט Assistant ExtraBold | לבן | מתאר אדום מותג #871d1f | מודגש |
  2 מילים בכל פעם | מיקום תחתון-מרכז מעל ה-UI של אינסטגרם (מתכוונן --marginv)

קלט תזמון: JSON של מילים עם זמנים:
  [{"word": "פילאטיס", "start": 0.12, "end": 0.55}, ...]

שימוש:
  # יצירת ASS בלבד
  python3 captions_build.py build --words words.json --out subs.ass

  # יצירה + צריבה על וידאו
  python3 captions_build.py burn --words words.json --video IN.mp4 --out FINAL.mp4
      [--words-per-cue 2] [--fontsize 120] [--marginv 430]
      [--fontsdir PATH] [--min-dur 0.30]

הערות:
  - הקובץ נכתב UTF-8. libass + fribidi מטפלים ב-RTL. אין צורך להפוך טקסט.
  - PlayRes 1080x1920 — libass מסקלל אוטומטית לכל רזולוציה (כולל 4K אנכי).
  - להימנע מכיסוי פנים: ברירת המחדל תחתון-מרכז; אפשר --marginv גבוה יותר להרמה.
"""

import argparse
import json
import os
import subprocess
import sys

BRAND_OUTLINE_ASS = "&H001F1D87"   # #871d1f ב-BGR של ASS (ברירת מחדל — מועדון)
WHITE_ASS = "&H00FFFFFF"
FONT_NAME = "Assistant ExtraBold"

# מתאר הכתוביות לפי מותג — hex RRGGBB. rel=אדום המועדון, personal/oshia=כחול המותג האישי
BRAND_COLORS = {
    "rel": "871d1f",
    "personal": "0077B6",
    "oshia": "0077B6",
}


def hex_to_ass_bgr(h):
    """#RRGGBB -> &H00BBGGRR (פורמט ASS)."""
    h = h.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()
DEFAULT_FONTSDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "brand-assets")


def fmt_ts(t):
    """שניות -> פורמט ASS h:mm:ss.cc"""
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def load_words(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    words = [w for w in data if str(w.get("word", "")).strip()]
    words.sort(key=lambda w: float(w["start"]))
    return words


import re


def clean_token(word):
    """ניקוי טקסט לכתובית: **בלי נקודות ובלי פסיקים — אף פעם** (חוק הראל, חוזר).
    מסירים . , … ; נשארים רק '?' ו-'!'."""
    t = str(word).strip()
    t = re.sub(r"[.,…]+", "", t)      # מסיר נקודות, פסיקים ואליפסיס בכל מקום במילה
    return t.strip()


def group_cues(words, per_cue=1, min_dur=0.30, max_dur=2.50, max_gap_snap=0.12,
               short_len=2, short_dur=0.20, join_max_gap=0.6):
    """קיבוץ לכתוביות קופצות — חוק הראל 4.6:
    - ברירת מחדל: **מילה אחת** בכל פעם.
    - **שתי מילים רק במקרה חריג**: מילה קצרצרה (עד short_len אותיות, למשל
      "של/את/מה/כל/מי") או קצרה מ-short_dur שניות — מתחברת למילה הבאה,
      כדי שלא תהבהב לבד. לעולם לא יותר מ-2.
    - בלי נקודות בטקסט (clean_token).
    - תקרת תצוגה max_dur — שלא תיתקע כתובית בפאוזות.
    - הצמדת קצוות בפערים זעירים למניעת הבהוב."""
    cues = []
    i = 0
    n = len(words)
    while i < n:
        grp = [words[i]]
        tok = clean_token(words[i]["word"])
        dur = float(words[i]["end"]) - float(words[i]["start"])
        is_short = len(re.sub(r"[^\w]", "", tok)) <= short_len or dur < short_dur
        # v9.38 — לא מצרפים מעל הפסקה: "עם" + "רוצים" מעל חלון MG (כתוביות מושתקות) או פאוזה ארוכה
        # הוצגו ככתובית אחת שנתקעה 2.5ש על המסך (דמו HSPU 4.10.26).
        gap_next = (float(words[i + 1]["start"]) - float(words[i]["end"])) if i + 1 < n else 99.0
        if per_cue == 1 and is_short and i + 1 < n and gap_next <= join_max_gap:
            grp.append(words[i + 1])   # החריג: צירוף קצרצרה למילה הבאה
            i += 1
        elif per_cue >= 2:
            while len(grp) < per_cue and i + 1 < n:
                grp.append(words[i + 1])
                i += 1
        i += 1

        text = " ".join(clean_token(w["word"]) for w in grp).strip()
        if not text:
            continue
        start = float(grp[0]["start"])
        end = float(grp[-1]["end"])
        if end - start < min_dur:
            end = start + min_dur
        if end - start > max_dur:
            end = start + max_dur
        cues.append({"start": start, "end": end, "text": text})

    for j in range(len(cues) - 1):
        gap = cues[j + 1]["start"] - cues[j]["end"]
        if 0 < gap <= max_gap_snap or gap < 0:
            cues[j]["end"] = cues[j + 1]["start"]
    return cues


def build_ass(cues, fontsize=120, marginv=430, outline=7, anim=False, outline_color=None):
    oc = outline_color or BRAND_OUTLINE_ASS
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,{FONT_NAME},{fontsize},{WHITE_ASS},{WHITE_ASS},{oc},&H80000000,-1,0,0,0,100,100,0,0,1,{outline},0,2,40,40,{marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    # אנימציה מינימלית בלבד (פידבק הראל 17.6: scale-bounce היה בולט מדי) — fade-in עדין,
    # בלי שינוי גודל. anim=False = סטטי לגמרי.
    pop = (r"{\fad(50,0)}" if anim else "")
    # תיקון קבוע (הראל 30.6): כל cue נעטף ב-RTL embedding (U+202B … U+202C) כדי
    # שכיוון הבסיס יהיה RTL — סימני ניקוד/שאלה (? !) ינחתו בצד שמאל (סוף המשפט בעברית),
    # לא בצד ימין. בלי זה libass/fribidi נותן לניטרלים בסוף שורה את כיוון ה-LTR ברירת המחדל.
    RLE, PDF = "‫", "‬"   # RIGHT-TO-LEFT EMBEDDING / POP DIRECTIONAL FORMATTING
    for c in cues:
        lines.append(
            f"Dialogue: 0,{fmt_ts(c['start'])},{fmt_ts(c['end'])},Pop,,0,0,0,,{pop}{RLE}{c['text']}{PDF}\n"
        )
    return "".join(lines)


def resolve_outline_color(args):
    if getattr(args, "outline_color", None):
        return hex_to_ass_bgr(args.outline_color)
    return hex_to_ass_bgr(BRAND_COLORS.get(getattr(args, "brand", "rel"), "871d1f"))


def cmd_build(args):
    words = load_words(args.words)
    cues = group_cues(words, args.words_per_cue, args.min_dur)
    ass = build_ass(cues, args.fontsize, args.marginv, args.outline,
                    outline_color=resolve_outline_color(args))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(ass)
    print(f"✅ {len(cues)} cues ({args.words_per_cue} מילים כ\"א) → {args.out}")
    return 0


def cmd_burn(args):
    ass_path = args.out + ".ass" if not args.ass else args.ass
    words = load_words(args.words)
    cues = group_cues(words, args.words_per_cue, args.min_dur)
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(build_ass(cues, args.fontsize, args.marginv, args.outline,
                          outline_color=resolve_outline_color(args)))

    fontsdir = args.fontsdir or DEFAULT_FONTSDIR
    vf = f"subtitles={ass_path}:fontsdir={fontsdir}"
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-i", args.video,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
    ]
    if args.loudnorm:
        # יישור loudness סופי לתקן ריל — באותו מעבר של הצריבה (אין שלב נוסף).
        # זה לא מיקס מוזיקה: המוזיקה כבר עורבבה ב-Descript; רק נרמול הקובץ המוגמר.
        cmd += ["-af", f"loudnorm=I={args.loudnorm}:TP=-1:LRA=11",
                "-c:a", "aac", "-b:a", "256k"]
    else:
        cmd += ["-c:a", "copy"]
    cmd += [args.out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        return 1
    print(f"✅ נצרב: {args.out}  ({len(cues)} cues)")
    return 0


def main():
    p = argparse.ArgumentParser(description="R.E.L Hebrew pop-captions builder")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = dict()
    pb = sub.add_parser("build", help="יצירת קובץ ASS בלבד")
    px = sub.add_parser("burn", help="יצירה + צריבה על וידאו")

    for sp in (pb, px):
        sp.add_argument("--words", required=True, help="JSON של מילים עם start/end")
        sp.add_argument("--words-per-cue", type=int, default=1)
        sp.add_argument("--min-dur", type=float, default=0.30)
        sp.add_argument("--fontsize", type=int, default=120)
        sp.add_argument("--marginv", type=int, default=430)
        sp.add_argument("--outline", type=int, default=7)
        sp.add_argument("--brand", default="rel",
                        choices=list(BRAND_COLORS.keys()),
                        help="מותג הכתוביות: rel=אדום המועדון, personal/oshia=כחול אישי")
        sp.add_argument("--outline-color", default=None,
                        help="עקיפת צבע מתאר ידנית (hex RRGGBB), גובר על --brand")

    pb.add_argument("--out", required=True, help="נתיב ASS לפלט")
    pb.set_defaults(func=cmd_build)

    px.add_argument("--video", required=True)
    px.add_argument("--out", required=True, help="נתיב וידאו לפלט")
    px.add_argument("--ass", default=None, help="נתיב ASS (ברירת מחדל: <out>.ass)")
    px.add_argument("--fontsdir", default=None)
    px.add_argument("--loudnorm", type=float, default=-14.0,
                    help="יעד LUFS ליישור סופי באותו מעבר (0 = כבוי, ברירת מחדל -14)")
    px.set_defaults(func=cmd_burn)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
