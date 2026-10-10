#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_qa.py — Visual Cut QA (v7): בדיקה ויזואלית של *כל* גבולות החיתוך.
====================================================================
G8 בדק רק את הפתיחה; כאן בודקים כל גבול: מחלצים פריים לפני/אחרי, מודדים
brightness delta, histogram difference, black frame, near-duplicate (freeze),
ו-scene score של ffmpeg סביב הגבול. הפלט: cut_qa_report.json + contact sheet.

זה מנוע דיווח — לא חותך, לא מוסיף xfade, לא משנה מדיה. הבעיות מוצגות
באפליקציית הרוויו עם טיימקוד.

שימוש:
  python3 cut_qa.py --video EXPORT_TIGHT.mp4 --keeps tight_keeps.json \
      [--edl edl.json] [--out cut_qa_report.json] [--sheet cut_qa_sheet.jpg]
  (בלי --keeps/--edl: מזהה גבולות עם scene detection בלבד)
תלויות: ffmpeg + PIL (רץ עם ~/.rel-whisper/bin/python אם למערכת אין PIL).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import gate_registry as GR
except Exception:                   # pragma: no cover
    GR = None

TH_BRIGHT = 28        # דלתת בהירות ממוצעת (0-255) בין שני צדי הגבול
TH_HIST = 0.42        # מרחק היסטוגרמה מנורמל (0-1)
TH_BLACK = 16         # בהירות ממוצעת שמתחתיה פריים נחשב שחור
TH_DUP = 2.0          # דלתא ממוצעת שמתחתיה שני פריימים עוקבים = freeze/duplicate


def sh(cmd, timeout=120):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          timeout=timeout)


def extract(video, t, out):
    r = sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0, t):.3f}",
            "-i", video, "-frames:v", "1", "-vf", "scale=270:-2", out])
    return r.returncode == 0 and Path(out).exists()


def img_stats(path):
    im = Image.open(path).convert("L")
    px = list(im.getdata())
    mean = sum(px) / len(px)
    hist = im.histogram()
    total = sum(hist)
    hist = [h / total for h in hist]
    return mean, hist, im


def hist_dist(h1, h2):
    return sum(abs(a - b) for a, b in zip(h1, h2)) / 2.0


TH_FLASH = 8.0        # L-flash (23.9.26): קפיצה בין פריימים עוקבים (0-255, 54x96 gray) שנחשבת "חיתוך"
K_FLASH = 4.0         # ...וגם פי K מחציון התנועה בחלון (דיבור/ידיים)
MAX_FLASH_F = 5       # פלאש = 1-5 פריימים זרים: שתי קפיצות במרחק ≤5 פריימים סביב הגבול
# כיול (23.9.26, EXPORT_TIGHT): חיוביים שהראל תפס — E-Myth 51.37 [14,0,15], לידים 18.55
# [25,0,38], חלבון 85.31 [11,0,30] (שתי קפיצות, פער 2). שליליים — ג'סטות אחרי חיתוך
# (ניפוץ 9.95, לידים 5.06, E-Myth 19.69) = קפיצה אחת בלבד. הגרסה הראשונה (השוואה לתנוחה
# יציבה) סימנה גם ג'סטות — נפסלה במדידה.


def flash_probe(video, t):
    """L-flash: 1-5 פריימים 'זרים' צמודים לגבול (לחיצה על הקלטה/עצירה בקצה קליפ).
    חתימה: שתי קפיצות חדות (חיתוך + חזרה) במרחק ≤MAX_FLASH_F פריימים זו מזו ליד הגבול.
    מחזיר {spikes, gap, base} או None."""
    try:
        import numpy as np
    except ImportError:
        return None
    t0 = max(0.0, t - 0.6)
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", "1.2", "-i", str(video),
                        "-vf", "fps=30,scale=54:96,format=gray", "-f", "rawvideo", "-"],
                       capture_output=True, timeout=60)
    F = np.frombuffer(r.stdout, np.uint8)
    if F.size < 54 * 96 * 20:
        return None
    F = F.reshape(-1, 96, 54).astype(np.float32)
    c = int(round((t - t0) * 30))
    cons = [float(np.mean(np.abs(F[j] - F[j - 1]))) for j in range(1, len(F))]  # cons[j-1] = jump into frame j
    base = float(np.median(cons))
    th = max(TH_FLASH, K_FLASH * base)
    lo, hi = max(0, c - 5), min(len(cons), c + 8)
    spikes = [j + 1 for j in range(lo, hi) if cons[j] > th]
    gaps = [b - a for a, b in zip(spikes, spikes[1:]) if 1 <= b - a <= MAX_FLASH_F]
    return {"spikes": len(spikes), "gap": min(gaps) if gaps else 0, "base": round(base, 1),
            "th": round(th, 1), "vals": [round(cons[j]) for j in range(lo, hi)]}


def is_flash(fp, seg_before=9.0, seg_after=9.0):
    return bool(fp and fp.get("gap"))


def boundaries_from_keeps(keeps, speed=1.0):
    """גבול חיתוך פנימי בציר הפלט = סוף כל keep (מצטבר), חוץ מהאחרון.

    v8.6 (P0-3): חלוקה ב-speed. שורש: tight_keeps.json נכתב בציר שלפני ההאצה,
    בעוד EXPORT_TIGHT.mp4 כבר עבר setpts/atempo. מאז ש-speed_fit הפך אוטומטי
    על כל סרטון שחרג מ-60ש (המקרה הרגיל), כל הגבולות שנבדקו היו במקומות
    הלא-נכונים — הדוח חילץ פריימים מאמצע קטעים ולא מגבולות חיתוך."""
    sp = float(speed) if speed and float(speed) > 0 else 1.0
    out, acc = [], 0.0
    for k in keeps[:-1]:
        acc += float(k["end"]) - float(k["start"])
        out.append(round(acc / sp, 3))
    return out


def main():
    ap = argparse.ArgumentParser(description="R.E.L visual cut-boundary QA")
    ap.add_argument("--video", required=True)
    ap.add_argument("--keeps", help="tight_keeps.json / keep_segments — לגזירת גבולות")
    ap.add_argument("--edl", help="edl.json (keep_segments) — חלופה ל---keeps")
    ap.add_argument("--out", default=None)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--speed", type=float, default=1.0,
                    help="ההאצה שהוחלה על הווידאו — הגבולות מ---keeps מחולקים בה")
    # v8.6 (P0-3): הכלי היה sys.exit(0) תמיד, ולכן לא יכול היה לחסום שום דבר —
    # 161 שורות בדיקה ויזואלית שהצנרת גם לא בדקה את ה-returncode שלהן.
    # עכשיו: דגלים חד-משמעיים (פריים שחור / תקיעה) מחזירים 1 וחוסמים קידום ל-FINAL.
    # brightness_jump/visual_jump נשארים דיווח — הם שיפוטיים ותלויי-תוכן.
    ap.add_argument("--block-on", default="black_frame,possible_freeze",
                    help="דגלים שגורמים ל-exit 1 (ריק = דיווח בלבד, התנהגות v7)")
    ap.add_argument("--no-flash", action="store_true", help="דילוג על בדיקת L-flash")
    a = ap.parse_args()

    if Image is None:
        print(json.dumps({"ok": False, "error": "PIL לא זמין — הרץ עם venv rel-whisper"}))
        sys.exit(2)

    V = Path(a.video)
    bounds = []
    if a.keeps and Path(a.keeps).exists():
        keeps = json.loads(Path(a.keeps).read_text(encoding="utf-8"))
        bounds = boundaries_from_keeps(keeps, a.speed)
    elif a.edl and Path(a.edl).exists():
        edl = json.loads(Path(a.edl).read_text(encoding="utf-8"))
        bounds = boundaries_from_keeps(edl.get("keep_segments", []))
    else:
        # fallback: scene detection
        r = sh(["ffmpeg", "-i", str(V), "-vf", "select='gt(scene,0.4)',metadata=print",
                "-f", "null", "-"], timeout=300)
        import re as _re
        bounds = [round(float(x), 3) for x in
                  _re.findall(r"pts_time:([\d.]+)", r.stderr)][:40]

    results, sheet_frames = [], []
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(bounds):
            fa, fb = f"{td}/b{i}_a.png", f"{td}/b{i}_b.png"
            fb2 = f"{td}/b{i}_b2.png"
            ok1 = extract(V, t - 0.06, fa)
            ok2 = extract(V, t + 0.06, fb)
            ok3 = extract(V, t + 0.14, fb2)
            if not (ok1 and ok2):
                results.append({"time": t, "flags": ["extract_failed"], "metrics": {}})
                continue
            m1, h1, im1 = img_stats(fa)
            m2, h2, im2 = img_stats(fb)
            flags, metrics = [], {}
            metrics["brightness_delta"] = round(abs(m1 - m2), 1)
            metrics["hist_dist"] = round(hist_dist(h1, h2), 3)
            if abs(m1 - m2) > TH_BRIGHT:
                flags.append("brightness_jump")
            if hist_dist(h1, h2) > TH_HIST:
                flags.append("visual_jump")
            if m2 < TH_BLACK:
                flags.append("black_frame")
            if ok3:
                m3, h3, _ = img_stats(fb2)
                if abs(m2 - m3) < TH_DUP and hist_dist(h2, h3) < 0.01:
                    flags.append("possible_freeze")
            if not a.no_flash:
                sb = t - (bounds[i - 1] if i > 0 else 0.0)
                sa = (bounds[i + 1] - t) if i + 1 < len(bounds) else 9.0
                fp = flash_probe(V, t)
                if fp:
                    metrics["flash"] = fp
                if is_flash(fp, sb, sa):
                    flags.append("flash_frame")
            results.append({"time": t, "flags": flags, "metrics": metrics})
            sheet_frames.append((t, im1, im2, bool(flags)))

        # contact sheet: לפני|אחרי לכל גבול, מסגרת אדומה לחשודים
        if a.sheet and sheet_frames:
            cw, ch = 270, sheet_frames[0][1].height
            rows = len(sheet_frames)
            sheet = Image.new("RGB", (cw * 2 + 30, (ch + 26) * rows), (14, 14, 16))
            from PIL import ImageDraw
            dr = ImageDraw.Draw(sheet)
            for i, (t, im1, im2, bad) in enumerate(sheet_frames):
                y = i * (ch + 26) + 22
                sheet.paste(im1.convert("RGB"), (0, y))
                sheet.paste(im2.convert("RGB"), (cw + 30, y))
                col = (224, 92, 96) if bad else (154, 155, 161)
                dr.text((4, y - 18), f"cut @ {t:.2f}s" + (" ⚠" if bad else ""), fill=col)
                if bad:
                    dr.rectangle([0, y, cw * 2 + 29, y + ch - 1], outline=(224, 92, 96), width=3)
            sheet.save(a.sheet, quality=85)

    flagged = [r for r in results if r["flags"]]
    block_set = {s.strip() for s in (a.block_on or "").split(",") if s.strip()}
    blockers = [r for r in flagged if block_set & set(r["flags"])]
    report = {"video": str(V), "boundaries": results,
              "checked": len(results), "flagged": len(flagged),
              "speed": a.speed, "block_on": sorted(block_set),
              "blockers": [{"time": r["time"], "flags": r["flags"]} for r in blockers],
              "result": "FAIL" if blockers else ("PASS_WITH_WARNINGS" if flagged else "PASS"),
              "thresholds": {"brightness": TH_BRIGHT, "hist": TH_HIST,
                             "black": TH_BLACK, "freeze": TH_DUP}}
    # cut_qa הוא מנוע דיווח: הוא חוסם **רק** על מה ש---block-on ביקש במפורש.
    # הנימוק לכל סוג דגל נכנס לדוח כדי שהראל יראה ברוויו למה זה סומן.
    if GR:
        report["why"] = {f: GR.annotate("cut_qa", f)
                         for f in sorted({x for r in flagged for x in r["flags"]})}
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    print(json.dumps({"ok": not blockers, "result": report["result"],
                      "checked": len(results), "flagged": len(flagged),
                      "blocking": len(blockers),
                      "flags": [(r["time"], r["flags"]) for r in flagged]},
                     ensure_ascii=False))
    sys.exit(1 if blockers else 0)


if __name__ == "__main__":
    main()
