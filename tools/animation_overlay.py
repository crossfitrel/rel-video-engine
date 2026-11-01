#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
animation_overlay.py — שילוב אנימציות / B-roll כ-overlay ממורכז על רקע מטושטש, מקומית עם ffmpeg.
CrossFit R.E.L — מסלול גימור ללא Descript credits (כש-prompt_project_agent חסום / אין קרדיטים).

לכל "חלון" זמן בסרטון:
  • האנימציה מוצגת ממורכזת ("מסגרת") ברוחב נתון (ברירת מחדל 900px).
  • הרקע מסביב = עותק מוגדל-לכיסוי + מטושטש של אותה אנימציה, מעט מוכהה.
  • אודיו האנימציה מושתק תמיד — נשמר רק הדיבור המקורי.
  • מחוץ לחלונות מוצג הדובר כרגיל.
אופציונלי: האצת מהירות (--speed) עם setpts+atempo (pitch נשמר) לקיצור אורך מתחת ל-60ש.

הערות:
  • הטיימקודים (START END) הם ב-timeline המקורי של ה-base; אם --speed != 1.0 הם מומרים אוטומטית ל-timeline הפלט.
  • --src-offset N (לפי סדר ה--overlay) = מאיזו שנייה בקובץ האנימציה להתחיל (לבחירת הקטע הנכון).

דוגמאות:
  python3 animation_overlay.py --base karsol.mp4 --out karsol_anim.mp4 \
      --overlay "mayo.mp4" 9 16.5  --overlay "crazy.mp4" 32.5 36
  python3 animation_overlay.py --base klikim.mp4 --out klikim_anim.mp4 --speed 1.15 \
      --overlay "vox.mp4" 24 33.5  --src-offset 16
"""
import argparse, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_ANCHORS = ("בירולים", "brand-assets", "מיכאל לוי", "תוצרי-אנימציה")


def resolve_media(pth: str) -> str:
    """L156 (1.11.26): broll_plan שנבנה במק נושא נתיבי /Users/hayon/...; ב-runner של Actions הקובץ
    יושב באותו נתיב יחסי מתחת לשורש הריפו. ממפים לפי המקטע שאחרי העוגן (כמו canon_lint._resolve, L145).
    בלי זה הבירול נפל בשקט וכל ריל ענן יצא בלי בירול, וה-MG נפל על 'טקסט על פנים'."""
    P = Path(pth)
    if P.exists():
        return str(P)
    parts = P.parts
    for anchor in _ANCHORS:
        if anchor in parts:
            cand = HERE.parent.joinpath(*parts[parts.index(anchor):])
            if cand.exists():
                return str(cand)
    return str(P)

def main():
    ap = argparse.ArgumentParser(description="שילוב אנימציות ממורכזות + רקע מטושטש (R.E.L)")
    ap.add_argument("--base", required=True, help="סרטון הבסיס (הדובר) שכבר עבר עריכה")
    ap.add_argument("--out", required=True, help="קובץ הפלט")
    ap.add_argument("--speed", type=float, default=1.0, help="האצת מהירות (1.0=ללא). מחיל setpts+atempo")
    ap.add_argument("--width", type=int, default=900, help="רוחב האנימציה הממורכזת בפיקסלים")
    ap.add_argument("--blur", type=int, default=22, help="עוצמת טשטוש הרקע (boxblur)")
    ap.add_argument("--crf", type=int, default=20, help="איכות h264 (נמוך=איכותי יותר)")
    ap.add_argument("--overlay", nargs=3, action="append", metavar=("FILE", "START", "END"),
                    required=True, help="קובץ אנימציה + התחלה + סוף (שניות, ב-timeline המקורי)")
    ap.add_argument("--src-offset", action="append", type=float,
                    help="היסט התחלה בקובץ האנימציה (שניות), לפי סדר ה--overlay (ברירת מחדל 0)")
    ap.add_argument("--fade", type=float, default=0.12,
                    help="מעבר רך (שניות) בכניסה וביציאה של כל בירול. v7.8 (25.7.26): "
                         "ההערה החוזרת 'כל פעם שנגמר בירול יש קפיצה מוזרה' נבעה מחיתוך "
                         "אלפא בינארי (enable=between) — הצופה נזרק בפריים אחד מהבירול "
                         "חזרה לדובר באמצע תנועה. 0.12ש כמעט בלתי-מורגש כמעבר אבל מוחק "
                         "את תחושת הקפיצה. 0 = התנהגות ישנה (חיתוך קשה).")
    a = ap.parse_args()

    spd = a.speed
    ov = a.overlay
    offs = (a.src_offset or [])
    offs = offs + [0.0] * (len(ov) - len(offs))

    # --- inputs (כל אנימציה עם -ss משלה אם יש offset) ---
    inputs = ["-i", a.base]
    for i, (f, s, e) in enumerate(ov):
        if offs[i] and offs[i] > 0:
            inputs += ["-ss", str(offs[i])]
        # v9.16 (הראל 18.8.26: "בסוף הסרטון יש 2 שניות של תמונה קפואה").
        # השורש: הקלט המשני נפתח בלי `-t`, ולכן הוא ארוך בהרבה מהחלון שלו.
        # ‏`eof_action=repeat` (v8.4) מחזיק את הפריים האחרון של **הבסיס** עד
        # שכל הקלטים נגמרים — כך שבירול אחרון עם footage עודף מאריך את
        # הפלט מעבר לווידאו. נמדד: EXPORT_TIGHT 35.58ש → EXPORT+BROLL 37.20ש,
        # ‏1.62ש של פריים קפוא בזנב. חותכים כל קלט לאורך החלון + מרווח
        # ביטחון של 0.10ש, כדי ש-repeat עדיין יהיה לו פריים להחזיק בתפר.
        inputs += ["-t", f"{(float(e) - float(s)) / spd + 0.10:.3f}", "-i", resolve_media(f)]

    # --- filtergraph ---
    fc = []
    if spd != 1.0:
        fc.append(f"[0:v]setpts=PTS/{spd}[bv]")
        cur = "[bv]"
    else:
        cur = "[0:v]"

    for i, (f, s, e) in enumerate(ov):
        idx = i + 1
        os_, oe_ = float(s) / spd, float(e) / spd   # חלון ב-timeline הפלט
        # מעבר רך לא יבלע יותר מ-25% מחלון בירול קצר
        fd = min(a.fade, max(0.0, (oe_ - os_) * 0.25)) if a.fade > 0 else 0.0
        # v8.3 (הראל 25.7.26): "צריך מעבר ישיר מבירול לבירול, בלי חזרה אליי
        # ביניהם." שורש: fade עם alpha=1 מוריד את *שקיפות הבירול* — ומתחתיו
        # נחשף הבסיס, כלומר הפנים. בין שני בירולים צמודים זה יצר ~0.24ש שבהן
        # הראל "מהבהב" בין הקליפים. לכן: fade רק בקצוות החיצוניים של רצף —
        # כניסה מהפנים ויציאה אליהם. בגבול משותף בין שני בירולים = קאט חד.
        eps = 0.05
        adj_prev = i > 0 and abs(float(ov[i - 1][2]) / spd - os_) <= eps
        adj_next = i + 1 < len(ov) and abs(float(ov[i + 1][1]) / spd - oe_) <= eps
        fd_in = 0.0 if adj_prev else fd
        fd_out = 0.0 if adj_next else fd
        fc.append(f"[{idx}:v]split[a{i}][b{i}]")
        fc.append(f"[a{i}]scale=1080:1920:force_original_aspect_ratio=increase,"
                  f"crop=1080:1920,boxblur={a.blur}:1,eq=brightness=-0.12[bg{i}]")
        fc.append(f"[b{i}]scale={a.width}:-2[fg{i}]")
        tail = ""
        if fd_in > 0 or fd_out > 0:
            tail = ",format=yuva420p"
            if fd_in > 0:
                tail += f",fade=t=in:st={os_:.3f}:d={fd_in:.3f}:alpha=1"
            if fd_out > 0:
                tail += f",fade=t=out:st={(oe_ - fd_out):.3f}:d={fd_out:.3f}:alpha=1"
        fc.append(f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2:shortest=1,"
                  f"setpts=PTS-STARTPTS+{os_}/TB{tail}[ov{i}]")
        # v8.4 (הראל 26.7.26) — eof_action: pass → repeat.
        # באג נעול שנמדד פריים-פריים: קליפ בירול של 3.6ש ב-30fps הוא 108
        # פריימים, והפריים האחרון מוצג ב-oe_-0.033. הבסיס מבקש פריים גם ב-
        # oe_-0.007, שם הקלט המשני כבר ב-EOF — ועם eof_action=pass ffmpeg
        # מעביר את **הבסיס**, כלומר בדיוק פריים אחד של הפנים בכל תפר. זה מה
        # שהראל ראה כ"רואים אותי בין בירול לבירול" גם כשהתוכנית הראתה חור=0
        # (הפער לא היה בתכנון אלא בקידוד). repeat מקפיא את הפריים האחרון של
        # הבירול במקום לחשוף את הבסיס ⇒ חשיפת-פנים בתפר היא בלתי-אפשרית
        # מבנית. מחוץ לחלון ה-enable ממילא מכבה את ה-overlay, אז אין דליפה.
        fc.append(f"{cur}[ov{i}]overlay=0:0:enable='between(t,{os_:.3f},{oe_:.3f})':"
                  f"eof_action=repeat[v{i}]")
        cur = f"[v{i}]"

    if spd != 1.0:
        fc.append(f"[0:a]atempo={spd}[ba]")
        amap = "[ba]"
    else:
        amap = "0:a"

    # אודיו: כשאין שינוי מהירות אין שום סיבה לקודד מחדש (הבירולים מושתקים ממילא) —
    # copy חוסך זמן ומונע דור-קידוד נוסף (v7.8).
    acodec = ["-c:a", "aac", "-b:a", "160k"] if spd != 1.0 else ["-c:a", "copy"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-nostdin", *inputs,
           "-filter_complex", ";".join(fc),
           "-map", cur, "-map", amap,
           "-c:v", "libx264", "-crf", str(a.crf), "-preset", "veryfast",
           "-pix_fmt", "yuv420p", *acodec,
           "-movflags", "+faststart", a.out]
    print(f"[animation_overlay] base={a.base} speed={spd} overlays={len(ov)} "
          f"fade={a.fade} -> {a.out}")
    sys.exit(subprocess.run(cmd).returncode)

if __name__ == "__main__":
    main()
