#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio_mix.py — R.E.L Social Video Editing System
================================================
מיקס מוזיקה/דיבור דטרמיניסטי מבוסס LUFS (EBU R128) — מצע מוזיקה **קבוע** (בלי ducking).

הבעיה שזה פותר:
  גיין באחוזים אף פעם לא עקבי, כי לכל מנגינה יש loudness אינהרנטי שונה.
  ערך גיין שמתאים לטראק אחד יישמע חזק מדי/חלש מדי בטראק אחר.

הפתרון:
  מודדים LUFS של המוזיקה ומנרמלים אותה למצע קבוע (יחס דיבור↔מוזיקה זהה לכל טראק).
  המוזיקה מתנגנת בעוצמה קבועה לכל אורך הסרטון — **בלי ducking** (החלטת הראל 23.6;
  ה-ducking לא נשמע טבעי). הדיבור נשאר ברמתו המקורית (כבר מנורמל בגימור).

תקני יעד (ברירת מחדל, מותאם אינסטגרם/ריל):
  מצע מוזיקה (קבוע)   : -30 LUFS  (~16 LU מתחת לדיבור; נמוך יותר = שקט יותר)
  מיקס סופי           : -14 LUFS, True Peak <= -1 dBTP (alimiter + oversampling)
  אורך                : ננעל לאורך הווידאו (-t) — סאונד מלא לכל האורך, בלי איבוד-זנב

תלות: ffmpeg + ffprobe ב-PATH.

שימוש:
  # מדידת LUFS של קובץ (וידאו/אודיו)
  python3 audio_mix.py measure INPUT

  # מיקס מלא: וידאו (עם דיבור) + טראק מוזיקה -> וידאו סופי מאוזן
  python3 audio_mix.py mix --video IN.mp4 --music TRACK.mp3 --out FINAL.mp4
      [--music-lufs -30] [--final-lufs -14] [--tp-limit 0.84]
"""

import argparse
import json
import os
import re
import subprocess
import sys


def run(cmd):
    # v9.30 (L74): stdin=DEVNULL — ffmpeg שיורש TTY (Desktop Commander) מחכה ל-[q]
    # ונכשל בשלב המוזיקה (26.7.26). היה ידוע ועוקף ב-"< /dev/null" בלבד.
    return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def measure_lufs(path):
    """מדידה דרך loudnorm pass-1 (print_format=json). מחזיר dict: I, TP, LRA, thresh."""
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", path,
        "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    r = run(cmd)
    # ה-JSON האחרון ב-stderr הוא הבלוק של loudnorm
    blocks = re.findall(r"\{[^{}]*\}", r.stderr, re.DOTALL)
    if not blocks:
        raise RuntimeError(f"לא נמצא פלט loudnorm עבור {path}\n{r.stderr[-800:]}")
    data = json.loads(blocks[-1])
    return {
        "I": float(data["input_i"]),
        "TP": float(data["input_tp"]),
        "LRA": float(data["input_lra"]),
        "thresh": float(data["input_thresh"]),
    }


def has_audio(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", path])
    return bool(r.stdout.strip())


def cmd_measure(args):
    m = measure_lufs(args.input)
    print(f"📊 {args.input}")
    print(f"   Integrated : {m['I']:.2f} LUFS")
    print(f"   True Peak  : {m['TP']:.2f} dBTP")
    print(f"   LRA        : {m['LRA']:.2f} LU")
    return 0


def get_duration(path, stream="v:0"):
    r = run(["ffprobe", "-v", "error", "-select_streams", stream,
             "-show_entries", "stream=duration", "-of", "default=nk=1:nw=1", path])
    try:
        return float(r.stdout.strip())
    except ValueError:
        r2 = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=nk=1:nw=1", path])
        return float(r2.stdout.strip())


def music_intro_dip(path, window=2.0, horizon=30.0, drop_db=4.0):
    """v9.30 (L93) — האם הטראק צונח לקטע שקט אחרי הפתיח (הראל 20.7.26: "המוזיקה
    מתחילה מאוחר מדי / ההתחלה שקטה — תגיע לקטע הטוב מהתחלה"). loudnorm מנרמל
    ממוצע ולא פותר דיפ מקומי. **מדווח בלבד** — מציע offset, לא משנה את המיקס
    (שינוי שמיעתי דורש את האוזן של הראל). None = לא נמדד."""
    try:
        import numpy as np
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-t", f"{horizon}", "-i", path,
                            "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                           capture_output=True, stdin=subprocess.DEVNULL)
        x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return None
    n = int(8000 * window)
    if len(x) < n * 4:
        return None
    db = [20 * np.log10(max(1e-6, float(np.sqrt(np.mean(x[i:i + n] ** 2)))))
          for i in range(0, len(x) - n + 1, n)]
    strong = float(np.median(sorted(db)[len(db) // 2:]))       # רמת "הקטע החזק"
    # דיפ רלוונטי = מתחיל ב-8ש הראשונות (זה מה שמתנגן מתחת לפתיחת הסרטון) ונמשך
    # ≥2 חלונות. נמדד 22.9.26: בלי התנאים האלה 65/105 טראקים סומנו — כל breakdown
    # בכל מקום. תקלת 20.7 (513742) = צניחה ב-4ש שנמשכת עד 12ש.
    dips = [k for k, v in enumerate(db[1:], 1)
            if v < strong - drop_db and k * window < 8.0
            and k + 1 < len(db) and db[k + 1] < strong - drop_db]
    if not dips:
        return {"dip": False, "strong_db": round(strong, 1)}
    k0 = dips[0]
    k1 = next((k for k in range(k0, len(db)) if db[k] >= strong - 1.5), None)
    return {"dip": True, "dip_at": round(k0 * window, 1), "strong_db": round(strong, 1),
            "suggested_offset": None if k1 is None else round(k1 * window, 1),
            "profile_db": [round(v, 1) for v in db]}



def music_start_offset(path, need=None, horizon=120.0):
    """v9.47 (L128) — מאיפה הטראק "כבר בקצב". הראל 9.10.26 על Throwdown: "המוזיקה מתחילה
    מאוחר מדי. מהתחלה צריך מוזיקה קצבית". נמדד 9.10.26 על 31 טראקים קלילים: 26 פותחים
    בפתיח רך של 6-45ש (חציון 15ש) — זה מה שהתנגן מתחת לפתיחת כל ריל.
    האלגוריתם: חלונות 0.5ש; strong = אחוזון 75 של ה-dB; offset = החלון הראשון שממנו
    16 החלונות הבאים (8ש) כולם ≥ strong-4.5dB; נסיגה: ממוצע 4ש ≥ strong-3 והחלון עצמו
    ≥ strong-6. need = כמה שניות חייבות להישאר אחרי ה-offset (אורך הווידאו) — אם לא
    נשאר, offset יורד עד שנשאר. None = לא נמדד (אין numpy/קריאה נכשלה) ⇒ 0."""
    try:
        import numpy as np
        sr = 8000
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path,
                            "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                           capture_output=True, stdin=subprocess.DEVNULL)
        x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return None
    win = sr // 2
    k = len(x) // win
    if k < 20:
        return 0.0
    db = np.array([20 * np.log10(max(1e-6, float(np.sqrt(np.mean(x[i * win:(i + 1) * win] ** 2)))))
                   for i in range(k)])
    strong = float(np.percentile(db, 75))
    lim = int(min(k - 8, horizon * 2))
    off = None
    for i in range(0, max(1, min(k - 16, lim))):
        if np.all(db[i:i + 16] >= strong - 4.5):
            off = i * 0.5
            break
    if off is None:
        for i in range(0, max(1, lim)):
            if np.mean(db[i:i + 8]) >= strong - 3 and db[i] >= strong - 6:
                off = i * 0.5
                break
    off = off or 0.0
    total = len(x) / sr
    if need is not None and total - off < need:
        off = max(0.0, total - need)
    return round(off, 2)


def parse_mute(spec, dur=None):
    """'0.0-0.76;2.1-2.4' → [[0.0,0.76],[2.1,2.4]] (חלונות תקינים בלבד, בתוך משך הווידאו)."""
    out = []
    for part in (spec or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part or "-" not in part[1:]:
            continue
        i = part.index("-", 1)
        try:
            a, b = float(part[:i]), float(part[i + 1:])
        except ValueError:
            continue
        if dur is not None:
            b = min(b, float(dur))
        if b - a >= 0.04 and a >= 0:
            out.append([a, b])
    return out

POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music-level-policy.json")


def load_level_policy(path=POLICY_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _has_intro(args, D=None):
    ss = getattr(args, "speech_start", None)
    return bool(ss and ss > 0.3 and (D is None or ss < D - 0.3))


def apply_dialog_relative_levels(args, dialog_i, D=None):
    """L135 — קובע את args.music_lufs/args.speech_lufs יחסית לדיבור הנמדד, ואוכף רצפה.
    מחזיר None כשאין מצב יחסי (מונטאז' בלי דיבור / דיבור לא נמדד)."""
    gs, gi, fl, fli = (getattr(args, k, None) for k in ("gap_speech", "gap_intro", "min_gap", "min_intro_gap"))
    if dialog_i is None or dialog_i < -70 or (gs is None and fl is None):
        return None
    intro = _has_intro(args, D)
    if gs is not None:
        if intro:
            args.speech_lufs = round(dialog_i - gs, 1)
            args.music_lufs = round(dialog_i - (gi if gi is not None else gs - 8.0), 1)
        else:
            args.music_lufs = round(dialog_i - gs, 1)
    speech = (args.speech_lufs if args.speech_lufs is not None else args.music_lufs - 9.0) if intro else args.music_lufs
    clamped = False
    if fl is not None and speech > dialog_i - fl:
        speech, clamped = round(dialog_i - fl, 1), True
    if intro:
        args.speech_lufs = speech
        if fli is not None and args.music_lufs > dialog_i - fli:
            args.music_lufs, clamped = round(dialog_i - fli, 1), True
        if args.music_lufs < speech:          # פתיח לעולם לא שקט מהמצע בדיבור
            args.music_lufs = speech
    else:
        args.music_lufs = speech
    # L137 — תיקון בלולאה סגורה: אם המדידה מצאה שהמצע יצא קרוב לדיבור מהמתוכנן,
    # cmd_mix מריץ שוב פעם אחת עם הזזה בגודל החוסר הנמדד (לא ניחוש).
    nudge = float(getattr(args, "_gap_nudge", 0) or 0)
    if nudge:
        speech = round(speech - nudge, 1)
        args.music_lufs = round(args.music_lufs - nudge, 1)
        if intro:
            args.speech_lufs = speech
    return {"dialog_i": round(dialog_i, 2), "speech_lufs": speech, "intro_lufs": args.music_lufs if intro else None,
            "speech_gap": round(dialog_i - speech, 2), "clamped": clamped}


def bed_filter(args, m, D, envelope=None):
    """L138 — שרשרת המצע אחת לכל המקומות (מיקס, שער מדוד, מעטפת מקומית), כדי שמה שנמדד = מה שנשמע.
    מחזיר את גוף השרשרת בלי תווית קלט/פלט."""
    s = (f"loudnorm=I={args.music_lufs}:TP=-3:LRA=11:linear=true:"
         f"measured_I={m['I']:.2f}:measured_TP={m['TP']:.2f}:measured_LRA={m['LRA']:.2f}:"
         f"measured_thresh={m['thresh']:.2f},aformat=sample_rates=48000:channel_layouts=stereo,"
         f"atrim=0:{D:.3f},afade=t=in:st=0:d=0.3,asetpts=N/SR/TB")
    if _has_intro(args, D):
        sl = args.speech_lufs if args.speech_lufs is not None else (args.music_lufs - 9.0)
        s += f",volume=enable='gte(t,{args.speech_start:.3f})':volume={sl - args.music_lufs:.2f}dB"
    mute_w = parse_mute(getattr(args, "mute", None), D)
    if mute_w:
        expr = "*".join(f"min(1,max(0,max(({a:.3f}-t)/0.04,(t-{b:.3f})/0.08)))" for a, b in mute_w)
        s += f",volume='{expr}':eval=frame"
    if envelope and envelope.get("cmdfile"):
        s += f",asendcmd=f='{envelope['cmdfile']}',volume@relenv=volume=1.0"
    return s


def _short_term_series(inputs, chain, D):
    """ebur128 short-term (חלון 3ש) כל 0.1ש → מערך numpy באורך ceil(D*10). None = לא נמדד."""
    import tempfile
    import numpy as np
    fd, tmp = tempfile.mkstemp(suffix=".r128.txt")
    os.close(fd)
    try:
        r = run(["ffmpeg", "-hide_banner", "-nostats", *inputs, "-filter_complex",
                 f"{chain},ebur128=metadata=1,ametadata=mode=print:key=lavfi.r128.S:file='{tmp}'",
                 "-t", f"{D:.3f}", "-f", "null", "-"])
        with open(tmp, encoding="utf-8", errors="ignore") as fh:
            txt = fh.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if r.returncode != 0:
        return None
    n = int(np.ceil(D * 10)) + 1
    out = np.full(n, -120.0)
    t = None
    for line in txt.splitlines():
        mt = re.search(r"pts_time:([\d.]+)", line)
        if mt:
            t = float(mt.group(1))
            continue
        if "lavfi.r128.S=" in line and t is not None:
            i = int(round(t * 10))
            if 0 <= i < n:
                try:
                    out[i] = max(-120.0, float(line.split("=", 1)[1]))
                except ValueError:
                    pass
    for i in range(1, n):                      # חורים (פריים לא מדויק על 0.1) — ממשיכים את הקודם
        if out[i] <= -120.0 and out[i - 1] > -120.0:
            out[i] = out[i - 1]
    return out


def local_envelope(args, m, D, dialog_i, workdir=None):
    """L138 (הראל 14.10.26, E-Myth: "שוב המוזיקה גבוהה מידיי") — ה-gap האינטגרלי לא מספיק.
    ב-E-Myth הוא היה 20.3 LU, אבל ב-10 השניות האחרונות הקול ירד ל-‎-28 והמצע הקבוע נשאר ‎-37:
    ‎~9 dB בלבד בין קול למוזיקה, בדיוק ב-CTA. כאן: בכל חלון 3ש שיש בו דיבור, המוזיקה לא
    קרובה לקול של אותו חלון יותר מ-local_gap. רק מנמיך (אף פעם לא מגביר), slew ‎6dB/ש
    כדי שלא יישמע כ"דאקינג שואב" (הראל 23.6). None = אין צורך/לא נמדד."""
    lg = getattr(args, "local_gap", None)
    if lg is None:
        return None
    import numpy as np
    voice = _short_term_series(["-i", args.video], "[0:a]aformat=sample_rates=48000:channel_layouts=stereo", D)
    bed = _short_term_series(["-stream_loop", "-1", "-i", args.music], f"[0:a]{bed_filter(args, m, D)}", D)
    if voice is None or bed is None:
        return {"error": "not_measured"}
    n = min(len(voice), len(bed))
    voice, bed = voice[:n], bed[:n]
    speech = (voice >= dialog_i - 12.0) & (voice > -60.0)
    need = np.where(speech, np.maximum(0.0, lg - (voice - bed)), 0.0)
    if float(need.max(initial=0.0)) < 0.3:
        return {"applied": False, "worst_local_gap": round(float((voice - bed)[speech].min()), 2) if speech.any() else None}
    # הרחבה ±0.5ש + slew 0.6dB לצעד (6dB/ש) לשני הכיוונים — ירידה מתחילה לפני, חזרה אחרי
    k = 5
    wide = np.array([need[max(0, i - k):i + k + 1].max() for i in range(n)])
    step = 0.6
    for i in range(1, n):
        wide[i] = max(wide[i], wide[i - 1] - step)
    for i in range(n - 2, -1, -1):
        wide[i] = max(wide[i], wide[i + 1] - step)
    import tempfile
    fd, cmdfile = tempfile.mkstemp(suffix=".relenv.cmd", dir=workdir)   # נתיב ASCII — בלי עברית/רווחים בתוך ה-filtergraph
    os.close(fd)
    lines, last = [], None
    for i in range(n):
        g = round(float(wide[i]), 2)
        if last is None or abs(g - last) >= 0.05:
            lines.append(f"{i / 10:.2f} volume@relenv volume {10 ** (-g / 20):.5f};")
            last = g
    with open(cmdfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    after = voice - (bed - wide)
    return {"applied": True, "cmdfile": cmdfile, "local_gap": lg,
            "seconds_reduced": round(float((wide >= 0.3).sum()) / 10, 1),
            "max_cut_db": round(float(wide.max()), 2),
            "worst_local_gap_before": round(float((voice - bed)[speech].min()), 2),
            "worst_local_gap_after": round(float(after[speech].min()), 2)}


def measure_bed_gap(args, m, D, dialog_i, envelope=None):
    """שער L135 — מרנדר את המצע לבד (אותה שרשרת גיין) ומודד אותו בחלון הדיבור.
    לא סומך על המספר שביקשנו: loudnorm יכול לעבור לדינמי בשקט."""
    intro = _has_intro(args, D)
    ss = args.speech_start if intro else 0.0
    chain = f"[0:a]{bed_filter(args, m, D, envelope)}"
    chain += f",atrim=start={ss:.3f}:end={D:.3f},asetpts=N/SR/TB,loudnorm=print_format=json"
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-stream_loop", "-1", "-i", args.music,
             "-filter_complex", chain, "-t", f"{D + 1:.3f}", "-f", "null", "-"])
    blocks = re.findall(r"\{[^{}]*\}", r.stderr, re.DOTALL)
    if not blocks:
        return None
    bed = float(json.loads(blocks[-1])["input_i"])
    return {"bed_speech_lufs": round(bed, 2), "dialog_i": round(dialog_i, 2), "gap_lu": round(dialog_i - bed, 2)}


def cmd_mix(args):
    if not has_audio(args.video):
        print(f"⚠️  אין ערוץ אודיו ב-{args.video}", file=sys.stderr)
        return 2

    D = get_duration(args.video, "v:0")          # אורך הווידאו = העוגן
    # v9.47 (L128) — מצע שמתחיל בקצב: גוזרים את הטראק מנקודת ה-offset לקובץ זמני,
    # ומשם הכל (מדידה, loudnorm, לולאה) רץ על הגזור — אחרת ה-gain הליניארי נמדד
    # על טראק שכולל פתיח רך ויוצא חזק מהיעד.
    _off_req = getattr(args, "music_offset", None)
    if _off_req not in (None, "", "0", "0.0", "none"):
        try:
            _off = (music_start_offset(args.music, need=D + 1.0) if str(_off_req) == "auto"
                    else float(_off_req))
        except ValueError:
            _off = None
        if _off and _off > 0.05:
            _trim = f"{args.out}.music_from_{_off:.2f}.wav"
            r_t = run(["ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
                       "-ss", f"{_off:.3f}", "-i", args.music, "-vn", "-ar", "48000", "-ac", "2", _trim])
            if r_t.returncode == 0 and os.path.exists(_trim):
                print(f"   offset מוזיקה : {_off:.2f}ש ({'auto' if str(_off_req) == 'auto' else 'ידני'}) — המצע נכנס בקצב מ-0")
                args.music = _trim
        elif str(_off_req) == "auto":
            print("   offset מוזיקה : 0 (הטראק כבר בקצב מההתחלה)")
    v = measure_lufs(args.video)
    m = measure_lufs(args.music)
    print("— לפני —")
    print(f"   דיבור (וידאו): {v['I']:.2f} LUFS  (אורך {D:.2f}s)")
    print(f"   מוזיקה        : {m['I']:.2f} LUFS")
    # L135 (11.10.26) — מפלס יחסי לדיבור + רצפה. עם LUFS מוחלט ה-gap בין דיבור למוזיקה
    # נע 1.7-27.7 LU בין ריליז (הדיבור בקלט נע ‎-10.8 עד ‎-37), ולכן "חזק מדי" חזר שוב
    # ושוב גם כשהמספר במניפסט ירד. מכאן: אם יש דיבור — המוזיקה נקבעת כ-dialog_I - gap,
    # ובכל מקרה לא קרובה לדיבור יותר מהרצפה (music-level-policy.json).
    _gap = apply_dialog_relative_levels(args, v["I"], D)
    if _gap:
        print(f"   מפלס יחסי     : דיבור {v['I']:.1f} → מוזיקה בדיבור {_gap['speech_lufs']:.1f} "
              f"(gap {_gap['speech_gap']:.1f} LU){' · ⛔ נחתך ברצפה' if _gap['clamped'] else ''}")
    _dip = music_intro_dip(args.music)
    if _dip and _dip.get("dip"):
        print(f"⚠️  music_intro_dip: הטראק צונח ב-{_dip['dip_at']}ש מתחת לקטע החזק "
              f"({_dip['strong_db']}dB) — offset מוצע {_dip.get('suggested_offset')}ש (מדווח בלבד)")

    # מצע מוזיקה — ברירת מחדל קבועה (בלי ducking, החלטת הראל 23.6: ducking קודם לא נשמע טבעי).
    # עדכון 20.7.26 (הראל, r4): פתיח מוזיקה בלבד (בלי דיבור מתחרה) נשמע "מחריש אוזניים" גם
    # ב-LUFS נמוך — כי אין מה שימסך אותו. + הראל אהב שהמוזיקה "יורדת" כשמתחיל לדבר (בפועל
    # זה היה מיסוך פסיכואקוסטי, לא ducking אמיתי — המצע היה קבוע). בעקבות זה: כש-speech-start
    # מסופק, יש כעת שני מפלסים אמיתיים — פתיח מתון (music-lufs) ואז ירידה נוספת בזמן דיבור
    # (speech-lufs, נמוך יותר) + fade-in קצר ב-t=0 כדי לרכך את הכניסה. ללא speech-start —
    # ההתנהגות הישנה (מצע קבוע) נשמרת במלואה (backward-compatible).
    #  1) מוזיקה -> loudnorm למצע קבוע (פותר "כל טראק בווליום אחר"), atrim לאורך הווידאו (D)
    #  2) דיבור (0:a) נשאר כפי שהוא (כבר מנורמל בגימור), aformat בלבד
    #  3) amix (normalize=0 כדי לא להחליש)
    #  4) loudnorm סופי + מגביל true-peak ב-oversampling (alimiter)
    # ❗ אורך הפלט ננעל ל-`-t D` (לא `-shortest`) + atrim על המוזיקה — כך אין איבוד-זנב.
    #    באג היסטורי (23.6): `-shortest`+loudnorm על קלט-לופ אינסופי חתכו ~6ש מהסוף → שקט בזנב.
    #
    # 🐛 תיקון 23.7.26 (פידבק הראל: "המוזיקה רועשת מדי, לא שומעים טוב את הדיבור"):
    #    שני ה-loudnorm למעלה (על טראק המוזיקה ועל המיקס הסופי) רצו ב-single-pass —
    #    ברירת המחדל של ffmpeg כשאין measured_* היא נרמול **דינמי** (per-frame gain-riding),
    #    לא גיין ליניארי קבוע. דינמי אומר: בכל קטע שקט (הפסקה בין משפטים, פתיח לפני שהראל
    #    מתחיל לדבר) ה-loudnorm "מנפח" את הגיין כלפי היעד הסופי (-14 LUFS) כי הוא לא יודע
    #    מראש שזה יתמלא בדיבור חזק מאוחר יותר — המוזיקה קופצת לעוצמה קרובה ליעד הסופי
    #    בדיוק ברגעים שאמורה להיות הכי שקטה, ובולעת/חופפת לתחילת הדיבור. זו הסיבה
    #    שהמצע נשמע "רועש מדי" למרות ש-music_lufs=-38 נמוך על הנייר.
    #    תיקון: two-pass ליניארי (linear=true + measured_I/TP/LRA/thresh ממדידה קודמת) —
    #    גיין קבוע אחד לכל האורך, בלי ניפוח דינמי של קטעים שקטים. את מדידת המוזיקה (m)
    #    כבר יש לנו למעלה; את מדידת המיקס-לפני-loudnorm-סופי (premix) מודדים ב-pass נפרד.
    # ברירת מחדל speech_lufs הועמקה 5→9 dB (23.7.26 r2). L138: שרשרת המצע נבנית פעם אחת
    # (bed_filter) ומשמשת גם את השער המדוד וגם את המעטפת המקומית.
    if _has_intro(args, D) and args.speech_lufs is None:
        args.speech_lufs = args.music_lufs - 9.0
    env = local_envelope(args, m, D, v["I"]) if v["I"] > -70 else None
    if env and env.get("applied"):
        print(f"   מעטפת מקומית  : {env['seconds_reduced']}ש הונמכו (עד ‎-{env['max_cut_db']}dB) — "
              f"gap מקומי מינימלי {env['worst_local_gap_before']} → {env['worst_local_gap_after']} LU (L138)")
    elif env and env.get("error"):
        print("   ❌ G_music_local: מדידת חלונות לא הצליחה — לא נמדד ≠ PASS", file=sys.stderr)
        return 3
    fc_pre = (
        f"[1:a]{bed_filter(args, m, D, env)}[mbed];"
        f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[v0];"
        f"[v0][mbed]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[premix]"
    )
    if _has_intro(args, D):
        print(f"   דאקינג        : פתיח {args.music_lufs:.1f} LUFS עד {args.speech_start:.2f}ש → דיבור {args.speech_lufs:.1f} LUFS (הראל 20.7 r4)")
    mute_w = parse_mute(getattr(args, "mute", None), D)
    if mute_w:
        print(f"   השתקת מצע     : {', '.join(f'{a:.2f}-{b:.2f}' for a, b in mute_w)} (hook_fx)")

    # --- PASS 1: רינדור ה-premix (אודיו בלבד, בלי loudnorm סופי) כדי למדוד אותו ---
    premix_wav = f"{args.out}.premix.wav"
    cmd_premix = [
        "ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error",
        "-i", args.video, "-stream_loop", "-1", "-i", args.music,
        "-filter_complex", fc_pre, "-map", "[premix]", "-vn",
        "-ar", "48000", "-ac", "2", premix_wav,
    ]
    r0 = run(cmd_premix)
    pm = None
    if r0.returncode == 0:
        try:
            pm = measure_lufs(premix_wav)
        except Exception:
            pm = None
    try:
        if os.path.exists(premix_wav):
            os.remove(premix_wav)
    except OSError:
        pass  # קובץ זמני בלבד — כשל מחיקה (לדוגמה הרשאות mount) לא אמור להפיל את הריצה
    if r0.returncode != 0 or pm is None:
        print("   ⚠️ מדידת premix נכשלה — נופל חזרה ל-loudnorm דינמי (single-pass) על המיקס הסופי", file=sys.stderr)
        fc = fc_pre.replace("[premix]", "[mix]") + (
            f";[mix]loudnorm=I={args.final_lufs}:TP=-2.0:LRA=11,"
            f"aresample=176400,aformat=channel_layouts=stereo,"
            f"alimiter=limit={args.tp_limit}:attack=5:release=60:level=disabled,aresample=48000[aout]"
        )
    else:
        # --- PASS 2: מיקס סופי — loudnorm ליניארי (measured_*) + alimiter, וידאו copy ---
        fc = fc_pre + (
            f";[premix]loudnorm=I={args.final_lufs}:TP=-2.0:LRA=11:linear=true:"
            f"measured_I={pm['I']:.2f}:measured_TP={pm['TP']:.2f}:measured_LRA={pm['LRA']:.2f}:"
            f"measured_thresh={pm['thresh']:.2f},"
            f"aresample=176400,aformat=channel_layouts=stereo,"
            f"alimiter=limit={args.tp_limit}:attack=5:release=60:level=disabled,aresample=48000[aout]"
        )

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        "-i", args.video,
        "-stream_loop", "-1", "-i", args.music,   # לולאת מוזיקה לכיסוי כל אורך הווידאו
        "-filter_complex", fc,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
        "-t", f"{D:.3f}", args.out,
    ]
    r = run(cmd)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        return 1

    out = measure_lufs(args.out)
    ad = get_duration(args.out, "a:0")
    print("— אחרי —")
    print(f"   מיקס סופי     : {out['I']:.2f} LUFS  (יעד {args.final_lufs})")
    print(f"   True Peak     : {out['TP']:.2f} dBTP")
    print(f"   אורך אודיו     : {ad:.2f}s / וידאו {D:.2f}s")
    # QA gate — מוודא שהסאונד מכסה את כל הווידאו (שלא יחזור באג הזנב)
    if abs(ad - D) > 0.3:
        print(f"   ❌ אזהרה: אורך האודיו ({ad:.2f}) ≠ וידאו ({D:.2f}) — סאונד נחתך בזנב!", file=sys.stderr)
        return 1
    # L135 — שער מדוד: המצע בחלון הדיבור מול הדיבור. גלאי שלא נמדד = לא PASS.
    if _gap or getattr(args, "min_gap", None) is not None:
        g = measure_bed_gap(args, m, D, v["I"], env)
        rec = {"policy": _gap, "measured": g, "min_gap": getattr(args, "min_gap", None),
               "local": {k: v_ for k, v_ in (env or {}).items() if k != "cmdfile"} or None}
        try:
            with open(f"{args.out}.musicgap.json", "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
        except OSError:
            pass
        if g is None:
            print("   ❌ G_music_gap: מדידת המצע נכשלה — לא נמדד ≠ PASS", file=sys.stderr)
            return 3
        tol = float(getattr(args, "gap_tolerance", 0.6) or 0.6)
        print(f"   G_music_gap   : מצע בדיבור {g['bed_speech_lufs']:.1f} · דיבור {g['dialog_i']:.1f} → gap {g['gap_lu']:.1f} LU")
        if args.min_gap is not None and g["gap_lu"] < args.min_gap - tol:
            if not getattr(args, "_gap_nudge", 0):
                # L137 — 11.10.26: ריל שנחתך בדיוק לרצפה נמדד 0.66 LU קרוב מהמבוקש ונכשל ב-0.03.
                # המדידה היא האמת: מזיזים בגודל החוסר הנמדד + 0.3 ומרנדרים פעם אחת. שנייה נכשלת ⇒ חוסם.
                args._gap_nudge = round(args.min_gap - g["gap_lu"] + 0.3, 2)
                args.music_offset = None          # המוזיקה כבר גזורה מה-offset בסבב הראשון
                print(f"   ↻ G_music_gap: נמדד {g['gap_lu']:.1f} < {args.min_gap} — מנמיך את המצע ב-{args._gap_nudge} LU ומרנדר שוב")
                return cmd_mix(args)
            print(f"   ❌ G_music_gap: המוזיקה {g['gap_lu']:.1f} LU מתחת לדיבור < רצפה {args.min_gap} — חזק מדי", file=sys.stderr)
            return 3
    if env and env.get("applied") and env["worst_local_gap_after"] < env["local_gap"] - 1.5:
        print(f"   ❌ G_music_local: חלון שבו המוזיקה {env['worst_local_gap_after']} LU מתחת לקול < {env['local_gap']}", file=sys.stderr)
        return 3
    if env and env.get("cmdfile"):
        try:
            os.remove(env["cmdfile"])
        except OSError:
            pass
    print(f"✅ נשמר: {args.out}  (מוזיקה קבועה, סאונד מלא לכל האורך)")
    if ".music_from_" in str(args.music):          # v9.47 — קובץ הביניים של ה-offset
        try:
            os.remove(args.music)
        except OSError:
            pass
    return 0


def main():
    p = argparse.ArgumentParser(description="R.E.L LUFS-based audio mixer")
    sub = p.add_subparsers(dest="cmd", required=True)

    pm = sub.add_parser("measure", help="מדידת LUFS של קובץ")
    pm.add_argument("input")
    pm.set_defaults(func=cmd_measure)

    px = sub.add_parser("mix", help="מיקס וידאו+מוזיקה מאוזן")
    px.add_argument("--video", required=True)
    px.add_argument("--music", required=True)
    px.add_argument("--out", required=True)
    px.add_argument("--music-lufs", type=float, default=-38.0, help="מפלס פתיח (LUFS); נמוך יותר = שקט יותר. -38 = רקע עדין מתחת לקול (הראל 23.6)")
    px.add_argument("--speech-start", type=float, default=None,
                    help="זמן (ש) שבו הדיבור הראשון מתחיל — אם סופק, המוזיקה יורדת למפלס נמוך יותר (speech-lufs) מרגע זה (דאקינג אמיתי, הראל 20.7 r4). ללא זה = מצע קבוע כתמיד")
    px.add_argument("--speech-lufs", type=float, default=None,
                    help="מפלס מוזיקה בזמן דיבור (LUFS); ברירת מחדל music-lufs-9 אם speech-start סופק (הועמק מ--5, 23.7.26 r2)")
    px.add_argument("--final-lufs", type=float, default=-14.0)
    px.add_argument("--music-offset", default=None,
                    help="v9.47 L128 — 'auto' (music_start_offset) או שניות: מאיפה מתחיל המצע בטראק")
    px.add_argument("--mute", default=None, help="v9.46 חלונות השתקת מצע 'a-b;c-d' (שניות) — music_drop של hook_fx")
    px.add_argument("--tp-limit", type=float, default=0.75, help="ceiling ל-alimiter true-peak (0-1). 0.75≈-2.5dB — מוריד מ-0.84 כי ה-AAC encode אחרי הלימיטר יוצר inter-sample peak שחומק ממנו (נצפה 20.7: 0.84 → TP+0.23dBTP בפועל, קליפינג). ראה local_finish_pipeline.py")
    px.add_argument("--gap-speech", type=float, default=None, help="L135: מוזיקה בזמן דיבור = dialog_I - gap (LU)")
    px.add_argument("--gap-intro", type=float, default=None, help="L135: פתיח בלי דיבור = dialog_I - gap (LU)")
    px.add_argument("--min-gap", type=float, default=None, help="L135: רצפה — המוזיקה בדיבור לעולם לא קרובה יותר מזה (LU)")
    px.add_argument("--min-intro-gap", type=float, default=None, help="L135: רצפה לפתיח (LU)")
    px.add_argument("--gap-tolerance", type=float, default=0.6)
    px.add_argument("--local-gap", type=float, default=None,
                    help="L138: בכל חלון 3ש עם דיבור — המוזיקה לפחות כך מתחת לקול של אותו חלון (LU). מנמיך בלבד")
    px.set_defaults(func=cmd_mix)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
