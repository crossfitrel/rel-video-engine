#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""candidates.py — מרחב ההחלטות הדיסקרטי (V2 שלב 1).

═══════════════════════════════════════════════════════════════════════════
העקרון שכל שאר V2 נשען עליו
═══════════════════════════════════════════════════════════════════════════
מודל שמייצר טיימקודים בעברית מול ASR עברי הוא מרשם להזיות: גם מודל טוב יטעה
ב-0.3ש, וזה חותך מילה. לכן **המודל לא רואה זמן רציף.** השכבה הדטרמיניסטית
מונה כאן את כל נקודות העריכה האפשריות ומצמידה לכל אחת וקטור מאפיינים נמדדים;
המודל **בוחר ומתייג** מתוך סט סופי.

מה זה קונה:
  * טיימקוד הזוי — **בלתי אפשרי מבנית** (כל זמן מגיע מגבול מילה מ-Whisper)
  * הפלט ולידטבילי ודטרמיניסטי לקומפילציה ל-EDL
  * עלות טוקנים חסומה (~60-140 מועמדים לסרטון)
  * המודל עוסק בשיפוט — מה שהוא טוב בו — ולא בחישוב

═══════════════════════════════════════════════════════════════════════════
מה נמדד, ולמה דווקא זה
═══════════════════════════════════════════════════════════════════════════
הקאנון עצמו מתעד את הקיר שאי אפשר לעבור עם הכלים של v1
(`edl-policy.json`, `_notes`):
  "מבט-למטה/לא-מוכן אחרי חיתוך — זו בעיית **שפת-גוף**, לא שקט.
   אין דרך אוטומטית לזהות זאת עדיין"
זו הודאה מדויקת: הבעיה חזותית-סמנטית והכלים אקוסטיים-לקסיקליים. לכן כאן
נמדדים גם מאפיינים **חזותיים** (תנועה, פנים, שינוי סצנה) לצד האקוסטיים —
כדי שלמודל יהיה על מה לשפוט "האם הרגע הזה נראה טוב לחתוך בו".

כל המאפיינים נמדדים בשלוש מעברים על המדיה בלבד (אודיו/סצנות/פריימים),
כולם מקביליים, ~4-8ש לסרטון של דקה על M4.

stdlib + numpy + opencv (שניהם כבר ב-venv rel-whisper) + ffmpeg. אין מודל כאן.

שימוש:
  ~/.rel-whisper/bin/python tools/candidates.py --workdir W [--out candidates.json]
  ~/.rel-whisper/bin/python tools/candidates.py --workdir W --summary
"""
from __future__ import annotations
import argparse, json, math, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SR = 16000          # קצב דגימה לניתוח אודיו
HOP = 0.010         # 10ms — רזולוציית מעטפת האנרגיה
FRAME_FPS = 8.0     # דגימת פריימים לניתוח חזותי
VIS_W = 180         # רוחב הפריים לניתוח (מספיק לתנועה/פנים, זול)

SCHEMA_VERSION = 2   # v2: גבולות מילה מוצמדים לאנרגיה (words_snapped.json)


def sh(cmd, timeout=900):
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, b"", (e.stderr or b"") + b"TIMEOUT")


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def probe_duration(video):
    """משך המדיה בפועל. מקור האמת היחיד לגבול הימני של מרחב המועמדים."""
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(video)], timeout=60)
    try:
        return float((r.stdout or b"").decode("utf-8", "replace").strip())
    except (TypeError, ValueError):
        return 0.0


# ═════════════════════════════════════════════════ מעבר 1: אנרגיית אודיו
def audio_envelope(video: Path):
    """מעטפת RMS ב-dBFS ברזולוציית 10ms, ממעבר יחיד על האודיו.

    למה לא silencedetect: הוא מחזיר טווחים בינאריים מעל/מתחת לסף, ולכן אי אפשר
    לשאול ממנו "כמה שקט היה בפער הזה" או "האם יש נשימה". מעטפת מלאה עונה על
    כל השאלות בבת אחת ועולה מעבר אחד. (הלקח מ-v1: אותו silencedetect רץ
    פעמיים בשלבים עוקבים על אותו קובץ.)"""
    import numpy as np
    r = sh(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
            "-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"])
    if r.returncode != 0 or not r.stdout:
        return None, None
    x = np.frombuffer(r.stdout, dtype="<i2").astype(np.float32) / 32768.0
    n = int(SR * HOP)
    if len(x) < n:
        return None, None
    m = (len(x) // n) * n
    fr = x[:m].reshape(-1, n)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)
    db = 20.0 * np.log10(rms + 1e-12)
    # רצפת רעש = אחוזון 10 (החדר, לא הדיבור)
    floor = float(np.percentile(db, 10))
    return db, floor


# ═════════════════════════════════ הצמדת גבולות מילה לאנרגיה שנמדדה
# למה זה קיים (נמדד 30.7.26, פרויקט "בדיקת-V2-לולאה"):
# תזמוני המילים של Whisper **מרופדים** — המילה "שלכם" מקבלת 5.28→6.00 בעוד
# האודיו שלה דועך כבר ב-5.74. התוצאה: מרחב המועמדים, שנבנה מגבולות מילה,
# לא רואה 4.66ש של שקט אקוסטי אמיתי ב-10 מקטעים — כי כל אחד מהם יושב
# *בתוך* מה ש-Whisper קורא לו מילה. זה בדיוק השקט ש-`tighten` היה מקצץ
# מאחורי גבו של הבמאי (4.92ש), ולכן הקצב הסופי נקבע ע"י מנוע הכללים הישן.
# הצמדה כאן חושפת +4.36ש לשיפוט הבמאי ⇒ הופכת את `tighten` למיותר.
# ── כיול הסף (תוקן 30.7.26 אחרי פידבק "יותר מדי שתיקות") ──
# הגרסה הראשונה חישבה `floor + 8`. על חומר אמיתי: רצפה ‎-96.2dB ⇒ סף ‎-88.2dB,
# בעוד **הדיבור עצמו יושב על ‎-34dB** ו-`silencedetect` — השער שכל שאר המערכת
# מודדת בו — עובד ב-‎-40dB. כלומר הסף היה 50dB מתחת לדיבור וראה אך ורק שקט
# דיגיטלי. תוצאה נמדדת: המערכת חשפה 21.2ש פער בעוד הכלי הבלתי-תלוי מוצא 29.0ש,
# והתוצר יצא 28.1% שקט ב-30 מקטעים.
# **הסף חייב להיות יחסי לדיבור, לא לרצפה.** `דיבור(p80) - 8dB` נותן כאן ‎-42.2
# ומסכים עם silencedetect. הרצפה נשארת כרצפה תחתונה למקרה של הקלטה שקטה.
SNAP_THR_UNDER_SPEECH = 8.0  # dB מתחת למפלס הדיבור = כבר לא דיבור
SNAP_THR_OVER_FLOOR = 8.0    # רצפה תחתונה מוחלטת (הקלטה נקייה במיוחד)
SNAP_THR_CEILING = -35.0     # לא מעל זה — אחרת חותכים זנבות עיצורים
SNAP_MAX_SHIFT = 1.20        # לא מזיזים גבול יותר מזה (שמרנות מול ASR רועש)
SNAP_MIN_WORD = 0.08         # מילה לא מתכווצת מתחת לזה
SNAP_MIN_RUN = 0.10          # שקט חייב להיות רצוף לפחות 100ms כדי להיחשב
SNAP_TAIL_PAD = 0.04         # משאירים 40ms של דעיכה אחרי ההוֹפּ הרועש האחרון.
#                              כויל 0.06→0.04 (30.7.26): הריפוד סימטרי, ולכן כל
#                              פער נמדד רחב ב-2×pad ממה שהתוכנית חשבה — על 24
#                              פערים זה ניפח את השקט הנמדד ב-~2.9ש.


def snap_threshold(db, floor):
    """סף ההצמדה — יחסי לדיבור, חסום ברצפה ובתקרה."""
    import numpy as np
    speech = float(np.percentile(np.asarray(db), 80))
    return max(floor + SNAP_THR_OVER_FLOOR,
               min(SNAP_THR_CEILING, speech - SNAP_THR_UNDER_SPEECH))


def snap_words_to_audio(words, db, floor):
    """מחזיר (מילים_מוצמדות, סטטיסטיקה). לא נוגע בטקסט — רק ב-start/end.

    שמרני בכוונה: לא מזיז יותר מ-SNAP_MAX_SHIFT, לא מכווץ מתחת ל-SNAP_MIN_WORD,
    לא נכנס לתחום המילה השכנה, ומשאיר SNAP_TAIL_PAD של דעיכה בכל קצה.
    כשאין מעטפת — מחזיר את הקלט כמו שהוא.
    """
    if db is None or floor is None or not words:
        return list(words), {"snapped": 0, "exposed_sec": 0.0, "available": False}
    thr = snap_threshold(db, floor)
    n = len(db)
    run = max(1, int(SNAP_MIN_RUN / HOP))

    out, moved, exposed = [], 0, 0.0
    for k, w in enumerate(words):
        s, e = float(w["start"]), float(w["end"])
        lo = float(words[k - 1]["end"]) if k > 0 else 0.0
        hi = float(words[k + 1]["start"]) if k + 1 < len(words) else e
        ns, ne = s, e
        # ── סף יחסי-למילה כשהמילה כולה חלשה מהסף הגלובלי (30.7.26) ──
        # נמדד: המילה "שרציתם" (25.12→26.00) נאמרה בשקט — השיא שלה ‎-45.6dB,
        # מתחת לסף הגלובלי ‎-42.2. הסריקה לאחור רצה עד תחילת המילה, הגנת
        # SNAP_MIN_WORD בלמה נכון את מחיקתה — **אבל אז ויתרנו גם על 0.87ש
        # השקט שאחריה.** התוצאה: הפאוזה היחידה בתוצר שעברה 0.65ש (0.76ש).
        # התיקון: למילה חלשה נגזר סף משלה מהשיא שלה עצמה.
        _i0, _i1 = max(0, int(s / HOP)), min(n, int(e / HOP) + 1)
        thr_w = thr
        if _i1 > _i0:
            wpeak = max(db[_i0:_i1])
            if wpeak <= thr and wpeak > floor + 10:
                thr_w = max(floor + 6, wpeak - 8.0)

        def loud(i, _t=thr_w):
            return 0 <= i < n and db[i] > _t

        # קצה ימני: לאחור עד ההוֹפּ הרועש האחרון, אם יש רצף שקט אמיתי
        i1 = min(n - 1, int(e / HOP))
        i = i1
        while i > int(s / HOP) and not loud(i):
            i -= 1
        cand_e = round((i + 1) * HOP + SNAP_TAIL_PAD, 3)
        if e - cand_e >= SNAP_MIN_RUN and e - cand_e <= SNAP_MAX_SHIFT and cand_e - s >= SNAP_MIN_WORD \
           and all(not loud(j) for j in range(int(cand_e / HOP), min(i1, int(cand_e / HOP) + run))):
            ne = cand_e
        # קצה שמאלי: קדימה עד ההוֹפּ הרועש הראשון
        i0 = max(0, int(s / HOP))
        i = i0
        while i < int(ne / HOP) and not loud(i):
            i += 1
        cand_s = round(max(0.0, i * HOP - SNAP_TAIL_PAD), 3)
        if cand_s - s >= SNAP_MIN_RUN and cand_s - s <= SNAP_MAX_SHIFT and ne - cand_s >= SNAP_MIN_WORD:
            ns = cand_s
        # אף פעם לא לתוך השכן
        ns = max(ns, lo)
        ne = min(ne, hi) if hi > ns else ne
        if ne - ns < SNAP_MIN_WORD:
            ns, ne = s, e
        if abs(ns - s) > 1e-6 or abs(ne - e) > 1e-6:
            moved += 1
            exposed += (ns - s) + (e - ne)
        out.append({**w, "start": round(ns, 3), "end": round(ne, 3)})
    import numpy as _np
    return out, {"snapped": moved, "exposed_sec": round(exposed, 3),
                 "threshold_db": round(thr, 1),
                 "speech_p80_db": round(float(_np.percentile(_np.asarray(db), 80)), 1),
                 "noise_floor_db": round(float(floor), 1), "available": True}


def db_stats(db, floor, t0, t1):
    """סטטיסטיקת אנרגיה בטווח זמן."""
    import numpy as np
    if db is None:
        return {}
    i0, i1 = max(0, int(t0 / HOP)), min(len(db), int(t1 / HOP))
    if i1 <= i0:
        return {}
    seg = db[i0:i1]
    return {"rms_mean_db": round(float(seg.mean()), 1),
            "rms_max_db": round(float(seg.max()), 1),
            "rms_min_db": round(float(seg.min()), 1),
            "above_floor_pct": round(100.0 * float((seg > floor + 6).mean()), 1)}


# ═════════════════════════════════════════════════ מעבר 2: שינויי סצנה
def scene_changes(video: Path, thresh=0.35):
    r = sh(["ffmpeg", "-nostdin", "-i", str(video), "-vf",
            f"select='gt(scene,{thresh})',metadata=print", "-f", "null", "-"])
    err = (r.stderr or b"").decode("utf-8", "replace")
    return [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", err)]



def clip_boundaries(W: Path):
    """גבולות הקליפים מ-concat.txt — חילוף שוט ודאי (גם כשאותה זווית ו-scene<0.35).

    22.10.26: בגלם של ארבעה קליפים באותו מועדון ffmpeg scene לא מצא אף חילוף,
    ושער קפיצת-התנוחה חסם חיתוך שנופל בדיוק על גבול קליפ (שתי תנוחות משני
    שוטים שונים). הגבול ידוע מהבנייה של INPUT — אין צורך לנחש אותו."""
    cc = W / "concat.txt"
    if not cc.exists():
        return []
    out, t = [], 0.0
    names = re.findall(r"file '([^']+)'", cc.read_text(encoding="utf-8"))
    for n in names[:-1]:
        d = probe_duration(W / n)
        if not d:
            return out
        t += float(d)
        out.append(round(t, 3))
    return out


# ═════════════════════════════════════════════════ מעבר 3: חזותי
def visual_track(video: Path):
    """תנועה גלובלית, תנועת שליש-תחתון (ידיים), ונוכחות פנים — ברזולוציה נמוכה.

    שליש תחתון: ההערה החוזרת של הראל על "מבט-למטה/לא-מוכן" ועל מחוות שנחתכות
    באמצע קשורה לידיים ולראש. תנועה בשליש התחתון היא פרוקסי זול לתנועת ידיים.
    פנים: Haar cascade של opencv — מספיק כדי לדעת *אם* יש פנים ואיפה, לא מי."""
    try:
        import cv2, numpy as np
    except Exception:
        return None
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return None
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(src_fps / FRAME_FPS)))
    casc_path = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
    casc = cv2.CascadeClassifier(casc_path) if Path(casc_path).exists() else None
    out, prev, i = [], None, 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step:
            i += 1
            continue
        ok, fr = cap.retrieve()
        i += 1
        if not ok or fr is None:
            continue
        t = (i - 1) / src_fps
        h, w = fr.shape[:2]
        sc = VIS_W / max(1, w)
        small = cv2.resize(fr, (VIS_W, max(1, int(h * sc))), interpolation=cv2.INTER_AREA)
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        rec = {"t": round(t, 3), "brightness": round(float(g.mean()), 1)}
        if prev is not None:
            d = cv2.absdiff(g, prev).astype("float32") / 255.0
            rec["motion"] = round(float(d.mean()), 4)
            lo = d[int(d.shape[0] * 0.62):, :]
            rec["motion_lower"] = round(float(lo.mean()), 4)
        prev = g
        if casc is not None:
            f = casc.detectMultiScale(g, 1.2, 4, minSize=(18, 18))
            if len(f):
                x, y, fw, fh = max(f, key=lambda b: b[2] * b[3])
                rec["face"] = [round(x / g.shape[1], 3), round(y / g.shape[0], 3),
                               round(fw / g.shape[1], 3), round(fh / g.shape[0], 3)]
        out.append(rec)
    cap.release()
    return out


# ═════════════════════════════════ רציפות תנוחה מעבר לגבול חיתוך
# הקאנון תיעד את זה כקיר: "מבט-למטה/לא-מוכן אחרי חיתוך — זו בעיית שפת-גוף,
# לא שקט. אין דרך אוטומטית לזהות זאת עדיין."
# יש. נמדד 30.7.26 על התוצר שהראל דיווח עליו ("יש רגע שאני מסתכל למטה"):
#   · מרכז הפנים יורד ב->0.035 מהחציון ב-71.07→76.40 — כלומר לאורך כל ה-CTA
#   · החיתוך שלפני ה-CTA (70.98→72.09) מסיר בדיוק את *תחילת* הירידה:
#     לפניו הראש במצב רגיל, אחריו הוא כבר למטה ⇒ קפיצה
#   · pose_delta על 25 החיתוכים: חציון 0.018 · אחוזון-90 0.094 ·
#     החיתוך הזה 0.104 — השני בגודלו בסרטון
# **המסקנה: לא צריך לפסול את החיתוך — צריך לבחור איפה בתוך הפער הוא נופל.**
POSE_SAMPLE_HOP = 0.08       # דגימת תנוחה בתוך פער
POSE_JUMP_WARN = 0.075       # מעל זה הקפיצה נראית לעין (אחוזון-90 נמדד 0.094)


def pose_at(vis, t, tol=0.5):
    """(cx, cy, h) של הפנים בזמן t, או None."""
    if not vis:
        return None
    best, bd = None, tol
    for v in vis:
        if "face" not in v:
            continue
        d = abs(v["t"] - t)
        if d <= bd:
            best, bd = v["face"], d
    if not best:
        return None
    return (best[0] + best[2] / 2.0, best[1] + best[3] / 2.0, best[3])


def pose_delta(vis, t_before, t_after):
    """מרחק מנורמל בין התנוחה משני צידי גבול חיתוך. None כשאין פנים."""
    a, b = pose_at(vis, t_before), pose_at(vis, t_after)
    if a is None or b is None:
        return None
    return round(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 + abs(a[2] - b[2]) * 0.5, 4)


def pose_samples(vis, t0, t1):
    """דגימות תנוחה לאורך פער — הקלט לבחירת נקודת החיתוך ב-`edit_plan`.
    נשמר במועמד אך **לא** נשלח למודל (ראה `_slim_candidate`): זו החלטה
    שהקוד מחשב, לא שיפוט."""
    if not vis:
        return []
    raw, t = [], t0
    while t <= t1 + 1e-6:
        p = pose_at(vis, t, tol=POSE_SAMPLE_HOP * 2)
        if p:
            raw.append([round(t - t0, 3), p[0], p[1], p[2]])
        t += POSE_SAMPLE_HOP
    # ── החלקה: חציון בחלון 3 ──
    # ‏Haar מפספס פריימים ומקפיץ את תיבת הפנים בפריים בודד. בלי החלקה
    # `best_split` בוחר לפי רעש: נמדד ‎30.7.26 שסריקת keep על אותו פער
    # החזירה 0.118 · 0.112 · 0.000 · 0.074 — לא מונוטוני, וה-0.000 היה
    # ארטיפקט של שתי דגימות שנפלו על אותו פריים שזוהה.
    out = []
    for i, p in enumerate(raw):
        w = raw[max(0, i - 1):i + 2]
        med = lambda j: sorted(x[j] for x in w)[len(w) // 2]      # noqa: E731
        out.append([p[0], round(med(1), 4), round(med(2), 4), round(med(3), 4)])
    return out


def vis_range(vis, t0, t1):
    if not vis:
        return {}
    sel = [v for v in vis if t0 - 0.001 <= v["t"] <= t1 + 0.001]
    if not sel:
        near = min(vis, key=lambda v: abs(v["t"] - (t0 + t1) / 2))
        sel = [near]
    mo = [v["motion"] for v in sel if "motion" in v]
    ml = [v["motion_lower"] for v in sel if "motion_lower" in v]
    br = [v["brightness"] for v in sel]
    faces = [v["face"] for v in sel if "face" in v]
    out = {"face_present_pct": round(100.0 * len(faces) / max(1, len(sel)), 0)}
    if mo:
        out["motion_mean"] = round(sum(mo) / len(mo), 4)
        out["motion_max"] = round(max(mo), 4)
    if ml:
        out["motion_lower_mean"] = round(sum(ml) / len(ml), 4)
    if br:
        out["brightness_mean"] = round(sum(br) / len(br), 1)
        out["brightness_delta"] = round(max(br) - min(br), 1)
    if len(faces) >= 2:
        dx = abs(faces[-1][0] - faces[0][0]) + abs(faces[-1][1] - faces[0][1])
        out["face_shift"] = round(dx, 3)
    return out


# ═════════════════════════════════════════════════ שפה
def sentences_from_words(words, gap=0.55):
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and float(w["start"]) - float(words[i - 1]["end"]) > gap:
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [{"i": i, "start": round(float(s[0]["start"]), 3),
             "end": round(float(s[-1]["end"]), 3),
             "text": " ".join(str(w["word"]) for w in s),
             "n_words": len(s)} for i, s in enumerate(out)]


def norm_he(t):
    return re.sub(r"[^א-ת0-9a-z ]", "", str(t).lower()).strip()


def take_similarity(sents, i, look=6):
    """דמיון המשפט לקודמיו — זיהוי טייק חוזר. difflib, כמו ב-v1, כדי שהמודל
    יראה בדיוק את אותו מספר שהמנוע הדטרמיניסטי רואה."""
    a = norm_he(sents[i]["text"])
    best, best_j = 0.0, None
    for j in range(max(0, i - look), i):
        b = norm_he(sents[j]["text"])
        if len(a.split()) < 3 or len(b.split()) < 3:
            continue
        r = SequenceMatcher(None, a, b).ratio()
        if r > best:
            best, best_j = r, j
    return round(best, 3), best_j


# ═════════════════════════════════════════════════ בניית המועמדים
FILLERS = {"אה", "אהה", "אההה", "אמ", "אממ", "אמממ", "אהם", "אהמ", "המ", "אווה"}


def build(workdir, *, hook_sec=6.0, cta_sec=8.0, min_gap=0.12):
    W = Path(workdir)
    inp = W / "INPUT.mp4"
    words = jload(W / "whisper_raw.json") or []
    if not inp.exists():
        raise FileNotFoundError("אין INPUT.mp4")
    if not words:
        raise ValueError("אין whisper_raw.json")
    words = sorted([w for w in words if str(w.get("word", "")).strip()],
                   key=lambda w: float(w["start"]))
    edl = jload(W / "edl.json", {}) or {}
    # ⚠️ המשך חייב להיגזר מהמדיה, לא מהתמלול (30.7.26).
    # הנוסחה הקודמת הייתה `edl.total_dur or last_word_end + 1.0`. בפרויקט חדש
    # שאין בו עדיין edl.json זה ייצר total=77.04 על קובץ באורך 76.45 — כלומר
    # הקטע האחרון ביקש 0.59ש שלא קיימות. edl_cut החזיר משך קצר מהצפוי ונכשל
    # ("expected 55.56 / actual 55.18"), והאשמה הראשונה שנפלה על עיגול-פריימים
    # הייתה שגויה. מקור האמת הוא ffprobe.
    probed = probe_duration(inp)
    total = float(edl.get("total_dur") or 0) or 0.0
    if probed:
        total = min(total, probed) if total else probed
    if not total:
        total = float(words[-1]["end"]) + 1.0
    existing_cuts = [(float(c["start"]), float(c["end"]))
                     for c in (edl.get("auto_cuts") or []) if c.get("active", True)]

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_env = ex.submit(audio_envelope, inp)
        f_sc = ex.submit(scene_changes, inp)
        f_vis = ex.submit(visual_track, inp)
        db, floor = f_env.result()
        scenes = f_sc.result()
        vis = f_vis.result()
    for _b in clip_boundaries(W):
        if not any(abs(_b - t) < 0.2 for t in scenes):
            scenes.append(_b)
    scenes = sorted(scenes)
    measure_secs = round(time.time() - t0, 1)

    # ── הצמדת גבולות מילה לאנרגיה שנמדדה בפועל ──
    # מכאן והלאה `words` הן המילים המוצמדות. זה מה שהופך את מרחב המועמדים
    # לשלם: כל שקט אקוסטי הופך לפער-מילים גלוי, ולכן ניתן לשיפוט הבמאי.
    # `words_snapped.json` נשמר כי `edit_plan` חייב לאמת מול **אותם** גבולות —
    # אחרת חיתוך תקין ייפסל כ"נוחת בתוך מילה".
    # ⚠️ שומרים את ההתחלה הגולמית של המילה הראשונה **לפני** ההצמדה.
    # ההצמדה רשאית להזיז מילה מאוחר יותר, ו-`open_visual` נבנה מהמילה
    # הראשונה שאחריה — כלומר חלון "לפני הדיבור" שנכנס לתוך הדיבור. ראה
    # L36 ואת הבנייה של open_visual למטה.
    raw_first_start = float(words[0]["start"]) if words else None
    words, snap_stats = snap_words_to_audio(words, db, floor)
    if snap_stats.get("available"):
        (W / "words_snapped.json").write_text(
            json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")

    # קו-הבסיס של גובה הפנים בסרטון — כדי לדעת מה נחשב "מבט למטה"
    _fy = sorted(v["face"][1] + v["face"][3] / 2 for v in (vis or []) if "face" in v)
    _fy_med = _fy[len(_fy) // 2] if _fy else None

    _mo_all = sorted(v["motion"] for v in (vis or []) if "motion" in v)
    _mo_med = _mo_all[len(_mo_all) // 2] if _mo_all else None

    def _motion_norm(vis_, t0, t1):
        """תנועה ממוצעת בטווח, מנורמלת לחציון הסרטון. 1.0 = תמונה טיפוסית."""
        if not _mo_med:
            return None
        sel = [v["motion"] for v in (vis_ or [])
               if "motion" in v and t0 <= v["t"] <= t1]
        return None if not sel else round((sum(sel) / len(sel)) / _mo_med, 3)

    def _pose_range(vis_, t0, t1):
        """כמה התנוחה זזה לאורך הפער כולו. גדול ⇒ אין פיצול 'בטוח',
        וצריך להחליט אחרת (לקצר, להאריך, או לכסות)."""
        ps = pose_samples(vis_, t0, t1)
        if len(ps) < 2:
            return None
        ys = [p[2] for p in ps]
        xs = [p[1] for p in ps]
        return round(max(max(ys) - min(ys), max(xs) - min(xs)), 4)

    def _face_low(vis_, t):
        """האם הפנים נמוכות מהחציון ב->0.035 — הפרוקסי ל'מבט למטה'."""
        if _fy_med is None:
            return None
        p = pose_at(vis_, t, tol=0.35)
        return None if p is None else bool(p[1] > _fy_med + 0.035)

    sents = sentences_from_words(words)
    sent_of_word = {}
    for s in sents:
        for k, w in enumerate(words):
            if s["start"] - 0.001 <= float(w["start"]) <= s["end"] + 0.001:
                sent_of_word[k] = s["i"]

    def rate_around(k, n=3):
        lo, hi = max(0, k - n), min(len(words), k + n + 1)
        if hi - lo < 2:
            return None
        span = float(words[hi - 1]["end"]) - float(words[lo]["start"])
        return round((hi - lo) / span, 2) if span > 0.2 else None

    cands = []

    # ── סוג 1: פער בין מילים ──
    for k in range(len(words) - 1):
        a, b = words[k], words[k + 1]
        ge, gs = float(a["end"]), float(b["start"])
        gap = round(gs - ge, 3)
        if gap < min_gap:
            continue
        si, sj = sent_of_word.get(k), sent_of_word.get(k + 1)
        in_gap = db_stats(db, floor, ge, gs)
        pre = db_stats(db, floor, max(0, ge - 0.35), ge)
        post = db_stats(db, floor, gs, gs + 0.35)
        v = vis_range(vis, ge, gs)
        # נשימה: יש אנרגיה מעל הרצפה בפער, אבל הרבה מתחת לדיבור
        breath = bool(in_gap and pre and
                      in_gap.get("rms_mean_db", -99) > floor + 4 and
                      in_gap.get("rms_mean_db", -99) < pre.get("rms_mean_db", 0) - 12)
        near = min([min(abs(ge - s), abs(gs - e)) for s, e in existing_cuts], default=None)
        cands.append({
            "candidate_id": f"gap_{k:04d}",
            "kind": "inter_word_gap",
            "t_start": round(ge, 3), "t_end": round(gs, 3),
            "prev_word": str(a["word"]), "next_word": str(b["word"]),
            "features": {
                "gap_sec": gap,
                "sentence_boundary": si != sj,
                "prev_ends_question": str(a["word"]).strip().endswith("?"),
                "prev_is_filler": norm_he(a["word"]) in FILLERS,
                "next_is_filler": norm_he(b["word"]) in FILLERS,
                "rms_in_gap_db": in_gap.get("rms_mean_db"),
                "rms_before_db": pre.get("rms_mean_db"),
                "rms_after_db": post.get("rms_mean_db"),
                "noise_floor_db": round(floor, 1) if floor is not None else None,
                "gap_is_true_silence": bool(in_gap and floor is not None and
                                            in_gap.get("rms_mean_db", 0) <= floor + 4),
                "breath_detected": breath,
                "speech_rate_before_wps": rate_around(k),
                "speech_rate_after_wps": rate_around(k + 1),
                "scene_change_in_gap": any(ge - 0.05 <= s <= gs + 0.05 for s in scenes),
                "motion_mean": v.get("motion_mean"),
                "motion_lower_mean": v.get("motion_lower_mean"),
                "face_present_pct": v.get("face_present_pct"),
                "face_shift": v.get("face_shift"),
                "brightness_delta": v.get("brightness_delta"),
                "in_hook_window": gs <= hook_sec,
                "in_cta_window": ge >= max(0.0, total - cta_sec),
                "distance_to_nearest_cut_sec": round(near, 3) if near is not None else None,
                "sentence_index": si,
                # רציפות תנוחה: כמה הראש/הפנים זזים אם החיתוך מפוצל חצי-חצי.
                # זה מה שהצופה רואה כ"קפיצה" — ראה pose_delta למעלה.
                # ⚠️ הגרסה הראשונה חישבה כאן `ge+gap/2` מול `gs-gap/2` — שתי
                # נקודות **בתוך** הפער במרחק 0.1ש זו מזו. מספר חסר משמעות,
                # ומסוכן במיוחד כי הוא נשלח למודל. הנכון: הדלתא בגבולות
                # שייווצרו בפועל ב-keep טיפוסי (0.24ש), כלומר מה שהצופה יראה.
                "pose_delta_at_024": (pose_delta(vis, ge + 0.12, gs - 0.12)
                                      if gap > 0.30 else None),
                "pose_range_in_gap": _pose_range(vis, ge, gs),
                "face_low_before": _face_low(vis, ge),
                "face_low_after": _face_low(vis, gs),
                # כמה התמונה חיה **סביב** הפער, ביחס לסרטון כולו.
                # שורש (הראל 30.7.26: "יש איזושהי תקיעה בסוף לפני אם בא לכם"):
                # פאוזה של 0.40ש על תמונה חיה נשמעת כ-beat; אותה פאוזה בדיוק
                # על תמונה קפואה נראית כתקיעה. נמדד שם: תנועה 2.04-2.27 מול
                # חציון 3.84 בסרטון — כלומר כחצי. **הפאוזה זהה, התפיסה שונה.**
                "motion_around_norm": _motion_norm(vis, ge - 0.8, gs + 0.8),
            },
            "pose_profile": pose_samples(vis, ge, gs),
            "hard_constraints": {"min_keep_after_sec": 0.10, "cut_would_touch_word": False},
        })

    # ── סוג 2: משפט שלם (מחיקה / טייק חוזר) ──
    for s in sents:
        sim, ref = take_similarity(sents, s["i"])
        v = vis_range(vis, s["start"], s["end"])
        e = db_stats(db, floor, s["start"], s["end"])
        cands.append({
            "candidate_id": f"sent_{s['i']:03d}",
            "kind": "sentence_span",
            "t_start": s["start"], "t_end": s["end"], "text": s["text"],
            "features": {
                "n_words": s["n_words"],
                "dur_sec": round(s["end"] - s["start"], 3),
                "speech_rate_wps": round(s["n_words"] / max(0.2, s["end"] - s["start"]), 2),
                "duplicate_similarity": sim,
                "duplicate_of_sentence": ref,
                "is_first": s["i"] == 0,
                "is_last": s["i"] == len(sents) - 1,
                "in_hook_window": s["start"] <= hook_sec,
                "in_cta_window": s["end"] >= max(0.0, total - cta_sec),
                "rms_mean_db": e.get("rms_mean_db"),
                "motion_mean": v.get("motion_mean"),
                "face_present_pct": v.get("face_present_pct"),
                "all_words_filler": all(norm_he(w) in FILLERS for w in s["text"].split()),
            },
            "hard_constraints": {"is_hook": s["i"] == 0, "cut_would_touch_word": False},
        })

    # ── סוג 3: חלון פתיחה ויזואלי (לפני המילה הראשונה) ──
    # ⚠️ החלון נגמר במוקדם מבין ההתחלה המוצמדת לגולמית (17.8.26).
    # השורש ב"טיפ-אחד-בטן-בר": ההצמדה הזיזה את "טיפ" מ-6.80 ל-7.14,
    # ‏`open_visual` נבנה כ-0→7.14, הבמאי חתך אותו כשקט-פתיחה — ו-85% מהמילה
    # הראשונה יצאו איתו. `map_words_to_keeps` מפיל מילה שנשאר ממנה פחות מחצי,
    # ולכן הכתובית הראשונה בסרטון הפכה מ"טיפ" ל"אחד" — בפורמט ששמו "טיפ אחד".
    # האודיו עדיין הכיל את שארית המילה, ולכן שער הכיסוי לא ראה כלום: הוא
    # השווה כתוביות מול `words_final` שממנו המילה כבר נעלמה.
    # חלון "לפני הדיבור" לא רשאי להיגמר אחרי שהדיבור התחיל, בשום מדידה.
    first = float(words[0]["start"])
    if raw_first_start is not None:
        first = min(first, raw_first_start)
    if first > 0.3:
        v = vis_range(vis, 0.0, first)
        cands.append({
            "candidate_id": "open_visual",
            "kind": "visual_opening",
            "t_start": 0.0, "t_end": round(first, 3),
            "features": {"dur_sec": round(first, 3),
                         "motion_mean": v.get("motion_mean"),
                         "face_present_pct": v.get("face_present_pct"),
                         "scene_changes": len([s for s in scenes if s < first]),
                         "is_potential_visual_hook": first > 2.5},
            "hard_constraints": {"protected_if_hook": True},
        })

    # ── סוג 3ב: שקט סיום אחרי המילה האחרונה ──
    # למה זה כאן (30.7.26): כשהידוק כבוי תחת --director, אף אחד לא מטפל בקצוות.
    # נמדד על תוצר: 0.68ש דד-אייר בפתיחה ו-0.81ש בסיום — **שתי השתיקות הארוכות
    # בסרטון**, ולשתיהן לא היה מועמד. הבמאי לא יכול היה לגעת בהן גם אם רצה.
    last = float(words[-1]["end"])
    if total - last > 0.20:
        v = vis_range(vis, last, total)
        e = db_stats(db, floor, last, total)
        cands.append({
            "candidate_id": "edge_tail",
            "kind": "edge_tail",
            "t_start": round(last, 3), "t_end": round(total, 3),
            "features": {"dur_sec": round(total - last, 3),
                         "rms_mean_db": e.get("rms_mean_db"),
                         "motion_mean": v.get("motion_mean"),
                         "face_present_pct": v.get("face_present_pct"),
                         "in_cta_window": True},
            "hard_constraints": {"cut_would_touch_word": False},
        })

    # ── סוג 4: חלונות בירול אפשריים (בין משפטים, מחוץ להוק ול-CTA) ──
    # v9.4 — החלון נושא עכשיו גם **ראיה חזותית**. שני שימושים:
    #   1. `motion_norm` נמוך = תמונה כמעט קפואה. עד היום הפתרון היחיד לרגע כזה
    #      היה לקצר את הפאוזה; זה הפתרון הלא-נכון — הליקוי הוא שאין מה לראות,
    #      לא שיש יותר מדי אוויר. כיסוי בבירול הוא הפתרון האמיתי, ולכן חלון
    #      תקוע הוא **המועמד הראשון** לכיסוי (ראה prompts/broll.pick).
    #   2. המשפטים השכנים נשלחים כהקשר: התאמה היא **פר-משפט**, אבל אסור לבחור
    #      קליפ שסותר את מה שנאמר מיד לפני/אחרי.
    for s in sents:
        if s["start"] <= hook_sec or s["end"] >= total - cta_sec:
            continue
        if s["end"] - s["start"] < 1.8:
            continue
        mn = _motion_norm(vis, s["start"], s["end"])
        # ⚠️ **בכוונה בלי `face_present_pct` כאן.** המפתח הזה נמצא ברשימת
        # השדות ש-`_slim_candidate` מעביר למודל, ולכן הוספתו לחלון בירול הייתה
        # משנה את ה-payload של הבמאי — כלומר digest אחר, cache שנפסל,
        # ו-`--backend replay` שמפסיק לשחזר — בלי שום תמורה: שכבת הבירול לא
        # משתמשת בו. אותה מלכודת של "מטא-דאטה משתנה ב-payload של פאס".
        cands.append({
            "candidate_id": f"broll_{s['i']:03d}",
            "kind": "broll_window",
            "t_start": s["start"], "t_end": s["end"], "text": s["text"],
            "features": {"dur_sec": round(s["end"] - s["start"], 3),
                         "sentence_index": s["i"], "n_words": s["n_words"],
                         "motion_norm": mn,
                         # הסף זהה ל-STALL_MOTION_NORM ב-edit_plan (0.70) —
                         # אותה תופעה בדיוק, רק שכאן הפתרון הוא כיסוי ולא קיצוץ.
                         "is_stalled": (mn is not None and mn < 0.70)},
            "prev_text": sents[s["i"] - 1]["text"] if s["i"] > 0 else None,
            "next_text": sents[s["i"] + 1]["text"] if s["i"] + 1 < len(sents) else None,
            "hard_constraints": {"not_on_hook": True, "not_on_cta": True},
        })

    doc = {
        "schema_version": SCHEMA_VERSION,
        "project": W.name,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "measure_secs": measure_secs,
        "source": {"input": "INPUT.mp4", "total_dur": round(total, 3),
                   "n_words": len(words), "n_sentences": len(sents),
                   "words_source": "words_snapped.json" if snap_stats.get("available")
                                   else "whisper_raw.json",
                   "asr_coverage": asr_coverage(words, total, db, floor)},
        "measurement": {
            "audio_envelope": {"hop_sec": HOP, "noise_floor_db": round(floor, 1) if floor is not None else None,
                               "available": db is not None},
            "word_snap": snap_stats,
            "scene_changes": {"threshold": 0.35, "times": scenes, "n": len(scenes)},
            "visual": {"fps": FRAME_FPS, "width": VIS_W, "frames": len(vis or []),
                       "available": bool(vis),
                       "face_frames": len([v for v in (vis or []) if "face" in v])},
        },
        "windows": {"hook_sec": hook_sec, "cta_sec": cta_sec},
        "sentences": sents,
        "counts": {k: len([c for c in cands if c["kind"] == k])
                   for k in ("inter_word_gap", "sentence_span", "visual_opening",
                             "edge_tail", "broll_window")},
        "n_candidates": len(cands),
        "candidates": cands,
    }
    return doc


def asr_coverage(words, total, db, floor):
    """כמה מהדיבור שנמדד באודיו באמת תומלל — ובעיקר: מתי התמלול נגמר.

    ⚠️ למה זה קיים (17.8.26, "דקה-להורים"): faster-whisper החזיר 134 מילים
    שנגמרו ב-155.57ש על קובץ של 181.39ש. ב-24 השניות שאחרי כן היה דיבור אמיתי
    — כולל ה-CTA ("אם הילד שלכם עדיין לא נמצא במסגרת של ספורט, דברו איתנו").
    ‏**התמלול נקטע בשקט.** אף שער לא ראה את זה, כי כל השערים שאלו "האם המילים
    שיש מסונכרנות" ואף אחד לא שאל "האם יש מילים לכל הדיבור".
    הכשל הזה שקוף במיוחד: הבמאי לא יכול לשמור משפט שהוא לא יודע שקיים, ולכן
    התוצר היה יוצא בלי CTA — ואף שער כתוביות לא היה נכשל, כי הכתוביות תואמות
    בדיוק את המילים שכן תומללו.
    כאן מודדים, ומדווחים. אין סף חוסם — ‏RMS אינו VAD, ופודקאסט עם מוזיקת סיום
    היה נחסם לשווא. השער האמיתי הוא שהמספר מגיע לעין.
    """
    out = {"last_word_end": None, "total_dur": round(float(total or 0), 3),
           "last_speech_end": None, "trailing_untranscribed_sec": None,
           "measurable": False}
    if not words:
        return out
    out["last_word_end"] = round(max(float(w["end"]) for w in words), 3)
    if db is None or floor is None or not len(db):
        return out
    # הרגע האחרון שבו האנרגיה מעל רצפת הרעש בבירור — כלומר עוד דיברו שם.
    thr = float(floor) + 12.0
    last_speech = None
    for i in range(len(db) - 1, -1, -1):
        if db[i] is not None and db[i] > thr:
            last_speech = i * HOP
            break
    if last_speech is None:
        return out
    out["measurable"] = True
    out["last_speech_end"] = round(last_speech, 3)
    out["trailing_untranscribed_sec"] = round(max(0.0, last_speech - out["last_word_end"]), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--hook-sec", type=float, default=6.0)
    ap.add_argument("--cta-sec", type=float, default=8.0)
    a = ap.parse_args()
    doc = build(a.workdir, hook_sec=a.hook_sec, cta_sec=a.cta_sec)
    out = Path(a.out) if a.out else (Path(a.workdir) / "candidates.json")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    _cov = (doc.get("source") or {}).get("asr_coverage") or {}
    if _cov.get("measurable") and (_cov.get("trailing_untranscribed_sec") or 0) >= 3.0:
        print(f"⚠️  ASR נקטע: המילה האחרונה ב-{_cov['last_word_end']}ש אבל דיבור "
              f"נמדד עד {_cov['last_speech_end']}ש — "
              f"{_cov['trailing_untranscribed_sec']}ש בלי תמלול. "
              f"הבמאי לא יכול לשמור משפט שאינו יודע שקיים; לבדוק לפני שממשיכים.")
    if a.summary:
        m = doc["measurement"]
        print(f"פרויקט: {doc['project']} · {doc['source']['total_dur']}ש · "
              f"{doc['source']['n_words']} מילים · {doc['source']['n_sentences']} משפטים")
        print(f"מדידה: {doc['measure_secs']}ש · רצפת רעש {m['audio_envelope']['noise_floor_db']}dB · "
              f"{m['scene_changes']['n']} שינויי סצנה · {m['visual']['frames']} פריימים נותחו "
              f"({m['visual']['face_frames']} עם פנים)")
        print(f"מועמדים: {doc['n_candidates']} — {doc['counts']}")
        gaps = [c for c in doc["candidates"] if c["kind"] == "inter_word_gap"]
        br = len([c for c in gaps if c["features"].get("breath_detected")])
        sil = len([c for c in gaps if c["features"].get("gap_is_true_silence")])
        sb = len([c for c in gaps if c["features"].get("sentence_boundary")])
        print(f"  מהפערים: {sb} על גבול משפט · {sil} שקט אמיתי · {br} נשימה מזוהה")
        dups = [c for c in doc["candidates"]
                if c["kind"] == "sentence_span" and c["features"]["duplicate_similarity"] > 0.6]
        print(f"  משפטים חשודים כטייק חוזר (>0.6): {len(dups)}")
    print(f"נשמר: {out}")


if __name__ == "__main__":
    main()
