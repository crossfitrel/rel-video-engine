#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fixed_intro.py — v7.9 · אפקטים/פתיחים קבועים של פורמטים חוזרים, אוטומטית
=========================================================================
שורש (פידבק הראל 25.7.26): "'מנפצים לכם מיתוסים' זה הפתיח שלנו שנבו אומר אחרי
הקטע הראשון — וזה צריך להיות עם האפקט והסאונד של הזכוכית שיש לנו ייעודית לזה."

הנכסים והמתכון היו קיימים מ-21.7 ב-`תוצרי-אנימציה/פתיחים-קבועים/catalog.json`,
אבל **שום דבר לא זיהה את הטריגר ולא הרכיב אותם** — זה נשאר ידני ולכן לא קרה.
הכלי הזה סוגר את הפער: מזהה בתמליל את משפט-הטריגר של הפורמט, ומרכיב את
האפקט + הצליל בדיוק על אותו רגע.

שני סוגי נכסים בקטלוג:
  • `transition` — overlay על רקע שחור שמורכב ב-blend=lighten על הפריים
    (למשל ניפוץ הזכוכית). האודיו של האפקט **מעורבב** עם הדיבור, לא מחליף אותו.
  • `full_intro` — קליפ פתיח שלם שמודבק בתחילת הסרטון (מאסל מן). לא ממומש כאן —
    הוא concat פשוט שנעשה בשלב ההכנה.

קריטי (מאומת 21.7, מתועד בקטלוג): ה-blend חייב לרוץ ב-**gbrp (RGB)** ולחזור
ל-yuv420p אחריו. blend ישיר על yuv נותן גוון ורוד-מגנטה על כל הפריים.

יישור זמן: שיא הניפוץ בקובץ האפקט הוא ב-~0.9ש. מיישרים אותו ל**סוף משפט
הטריגר** — הרגע שבו "המיתוס מתנפץ" — ולכן ה-overlay מתחיל ב-(סוף_המשפט - 0.9).

שימוש:
  python3 fixed_intro.py detect --words words_final.json [--json out.json]
  python3 fixed_intro.py apply --video IN.mp4 --out OUT.mp4 --at 12.34 [--id myth-busting-shatter]
"""
import argparse, json, re, subprocess, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
CATALOG = SYSDIR / "תוצרי-אנימציה" / "פתיחים-קבועים" / "catalog.json"
ASSETS = CATALOG.parent

# טריגרים: ביטוי → מזהה פורמט בקטלוג. מנורמל (בלי ניקוד/פיסוק) לפני השוואה.
TRIGGERS = {
    "myth-busting-shatter": [
        "מנפצים לכם מיתוסים", "מנפצים מיתוסים", "פינת ניפוץ מיתוסים",
        "ניפוץ מיתוסים", "מנפץ לכם מיתוסים",
    ],
}
# תזמון פנימי של הנכס (מהקטלוג): שיא הניפוץ + הצליל
PEAK_SEC = {"myth-busting-shatter": 0.9}
NIQQUD = re.compile(r"[֑-ׇ]")


def norm(s):
    s = NIQQUD.sub("", unicodedata.normalize("NFC", s))
    return re.sub(r"[^֐-׿A-Za-z0-9 ]", " ", s)


def detect(words):
    """מוצא את משפט-הטריגר ומחזיר את זמן **סוף** הביטוי (ציר הסרטון הנוכחי)."""
    toks = [(norm(w["word"]).strip(), float(w["start"]), float(w["end"])) for w in words]
    text_words = [t[0] for t in toks]
    hits = []
    for fid, phrases in TRIGGERS.items():
        for ph in phrases:
            pw = [x for x in norm(ph).split() if x]
            n = len(pw)
            for i in range(len(text_words) - n + 1):
                if text_words[i:i + n] == pw:
                    hits.append({"format_id": fid, "phrase": ph,
                                 "start": toks[i][1], "end": toks[i + n - 1][2]})
    hits.sort(key=lambda h: h["start"])
    return hits


def load_catalog():
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def asset_paths(fid):
    cat = load_catalog()
    for f in cat.get("פורמטים", []):
        if f.get("id") != fid:
            continue
        ov = f.get("asset_overlay_נקי") or {}
        v = ASSETS / ov.get("קובץ_וידאו", "")
        a = ASSETS / ov.get("קובץ_אודיו_עצמאי", "")
        return (v if v.exists() else None), (a if a.exists() else None)
    return None, None


def apply(video, out, at, fid, mix_db=-3.0, lossless=False):
    """מרכיב את אפקט המעבר כך ששיא הניפוץ נוחת על `at` (סוף משפט הטריגר)."""
    fx_v, fx_a = asset_paths(fid)
    if not fx_v:
        return False, f"נכס האפקט של {fid} לא נמצא בקטלוג"
    peak = PEAK_SEC.get(fid, 0.9)
    start = max(0.0, at - peak)
    # שכבת הווידאו: מוזזת ל-start; blend=lighten ב-RGB (מתכון מאומת 21.7).
    # שכבת האודיו: adelay ל-start ואז amix עם הדיבור — לא מחליפים את הדיבור.
    fc = [
        f"[1:v]scale=1080:1920,setpts=PTS-STARTPTS+{start:.3f}/TB,format=gbrp[fx]",
        "[0:v]format=gbrp[base]",
        "[base][fx]blend=all_mode=lighten:shortest=0[vrgb]",
        "[vrgb]format=yuv420p[v]",
    ]
    inputs = ["-i", str(video), "-i", str(fx_v)]
    amap = "0:a"
    if fx_a:
        inputs += ["-i", str(fx_a)]
        fc += [f"[2:a]adelay={int(start*1000)}|{int(start*1000)},volume={mix_db}dB[fxa]",
               "[0:a][fxa]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"]
        amap = "[a]"
    # v8.8 — במנוע v2 הפלט הוא תחנת ביניים לפני המוזיקה, ולכן האודיו חייב
    # להישאר PCM. מעבר ל-AAC כאן היה מוסיף דור אודיו שלם רק בגלל אפקט ויזואלי.
    tail = (["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"] if lossless
            else ["-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart"])
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-nostdin", *inputs,
           "-filter_complex", ";".join(fc), "-map", "[v]", "-map", amap,
           "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           *tail, str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not Path(out).exists():
        return False, r.stderr[-400:]
    return True, f"אפקט {fid} הורכב · שיא ב-{at:.2f}ש (overlay מ-{start:.2f}ש)"



# ════════════════════════════════ פתיח מלא (full_intro) ════════════════════
# שורש (הראל 18.8.26): "שכחנו לצרף את הפתיח של מאסל מן". הנכס והכללים ישבו
# בקטלוג מ-21.7 — אבל `full_intro` היה מתועד כאן כ"לא ממומש, concat שנעשה
# בשלב ההכנה", כלומר תלוי בזיכרון אנושי. זה בדיוק מה שנשכח.
#
# הזיהוי אינו מהתמליל אלא **מהכותרת/הבריף** — הדובר לא אומר "מאסל מן" בגוף
# הסרטון, ולכן טריגר תמלולי לא היה תופס את זה לעולם.
FULL_INTRO_TRIGGERS = {
    "muscle-man": ["מאסל מן", "מאסלמן", "muscle man", "muscleman"],
}


def full_intro_asset(fid):
    """מחזיר (נתיב, רשומת קטלוג) לפורמט שסוגו 'פתיח מלא'."""
    cat = load_catalog()
    for f in cat.get("פורמטים", []):
        if f.get("id") != fid:
            continue
        # מלכודת תת-מחרוזת: הסוג של אפקט המעבר הוא "אפקט מעבר ..., לא פתיח
        # מלא של הסרטון כולו" — מכיל את הביטוי ושולל אותו. חייבים
        # התחלה-של-מחרוזת, לא הכלה. נתפס ע"י tests/test_full_intro.py.
        if not str(f.get("סוג", "")).strip().startswith("פתיח מלא"):
            return None, None
        pth = ASSETS / str(f.get("קובץ", ""))
        return (pth if pth.exists() else None), f
    return None, None


def detect_full_intro(*texts):
    """מזהה פורמט בעל פתיח מלא לפי כותרת/בריף/שם פרויקט. מחזיר (fid, ביטוי)."""
    hay = norm(" ".join(str(t or "") for t in texts)).lower()
    hay = re.sub(r"\s+", " ", hay)
    for fid, phrases in FULL_INTRO_TRIGGERS.items():
        for ph in phrases:
            if re.sub(r"\s+", " ", norm(ph).lower()) in hay:
                return fid, ph
    return None, None


def _probe_float(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "default=nw=1:nk=1", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    for ln in (r.stdout or "").splitlines():
        try:
            return float(ln.strip())
        except ValueError:
            continue
    return None


def _measure_i(path):
    """מפלס LUFS משוקלל (ebur128). מחזיר None אם לא נמדד."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path), "-af", "ebur128",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"^\s*I:\s*(-?[\d.]+)\s*LUFS", r.stderr or "", re.M)
    return float(m[-1]) if m else None


def _loudnorm_stats(path, target_i):
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path), "-af",
                        f"loudnorm=I={target_i}:TP=-1.0:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", r.stderr or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def prepend_full_intro(video, out, fid, workdir=None, target_i=None):
    """מדביק פתיח קבוע בתחילת `video`. מחזיר (ok, detail, intro_sec).

    שלושה דברים שנמדדו ב-18.8.26 על פינת מאסל מן, וכל אחד מהם לבדו שובר:

    1. **concat demuxer עם `-c copy` משאיר duration ישן בזרם הווידאו** —
       ה-format מדווח נכון אבל ה-stream לא, ו-avg_frame_rate יוצא מדומה
       (נמדד 37.44fps במקום 30, ‏G5b נכשל). המסלול היחיד שאומת נקי:
       mp4 → mpegts → concat → mp4.
    2. **אורך האודיו של הפתיח ≠ אורך הווידאו שלו** (10.20 מול 10.13) שובר
       את החיבור. חותכים את שניהם לאורך הווידאו.
    3. **הפתיח מוקלט במפלס אחר מהגוף** (‏-22.0 מול -14.4 LUFS = קפיצה של
       7.6 יחידות, נשמע כמו שקט ואז צעקה). מנרמלים את הפתיח **למפלס הגוף
       הנמדד** — לא לערך קבוע, כדי שזה יישאר נכון גם אם יעד ה-loudness ישתנה.

    הווידאו של הפתיח ושל הגוף מועתקים כזרם — אפס דור קידוד נוסף.
    """
    asset, rec = full_intro_asset(fid)
    if not asset:
        return False, f"נכס פתיח מלא של {fid} לא נמצא בקטלוג", 0.0

    work = Path(workdir) if workdir else Path(out).parent
    tmp = work / "_fixed_intro_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    a48, afit, ts_a, ts_b = (tmp / "intro_48k.mp4", tmp / "intro_fit.mp4",
                             tmp / "a.ts", tmp / "b.ts")

    def run(cmd):
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
        return r.returncode == 0, (r.stderr or "")[-300:]

    body_i = target_i if target_i is not None else _measure_i(video)
    vdur = _probe_float(asset, "stream=duration", "v:0") or \
        _probe_float(asset, "format=duration")
    if not vdur:
        return False, "לא הצלחתי למדוד את אורך הפתיח", 0.0

    # (2) יישור קצב דגימה + חיתוך שני הזרמים לאורך הווידאו
    ok, err = run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", asset,
                   "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                   "-ar", "48000", "-ac", "2", a48])
    if not ok:
        return False, f"המרת אודיו הפתיח נכשלה: {err}", 0.0

    # (3) נרמול הפתיח למפלס הגוף
    af = "apad"
    if body_i is not None:
        stats = _loudnorm_stats(a48, body_i)
        if stats:
            af = ("loudnorm=I={i}:TP=-1.0:LRA=11:measured_I={mi}:measured_TP={mtp}"
                  ":measured_LRA={mlra}:measured_thresh={mth}:linear=true,apad").format(
                i=body_i, mi=stats["input_i"], mtp=stats["input_tp"],
                mlra=stats["input_lra"], mth=stats["input_thresh"])
    ok, err = run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", a48,
                   "-c:v", "copy", "-af", af, "-t", f"{vdur:.6f}",
                   "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                   "-movflags", "+faststart", afit])
    if not ok:
        return False, f"נרמול הפתיח נכשל: {err}", 0.0

    # (1) mpegts הוא המסלול היחיד שמייצר מטא-דאטה תקינה בזרם
    for src_f, dst in ((afit, ts_a), (video, ts_b)):
        ok, err = run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src_f,
                       "-c", "copy", "-bsf:v", "h264_mp4toannexb", "-f", "mpegts", dst])
        if not ok:
            return False, f"המרה ל-mpegts נכשלה: {err}", 0.0
    ok, err = run(["ffmpeg", "-nostdin", "-y", "-v", "error",
                   "-i", f"concat:{ts_a}|{ts_b}", "-c", "copy",
                   "-bsf:a", "aac_adtstoasc", "-video_track_timescale", "30000",
                   "-movflags", "+faststart", out])
    if not ok:
        return False, f"חיבור נכשל: {err}", 0.0

    fps = _probe_float(out, "stream=avg_frame_rate", "v:0")
    total = _probe_float(out, "format=duration") or 0.0
    for f in (a48, afit, ts_a, ts_b):
        try:
            f.unlink()
        except OSError:
            pass
    try:
        tmp.rmdir()
    except OSError:
        pass
    lvl = f" · הפתיח נורמל מ-{_fmt(_measure_i(asset))} ל-{_fmt(body_i)} LUFS" if body_i else ""
    return True, (f"פתיח «{rec.get('שם', fid)}» הודבק — {vdur:.2f}ש + גוף "
                  f"= {total:.2f}ש{lvl}"), float(vdur)


def _fmt(x):
    return "?" if x is None else f"{x:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["detect", "apply", "detect-full", "prepend"])
    ap.add_argument("--words")
    ap.add_argument("--video")
    ap.add_argument("--out")
    ap.add_argument("--at", type=float)
    ap.add_argument("--id", default="myth-busting-shatter")
    ap.add_argument("--json")
    ap.add_argument("--title", default="")
    ap.add_argument("--target-i", type=float)
    a = ap.parse_args()

    if a.mode == "detect":
        words = json.loads(Path(a.words).read_text(encoding="utf-8"))
        hits = detect(words)
        out = {"hits": hits, "count": len(hits)}
        txt = json.dumps(out, ensure_ascii=False, indent=1)
        if a.json:
            Path(a.json).write_text(txt, encoding="utf-8")
        print(txt)
        return
    if a.mode == "detect-full":
        fid, ph = detect_full_intro(a.title)
        asset, rec = full_intro_asset(fid) if fid else (None, None)
        out = {"format_id": fid, "phrase": ph,
               "asset": str(asset) if asset else None,
               "seconds": (rec or {}).get("משך_שניות")}
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    if a.mode == "prepend":
        ok, msg, sec = prepend_full_intro(a.video, a.out, a.id, target_i=a.target_i)
        print(json.dumps({"ok": ok, "detail": msg, "intro_sec": sec}, ensure_ascii=False))
        sys.exit(0 if ok else 1)
    ok, msg = apply(a.video, a.out, a.at, a.id)
    print(json.dumps({"ok": ok, "detail": msg}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
