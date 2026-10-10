#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚠️ כבוי כברירת מחדל (24.9.26): הראל ראה את ההאטה ("פייד מוזר... זז לאט יותר") ודחה.
המדידה הראתה שהפלאשים שהוא תפס היו שבבי הידוק בגבול קליפ — התיקון הקנוני הוא L105
(tighten_finish --boundaries-edl). הכלי נשאר לשימוש ידני בלבד, לעולם לא אוטומטית.

clip_edge_stabilize.py — ייצוב קצוות קליפים (L-flash, הראל 23.9.26).
=====================================================================
שורש: בצילום אייפון רב-קליפי, כל קליפ נפתח ב"לחיצה על הקלטה" (מבט למטה/יד לטלפון)
ונסגר ב"לחיצה על עצירה" (רכינה קדימה). keep אוטומטי (מילה ראשונה −0.2 / מילה אחרונה
+0.3, וכש-Whisper מותח את המילה האחרונה עד סוף הקליפ — עד הקצה) מכניס פריים-שניים
מהתנועה הזו לגבול החיתוך ⇒ "קפיצה מוזרה של קטע כפול" (הראל, 3 סרטונים ב-23.9).

תיקון: במקור (לפני EDL). לכל קליפ מזהים ויזואלית את הפריימים הלא-יציבים בראש
(לפני שהדובר "נוחת" לתנוחת הדיבור) ובזנב (אחרי סוף הדיבור לפי אנרגיית אודיו),
ומחליפים **רק את הווידאו** שלהם ב'האטה רציפה' של הפריימים היציבים הסמוכים (לא הקפאה/מראה/לולאה — ראו rebuild). האודיו לא נגעים בו,
משך כל קליפ זהה עד לפריים ⇒ תמלול/EDL/tight_keeps/תוכנית בירול נשארים תקפים.
תקרה: הקפאת ראש לא נכנסת יותר מ-0.15ש לתוך הדיבור; זנב לא מתחיל לפני סוף הדיבור.

שימוש:  python3 clip_edge_stabilize.py --workdir W [--dry-run]
  דורש: W/concat.txt (רשימת clip_NN.mp4) + W/whisper_raw.json (ציר INPUT).
  פלט:  clip_NN.mp4 מיוצבים (מקור ב-_trash/clips_prestab/), INPUT.mp4 מחדש,
        clip_edge_report.json.  אוכף: cut_qa דגל flash_frame.
"""
import argparse, json, subprocess, shutil, sys
from pathlib import Path
import numpy as np

FPS = 30; W_, H_ = 54, 96
TH_MIN = 9.0; K_BASE = 2.5; HEAD_CAP = 0.15


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, **kw)


def dur(f):
    o = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], text=True)
    return float(o.stdout.strip())


def frames(f):
    p = run(["ffmpeg", "-v", "error", "-i", f, "-vf", f"fps={FPS},scale={W_}:{H_},format=gray",
             "-f", "rawvideo", "-"])
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, H_, W_).astype(np.float32)


def energy(f):
    p = run(["ffmpeg", "-v", "error", "-i", f, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
    a = np.frombuffer(p.stdout, np.int16).astype(np.float32)
    hop = 160  # 10ms
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-6)
    return 20 * np.log10(rms + 1e-6)


def speech_bounds(db):
    peak = np.percentile(db, 99); floor = np.percentile(db, 10)
    th = max(peak - 30, floor + 10)
    idx = np.where(db > th)[0]
    if not len(idx):
        return None, None
    return idx[0] / 100.0, (idx[-1] + 1) / 100.0


def df(a, b):
    return float(np.mean(np.abs(a - b)))


def analyse(clip, words_local):
    F = frames(clip); n = len(F); D = n / FPS
    on, off = speech_bounds(energy(clip))
    if on is None or not words_local or n < 30:
        return {"head_f": 0, "tail_f": n, "n": n, "note": "no speech"}
    fw = min(words_local[0]["start"], on + 0.3); fw = max(fw, on - 0.1)
    # head
    k0 = min(n - 10, int(round((max(fw, on) + 0.15) * FPS)))
    ref = np.median(F[k0:k0 + 9], axis=0)
    base = float(np.median([df(F[j], ref) for j in range(k0, min(k0 + 9, n))]))
    th = max(TH_MIN, K_BASE * base)
    un = [j for j in range(0, k0) if df(F[j], ref) > th]
    head_f = (max(un) + 1) if un else 0
    cap_f = int(round((on + HEAD_CAP) * FPS))
    head_resid = max(0, head_f - cap_f) / FPS
    head_f = min(head_f, cap_f)
    # tail
    t_end = off
    e0 = max(0, int(round((t_end - 0.45) * FPS))); e1 = max(e0 + 3, int(round((t_end - 0.15) * FPS)))
    ref2 = np.median(F[e0:e1], axis=0)
    base2 = float(np.median([df(F[j], ref2) for j in range(e0, min(e1, n))]))
    th2 = max(TH_MIN, K_BASE * base2)
    start_scan = int(round((t_end - 0.05) * FPS))
    un2 = [j for j in range(max(start_scan, head_f + 1), n) if df(F[j], ref2) > th2]
    tail_f = min(un2) if un2 else n
    return {"head_f": int(head_f), "tail_f": int(tail_f), "n": n, "dur": round(D, 3),
            "speech": [round(on, 2), round(off, 2)], "first_word": round(fw, 2),
            "th_head": round(th, 1), "th_tail": round(th2, 1),
            "head_freeze_s": round(head_f / FPS, 3), "tail_freeze_s": round((n - tail_f) / FPS, 3),
            "head_residual_s": round(head_resid, 3)}


MIN_FILL = 2   # ראש/זנב קצר מזה — משאירים


def _stretch(src_label, f0, f1, out_label, n_out, tail=False):
    """פריימים [f0,f1) בחצי מהירות, כל פריים ביניים = ממוצע שני שכנים (dup+tblend) ⇒ בדיוק n_out
    פריימים, אף זוג עוקב לא זהה. minterpolate נפסל: הפיק פחות פריימים ⇒ tpad שכפל 9 זהים (23.9)."""
    a0, a1, skip = (f0 - 1, f1, 1) if tail else (f0, f1 + 1, 0)
    return (f"{src_label}trim=start_frame={a0}:end_frame={a1},setpts=2*(PTS-STARTPTS),fps={FPS},"
            f"tblend=all_mode=average,trim=start_frame={skip}:end_frame={skip + n_out},setpts=PTS-STARTPTS{out_label}")


def rebuild(src, dst, r):
    """מילוי 'האטה רציפה': הראש [0,2h) = הפריימים היציבים [h,2h) בחצי מהירות, ומ-2h הכל אמיתי;
    הזנב [t-tl, n) = [t-tl,t) בחצי מהירות. בלי קפיצה (הרציפות נשמרת בנקודת המפגש) ובלי זוג זהה.
    נבדקו ונפסלו במדידה (23.9, חלבון): clone/מראה ⇒ זוג פריימים זהה ליד הגבול = possible_freeze חוסם;
    לולאה קדימה ⇒ קפיצה אחורה 1-5 פריימים אחרי החיתוך = flash_frame ('קפיצה כפולה').
    מחיר: עד ~0.3ש של חצי-מהירות בתחילת הדיבור (אודיו לא נגוע)."""
    h, t, n = r["head_f"], r["tail_f"], r["n"]
    h = h if h >= MIN_FILL else 0
    tl = n - t if n - t >= MIN_FILL else 0
    if 2 * h > n - 2 * tl:            # קליפ קצר מדי לשניהם — מוותרים על הזנב, ואז מקצרים ראש
        tl = 0
        h = min(h, n // 2 - 1) if h else 0
    parts, chains = [], []
    k = (1 if h else 0) + 1 + (1 if tl else 0)
    srcs = [f"[s{i}]" for i in range(k)]
    chains.append(f"[0:v]fps={FPS},format=yuv420p,split={k}" + "".join(srcs))
    i = 0
    if h:
        chains.append(_stretch(srcs[i], h, 2 * h, "[a]", 2 * h)); parts.append("[a]"); i += 1
    mid0, mid1 = 2 * h, n - 2 * tl
    chains.append(f"{srcs[i]}trim=start_frame={mid0}:end_frame={mid1},setpts=PTS-STARTPTS[b]"); parts.append("[b]"); i += 1
    if tl:
        chains.append(_stretch(srcs[i], n - 2 * tl, n - tl, "[c]", 2 * tl, tail=True)); parts.append("[c]")
    fc = ";".join(chains) + f";{''.join(parts)}concat=n={len(parts)}:v=1:a=0,settb=1/{FPS * 512},setpts=N*512[v]"
    p = run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "0:a:0",
             "-r", str(FPS), "-video_track_timescale", "15360",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy",
             "-movflags", "+faststart", dst], text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-400:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--words", default="whisper_raw.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip", default=r"scr|screen|RPReplay",
                    help="regex לשמות קליפים שאינם צילום מצלמה (הקלטת מסך — שינויי UI אינם 'לחיצה')")
    a = ap.parse_args()
    W = Path(a.workdir).expanduser()
    clips = [W / ln.split("'")[1] for ln in (W / "concat.txt").read_text().splitlines() if ln.startswith("file")]
    words = json.loads((W / a.words).read_text(encoding="utf-8"))
    words = words.get("words", words) if isinstance(words, dict) else words
    bak = W / "_trash" / "clips_prestab"; bak.mkdir(parents=True, exist_ok=True)
    rep, off = [], 0.0
    import re
    for c in clips:
        orig = bak / c.name
        if a.skip and re.search(a.skip, c.name):
            d = dur(c); rep.append({"clip": c.name, "offset": round(off, 3), "skipped": "non-camera"}); off += d
            print(f"{c.name} skipped (non-camera)"); continue
        src = orig if orig.exists() else c          # אידמפוטנטי: תמיד מהמקור
        d = dur(src)
        wl = [dict(w, start=w["start"] - off) for w in words if off <= w["start"] < off + d]
        r = analyse(src, wl); r["clip"] = c.name; r["offset"] = round(off, 3)
        rep.append(r); off += d
        print(f"{c.name} head_freeze={r.get('head_freeze_s', 0):.2f}s tail_freeze={r.get('tail_freeze_s', 0):.2f}s"
              f" resid={r.get('head_residual_s', 0):.2f}", flush=True)
        if a.dry_run:
            continue
        if r["head_f"] < MIN_FILL and r["n"] - r["tail_f"] < MIN_FILL:
            if orig.exists():                        # ריצה קודמת מילאה — מחזירים את המקור
                shutil.copy2(orig, c)
            continue
        if not orig.exists():
            shutil.copy2(c, orig)
        rebuild(orig, c, r)
    (W / "clip_edge_report.json").write_text(json.dumps({"clips": rep}, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    if a.dry_run:
        return
    inp = W / "INPUT.mp4"
    if inp.exists() and not (W / "_trash" / "INPUT_prestab.mp4").exists():
        shutil.copy2(inp, W / "_trash" / "INPUT_prestab.mp4")
    p = run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", W / "concat.txt",
             "-c", "copy", "-movflags", "+faststart", inp], text=True)
    if p.returncode != 0:
        sys.exit("concat failed: " + p.stderr[-300:])
    print("INPUT rebuilt", round(dur(inp), 3))


if __name__ == "__main__":
    main()
