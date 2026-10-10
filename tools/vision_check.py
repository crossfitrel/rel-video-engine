#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vision_check — חוק הראייה, במספרים.

למה זה נולד
-----------
הראל, 17.8.26: *"להפסיק לעבוד על וידאו בעיוורון."* עד היום כל אמירה על מה
שיש בסרטון — הוק חלש, שוט מת, כתובית לא קריאה — נשענה על `report.md`,
על שם הקובץ או על התסריט המתוכנן. כלומר על מטא-דאטה, לא על צפייה.

הכלי הזה עושה שני דברים, ורק אותם:

1. **מוודא שיש bundle ראייה טרי ל-FINAL** — `{FINAL}_eyes/` עם גיליונות מגע,
   תמליל ו-data.json, שנוצר **אחרי** הקובץ שהוא מתאר. bundle ישן מקובץ חדש
   הוא בדיוק העיוורון שהכלי בא למנוע, ולכן נפסל.
2. **מחלץ מספר לכל שער ראייה** — כל שער בסעיף 3 של הנחיות הפרויקט מקבל ערך
   מדוד מ-`data.json`, לא תחושה. הפלט `VISION.json`.

מה הכלי **לא** עושה
-------------------
הוא לא מחליף את הצפייה. `contact_*.jpg` נקראים בכלי `Read` בידי מי שמדווח —
זו הצפייה בפועל. v9.29: `V7_captions_readable` כבר לא "ידני לנצח" —
`caption_vision.py` משווה כל cue בפיקסלים לרינדור הצפוי (ראו שם), ו-V7 קורא
את `CAPTION_VISION.json`. הגיליון `caption_vision_sheet.jpg` עדיין נקרא ב-Read
כשיש ממצא — הראיה, לא התווית.

למה כמעט הכל reporting
----------------------
עקרון 1 של הפרויקט: *כל סף נגזר ממדידה של סרטונים שהראל אישר, לא מניחוש.*
הספים בסעיף 3 (0.3ש למילה ראשונה · 2.0ש לשינוי · 1.2ש לשתיקה · 3.5ש לחלון
סטטי) הם מספרים עגולים שאיש עוד לא מדד מול המעטפת. לכן — **מדווחים**, לא
חוסמים. מי שרוצה לחסום מריץ `--build-reference` על הסרטונים המאושרים,
מקבל `vision_reference.json` עם min/max/median, ורק אז מקדם ל-blocking
דרך `gate_registry`. עד אז: מספר על השולחן, לא שער מזויף.

הערת-אמת אחת שהמדידה כבר נותנת: `reference_profile.json` (16 מאושרים) מראה
`longest_pause` חציון 0.81ש ומקסימום 5.83ש. סף חוסם של 1.2ש היה פוסל
סרטונים שהראל עצמו אישר ופרסם. הכלל הקיים והמדוד (פאוזה ≤0.65ש בתוצר תחת
`--director`) כבר מחמיר יותר ממנו ממילא.

שימוש
-----
  python3 vision_check.py --video FINAL.mp4                  # מנתח אם צריך, ומודד
  python3 vision_check.py --video FINAL.mp4 --workdir W      # כותב VISION.json ל-W
  python3 vision_check.py --video FINAL.mp4 --from-bundle    # לא מריץ analyze
  python3 vision_check.py --build-reference a.mp4 b.mp4 ...  # בונה מעטפת ראייה
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path
import os as _os

# v9.22 (L50b): כמו הצינור — הרצה מסביבה בלי Homebrew (שרת/LaunchAgent) לא מוצאת ffmpeg,
# ו-video_eyes נופל ב-exit 1 בשקט. מקדימים את הנתיבים לפני כל תת-תהליך.
_cur = _os.environ.get("PATH", "").split(_os.pathsep)
_os.environ["PATH"] = _os.pathsep.join(
    [d for d in ("/opt/homebrew/bin", "/usr/local/bin") if _os.path.isdir(d) and d not in _cur] + _cur)

HERE = Path(__file__).resolve().parent          # tools/
SYSDIR = HERE.parent                            # שורש הפרויקט
VIDEO_EYES = SYSDIR / "scripts" / "video_eyes.py"
REFERENCE = HERE / "vision_reference.json"

# מקור הסף — אותה טרמינולוגיה של gate_registry.
MEASURED = "measured"
CANON = "canon"
UNMEASURED = "unmeasured"
# v9.29: נמדד מול המאושרים, והמדידה עצמה הראתה שסף חוסם אינו מוצדק (V3/V4).
MEASURED_NOT_PROMOTED = "measured_not_promoted"

# סף התנועה שמתחתיו הפריים נחשב "כמעט סטטי" — מגיע מ-video_eyes עצמו
# (summarize_motion סופר still כ-motion < 1.0), לא מספר חדש שהומצא כאן.
STILL = 1.0
MOTION_FPS = 4.0        # video_eyes דוגם תנועה ב-4 דגימות לשנייה


# ═══════════════════════════════════════════════════════════════════════
# bundle
# ═══════════════════════════════════════════════════════════════════════
def bundle_dir(video: Path) -> Path:
    return video.with_name(video.stem + "_eyes")


def ensure_bundle(video: Path, from_bundle: bool, model: str) -> tuple[Path, str]:
    """מחזיר (תיקיית bundle, מצב). מצב ∈ fresh / reused / stale / missing."""
    b = bundle_dir(video)
    data = b / "data.json"
    if data.exists():
        if data.stat().st_mtime >= video.stat().st_mtime:
            return b, "reused"
        if from_bundle:
            return b, "stale"
    elif from_bundle:
        return b, "missing"
    if not VIDEO_EYES.exists():
        raise SystemExit(f"video_eyes.py לא נמצא ב-{VIDEO_EYES}")
    subprocess.run([sys.executable, str(VIDEO_EYES), "analyze", str(video),
                    "--clean", "--model", model], check=True)
    return b, "fresh"


# ═══════════════════════════════════════════════════════════════════════
# מדידה — כל שער מחזיר (value, detail). None = אין נתון.
# ═══════════════════════════════════════════════════════════════════════
def m_first_frame(d: dict):
    """אנרגיית התנועה בחצי השנייה הראשונה. פתיחה סטטית = מספר קרוב ל-0."""
    s = [x["motion"] for x in d.get("motion_series", []) if x["t"] <= 0.5]
    if not s:
        return None, "אין motion_series"
    v = round(max(s), 2)
    return v, f"שיא תנועה ב-0-0.5ש = {v} (סטטי < {STILL})"


def m_change_before_2s(d: dict):
    """הרגע הראשון שבו קורה שינוי ויזואלי — קאט או תנועה מעל סף הסטטיות."""
    cuts = [c for c in d.get("scenes", []) if 0 < c < 2.0]
    first_cut = round(min(cuts), 2) if cuts else None
    moving = [x["t"] for x in d.get("motion_series", [])
              if x["t"] <= 2.0 and x["motion"] >= STILL]
    first_move = round(min(moving), 2) if moving else None
    cands = [x for x in (first_cut, first_move) if x is not None]
    if not cands:
        return None, "אין שינוי ויזואלי עד 2.0ש — לא קאט ולא תנועה מעל הסף"
    v = min(cands)
    how = "קאט" if first_cut is not None and v == first_cut else "תנועה"
    return v, f"שינוי ראשון ב-{v}ש ({how})"


def m_first_word(d: dict):
    segs = ((d.get("transcript") or {}).get("segments")) or []
    if not segs:
        wt = d.get("words_timeline") or {}
        if wt.get("first_word") is None:
            return None, "אין תמליל ואין words_final ליד ה-FINAL"
        v = wt["first_word"]
        return v, f"המילה הראשונה ב-{v}ש (מציר הכתוביות {wt.get('source')})"
    v = round(float(segs[0].get("start", 0.0)), 2)
    return v, f"המילה הראשונה ב-{v}ש"


def m_wpm(d: dict):
    v = ((d.get("transcript") or {}).get("words_per_minute"))
    if v is None:
        wt = d.get("words_timeline") or {}
        if wt.get("wpm") is None:
            return None, "אין תמליל / דיבור קצר מדי למדידה"
        return wt["wpm"], f"{wt['wpm']} מילים לדקה (מציר הכתוביות {wt.get('source')})"
    return float(v), f"{v} מילים לדקה"


def words_timeline(video: Path) -> dict:
    """v9.29 (22.9.26) — מקור ל-V3/V4 כשה-bundle בלי תמליל.

    נמדד: **אף אחד** מ-16 ה-bundles של הסרטונים המאושרים לא מכיל transcript
    (video_eyes רץ שם בלי whisper), ולכן V3/V4 החזירו no_data תמיד — 'לא נמדד'
    שנראה כמו שער. ציר הכתוביות (words_final.json, forced-aligned) הוא בדיוק
    הדיבור שנצרב ב-FINAL, והוא יושב ליד הקובץ. היסט פתיח קבוע נלקח מ-
    FINAL_PROVENANCE; כשאינו רשום — הערך יחסי-לגוף, וזה מסומן."""
    wdir = video.parent
    wf = wdir / "words_final.json"
    if not wf.exists():
        return {}
    try:
        w = json.loads(wf.read_text(encoding="utf-8"))
        w = w if isinstance(w, list) else (w.get("words") or [])
        w = [x for x in w if str(x.get("word", "")).strip()]
    except Exception:
        return {}
    if not w:
        return {}
    off, src = 0.0, "words_final"
    try:
        prov = json.loads((wdir / "FINAL_PROVENANCE.json").read_text(encoding="utf-8"))
        if "intro_offset_sec" in prov:
            off = float(prov.get("intro_offset_sec") or 0.0)
            src = "words_final+provenance"
        else:
            src = "words_final (יחסי-גוף: היסט פתיח לא רשום)"
    except Exception:
        src = "words_final (יחסי-גוף: אין FINAL_PROVENANCE)"
    t0 = float(w[0]["start"]); t1 = float(w[-1]["end"])
    span = t1 - t0
    wpm = round(len(w) / span * 60.0, 1) if span >= 10.0 else None
    return {"first_word": round(t0 + off, 2), "wpm": wpm, "n_words": len(w),
            "source": src}


def m_dead_silence(d: dict):
    # bundle שנוצר ב---no-audio מחזיר silences ריק — זה "לא נמדד", לא "אין
    # שתיקה". בלי ההבחנה הזאת השער היה עובר PASS על סרטון שאיש לא האזין לו.
    if not d.get("audio_levels"):
        return None, "אין ניתוח אודיו ב-bundle (--no-audio) — לא נמדד"
    sil = d.get("silences") or []
    if not sil:
        return 0.0, "אין מקטעי שתיקה מעל 0.6ש"
    longest = max(sil, key=lambda s: s["end"] - s["start"])
    v = round(longest["end"] - longest["start"], 2)
    return v, f"השתיקה הארוכה ביותר {v}ש ב-{longest['start']}-{longest['end']}ש"


def m_static_window(d: dict):
    """רצף הארוך ביותר של דגימות מתחת לסף הסטטיות, בשניות."""
    ser = d.get("motion_series") or []
    if not ser:
        return None, "אין motion_series"
    best = run = 0
    start = best_start = 0.0
    for x in ser:
        if x["motion"] < STILL:
            if run == 0:
                start = x["t"]
            run += 1
            if run > best:
                best, best_start = run, start
        else:
            run = 0
    v = round(best / MOTION_FPS, 2)
    return v, f"החלון הסטטי הארוך ביותר {v}ש החל מ-{best_start}ש"


CHECKS = [
    # id, כותרת, פונקציה, סף, כיוון (max=לא לעבור / min=לא לרדת מתחת), מקור
    ("V1_first_frame_alive", "פריים ראשון לא סטטי",
     m_first_frame, STILL, "min", UNMEASURED),
    ("V2_change_before_2s", "שינוי ויזואלי לפני 2.0ש",
     m_change_before_2s, 2.0, "max", UNMEASURED),
    ("V3_first_word", "מילה ראשונה לפני 0.3ש",
     m_first_word, 0.30, "max", UNMEASURED),
    ("V4_speech_rate", "קצב דיבור",
     m_wpm, None, None, UNMEASURED),
    ("V5_dead_silence", "אין שתיקה מתה",
     m_dead_silence, 1.2, "max", UNMEASURED),
    ("V6_static_window", "אין חלון סטטי ארוך",
     m_static_window, 3.5, "max", UNMEASURED),
]

MANUAL = {
    "id": "V7_captions_readable",
    "title": "כתוביות קריאות בגודל אריח",
    "status": "manual",
    "detail": "v9.29: נמדד ב-caption_vision (V7 ברשימת checks). הגיליון "
              "caption_vision_sheet.jpg נקרא ב-Read כשיש ממצא.",
}


def v7_captions(video: Path) -> dict:
    """V7 על הפיקסלים (v9.29, 22.9.26) — caption_vision.analyze על ה-FINAL.
    חוסם רק על דגלים שהכיול הוכיח (caption-vision-calibration.json)."""
    try:
        sys.path.insert(0, str(HERE))
        import caption_vision as cvm
        doc = cvm.analyze(video.parent, video=video, sheet=True, write=True)
    except Exception as e:                     # גלאי שנופל ≠ PASS (עקרון 11)
        return {"id": "V7_captions_readable", "title": MANUAL["title"], "value": None,
                "threshold": None, "direction": None, "threshold_source": UNMEASURED,
                "enforcement": "reporting", "status": "no_data",
                "detail": f"caption_vision נכשל: {e}"}
    if not doc.get("measured"):
        return {"id": "V7_captions_readable", "title": MANUAL["title"], "value": None,
                "threshold": None, "direction": None, "threshold_source": UNMEASURED,
                "enforcement": "reporting", "status": "no_data",
                "detail": f"לא נמדד: {doc.get('why', 'אין cues')}"}
    blocking = doc.get("blocking_flags") or []
    measured = doc.get("threshold_source") == "measured" and blocking
    hits = doc.get("blocking_hits") or {}
    c = doc.get("counts") or {}
    detail = (f"{doc['n_measured']}/{doc['n_cues']} cues מול רינדור צפוי · f חציון "
              f"{doc['f_ok_median']} · " + (" · ".join(f"{k} {v}" for k, v in sorted(c.items()))
                                             or "אפס ממצאים")
              + (f" · היסט {doc['intro_offset_sec']}ש ({doc['offset_source']})"
                 if doc.get("intro_offset_sec") else ""))
    return {"id": "V7_captions_readable", "title": MANUAL["title"],
            "value": sum(hits.values()) if hits else 0, "threshold": 0,
            "direction": "max", "threshold_source": MEASURED if measured else UNMEASURED,
            "enforcement": "blocking" if measured else "reporting",
            "status": "fail" if hits else "pass", "detail": detail,
            "blocking_flags": blocking, "sheet": doc.get("sheet"),
            "report": str(video.parent / "CAPTION_VISION.json")}


def load_reference() -> dict:
    if REFERENCE.exists():
        try:
            return json.loads(REFERENCE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def evaluate(d: dict) -> list[dict]:
    ref = (load_reference().get("envelope") or {})
    out = []
    for cid, title, fn, thr, direction, source in CHECKS:
        value, detail = fn(d)
        r = ref.get(cid)
        promote = True
        if r:                                  # המעטפת גוברת על המספר העגול
            # v9.29: רשומה יכולה להיות "נמדד אבל לא מקודם" (promote=false) —
            # כשהמדידה עצמה מראה שסף חוסם היה פוסל סרטונים מאושרים או שאין
            # מחלקה שלילית. אז הסף הקאנוני נשאר, מדווח, והמעטפת מוצגת בפירוט.
            promote = r.get("promote", True)
            if promote:
                thr = r.get("threshold", thr)
            source = MEASURED if promote else MEASURED_NOT_PROMOTED
        status = "no_data"
        if value is not None and thr is not None:
            if direction == "max":
                status = "pass" if value <= thr else "fail"
            else:
                status = "pass" if value >= thr else "fail"
        elif value is not None:
            status = "measured"
        if r and not promote and r.get("why_not_blocking"):
            detail += f" · מעטפת {r.get('n')} מאושרים: {r.get('min')}–{r.get('max')} " \
                      f"(חציון {r.get('median')}) — {r['why_not_blocking']}"
        out.append({
            "id": cid, "title": title, "value": value, "threshold": thr,
            "direction": direction, "threshold_source": source,
            # כל עוד הסף לא נמדד — מדווח, לא חוסם. עקרון 1 של הפרויקט.
            "enforcement": "blocking" if source == MEASURED else "reporting",
            "status": status, "detail": detail,
        })
    return out


def run(video: Path, workdir: Path | None, from_bundle: bool, model: str) -> dict:
    b, mode = ensure_bundle(video, from_bundle, model)
    data_p = b / "data.json"
    if not data_p.exists():
        raise SystemExit(f"אין bundle ראייה ל-{video.name} ({mode}) — "
                         f"להריץ: python3 scripts/video_eyes.py analyze {video.name} --clean")
    d = json.loads(data_p.read_text(encoding="utf-8"))
    d["words_timeline"] = words_timeline(video)
    checks = evaluate(d)
    checks.append(v7_captions(video))
    sheets = sorted(p.name for p in b.glob("contact_*.jpg"))
    failed_blocking = [c["id"] for c in checks
                       if c["status"] == "fail" and c["enforcement"] == "blocking"]
    reported = [c["id"] for c in checks
                if c["status"] == "fail" and c["enforcement"] == "reporting"]
    doc = {
        "video": str(video),
        "bundle": str(b),
        "bundle_mode": mode,                    # fresh / reused / stale / missing
        "bundle_is_fresh": mode in ("fresh", "reused"),
        "sheets": sheets,                       # אלה הקבצים שחייבים להיקרא ב-Read
        "sheets_read_is_manual": True,
        "duration_sec": (d.get("meta") or {}).get("duration_sec"),
        "checks": checks,
        "manual": MANUAL,
        "blocking_failures": failed_blocking,
        "reported_failures": reported,
        "ok": not failed_blocking and mode in ("fresh", "reused"),
    }
    target = (workdir or b)
    (Path(target) / "VISION.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


# ═══════════════════════════════════════════════════════════════════════
# --build-reference — הדרך היחידה להפוך סף עגול לסף מדוד
# ═══════════════════════════════════════════════════════════════════════
# V3/V4 נמדדים מציר הכתוביות (v9.29). הם לא מקודמים אוטומטית לסף-הקצה כמו
# V1/V2/V5/V6: הסף הקאנוני נשאר, ומקודם לחוסם רק אם אף סרטון מאושר לא נכשל בו.
WORDS_CHECKS = ("V3_first_word", "V4_speech_rate")


def promotion(cid: str, vals: list[float]) -> dict:
    """ההחלטה אם מדידה מצדיקה חסימה — נגזרת מהנתונים, נשמרת כדאטה."""
    row = next(c for c in CHECKS if c[0] == cid)
    canon, direction = row[3], row[4]
    if canon is None:
        return {"promote": False, "canon_threshold": None,
                "why_not_blocking": "אין סף קאנוני ואין מחלקה שלילית (סרטון שנפסל על זה) — "
                                    "מספר על השולחן, לא שער"}
    bad = [v for v in vals if (v > canon if direction == "max" else v < canon)]
    if bad:
        return {"promote": False, "canon_threshold": canon, "approved_failing": len(bad),
                "why_not_blocking": f"הסף הקאנוני {canon} היה פוסל {len(bad)}/{len(vals)} "
                                    f"סרטונים שהראל אישר ופרסם"}
    return {"promote": True, "canon_threshold": canon, "approved_failing": 0}


def measure_words(videos: list[str]) -> dict:
    """מוסיף ל-vision_reference.json את V3/V4 בלבד, מציר הכתוביות — בלי להריץ
    video_eyes מחדש על סרטונים מאושרים (לא נוגעים בתיקיות שלהם)."""
    ref = load_reference() or {"envelope": {}}
    per: dict[str, list[float]] = {}
    used = []
    for v in videos:
        p = Path(v).expanduser()
        wt = words_timeline(p)
        if not wt:
            print(f"⚠️  אין words_final ליד {p}")
            continue
        used.append({"video": str(p), **wt})
        for cid, fn in (("V3_first_word", m_first_word), ("V4_speech_rate", m_wpm)):
            val, _ = fn({"words_timeline": wt})
            if val is not None:
                per.setdefault(cid, []).append(float(val))
    for cid, vals in per.items():
        direction = next(c[4] for c in CHECKS if c[0] == cid) or "min"
        lo, hi = min(vals), max(vals)
        ref.setdefault("envelope", {})[cid] = {
            "min": round(lo, 3), "max": round(hi, 3),
            "median": round(statistics.median(vals), 3), "n": len(vals),
            "threshold": round(hi, 3) if direction == "max" else round(lo, 3),
            "direction": direction, "source": "words_final (ציר הכתוביות)",
            "measured_at": __import__("time").strftime("%Y-%m-%d"),
            **promotion(cid, vals)}
    ref["words_measurements"] = used
    REFERENCE.write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
    return ref


def build_reference(videos: list[str], model: str) -> dict:
    per: dict[str, list[float]] = {}
    used = []
    for v in videos:
        p = Path(v).expanduser()
        if not p.exists():
            print(f"⚠️  אין קובץ: {p}")
            continue
        b, _ = ensure_bundle(p, False, model)
        d = json.loads((b / "data.json").read_text(encoding="utf-8"))
        d["words_timeline"] = words_timeline(p)
        used.append(str(p))
        for cid, _t, fn, _thr, _dir, _s in CHECKS:
            val, _ = fn(d)
            if val is not None:
                per.setdefault(cid, []).append(float(val))
    env = {}
    for cid, vals in per.items():
        direction = next(c[4] for c in CHECKS if c[0] == cid)
        lo, hi = min(vals), max(vals)
        med = round(statistics.median(vals), 3)
        # הסף = הקצה שהראל בפועל אישר, לא ניחוש: max למי שאסור לעבור,
        # min למי שאסור לרדת מתחתיו.
        thr = round(hi, 3) if direction == "max" else round(lo, 3)
        env[cid] = {"min": round(lo, 3), "max": round(hi, 3), "median": med,
                    "n": len(vals), "threshold": thr, "direction": direction}
        if cid in WORDS_CHECKS:
            env[cid].update(promotion(cid, vals))
    doc = {"_readme": "מעטפת ראייה שנמדדה מסרטונים שהראל אישר ופרסם. "
                      "רק שער עם רשומה כאן רשאי לחסום.",
           "n_videos": len(used), "videos": used, "envelope": env}
    REFERENCE.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--from-bundle", action="store_true",
                    help="לא להריץ analyze — לקרוא bundle קיים בלבד")
    ap.add_argument("--model", default="medium")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 כשיש כשל חוסם או bundle לא טרי")
    ap.add_argument("--build-reference", nargs="+", metavar="VIDEO")
    ap.add_argument("--measure-words", nargs="+", metavar="FINAL",
                    help="V3/V4 בלבד מציר הכתוביות — מעדכן את vision_reference.json")
    a = ap.parse_args()

    if a.measure_words:
        ref = measure_words(a.measure_words)
        for cid in WORDS_CHECKS:
            e = (ref.get("envelope") or {}).get(cid)
            if e:
                print(f"{cid}: n={e['n']} {e['min']}–{e['max']} חציון {e['median']} · "
                      f"promote={e['promote']} · {e.get('why_not_blocking', 'חוסם')}")
        return 0

    if a.build_reference:
        doc = build_reference(a.build_reference, a.model)
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        print(f"\n✅ vision_reference.json נכתב · {doc['n_videos']} סרטונים · "
              f"{len(doc['envelope'])} שערים הפכו למדודים")
        return 0

    if not a.video:
        ap.error("צריך --video או --build-reference")
    doc = run(Path(a.video).expanduser(),
              Path(a.workdir).expanduser() if a.workdir else None,
              a.from_bundle, a.model)
    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=1))
    else:
        icon = "✅" if doc["ok"] else "🔴"
        print(f"{icon} ראייה · bundle {doc['bundle_mode']} · "
              f"{len(doc['sheets'])} גיליונות מגע")
        for c in doc["checks"]:
            mark = {"pass": "✅", "fail": "🔴", "measured": "•",
                    "no_data": "—"}[c["status"]]
            src = {MEASURED: "", MEASURED_NOT_PROMOTED: " [נמדד · לא מקודם]"}.get(
                c["threshold_source"], " [סף לא-מדוד]")
            print(f"  {mark} {c['id']}: {c['detail']}{src}")
        print("\nהצפייה בפועל = Read על: " + ", ".join(doc["sheets"]))
    return (0 if doc["ok"] else 1) if a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
