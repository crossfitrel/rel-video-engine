#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_seam_qa.py — R.E.L Social Video Editing System (v8.4, 26.7.26)
====================================================================
מודד את מה שהראל רואה בעין ואף שער לא בדק: **חשיפת דובר בתפר בין שני
בירולים סמוכים**.

למה זה נולד
-----------
"בין בירול לבירול לא צריך לראות אותי" חזרה שלוש פעמים (25.7 ×2, 26.7). בכל
פעם התיקון היה בתכנון (gap/גישור/הזזה), ותוכנית הבירולים אכן הראתה
hole=0.0 — אבל בפלט נשאר **פריים אחד** של הדובר בכל תפר, כי ffmpeg הגיע
ל-EOF בקליפ הבירול לפני סוף החלון (eof_action=pass). כלומר נמדד הדבר
הלא-נכון: תוכנית תקינה ≠ פלט תקין. השער הזה מודד את הפלט.

השיטה (v8.4c — נבחרה אחרי כיול על שני בילדים אמיתיים)
-----------------------------------------------------
משווים כל פריים חשוד ב-FINAL אל **וידאו הבסיס לפני הבירולים**
(EXPORT_TIGHT.mp4) באותה חותמת-זמן. אותה גאומטריה, אותו מקור ⇒ אם הפריימים
כמעט זהים, הבסיס נראה מבעד לבירול = חשיפת דובר.

נמדד על שני בילדים (16 פריימים כל אחד):
  בילד שבור — פריימים חשופים d=0.099-0.116, שאר הפריימים 0.22-0.46
  בילד מתוקן — כל הפריימים 0.22-0.51, מינימום 0.22
⇒ סף 0.16 מפריד חד. (הכתוביות הצרובות תופסות רצועה קטנה ולא מזיזות את
ההיסטוגרמה מעל הסף.)

שתי גישות אחרות נבדקו ונדחו במידה, לא בהשערה:
  • השוואה לפריים-דובר אחר — נכשלה: פריים-פנים בתפר רחוק מפריים-דובר אחר
    (0.30) יותר מאשר מהבירול (0.22); שינוי פוזה/זום הורג את ההשוואה.
  • השוואה לקליפ המקור בדיסק — נכשלה על קליפ לרוחב: ה-overlay מוסיף רקע
    מטושטש, וההיסטוגרמה של הפריים המורכב שונה מהמקור הגולמי ⇒ false-positive
    על בילד נקי (נמדד: תפרים 40.96 ו-44.48).

שימוש:
  python3 broll_seam_qa.py --video FINAL.mp4 --plan broll_plan.json \
      [--base EXPORT_TIGHT.mp4] [--out broll_seam_report.json] [--tol 0.16]
יציאה: 0 = נקי, 1 = נמצאה חשיפת דובר בתפר.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image

FPS_STEP = 1 / 30.0


def grab(video, t, w=64):
    """פריים בזמן t כתמונת PIL קטנה (grayscale) — או None."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        out = f.name
    r = subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error",
                        "-ss", f"{max(0.0, t):.3f}", "-i", str(video),
                        "-vf", f"scale={w}:-1", "-frames:v", "1", out],
                       capture_output=True)
    if r.returncode != 0 or not Path(out).exists() or Path(out).stat().st_size == 0:
        Path(out).unlink(missing_ok=True)
        return None
    im = Image.open(out).convert("L").copy()
    Path(out).unlink(missing_ok=True)
    return im


def dist(a, b):
    """מרחק היסטוגרמה מנורמל 0..1 בין שני פריימים."""
    if a is None or b is None:
        return 1.0
    ha, hb = a.histogram(), b.histogram()
    ta, tb = sum(ha) or 1, sum(hb) or 1
    return sum(abs(x / ta - y / tb) for x, y in zip(ha, hb)) / 2.0


def _unused_src_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=duration", "-of",
                        "default=nw=1:nk=1", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def main():
    ap = argparse.ArgumentParser(description="R.E.L b-roll seam QA")
    ap.add_argument("--video", required=True)
    ap.add_argument("--plan", required=True, help="broll_plan.json")
    ap.add_argument("--base", default=None,
                    help="וידאו הבסיס לפני בירולים (ברירת מחדל: EXPORT_TIGHT.mp4 בתיקייה)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--tol", type=float, default=0.16,
                    help="מתחת לזה הפריים כמעט זהה לבסיס ⇒ חשיפת דובר")
    a = ap.parse_args()

    # ברירת המחדל היא הציר המהודק; אבל תחת `--director` שלב ההידוק מדולג
    # ו-EXPORT_TIGHT.mp4 לא נוצר כלל — הציר המהודק **הוא** EXPORT.mp4.
    # בלי הנפילה הזו השער היה מדלג בשקט על כל סרטון של מנוע ההחלטה (30.7.26).
    base = Path(a.base) if a.base else Path(a.video).parent / "EXPORT_TIGHT.mp4"
    if not a.base and not base.exists():
        alt = Path(a.video).parent / "EXPORT.mp4"
        if alt.exists():
            base = alt
    if not base.exists():
        print(f"⚠️  אין וידאו בסיס ({base.name}) — לא ניתן למדוד תפרים, מדלג")
        print(json.dumps({"ok": True, "skipped": "no base video"}, ensure_ascii=False))
        sys.exit(0)

    plan = json.load(open(a.plan, encoding="utf-8")).get("plan", [])
    seams, flags = [], []
    for i in range(len(plan) - 1):
        cur, nxt = plan[i], plan[i + 1]
        gap = round(float(nxt["insert_at"]) - float(cur["insert_end"]), 3)
        if gap > 0.30:
            continue          # מקטע נפרד בכוונה — חזרה לדובר היא לגיטימית
        t_end = float(cur["insert_end"])
        bad = []
        # הפריימים האחרונים **בתוך** החלון — שם נצפתה החשיפה בפועל
        for k in (2, 1):
            t = round(t_end - k * FPS_STEP, 3)
            if t <= float(cur["insert_at"]):
                continue
            d = dist(grab(a.video, t), grab(base, t))
            if d < a.tol:
                bad.append({"t": t, "d_base": round(d, 3)})
        rec = {"seam": round(t_end, 2), "gap": gap,
               "after": cur["file"], "before": nxt["file"],
               "exposed_frames": bad}
        seams.append(rec)
        if bad:
            flags.append(rec)

    report = {"video": str(a.video), "checked_seams": len(seams),
              "flagged": len(flags), "tol": a.tol,
              "ok": not flags, "seams": seams}
    if a.out:
        json.dump(report, open(a.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    if flags:
        for f in flags:
            ts = ", ".join(str(x["t"]) for x in f["exposed_frames"])
            print(f"❌ חשיפת דובר בתפר {f['seam']}ש ({len(f['exposed_frames'])} "
                  f"פריימים: {ts}) — אחרי \"{f['after']}\"")
    else:
        print(f"✅ {len(seams)} תפרים נבדקו — אפס חשיפת דובר")
    print(json.dumps({"ok": report["ok"], "checked": len(seams),
                      "flagged": len(flags)}, ensure_ascii=False))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
