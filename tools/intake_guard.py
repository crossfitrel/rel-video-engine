#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
intake_guard — שלושה שומרים על הגלם לפני שהוא הופך לפרויקט (v9.26, 19.9.26).

שלושתם נולדו בארכיון REL Throwdown 2026 (47 ריליז), ושלושתם אותה משפחה:
**הקלט השתנה או שגוי, והמערכת המשיכה כאילו הכל תקין.**

L68 — קליפ מתוקן לא נכנס לבנייה חוזרת (I2_stale_clip_copy)
    תיקנו קליפ במקור (סיבוב, צנזור קללה בנביחה) ובנו מחדש — אבל בתיקיית העבודה
    ישב עותק `clip_NN.mp4` ישן, וה-INPUT.mp4 + whisper_raw.json נשמרו במטמון.
    הריל נבנה שוב עם הגלם הישן, בלי שגיאה. תיקון: `sync_clip_copy` משווה גודל
    (וגם mtime חדש יותר במקור); שונה ⇒ מעתיק מחדש **ומוחק את כל הנגזרות**
    (INPUT, תמלולים). נגזרת שנשארת היא מטמון שמשקר.

L69 — גלם שצולם בכיוון שגוי (I1_orientation)
    אייפון מחזיק לאורך, אבל הקובץ נשמר landscape עם rotation 180 ⇒ הנגן לא מסובב
    לרוחב, הדמות שוכבת על הצד. מטא-דאטה לבדה לא מספיקה (landscape לגיטימי קיים —
    רקע מטושטש), ולכן **הפריים מכריע**: זיהוי פנים ב-0°/90°/270°. יותר פנים בסיבוב
    ⇒ חשד + פריים לבדיקה + הצעת תיקון. **מדווח ולא חוסם**: נמדד 7/256 חיובי-שגוי
    (ORIENT_EVIDENCE). אין גלאי ⇒ `measured:false`, לא PASS שקט (עיקרון 11).

L70 — turbo+VAD מפספס דיבור רועש על INPUT (P18_caption_density)
    בקליפים רועשים (קהל, מוזיקה ברחבה) ה-VAD זורק דיבור אמיתי, וקטע שנשמר יוצא
    כמעט בלי מילים ⇒ חור בכתוביות. צפיפות < 0.6 מילים/ש בקטע ≥2.5ש = חשד.
    הסף לא נמדד מול סרטונים מאושרים ⇒ **מדווח, לא חוסם**. התיקון: האזנה חוזרת
    ב-large-v3 בלי VAD על הקליפ (`relisten`).

שימוש
-----
  python3 intake_guard.py orient CLIP.mp4 [...]          # I1 (exit 1 = חשד, לבדוק פריים)
  python3 intake_guard.py density --workdir W            # P18 (edl.json + whisper_raw.json)
  python3 intake_guard.py relisten CLIP.mp4 OUT.json     # large-v3, בלי VAD
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# נגזרות של הקליפים בתיקיית עבודה. קליפ שהוחלף ⇒ כולן מתות.
DERIVED = ("INPUT.mp4", "whisper_raw.json", "whisper_raw.orig.json",
           "words_final.json", "ROUGH.mp4")

DENSITY_MIN_RATE = 0.6      # מילים/ש — UNMEASURED (מניסיון ארכיון Throwdown), מדווח בלבד
DENSITY_MIN_LEN = 2.5       # ש — קטע קצר מזה לא נשפט (נשימה, מבט)
# הכרעת כיוון — נמדד על 257 קליפים של ארכיון Throwdown 2026 (19.9.26):
# תופס את הקליפ ההפוך היחיד (IMG_4997: 0:0 · 180:4), אבל גם 7 קליפים תקינים
# (2.7% — כולל קלוז-אפ פנים חד, IMG_5003 0:1 · 180:4). haar לא מפריד ⇒ I1 **מדווח**
# עם פריים לבדיקה, ואינו חוסם. מסלול החמרה: גלאי פנים של macOS Vision (roll).
ORIENT_EVIDENCE = {"clips": 257, "true_pos": 1, "false_pos": 7, "fp_rate": 0.027}
ORIENT_SAMPLES = (0.1, 0.3, 0.5, 0.7, 0.9)
ORIENT_MIN_NEIGHBORS = 8     # 5 מייצר פנים-שווא בקהל/מוט; 8 מנקה (נמדד)
ORIENT_MIN_VOTES = 3         # לפחות 3 מתוך 5 פריימים עם פנים בכיוון החלופי
ORIENT_MARGIN = 3            # ויותר ב-3 מהכיוון הנוכחי
FIX_VF = {90: "transpose=1", 180: "hflip,vflip", 270: "transpose=2"}


# ═══════════════════════════════════════════════════════════════════════
# L68 — I2_stale_clip_copy
# ═══════════════════════════════════════════════════════════════════════
def clip_copy_is_stale(src: Path, dst: Path) -> bool:
    src, dst = Path(src), Path(dst)
    if not dst.exists():
        return True
    s, d = src.stat(), dst.stat()
    return s.st_size != d.st_size or s.st_mtime > d.st_mtime + 1.0


def sync_clip_copy(src, dst, workdir=None, derived=DERIVED) -> dict:
    """מעתיק את הקליפ אם העותק ישן, ומוחק את כל הנגזרות שנבנו מהעותק הישן."""
    src, dst = Path(src), Path(dst)
    W = Path(workdir) if workdir else dst.parent
    out = {"gate": "I2_stale_clip_copy", "clip": dst.name, "copied": False, "invalidated": []}
    if not clip_copy_is_stale(src, dst):
        return out
    existed = dst.exists()
    shutil.copy2(src, dst)
    out["copied"] = True
    if existed:
        for f in derived:
            p = W / f
            if p.exists():
                p.unlink()
                out["invalidated"].append(f)
    return out


# ═══════════════════════════════════════════════════════════════════════
# L69 — I1_orientation
# ═══════════════════════════════════════════════════════════════════════
def probe_geometry(path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:stream_tags=rotate:stream_side_data=rotation",
                        "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
    st = (json.loads(r.stdout or "{}").get("streams") or [{}])[0]
    rot = st.get("tags", {}).get("rotate")
    for sd in st.get("side_data_list") or []:
        if "rotation" in sd:
            rot = sd["rotation"]
    rot = int(float(rot or 0)) % 360
    w, h = int(st.get("width") or 0), int(st.get("height") or 0)
    dw, dh = (h, w) if rot in (90, 270) else (w, h)
    return {"width": w, "height": h, "rotation": rot, "display_w": dw, "display_h": dh,
            "display": "portrait" if dh >= dw else "landscape"}


def _face_votes(path, samples=ORIENT_SAMPLES) -> dict | None:
    """ספירת פריימים עם פנים בכל כיוון. None = אין גלאי (measured:false)."""
    try:
        import cv2
        xml = Path(getattr(getattr(cv2, "data", None), "haarcascades", "") or "") / \
            "haarcascade_frontalface_default.xml"
        if not xml.exists():
            return None
        casc = cv2.CascadeClassifier(str(xml))
    except Exception:
        return None
    try:
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(path)], timeout=60).strip())
    except Exception:
        return None
    votes = {0: 0, 90: 0, 180: 0, 270: 0}
    rots = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
            270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    for f in samples:
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{dur * f:.2f}", "-i",
                            str(path), "-frames:v", "1", "-vf", "scale=480:-2", "-f", "image2pipe",
                            "-vcodec", "png", "-"], capture_output=True, timeout=60)
        if not r.stdout:
            continue
        import numpy as np
        img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        for deg in votes:
            im = img if deg == 0 else cv2.rotate(img, rots[deg])
            if len(casc.detectMultiScale(im, 1.1, ORIENT_MIN_NEIGHBORS, minSize=(36, 36))):
                votes[deg] += 1
    return votes


def judge_orientation(geom: dict, votes: dict | None) -> dict:
    """הכרעה טהורה (נבדקת בלי מדיה). הפריים מכריע; המטא-דאטה רק מעוררת חשד."""
    out = {"gate": "I1_orientation", "geometry": geom, "votes": votes,
           "measured": votes is not None, "pass": True, "sideways": False, "transpose": None}
    suspicious = geom.get("display") == "landscape"
    if votes is None:
        out["detail"] = ("אין גלאי פנים — לא נמדד" + (" · landscape בתצוגה: לבדוק פריים ידנית"
                                                     if suspicious else ""))
        return out
    alt = {d: votes.get(d, 0) for d in (90, 180, 270)}
    best = max(alt, key=lambda d: alt[d])
    v0 = votes.get(0, 0)
    if alt[best] >= ORIENT_MIN_VOTES and alt[best] >= v0 + ORIENT_MARGIN:
        out["pass"] = False
        out["sideways"] = True
        out["rotate_by"] = best
        out["fix_vf"] = FIX_VF[best]
        out["transpose"] = {90: 1, 270: 2}.get(best)      # fixrot.sh: 1=cw, 2=ccw; 180=None
        what = "הפוך" if best == 180 else "על הצד"
        out["detail"] = (f"הדמות {what}: פנים ב-{alt[best]} פריימים בסיבוב {best}° מול "
                         f"{v0} ישר (rotation={geom.get('rotation')}) ⇒ -vf {FIX_VF[best]}")
    else:
        out["detail"] = f"כיוון תקין ({geom.get('display')}, פנים ישר={votes[0]})"
    return out


def check_orientation(path) -> dict:
    return judge_orientation(probe_geometry(path), _face_votes(path))


# ═══════════════════════════════════════════════════════════════════════
# L70 — P18_caption_density
# ═══════════════════════════════════════════════════════════════════════
def word_density_gaps(words, keeps, min_len=DENSITY_MIN_LEN, min_rate=DENSITY_MIN_RATE,
                      skip_music=False) -> list[dict]:
    """קטעים שנשמרו ויש בהם פחות מ-min_rate מילים לשנייה (אותו ציר: INPUT)."""
    if skip_music:
        return []
    starts = sorted(float(w["start"]) for w in words or [] if str(w.get("word", "")).strip())
    gaps = []
    for k in keeps or []:
        s, e = float(k["start"]), float(k["end"])
        if e - s < min_len:
            continue
        n = sum(1 for t in starts if s <= t < e)
        rate = n / (e - s)
        if rate < min_rate:
            gaps.append({"start": round(s, 2), "end": round(e, 2), "words": n,
                         "rate": round(rate, 2)})
    return gaps


def density_from_workdir(W) -> dict:
    W = Path(W)
    def jl(p, d=None):
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            return d
    edl = jl(W / "edl.json", {}) or {}
    words = jl(W / "whisper_raw.json")
    man = jl(W / "project_manifest.json", {}) or {}
    # רק ריל בלי דיבור מוחרג. "מונטאז" לבד מופיע גם בתיאור של ריל מדובר (נמדד: ראיון
    # הפודיומיסטים דולג בטעות) — ההחרגה חייבת את הצירוף המפורש.
    _t = str(man.get("topic", ""))
    music_only = ("מונטאז׳ מוזיקלי" in _t or "מונטאז' מוזיקלי" in _t or "בלי דיבור" in _t
                  or man.get("content_type") == "montage")
    if words is None or not edl.get("keep_segments"):   # [] = אפס מילים = החור הגרוע ביותר, לא "לא נמדד"
        return {"gate": "P18_caption_density", "measured": False, "gaps": []}
    gaps = word_density_gaps(words, edl["keep_segments"], skip_music=music_only)
    return {"gate": "P18_caption_density", "measured": True, "gaps": gaps,
            "skipped": "music_montage" if music_only else None}


def relisten(clip, out_json, model="large-v3") -> int:
    """תיקון L70: האזנה חוזרת בלי VAD — תזמוני מילים לקליפ בודד."""
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(clip), language="he", word_timestamps=True, vad_filter=False,
                           beam_size=5, condition_on_previous_text=False)
    out = [{"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2),
            "prob": round(w.probability, 3), "relisten": model}
           for s in segs for w in (s.words or []) if w.word.strip()]
    Path(out_json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK {len(out)} words -> {out_json} (model={model}, vad=off)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    o = sp.add_parser("orient"); o.add_argument("clips", nargs="+")
    d = sp.add_parser("density"); d.add_argument("--workdir", required=True)
    r = sp.add_parser("relisten"); r.add_argument("clip"); r.add_argument("out")
    r.add_argument("--model", default="large-v3")
    a = ap.parse_args()
    if a.cmd == "orient":
        res = [dict(check_orientation(c), clip=str(c)) for c in a.clips]
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 1 if any(not x["pass"] for x in res) else 0
    if a.cmd == "density":
        print(json.dumps(density_from_workdir(a.workdir), ensure_ascii=False, indent=1))
        return 0
    return relisten(a.clip, a.out, a.model)


if __name__ == "__main__":
    sys.exit(main())
