#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edl_cut.py — מחיל EDL על הווידאו מקומית (ffmpeg): חיתוך frame-accurate של keep_segments
וצירוף ל-ROUGH.mp4 — הקובץ שעולה ל-Descript (קטן, נקי-שקטים, ~90% ערוך).

שיטה מוכחת (לקח בירולים): כל סגמנט מקודד בנפרד (re-encode מדויק, setsar) → concat demuxer -c copy.
QA מובנה: משך הפלט = סכום הסגמנטים ±0.3ש, אחרת exit 2.

הרצה:
  python3 edl_cut.py --video in_1080.mp4 --edl _work/{שם}/edl.json --out _work/{שם}/ROUGH.mp4
      [--crf 18] [--preset veryfast] [--tmp /tmp/edlcut]
"""
import argparse, json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def ffprobe_dur(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except Exception:
        return 0.0

def ffprobe_vdur(p):
    """משך **ערוץ הווידאו** (לא format) — הבאג של concat demuxer + -c copy קוטע את
    הווידאו בזמן שהאודיו ממשיך, ו-format=duration מראה את האודיו (23.7.26)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-count_packets", "-show_entries", "stream=nb_read_packets,r_frame_rate",
                          "-of", "json", str(p)], capture_output=True, text=True)
    try:
        st = json.loads(out.stdout)["streams"][0]
        num, den = (float(x) for x in st["r_frame_rate"].split("/"))
        return int(st["nb_read_packets"]) / (num / den)
    except Exception:
        return 0.0


def concat_filter(seg_files, dst, crf, preset):
    """concat **filter** — מפענח כל קלט בנפרד. המסלול שתיקן את הקטיעה (23.7.26)."""
    inputs = []
    for f in seg_files:
        inputs += ["-i", str(f)]
    n = len(seg_files)
    filt = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error"] + inputs + [
        "-filter_complex", filt, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(dst)]
    return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--edl", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="veryfast")  # לא ultrafast — מנפח פי 2 (לקח)
    ap.add_argument("--tmp")
    ap.add_argument("--jobs", type=int, default=0,
                    help="כמה סגמנטים לקודד במקביל (0=אוטומטי לפי מספר הליבות, 1=סדרתי כמו קודם)")
    ap.add_argument("--xfade", type=float, default=0.0,
                     help="קרוספייד קצר (שניות) בכל גבול חיתוך פנימי, נגד 'פלאש' קפיצת-פריים (לקח 19.7). 0=כבוי (ברירת מחדל, התנהגות ישנה)")
    a = ap.parse_args()

    edl = json.loads(Path(a.edl).read_text(encoding="utf-8"))
    segs = edl["keep_segments"]
    if not segs:
        sys.exit("EDL בלי keep_segments")
    tmpd = Path(a.tmp) if a.tmp else Path(tempfile.mkdtemp(prefix="edlcut_"))
    tmpd.mkdir(parents=True, exist_ok=True)

    # v7.8 — קידוד סגמנטים במקביל (מדידה 25.7.26: 15 סגמנטים סדרתיים = 16.5ש על M4;
    # כל סגמנט הוא תהליך ffmpeg נפרד שמשתמש בחלק קטן מהליבות, אז הרצה מקבילה מנצלת
    # את כל המכונה. הפלט זהה ביט-בביט לסדרתי (אותה פקודה בדיוק לכל סגמנט) — רק סדר
    # הביצוע משתנה. --jobs 1 מחזיר להתנהגות הסדרתית הישנה.
    # -threads מוגבל לכל סגמנט כדי שהעובדים לא ייחנקו הדדית על אותן ליבות.
    n_jobs = a.jobs if a.jobs and a.jobs > 0 else min(6, max(1, (os.cpu_count() or 4) - 2), len(segs))
    per_threads = max(1, (os.cpu_count() or 8) // max(1, n_jobs))

    def encode_seg(i_s):
        i, s = i_s
        sf = tmpd / f"seg_{i:03d}.mp4"
        dur = s["end"] - s["start"]
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-nostdin",
               "-ss", f"{s['start']:.3f}", "-i", a.video, "-t", f"{dur:.3f}",
               "-threads", str(per_threads),
               "-c:v", "libx264", "-crf", str(a.crf), "-preset", a.preset,
               "-pix_fmt", "yuv420p", "-vf", "setsar=1",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
               "-movflags", "+faststart", str(sf)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not sf.exists():
            return i, None, r.stderr[-400:]
        return i, sf, None

    with ThreadPoolExecutor(max_workers=n_jobs) as ex:
        results = sorted(ex.map(encode_seg, list(enumerate(segs))), key=lambda x: x[0])
    for i, sf, err in results:
        if sf is None:
            sys.exit(f"סגמנט {i} נכשל: {err}")
    seg_files = [sf for _, sf, _ in results]

    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = out.with_suffix(".tmp.mp4")  # atomic write (לקח)
    durs = [s["end"] - s["start"] for s in segs]
    xf = a.xfade if a.xfade and a.xfade > 0 and len(seg_files) > 1 else 0.0
    # אל תיתן ל-xfade לבלוע יותר מ-40% מסגמנט קצר (הגנה מפני סגמנטים קצרצרים)
    if xf > 0:
        min_seg = min(durs)
        xf = min(xf, max(0.02, min_seg * 0.4))

    if xf <= 0:
        lst = tmpd / "list.txt"
        lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in seg_files), encoding="utf-8")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                            "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(tmp_out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"concat נכשל: {r.stderr[-400:]}")
        # v9.30 (L84) — concat demuxer + -c copy יכול לקטוע את ערוץ הווידאו בשקט
        # (exit 0, אודיו ממשיך). עד היום זה נתפס רק אחרי שה-ROUGH השבור כבר נכתב.
        # עכשיו: מודדים את ערוץ הווידאו עצמו, ובכשל בונים מחדש ב-concat filter.
        _exp = sum(durs)
        _vd = ffprobe_vdur(tmp_out)
        if _vd and abs(_vd - _exp) > max(0.35, 0.02 * len(seg_files)):
            print(json.dumps({"concat_demuxer_truncated": True, "video_dur": round(_vd, 2),
                              "expected": round(_exp, 2), "retry": "concat_filter"},
                             ensure_ascii=False), file=sys.stderr)
            r = concat_filter(seg_files, tmp_out, a.crf, a.preset)
            if r.returncode != 0:
                sys.exit(f"concat filter נכשל: {r.stderr[-400:]}")
    else:
        # xfade על הוידאו בלבד — מרכך "פלאש" קפיצת-פריים (לקח 19.7). האודיו נשאר concat קשיח:
        # acrossfade בין קטעי דיבור שונים גורם לטבילת-עוצמה אמיתית שנקראת "שקט" ע"י ה-gate ונשמעת
        # כגמגום/דעיכה בדיבור — הרבה יותר גרוע מקאט קשיח (ממצא 19.7).
        inputs = []
        for f in seg_files:
            inputs += ["-i", str(f)]
        vlabel = "0:v"; cum = durs[0]
        vchain = []
        for i in range(1, len(seg_files)):
            voff = round(cum - xf, 3)
            vout = f"v{i}"
            vchain.append(f"[{vlabel}][{i}:v]xfade=transition=fade:duration={xf:.3f}:offset={voff:.3f}[{vout}]")
            vlabel = vout
            cum = cum + durs[i] - xf
        # אודיו: hard-trim (לא blend) של xf בסוף כל קטע חוץ מהאחרון — שומר סנכרון מדויק מול
        # התקצרות הוידאו מה-xfade, בלי לגעת בעוצמת/בהירות האודיו (concat קשיח = בלי טבילת-עוצמה)
        atrims = []
        for i, dseg in enumerate(durs):
            if i < len(durs) - 1:
                atrims.append(f"[{i}:a]atrim=0:{(dseg - xf):.3f},asetpts=PTS-STARTPTS[aa{i}]")
            else:
                atrims.append(f"[{i}:a]asetpts=PTS-STARTPTS[aa{i}]")
        achain = ";".join(atrims) + ";" + "".join(f"[aa{i}]" for i in range(len(seg_files))) + f"concat=n={len(seg_files)}:v=0:a=1[aout]"
        filt = ";".join(vchain) + ";" + achain
        cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + [
            "-filter_complex", filt, "-map", f"[{vlabel}]", "-map", "[aout]",
            "-c:v", "libx264", "-crf", str(a.crf), "-preset", a.preset, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(tmp_out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"xfade נכשל: {r.stderr[-600:]}")
    tmp_out.replace(out)

    expect = sum(durs) - (xf * (len(seg_files) - 1) if xf > 0 else 0)
    got = ffprobe_dur(out)
    # v7.8 — הסובלנות גדלה עם מספר הסגמנטים. כל סגמנט מתקרב לגבול-פריים שלו (עד 33ms
    # ב-30fps), והסטייה מצטברת: על 29 סגמנטים ראינו 0.42ש — נכשל מול סף קבוע 0.35
    # למרות שהחיתוך תקין לחלוטין (נמדד 25.7.26 על "ניפוץ מיתוסים", 146ש/29 סגמנטים).
    # סף קבוע היה אומר ש"ככל שהעריכה עדינה יותר, כך ה-QA נכשל יותר" — הפוך מהרצוי.
    tol = max(0.35, 0.02 * len(seg_files))
    vgot = ffprobe_vdur(out)
    ok = abs(got - expect) <= tol and (not vgot or abs(vgot - expect) <= tol)
    print(json.dumps({"ok": ok, "out": str(out), "expected_dur": round(expect, 2),
                      "actual_dur": round(got, 2), "video_dur": round(vgot, 2),
                      "segments": len(segs),
                      "tolerance": round(tol, 2)}, ensure_ascii=False))
    if not ok:
        sys.exit(2)

if __name__ == "__main__":
    main()
