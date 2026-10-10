#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_sheet.py — בונה contact sheet (פריים אמצעי לכל קליפ) מתיקייה/רשימת קבצים.
שתי מטרות:
  1. אימות — אחרי החיתוך, בונים sheet של התוצרים וקוראים אותו ויזואלית כדי לוודא
     שהמסגור/האיכות תקינים *לפני* שמצהירים "מוכן". (לקח: לא לסמוך — לאמת ויזואלית.)
  2. תצוגה מקדימה של קטעים קצרים לפני format.

שימוש:
  python3 broll_sheet.py --dir CLIPS_DIR --out OUT.jpg [--tile 5x3]
  python3 broll_sheet.py --clips a.mp4 b.mp4 --out OUT.jpg

כתוב את --out לתיקיית outputs כדי שתוכל לקרוא אותו (מיפוי נתיב host).
"""
import argparse
import glob
import os
import subprocess
import tempfile


def dur_of(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nk=1:nw=1", p], capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 1.0


def main():
    ap = argparse.ArgumentParser(description="contact sheet של קליפים")
    ap.add_argument("--dir", help="תיקיית קליפים (כל *.mp4/*.mov)")
    ap.add_argument("--clips", nargs="+", help="רשימת קבצים מפורשת")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tile", default="5x3")
    ap.add_argument("--cell-w", type=int, default=216)
    args = ap.parse_args()

    clips = []
    if args.dir:
        for ext in ("*.mp4", "*.mov", "*.webm", "*.m4v"):
            clips += glob.glob(os.path.join(args.dir, ext))
    if args.clips:
        clips += args.clips
    clips = sorted(set(clips))
    if not clips:
        print("no clips found")
        return

    tdir = tempfile.mkdtemp()
    h = int(args.cell_w * 16 / 9)
    for i, c in enumerate(clips):
        d = dur_of(c)
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-ss", f"{d / 2}", "-i", c, "-frames:v", "1",
                        "-vf", f"scale={args.cell_w}:{h}", f"{tdir}/v{i:03d}.jpg"])
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", "1",
                    "-pattern_type", "glob", "-i", f"{tdir}/v*.jpg",
                    "-vf", f"tile={args.tile}:padding=4:color=white", "-q:v", "3", args.out])
    print(f"clips={len(clips)} sheet={args.out} exists={os.path.exists(args.out)}")
    for i, c in enumerate(clips):
        print(f"#{i}: {os.path.basename(c)}")


if __name__ == "__main__":
    main()
