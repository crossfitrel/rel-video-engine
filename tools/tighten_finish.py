#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tighten_finish.py — פס גימור אקוסטי: מסיר שקטים אמיתיים (silencedetect) בין קטעים,
מצרף ב-single-pass filter_complex (בלי stutter/קפיצה-כפולה של concat copy), ומאיץ קצב אופציונלי.
פותר: (1) שקטים ששרדו כי תזמון-מילים של whisper רופף, (2) קפיצה כפולה במעברים, (3) קצב.

הרצה:
  python3 tighten_finish.py --in ROUGH.mp4 --out ROUGH2.mp4 [--speed 1.1]
     [--keep-sil 0.12] [--noise -30] [--min-sil 0.30] [--intro-keep 0.0] [--tail-keep 0.6]
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

def dur(p):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=nw=1:nk=1",str(p)],capture_output=True,text=True)
    return float(r.stdout.strip() or 0)

def detect_silences(path, noise, mind):
    r = subprocess.run(["ffmpeg","-nostdin","-i",str(path),"-af",
        f"silencedetect=noise={noise}dB:d={mind}","-f","null","-"],
        capture_output=True,text=True)
    sil = []; cur = None
    for line in r.stderr.splitlines():
        m1 = re.search(r"silence_start: (-?[\d.]+)", line)
        m2 = re.search(r"silence_end: (-?[\d.]+)", line)
        if m1 is not None:
            cur = max(0.0, float(m1.group(1)))
        if m2 is not None and cur is not None:
            sil.append((cur, float(m2.group(1)))); cur = None
    if cur is not None:
        sil.append((cur, None))
    return sil

def refine_boundaries(inp, bnd, win=0.2):
    """הגבול בפועל ב-EXPORT זז 1-3 פריימים מסכום ה-keeps (עיגול פריימים מצטבר ב-edl_cut) — מאתרים
    את הקפיצה הגדולה בפועל ב-±win. L105 (E-Myth 51.37: הצמדה לסכום התיאורטי השאירה 2 פריימים)."""
    try:
        import numpy as np
    except ImportError:
        return bnd
    out = []
    for b in bnd:
        t0 = max(0.0, b - win)
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{2 * win:.3f}", "-i", str(inp),
                            "-vf", "fps=30,scale=54:96,format=gray", "-f", "rawvideo", "-"], capture_output=True)
        F = np.frombuffer(r.stdout, np.uint8)
        if F.size < 54 * 96 * 4:
            out.append(b); continue
        F = F.reshape(-1, 96, 54).astype(np.float32)
        d = [float(np.mean(np.abs(F[j] - F[j - 1]))) for j in range(1, len(F))]
        j = int(np.argmax(d)) + 1
        out.append(round(t0 + j / 30.0, 3) if max(d) > 6 else b)
    return out


def snap_keeps(keeps, bnd, snap=0.15, min_len=0.1):
    """L105: קצה keep במרחק <snap מגבול EDL נצמד לגבול (אין שארית פריימים מקליפ שכן)."""
    out, n = [], 0
    for s0, e0 in keeps:
        for b in bnd:
            if b - snap < s0 < b: s0 = b; n += 1
            if b < e0 < b + snap: e0 = b; n += 1
        if e0 - s0 >= min_len:
            out.append((round(s0, 3), round(e0, 3)))
    return out, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--keep-sil", type=float, default=0.12)
    # v8.6: ברירת המחדל יושרה -30 → -40 dB. שורש: הצנרת תמיד העבירה ‎--noise -40
    # במפורש, וההערה בשורה 62 למטה מצהירה "-40dB" — אבל ברירת המחדל הייתה -30,
    # כלומר כל הרצה ידנית של הכלי קיבלה סף אחר מזה שהמערכת כוילה עליו (‎-30dB
    # תופס גם דממת-ביניים בתוך מילה, וזה בדיוק הלקח מ-20.7 שחתך את סוף המילים
    # "חושבים" ו"אחרת"). התנהגות הצנרת לא משתנה — היא ממילא שולחת -40.
    ap.add_argument("--noise", default="-40")
    ap.add_argument("--min-sil", type=float, default=0.30)
    ap.add_argument("--intro-keep", type=float, default=0.0, help="לא לחתוך שקט בתוך N השניות הראשונות (פתיח ויזואלי)")
    ap.add_argument("--tail-keep", type=float, default=0.6, help="להשאיר עד N שניות שקט בסוף (סגיר)")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--protect-words", help="words JSON (whisper) — שקט שחופף מילה לא נחתך (הגנה מחיתוך דיבור שקט; לקח 19.7)")
    ap.add_argument("--word-margin", type=float, default=0.10)
    ap.add_argument("--emit-keeps", help="כתיבת keep_segments ל-JSON (למיפוי-מחדש של תזמוני מילים)")
    ap.add_argument("--xfade", type=float, default=0.0,
                     help="קרוספייד קצר (שניות) בכל תפר הידוק, נגד 'פלאש' קפיצת-פריים (לקח 19.7). 0=כבוי")
    ap.add_argument("--boundaries-edl", help="edl.json — גבולות keep של EXPORT: קצה הידוק במרחק <SNAP מגבול נצמד אליו (L105)")
    ap.add_argument("--snap", type=float, default=0.15)
    a = ap.parse_args()

    D = dur(a.inp)
    sil = detect_silences(a.inp, a.noise, a.min_sil)

    # הגנת דיבור: מחסירים מכל שקט את מרווחי המילים (±margin); נשארים רק
    # תת-קטעים נקיים-ממילים באורך >= min-sil. מונע חיתוך דיבור שקט ש-silencedetect פספס.
    if a.protect_words:
        words = json.loads(Path(a.protect_words).read_text(encoding="utf-8"))
        # לקח 19.7 (ריצות 3-5): גם start וגם end של whisper מרופדים מכדי לשמש מפת-דיבור.
        # לכן: (א) הסינון האנרגטי נעשה בסף שמרני (-40dB) שמפריד דממת-חדר מדיבור שקט;
        # (ב) ההגנה כאן היא נקודתית — לא חותכים על-פני תחילת מילה (±margin) בלבד.
        iv = sorted((max(0.0, float(w["start"]) - a.word_margin),
                     float(w["start"]) + a.word_margin + 0.05)
                    for w in words)
        merged_w = []
        for s, e in iv:
            if merged_w and s <= merged_w[-1][1]:
                merged_w[-1][1] = max(merged_w[-1][1], e)
            else:
                merged_w.append([s, e])
        def carve(s, e):
            free, pos = [], s
            for ws, we in merged_w:
                if we <= pos: continue
                if ws >= e: break
                if ws > pos: free.append((pos, ws))
                pos = max(pos, we)
            if pos < e: free.append((pos, e))
            return [(fs, fe) for fs, fe in free if fe - fs >= a.min_sil]
        carved = []
        for s, e in sil:
            e2 = D if e is None else e
            carved += [(fs, (fe if e is not None or fe < e2 else None)) for fs, fe in carve(s, e2)]
        sil = [(s, e) for s, e in carved]
    ks = a.keep_sil
    # build cut intervals from silences (keep a floor of ks per silence)
    cuts = []
    for s, e in sil:
        if e is None:  # trailing silence to EOF
            e = D
            # keep up to tail-keep of trailing silence
            cstart = s + a.tail_keep
            if cstart < e - 0.02:
                cuts.append((cstart, e))
            continue
        if e <= a.intro_keep:   # inside protected intro
            continue
        cs = max(s + ks/2, a.intro_keep)
        ce = e - ks/2
        if ce - cs > 0.05:
            cuts.append((cs, ce))
    # לקח הראל 19.7 (shina, 4ש אחרונות "בלאגן"): (א) באזור ה-CTA (8ש אחרונות) חותכים
    # רק שקט ארוך (>=0.8ש) — פאוזות קצרות שם הן קצב, לא דד-אייר; (ב) מגבלת צפיפות —
    # מקסימום 2 חיתוכים בכל חלון 5ש; צביר צפוף = שומרים את הגדולים, מוותרים על הקטנים.
    cta_zone = D - 8.0
    cuts = [(cs, ce) for cs, ce in cuts if cs < cta_zone or (ce - cs) >= 0.8]
    cuts.sort()
    limited = []
    for cs, ce in cuts:
        recent = [c for c in limited if cs - c[0] < 5.0]
        if len(recent) >= 2:
            smallest = min(recent, key=lambda c: c[1] - c[0])
            if (ce - cs) > (smallest[1] - smallest[0]):
                limited.remove(smallest)
                limited.append((cs, ce))
            # אחרת מוותרים על החיתוך הנוכחי
        else:
            limited.append((cs, ce))
    cuts = sorted(limited)
    keeps, pos = [], 0.0
    for cs, ce in cuts:
        if cs > pos + 0.04:
            keeps.append((round(pos,3), round(cs,3)))
        pos = max(pos, ce)
    if pos < D - 0.04:
        keeps.append((round(pos,3), round(D,3)))
    # L105 (הראל 23.9, חלבון 15.98): שקט שחוצה גבול EXPORT (סוף קליפ→תחילת קליפ) נחתך עם ריפוד
    # keep_sil/2 — וה-keep הבא מתחיל 0.055ש *לפני* הגבול ⇒ 1-2 פריימים מסוף הקליפ הקודם אחרי חיתוך
    # ההידוק = פלאש. קצה הידוק במרחק <SNAP מגבול EDL נצמד לגבול; שארית <0.1ש נזרקת.
    if a.boundaries_edl and Path(a.boundaries_edl).exists():
        _ks = json.loads(Path(a.boundaries_edl).read_text(encoding="utf-8")).get("keep_segments") or []
        _ks = [(k["start"], k["end"]) if isinstance(k, dict) else (k[0], k[1]) for k in _ks]
        _tot = sum(e - s for s, e in _ks)
        if _ks and abs(_tot - D) < 0.3:
            bnd, acc = [], 0.0
            for s0, e0 in _ks[:-1]:
                acc += e0 - s0; bnd.append(acc)
            bnd = refine_boundaries(a.inp, bnd)
            keeps, nsnap = snap_keeps(keeps, bnd, a.snap)
            print(f"[tighten] L105 snap: {nsnap} קצוות נצמדו לגבולות EDL ({len(bnd)} גבולות)")
        else:
            print(f"[tighten] L105 snap דולג: EDL {_tot:.2f}ש ≠ EXPORT {D:.2f}ש")
    if not keeps:
        sys.exit("no keep segments")
    kept = sum(e-s for s,e in keeps)
    if a.emit_keeps:
        Path(a.emit_keeps).write_text(json.dumps(
            [{"start": s, "end": e} for s, e in keeps]), encoding="utf-8")

    # single-pass filter_complex: trim+concat (seamless), then optional speed
    parts, vlabels, alabels = [], [], []
    for i,(s,e) in enumerate(keeps):
        parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];")
        parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}];")
        vlabels.append(f"[v{i}]"); alabels.append(f"[a{i}]")

    xf = a.xfade if a.xfade and a.xfade > 0 and len(keeps) > 1 else 0.0
    if xf > 0:
        durs_k = [e - s for s, e in keeps]
        xf = min(xf, max(0.02, min(durs_k) * 0.4))

    if xf <= 0:
        inter = "".join(f"[v{i}][a{i}]" for i in range(len(keeps)))
        concat = inter + f"concat=n={len(keeps)}:v=1:a=1[vc][ac];"
        fc = "".join(parts) + concat
        vout, aout = "[vc]", "[ac]"
    else:
        # xfade על הוידאו בלבד בכל תפר הידוק — מרכך "פלאש" קפיצת-פריים (לקח 19.7).
        # האודיו נשאר hard-trim+concat (לא acrossfade): acrossfade בין קטעי דיבור שונים גורם
        # לטבילת-עוצמה אמיתית שנקראת כ"שקט" ע"י ה-gate ונשמעת כגמגום בדיבור (ממצא 19.7).
        durs_k = [e - s for s, e in keeps]
        vlabel, cum = "v0", durs_k[0]
        xfparts = []
        for i in range(1, len(keeps)):
            voff = round(cum - xf, 3)
            vout_l = f"vx{i}"
            xfparts.append(f"[{vlabel}][v{i}]xfade=transition=fade:duration={xf:.3f}:offset={voff:.3f}[{vout_l}];")
            vlabel = vout_l
            cum = cum + durs_k[i] - xf
        atrims = []
        for i, dseg in enumerate(durs_k):
            if i < len(durs_k) - 1:
                atrims.append(f"[a{i}]atrim=0:{(dseg - xf):.3f},asetpts=PTS-STARTPTS[aa{i}];")
            else:
                atrims.append(f"[a{i}]asetpts=PTS-STARTPTS[aa{i}];")
        aconcat = "".join(f"[aa{i}]" for i in range(len(keeps))) + f"concat=n={len(keeps)}:v=0:a=1[aout];"
        fc = "".join(parts) + "".join(xfparts) + "".join(atrims) + aconcat
        vout, aout = f"[{vlabel}]", "[aout]"
    if abs(a.speed-1.0) > 0.001:
        # באג v8.6 (P0-6): השרשרת הזו קיבעה [vc]/[ac] — התוויות של ענף ה-concat.
        # בענף ה-xfade התוויות הן [vx{i}] ו-[aout], ולכן ffmpeg נכשל על תווית שלא
        # קיימת בכל שילוב של --xfade עם --speed. מגיעים לזה משני כיוונים: דגלים
        # מפורשים, וגם speed_fit האוטומטי על כל סרטון שחרג מ-60ש כשה-xfade דלוק —
        # שנפל ל-fail("האצה אוטומטית נכשלה"). עכשיו משתמשים ב-vout/aout בפועל.
        _vin, _ain = vout, aout
        fc += f"{_vin}setpts=PTS/{a.speed}[vs];{_ain}atempo={a.speed}[as];"
        vout, aout = "[vs]", "[as]"
    # תיקון 23.7.26: פסיק-נקודה סוגר בסוף שרשרת ה-filter_complex גורם לגרסאות ffmpeg
    # מסוימות (למשל 4.4.2, apt/Ubuntu) לנסות לפרש שרשרת-פילטר ריקה נוספת אחריו ולהיכשל
    # עם "No such filter: ''" — למרות שהגרף עצמו תקין. לא נדרש ע"י התחביר; מוסר תמיד.
    fc = fc.rstrip(";")
    cmd = ["ffmpeg","-nostdin","-y","-loglevel","error","-i",a.inp,
        "-filter_complex", fc, "-map", vout, "-map", aout,
        "-c:v","libx264","-crf",str(a.crf),"-preset","veryfast","-pix_fmt","yuv420p","-r","30",
        "-c:a","aac","-b:a","192k","-ar","48000","-ac","2","-movflags","+faststart", a.out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg failed: " + r.stderr[-600:])
    outd = dur(a.out)
    print(json.dumps({"ok":True,"in_dur":round(D,2),"kept_before_speed":round(kept,2),
        "out_dur":round(outd,2),"segments":len(keeps),"silences_cut":len(cuts),
        "speed":a.speed}, ensure_ascii=False))

if __name__ == "__main__":
    main()
