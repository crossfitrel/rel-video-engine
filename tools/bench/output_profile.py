#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""output_profile.py — פרופיל התוצר מול מה שהראל בפועל מאשר (V3, 30.7.26).

═══════════════════════════════════════════════════════════════════════════
למה הכלי הזה קיים
═══════════════════════════════════════════════════════════════════════════
כל השערים בצנרת מודדים את **התוכנית**: פערי-מילים, ערכי `tighten_to`, מספר
החלטות. אבל הראל לא צופה בתוכנית — הוא צופה בקובץ. שלוש פעמים ברצף התברר
שהתוכנית עמדה בכל השערים והתוצר בכל זאת היה פגום:

  · תוכנית של 6.8ש פאוזה ⇒ תוצר עם 15.4ש שקט (הסף היה מכויל 50dB מתחת לדיבור)
  · תוכנית עם פאוזה ארוכה 0.40ש ⇒ תוצר עם 0.76ש (מילה שקטה לא הוצמדה)
  · תוכנית "תקינה" ⇒ 24 תפרים ב-47ש, פי 2.7 מכל סרטון שהראל אישר

**מסקנה: מדידה על התוצר היא לא בונוס, היא השער האמיתי.**

═══════════════════════════════════════════════════════════════════════════
מה נמדד — וכולו מהמדיה, לא מהמטא-דאטה
═══════════════════════════════════════════════════════════════════════════
1. **שקט** — `silencedetect -40dB/0.15ש`: אחוז, מספר מקטעים, הפאוזה הארוכה.
2. **תפרים** — **מאותרים מהווידאו עצמו** (שיאי הבדל-פריים מקומיים), לא
   מזמנים שנגזרו מה-EDL. ⚠️ זה תיקון של טעות אמיתית: משכי הסגמנטים סוחפים
   בין מנועי רינדור, ולכן זמן-תפר מחושב מצביע על פריים שגוי. המדידה השגויה
   הראתה שהתוצר גרוע פי 5 מהמציאות, וכמעט הובילה ל"תיקון" של בעיה לא קיימת.
3. **תמונה קפואה** — חלונות שבהם התנועה <60% מחציון הסרטון.
4. **מוזיקה חשופה** — פערים ≥0.35ש והפרש המפלס בין דיבור למוזיקה.

ההשוואה היא מול `reference_profile.json` — מעטפת שנמדדה מהסרטונים שהראל
אישר ופרסם. **הספים אינם ניחוש; אפשר לגזור אותם מחדש בכל עת.**

שימוש:
  ~/.rel-whisper/bin/python tools/bench/output_profile.py --workdir W
  ~/.rel-whisper/bin/python tools/bench/output_profile.py --build-reference
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))
REF_PATH = TOOLS / "reference_profile.json"

SIL_DB = -40
SIL_MIN = 0.15
STILL_FRAC = 0.60          # מתחת לזה התמונה נחשבת קפואה
STILL_MIN_SEC = 0.80


def sh(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def dur(p):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(p)])
    try:
        return float((r.stdout or "").strip())
    except ValueError:
        return 0.0


def silences(p, db=SIL_DB, d=SIL_MIN):
    r = sh(["ffmpeg", "-nostdin", "-i", str(p), "-af",
            f"silencedetect=n={db}dB:d={d}", "-f", "null", "-"])
    out, cur = [], None
    for ln in (r.stderr or "").splitlines():
        m = re.search(r"silence_start: ([\d.]+)", ln)
        if m:
            cur = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", ln)
        if m and cur is not None:
            out.append((cur, float(m.group(1))))
            cur = None
    return out


def gray_frames(p, fps=30.0, w=160):
    import numpy as np
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(p), "-vf",
                        f"fps={fps},scale={w}:-2", "-pix_fmt", "gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    h = int(w * 1920 / 1080)
    h += h % 2
    n = len(r.stdout) // (w * h)
    if n < 10:
        return None
    return np.frombuffer(r.stdout[:n * w * h], dtype="uint8").reshape(n, h, w).astype("float32")


def seam_spikes(p, n_cuts, fps=30.0):
    """מאתר תפרים **מהווידאו**: n_cuts השיאים המקומיים הגדולים ביותר."""
    import numpy as np
    fr = gray_frames(p, fps)
    if fr is None or n_cuts < 1:
        return [], 0.0
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    med = float(np.median(d)) or 1e-6
    r = d / med
    sel = []
    for i in np.argsort(r)[::-1]:
        if all(abs(int(i) - j) > 8 for j in sel):
            sel.append(int(i))
        if len(sel) >= n_cuts:
            break
    return sorted((float(r[i]) for i in sel), reverse=True), med


def still_windows(p, fps=10.0):
    import numpy as np
    fr = gray_frames(p, fps)
    if fr is None:
        return []
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    win = int(fps)
    if len(d) <= win:
        return []
    roll = np.convolve(d, np.ones(win) / win, mode="valid")
    med = float(np.median(roll)) or 1e-6
    out, run = [], []
    for i, v in enumerate(roll):
        if v < STILL_FRAC * med:
            run.append(i / fps)
        else:
            if run and run[-1] - run[0] >= STILL_MIN_SEC:
                out.append((round(run[0], 2), round(run[-1] + 1.0, 2)))
            run = []
    if run and run[-1] - run[0] >= STILL_MIN_SEC:
        out.append((round(run[0], 2), round(run[-1] + 1.0, 2)))
    return out


def profile(workdir, video=None):
    W = Path(workdir)
    src = Path(video) if video else next(
        (W / n for n in ("FINAL.mp4", "master_v2.mkv", "FINAL_PENDING.mp4")
         if (W / n).exists()), None)
    if src is None:
        return {"ok": False, "error": "אין תוצר למדוד"}
    # ⚠️ שני קבצים שונים לשתי מדידות שונות — וזו לא קוסמטיקה.
    # ‏silencedetect ‎-40dB על FINAL מודד כמעט אפס, כי **מצע המוזיקה יושב מעל
    # הסף**. בבנייה הראשונה של הייחוס זה נתן "שקט 0.0-9.9%" על סרטונים
    # שבפועל יש בהם 13-31% שקט-דיבור. השקט נמדד תמיד על הציר לפני המוזיקה;
    # התפרים והתמונה הקפואה נמדדים על התוצר המסופק.
    speech_src = next((W / n for n in ("EXPORT_TIGHT.mp4", "EXPORT.mp4", "master_v2.mkv")
                       if (W / n).exists()), src)
    D = dur(src)
    sil = silences(speech_src)
    D_sp = dur(speech_src) or D
    tot = sum(b - a for a, b in sil)
    try:
        ks = json.loads((W / "edl.json").read_text(encoding="utf-8"))["keep_segments"]
        n_cuts = max(0, len(ks) - 1)
    except Exception:
        n_cuts = 0
    spikes, _ = seam_spikes(src, n_cuts)
    still = still_windows(src)
    return {
        "ok": True,
        "video": src.name,
        "speech_video": speech_src.name,
        "dur_sec": round(D, 2),
        "silence_sec": round(tot, 2),
        "silence_pct": round(100.0 * tot / D_sp, 1) if D_sp else 0.0,
        "n_silences": len(sil),
        "longest_pause": round(max((b - a for a, b in sil), default=0.0), 2),
        "n_cuts": n_cuts,
        "cuts_per_sec": round(n_cuts / D, 3) if D else 0.0,
        "seam_max": round(spikes[0], 1) if spikes else 0.0,
        "seam_median": round(spikes[len(spikes) // 2], 1) if spikes else 0.0,
        "still_windows": still,
    }


def compare(prof, ref=None):
    ref = ref or (json.loads(REF_PATH.read_text(encoding="utf-8"))
                  if REF_PATH.exists() else None)
    if not ref:
        return [], ["אין reference_profile.json — הריצו --build-reference"]
    env = ref["envelope"]
    ok, bad = [], []
    for key, label in (("silence_pct", "שקט %"), ("longest_pause", "פאוזה ארוכה"),
                       ("cuts_per_sec", "תפרים/ש"), ("seam_median", "תפר חציוני")):
        lo, hi = env[key]["min"], env[key]["max"]
        v = prof.get(key, 0)
        (ok if lo - 1e-9 <= v <= hi + 1e-9 else bad).append(
            f"{label}: {v} (טווח מאושר {lo}–{hi})")
    if prof.get("still_windows"):
        bad.append(f"תמונה קפואה: {len(prof['still_windows'])} חלונות ≥{STILL_MIN_SEC}ש "
                   f"— {prof['still_windows'][:3]}")
    return ok, bad


def envelope_score(prof, ref=None) -> dict:
    """ציון 0-10 **נמדד מהתוצר**, לא ציון שהמודל נותן לעצמו.

    למה זה קיים (הראל, V6 §3.6): הבמאי מדרג את עצמו — 7.43 מול סף 7.5 —
    וציון שהמודל נותן לעצמו אינו מדידה. כאן כל רכיב נגזר מהמעטפת של
    ‏16 סרטונים שהראל אישר: בתוך הטווח = 1.0, ומחוץ לו יורד ליניארית לפי
    כמה רחוק, מנורמל לרוחב הטווח עצמו. אין כאן סף עגול חדש.

    מחזיר גם `components` — כדי שכשהציון נמוך יהיה ברור **מה** הוריד אותו.
    """
    ref = ref or (json.loads(REF_PATH.read_text(encoding="utf-8"))
                  if REF_PATH.exists() else None)
    if not ref:
        return {"score": None, "why": "אין reference_profile.json"}
    env = ref["envelope"]
    comps, total = {}, 0.0
    keys = (("silence_pct", "שקט %"), ("longest_pause", "פאוזה ארוכה"),
            ("cuts_per_sec", "תפרים/ש"), ("seam_median", "תפר חציוני"))
    for key, label in keys:
        lo, hi = float(env[key]["min"]), float(env[key]["max"])
        v = float(prof.get(key, 0) or 0)
        span = max(1e-6, hi - lo)
        if lo <= v <= hi:
            s = 1.0
        else:
            d = (lo - v) if v < lo else (v - hi)
            s = max(0.0, 1.0 - d / span)
        comps[key] = {"label": label, "value": v, "range": [lo, hi],
                      "score": round(s, 3)}
        total += s
    # ── תמונה קפואה: **מדווחת ולא מנוקדת** ────────────────────────────────
    # הגרסה הראשונה שלי כאן הענישה 0.25 לכל חלון, וההרצה הראשונה החזירה
    # ‏0.0/10 על תוצר שכל ארבעת מדדי המעטפת שלו בטווח. זה בדיוק הדפוס שהמדד
    # הזה נועד להחליף: מספר עגול שאיש לא מדד, שמאפס תוצר תקין.
    # אין בייחוס מדידה של "כמה חלונות קפואים יש בסרטון שהראל אישר", ולכן
    # אין בסיס לנקד את זה. מדווח — ואם יתברר שזה ליקוי, יימדד ואז ינוקד.
    stills = len(prof.get("still_windows") or [])
    score = round(10.0 * (total / len(keys)), 2)
    return {"score": score, "components": comps,
            "still_windows": stills,
            "still_note": ("מדווח ולא מנוקד — אין מדידה של חלונות קפואים "
                           "בסרטונים מאושרים. מצלמה סטטית מייצרת אותם לגיטימית"),
            "source": "measured:reference_profile", "n_ref": ref.get("n_projects")}


def build_reference(projects=None):
    """גוזר את המעטפת מהסרטונים שהראל אישר ופרסם. ניתן להרצה מחדש בכל עת."""
    from relvid.paths import work_root
    root = work_root()
    rows = []
    cands = projects or [p.name for p in root.iterdir()
                         if (p / "FINAL.mp4").exists() and (p / "edl.json").exists()]
    for name in cands:
        d = root / name
        if name.startswith(("בדיקת-", "V3-", "_")):
            continue                       # פרויקטי בדיקה אינם ייחוס
        p = profile(d, d / "FINAL.mp4")
        if not p.get("ok") or not (20 <= p["dur_sec"] <= 80) or p["n_cuts"] < 1:
            continue
        p["project"] = name
        rows.append(p)
    if not rows:
        raise SystemExit("לא נמצאו סרטונים מאושרים לבניית ייחוס")
    env = {}
    for k in ("silence_pct", "longest_pause", "cuts_per_sec", "seam_median", "seam_max"):
        vals = sorted(r[k] for r in rows)
        env[k] = {"min": vals[0], "max": vals[-1],
                  "median": vals[len(vals) // 2], "n": len(vals)}
    doc = {"_readme": "מעטפת שנמדדה מסרטונים שהראל אישר ופרסם. כל סף במערכת "
                      "שנוגע לקצב/שקט/תפרים חייב להיגזר מכאן ולא מניחוש. "
                      "לבנייה מחדש: output_profile.py --build-reference",
           "built_at": __import__("time").strftime("%Y-%m-%d %H:%M"),
           "n_projects": len(rows), "envelope": env,
           "projects": [{k: r[k] for k in
                         ("project", "dur_sec", "silence_pct", "longest_pause",
                          "n_cuts", "cuts_per_sec", "seam_median", "seam_max")}
                        for r in rows]}
    REF_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ ייחוס נבנה מ-{len(rows)} סרטונים → {REF_PATH.name}")
    for k, v in env.items():
        print(f"   {k:<16} {v['min']}–{v['max']} (חציון {v['median']})")
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir")
    ap.add_argument("--video", default=None)
    ap.add_argument("--build-reference", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.build_reference:
        build_reference()
        return 0
    if not a.workdir:
        ap.error("--workdir נדרש")
    prof = profile(a.workdir, a.video)
    if not prof.get("ok"):
        print("⚠️ " + prof.get("error", "?"))
        return 0
    ok, bad = compare(prof)
    es = envelope_score(prof)
    out = Path(a.workdir) / "output_profile.json"
    out.write_text(json.dumps({**prof, "in_range": ok, "out_of_range": bad,
                               "envelope_score": es},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(prof, ensure_ascii=False))
        return 0
    mark = "✅" if not bad else "⚠️"
    print(f"{mark} פרופיל תוצר: {prof['dur_sec']}ש · שקט {prof['silence_pct']}% "
          f"(ארוכה {prof['longest_pause']}ש) · {prof['n_cuts']} תפרים "
          f"({prof['cuts_per_sec']}/ש) · תפר חציוני {prof['seam_median']}")
    if es.get("score") is not None:
        print(f"   📐 ציון מעטפת **נמדד**: {es['score']}/10 "
              f"(מ-{es['n_ref']} סרטונים מאושרים) — לא ציון שהמודל נתן לעצמו")
        for k, c in (es.get("components") or {}).items():
            if c["score"] < 1.0:
                print(f"      ↓ {c['label']}: {c['value']} מול "
                      f"{c['range'][0]}–{c['range'][1]} → {c['score']}")
    for m in bad:
        print("   ⚠️  " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
