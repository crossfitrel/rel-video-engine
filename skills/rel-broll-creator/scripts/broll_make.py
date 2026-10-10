#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_make.py — מייצר קבצי בירול מוכנים מסרטון או מקטעים קצרים.
שלב 2 של הצנרת. שני מצבים:

  cut    — מסרטון ארוך + plan (אינדקסים שבחרת מ-candidates.json): חותך כל קטע לבירול.
  format — מקבצי קטעים קצרים: הופך כל קטע (או צירוף קטעים) לבירול בפורמט אחיד.

ברירת מחדל מותגית (אושרה ע"י הראל 22.6.2026):
  - אנכי 1080×1920, **blur-fill** (שומר את כל הפריים, רקע מטושטש למעלה/למטה).
  - אודיו מושתק (-an) — בירול הוא overlay מושתק תמיד.
  - libx264 crf 20, veryfast, +faststart.
  - שם: "בירול {event} - {NN} {desc}.mp4" — המילה "בירול" חובה (המערכת מזהה לפיה).

מצבי מסגור (--mode):
  blur        — ברירת מחדל. אנכי, רקע מטושטש. לא מאבד תוכן. (מומלץ)
  crop        — center-crop אנכי מלא-פריים. punch על אקשן ממורכז, אבל חותך צדדים.
  horizontal  — שומר מסגור מקורי (master גמיש). לא reel-ready.

שימוש:
  # מסרטון ארוך לפי plan:
  python3 broll_make.py cut --video V --plan plan.json --dest DIR --event "Throwdown 2025" [--mode blur]
     plan.json = [{"num":15,"start":29.7,"dur":2.3,"desc":"הרמה"}, ...]

  # מקטעים קצרים (כל קובץ → בירול):
  python3 broll_make.py format --clips a.mov b.mov --dest DIR --event "Throwdown 2025" --start-num 1 [--mode blur]

  # צירוף כמה קטעים קצרים לבירול אחד (stitch):
  python3 broll_make.py stitch --clips a.mov b.mov c.mov --dest DIR --event "אירוע" --num 5 --desc "רצף" [--mode blur]
"""
import argparse
import os
import subprocess
import tempfile

BLUR = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,gblur=sigma=25[bg];[b]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2")
CROP = "crop='min(iw,ih*9/16)':ih,scale=1080:1920:flags=lanczos"


def vf_for(mode):
    return {"blur": BLUR, "crop": CROP, "horizontal": None}.get(mode, BLUR)


def encode(src, ss, dur, out, mode):
    vf = vf_for(mode)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    cmd += ["-i", src]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-an"]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    return subprocess.run(cmd, capture_output=True, text=True)


def name(dest, event, num, desc=""):
    base = f"בירול {event} - {num:02d}" + (f" {desc}" if desc else "")
    return os.path.join(dest, base.strip() + ".mp4")


def kb(p):
    return os.path.getsize(p) // 1024 if os.path.exists(p) else 0


def cmd_cut(args):
    import json
    plan = json.load(open(args.plan, encoding="utf-8"))
    for p in plan:
        out = name(args.dest, args.event, p["num"], p.get("desc", ""))
        r = encode(args.video, p["start"], p["dur"], out, args.mode)
        print(p["num"], kb(out), "KB", r.stderr[-60:] if r.returncode else "")


def cmd_format(args):
    for i, clip in enumerate(args.clips, start=args.start_num):
        out = name(args.dest, args.event, i)
        r = encode(clip, None, None, out, args.mode)
        print(i, os.path.basename(clip), kb(out), "KB", r.stderr[-60:] if r.returncode else "")


def cmd_stitch(args):
    # מנרמל כל קליפ לפורמט הבירול ואז משרשר לקובץ אחד
    tmp = tempfile.mkdtemp()
    parts = []
    for i, clip in enumerate(args.clips):
        pp = os.path.join(tmp, f"p{i}.mp4")
        encode(clip, None, None, pp, args.mode)
        parts.append(pp)
    listf = os.path.join(tmp, "list.txt")
    open(listf, "w").write("\n".join(f"file '{p}'" for p in parts))
    out = name(args.dest, args.event, args.num, args.desc)
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-f", "concat", "-safe", "0", "-i", listf,
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                       capture_output=True, text=True)
    print(args.num, len(parts), "clips ->", kb(out), "KB", r.stderr[-60:] if r.returncode else "")


def main():
    ap = argparse.ArgumentParser(description="יצירת בירולים מסרטון / מקטעים")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cut")
    c.add_argument("--video", required=True)
    c.add_argument("--plan", required=True)
    c.add_argument("--dest", required=True)
    c.add_argument("--event", required=True)
    c.add_argument("--mode", default="blur")
    c.set_defaults(func=cmd_cut)

    f = sub.add_parser("format")
    f.add_argument("--clips", nargs="+", required=True)
    f.add_argument("--dest", required=True)
    f.add_argument("--event", required=True)
    f.add_argument("--start-num", type=int, default=1)
    f.add_argument("--mode", default="blur")
    f.set_defaults(func=cmd_format)

    s = sub.add_parser("stitch")
    s.add_argument("--clips", nargs="+", required=True)
    s.add_argument("--dest", required=True)
    s.add_argument("--event", required=True)
    s.add_argument("--num", type=int, required=True)
    s.add_argument("--desc", default="")
    s.add_argument("--mode", default="blur")
    s.set_defaults(func=cmd_stitch)

    args = ap.parse_args()
    os.makedirs(args.dest, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
