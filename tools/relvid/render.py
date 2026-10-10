#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relvid.render — מנוע רינדור v2: גרף סגמנטים + מטמון תוכן (V2 שלב 2).

═══════════════════════════════════════════════════════════════════════════
למה זה קיים
═══════════════════════════════════════════════════════════════════════════
נמדד ב-baseline (30.7.26): הצנרת v1 מקודדת את הסרטון **4-7 פעמים מקצה לקצה**
ומייצרת **4-6 דורות AAC** על הדיבור. שרשרת ה-crf בפועל:
    23 (INPUT) → 18 (recut) → 18 (tighten) → 20 (broll) → 16 (captions) → 23 (deliver)
שני הקידודים האחרונים הם הבזבוז החד ביותר: crf16 שנדחס מיד ל-crf23.

**התובנה שפותרת את זה היא סדר, לא קידוד.** ב-v1 המוזיקה נכנסת *לפני* הכתוביות,
ולכן צריבת הכתוביות היא קידוד וידאו נוסף, וה-loudness אחריה עוד אחד. אם צורבים
את הכתוביות **בתוך** הקידוד של החיתוך עצמו, ומשאירים את המוזיקה לסוף (היא נוגעת
רק באודיו) — נשארים עם:

    N סגמנטים → קידוד h264 אחד לכל סגמנט, ישר בפרמטרי המסירה
    concat -c copy                                   ← אפס קידוד
    audio_mix (-c:v copy, aac יחיד, loudnorm ל--14)  ← אפס קידוד וידאו

**דור וידאו אחד. דור AAC אחד.** (KPI 3 ו-4 במסמך V2.)

═══════════════════════════════════════════════════════════════════════════
מה זה קונה מעבר לאיכות
═══════════════════════════════════════════════════════════════════════════
* **מטמון לפי hash תוכן.** מפתח הסגמנט נגזר מכל מה שמשפיע על הפיקסלים שלו
  (מקור+טווח+כתוביות+בירול+פרמטרי קידוד). תיקון כתובית אחת ⇒ רינדור סגמנט אחד.
  שינוי מוזיקה בלבד ⇒ **אפס** רינדור וידאו.
* **רינדור מחדש של קטע** — התנאי שבלעדיו לולאת Reviewer→Director (פאס 4→2)
  אינה מעשית: לולאה שדורשת רינדור מלא בכל סבב לא תרוץ.
* **מקביליות אמיתית** — סגמנטים בלתי-תלויים על 10 ליבות.
* **נרמול פעם אחת, בכניסה** — רזולוציה, fps ותיוג צבע. ב-v1 אין אף שלב
  שמנרמל ל-1080×1920, ו-G5_format חוסם על זה רק בסוף, אחרי כל הקידודים.

═══════════════════════════════════════════════════════════════════════════
עקרונות
═══════════════════════════════════════════════════════════════════════════
1. **אין כפילות לוגיקה.** גיאומטריית הכתוביות, הקיבוץ, ה-RTL ורינדור ה-PNG
   מיובאים מ-`captions_build`/`captions_overlay`; המוזיקה נשארת ב-`audio_mix`.
   כאן יש רק **תזמור**.
2. **הסגמנטים חייבים להיות ניתנים ל-concat -c copy** ⇒ פרמטרי קידוד זהים
   לחלוטין בכולם (אותה רזולוציה, pix_fmt, fps, profile).
3. **האודיו בסגמנטים הוא PCM** — כדי שהשרשור לא יוסיף דור, וה-AAC היחיד
   ייווצר במיקס הסופי.
4. **גבולות סגמנט = גבולות חיתוך בלבד.** לא מפצלים לפי cues (‏70-180 cues
   היו הופכים ל-300 קריאות ffmpeg, ורק זמן ההפעלה שלהן ~30ש). במקום זה
   הכתוביות והבירולים מרונדרים *בתוך* הסגמנט בזמנים מקומיים.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
TOOLS = PKG_DIR.parent
SYSDIR = TOOLS.parent
APPDIR = SYSDIR / "captions-app"
for p in (str(TOOLS), str(APPDIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# פרמטרי המסירה — מקור אמת אחד. כל סגמנט מקודד בדיוק בהם, ולכן ה-concat
# הוא stream copy וה-FINAL לא עובר קידוד נוסף.
# ── תקציב האיכות (עודכן 30.7.26 — הראל: "האיכות ירודה מאוד, מטושטש") ──
# crf23/veryfast נבחר כשהצנרת עשתה 4-7 דורות קידוד וכל דור היה יקר. **ב-v2 יש
# דור אחד**, ולכן כל תקציב האיכות מוצא שם. נמדד מול ייחוס crf12 על אותו מקור:
#     crf23/veryfast  SSIM 0.9875  1.82 Mbps   ← היה
#     crf20/veryfast  SSIM 0.9908  2.56 Mbps
#     crf19/medium    SSIM 0.9932  3.07 Mbps   ← עכשיו
#     crf17/medium    SSIM 0.9944  3.65 Mbps
# ה-INPUT עצמו הוא 3.33 Mbps — crf23 פלט כמחצית מהמקור. crf19/medium ל-55ש
# ≈ 21MB, הרבה מתחת לתקרת 60MB של G5_format.
DELIVER = {
    "width": 1080, "height": 1920, "fps": 30,
    "vcodec": "libx264", "crf": 19, "preset": "medium", "pix_fmt": "yuv420p",
    "profile": "high", "level": "4.0",
    "acodec": "pcm_s16le", "ar": 48000, "ac": 2,
    "colorspace": "bt709", "primaries": "bt709", "trc": "bt709", "range": "tv",
}
CACHE_DIRNAME = ".rendercache"
# ⚠️ שמות תוצרים: **אסור** להשתמש ב-FINAL_v2.mp4 — זה שם שהראל משתמש בו לגרסה
# שנייה של סרטון (נמצא קובץ כזה מ-20.7 בפרויקט אמיתי, ומחיקה שלו הייתה אובדן
# תוצר). התוצרים של המנוע: master_v2.mkv (ביניים) · FINAL_engine2.mp4 (בהשוואות).
# v2.2 — fade בתפר בירול ו-eof_action. שניהם משנים פיקסלים בכל סגמנט שיש בו
# בירול, ולכן כל המטמון נפסל בכוונה: סגמנט שנשמר לפני התיקון נראה כמו הבאג.
ENGINE_VERSION = "v2.2"          # שינוי כאן = פסילת כל המטמון (בכוונה)
MIN_SEG = 0.04                   # סגמנט קצר מזה נבלע בשכן


def _txt(x) -> str:
    """‏v9.9 — `TimeoutExpired.stdout/stderr` הם **bytes** גם כש-`text=True`.

    נתפס במדידה 31.7.26: כל תקיעה שבה ffmpeg הספיק לכתוב משהו ל-stderr
    הפילה את `sh` ב-`TypeError: can't concat str to bytes` — כלומר **רשת
    הביטחון של הנפילה ל-v1 עצמה נשברה**, ובמקום `rc=124` מסודר קיבלנו
    חריגה שמפילה את הריצה. עבד רק כי `-loglevel error` בדרך כלל שותק.
    """
    if x is None:
        return ""
    return x.decode("utf-8", "replace") if isinstance(x, (bytes, bytearray)) else str(x)


def sh(cmd, timeout=1800, cwd=None):
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(
            args=[str(c) for c in cmd], returncode=124, stdout=_txt(e.stdout),
            stderr=_txt(e.stderr) + f"\n[TIMEOUT] {timeout}s")


def _jload(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _probe_dur(p) -> float:
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(p)], timeout=60)
    try:
        return float((r.stdout or "").strip())
    except (TypeError, ValueError):
        return 0.0


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _file_id(p: Path) -> dict:
    """זהות קובץ לצורך מטמון — גודל+mtime, לא hash מלא (INPUT יכול להיות 100MB+
    וה-hash היה מוסיף שנייה לכל בדיקת מטמון). אם המקור הוחלף בקובץ באותו גודל
    ובאותו mtime — זה אותו קובץ לכל דבר מעשי."""
    try:
        st = Path(p).stat()
        return {"name": Path(p).name, "size": st.st_size, "mtime": int(st.st_mtime)}
    except OSError:
        return {"name": str(p), "size": -1, "mtime": -1}


# ═══════════════════════════════════════════════════════════ מודל
@dataclass
class Cue:
    start: float          # ציר הפלט
    end: float
    text: str


@dataclass
class BrollClip:
    path: str
    start: float          # ציר הפלט
    end: float
    src_offset: float     # היסט בתוך קובץ הבירול
    fade: float = 0.12
    # מעבר רך רק בקצה **חיצוני** של רצף. בתפר פנימי (בירול צמוד, או המשך של
    # אותו קליפ בסגמנט הבא) fade חושף את הפנים מתחת — ראה build_timeline.
    fade_in: bool = True
    fade_out: bool = True


@dataclass
class Segment:
    src: str              # קובץ המקור (INPUT.mp4)
    t_in: float           # ציר המקור
    t_out: float
    out_start: float      # מיקום בציר הפלט
    cues: list = field(default_factory=list)      # Cue, בזמנים **מקומיים**
    broll: list = field(default_factory=list)     # BrollClip, בזמנים **מקומיים**
    idx: int = 0
    key: str = ""
    speed: float = 1.0
    # ── מספר הפריימים המדויק שהסגמנט מייצר ──
    # שורש (נמדד 30.7.26): בלי זה כל סגמנט מתעגל בנפרד לגבול פריים, וההצטברות
    # נתנה **+0.373ש** על 5 סגמנטים מול הפלט של v1 — כלומר סרטון בעל משך אחר.
    # v1 לא סובל מזה כי ה-tighten שלו הוא filter_complex יחיד על כל הקובץ, ולכן
    # העיגול קורה פעם אחת. הפתרון כאן: מכמתים את הציר ה**מצטבר** לפריימים בזמן
    # התכנון, וכל סגמנט מקבל ספירה מדויקת ש-`-frames:v` אוכף. הסכום מדויק
    # בהגדרה, העיגול קורה פעם אחת, והוא דטרמיניסטי (ולכן המטמון יציב).
    n_frames: int = 0
    # ── Visual Hook (11.9.26) — IR אופציונלי מתוכנית קפואה ──
    # ריק כברירת מחדל ⇒ המפתח, הגרף והפלט זהים בייט-לבייט למנוע שלפני הפיצ'ר.
    # כל פריט: {"cue_id","filter","fragment","fragment_digest","global_frames"}
    # מ-`relvid.hook_render.compile_for_segment`. הפילטר מוחל על [base] לפני
    # הבירול והכתוביות — בלי overlay (ראה FFMPEG-STALL.md).
    hooks: list = field(default_factory=list)

    @property
    def dur(self) -> float:
        """משך בציר המקור (לפני האצה)."""
        return round(self.t_out - self.t_in, 3)

    @property
    def dur_final(self) -> float:
        """משך בציר הפלט הסופי (אחרי האצה) — זה הציר שבו חיים ה-cues והבירולים."""
        if self.n_frames:
            return round(self.n_frames / DELIVER["fps"], 3)
        return round(self.dur / max(self.speed, 0.001), 3)

    @property
    def out_start_final(self) -> float:
        return round(self.out_start / max(self.speed, 0.001), 3)


@dataclass
class Timeline:
    workdir: Path
    input_path: Path
    segments: list
    band: dict            # גיאומטריית רצועת הכתוביות — גלובלית, זהה בכל סגמנט
    brand: str = "rel"
    crf: int = DELIVER["crf"]
    speed: float = 1.0
    color: dict = field(default_factory=lambda: {"primaries": "bt709", "trc": "bt709",
                                                 "space": "bt709", "range": "tv",
                                                 "source_tagged": False})

    @property
    def dur(self) -> float:
        return round(sum(s.dur for s in self.segments) / max(self.speed, 0.001), 3)


# ═══════════════════════════════════════════════════════════ בניית הציר
def _clip_to_segments(items, segments, get_span, make):
    """מפזר פריטים מציר-הפלט לסגמנטים, עם חיתוך לגבול הסגמנט.

    פריט שחוצה גבול סגמנט (בירול ארוך, ולעיתים cue) מופיע בשני הסגמנטים —
    כל אחד עם החלק שלו ועם היסט-מקור מתוקן. זו הסיבה שאין צורך לפצל סגמנטים
    לפי הפריטים עצמם."""
    # החישוב כולו בציר הפלט **הסופי** (אחרי האצה) — שם חיים words_final.json
    # ו-broll_plan.json. הפיכה לזמנים מקומיים-לפני-האצה נעשית רק בהרכבת ה-ffmpeg.
    for it in items:
        s0, e0 = get_span(it)
        for seg in segments:
            a, b = seg.out_start_final, seg.out_start_final + seg.dur_final
            lo, hi = max(s0, a), min(e0, b)
            if hi - lo <= 0.01:
                continue
            make(seg, it, lo - a, hi - a, lo - s0)


SEAM_EPS = 0.05          # v8.3 — "צמוד" בציר הפלט. אותו סף כמו ב-animation_overlay


def mark_seam_fades(clips, eps=SEAM_EPS):
    """מסמן איפה `fade` הוא מעבר ואיפה הוא חור. משנה את הרשימה במקום.

    v8.3 (הראל 25.7.26, נמדד): `fade` על אלפא מוריד את שקיפות **הבירול**,
    ומתחתיו נחשף הבסיס — כלומר הפנים. בקצה חיצוני של רצף זה בדיוק מה שרוצים
    (כניסה מהפנים ויציאה אליהם); בתפר פנימי בין שני בירולים צמודים זה ~0.24ש
    של הבהוב. v1 (`animation_overlay`) מכבה שם את ה-fade מאז v8.3 — **v2 לא**,
    ולכן הלקח נסוג בשקט כשהמנוע הוחלף, ואיש לא ראה זאת כי הבדיקות בדקו זמנים
    ולא פיקסלים.
    """
    clips.sort(key=lambda c: c.start)
    for i, c in enumerate(clips):
        if i and abs(clips[i - 1].end - c.start) <= eps:
            c.fade_in = False
        if i + 1 < len(clips) and abs(clips[i + 1].start - c.end) <= eps:
            c.fade_out = False
    return clips


def broll_fragment(c, ls, le, off):
    """שבר של קליפ בירול בתוך סגמנט אחד, עם דגלי fade נכונים.

    קליפ שחוצה גבול חיתוך מפוצל לשני סגמנטים נפרדים, וסגמנט אינו יכול לדעת
    לבד שהשכן שלו ממשיך אותו — ולכן הדגל נגזר מהמיקום בתוך **הקליפ המקורי**:
    fade רק בראש האמיתי ובזנב האמיתי. בלי זה בירול שחוצה קאט דוהה בדיוק בקאט,
    והפנים חוזרות לשבריר שנייה — כלומר בדיוק הקפיצה שהיישור נועד למנוע.
    """
    head = off <= 1e-3
    tail = off + (le - ls) >= (c.end - c.start) - 1e-3
    return BrollClip(c.path, round(ls, 3), round(le, 3), round(c.src_offset + off, 3),
                     fade=c.fade, fade_in=c.fade_in and head,
                     fade_out=c.fade_out and tail)


def build_timeline(workdir, *, brand="rel", crf=None, words_file=None,
                   broll_plan_file=None, input_file=None, hook_plan=None) -> Timeline:
    """בונה את גרף הסגמנטים מהארטיפקטים שכבר קיימים בפרויקט.

    מקור הסגמנטים: `sync.tight_keeps_in_source(edl, tight_keeps)` — הטווחים
    שנשארו אחרי החיתוך **וגם** אחרי ההידוק, ממופים חזרה לציר ה-INPUT. זו בדיוק
    אותה פונקציה שהאפליקציה משתמשת בה כדי לצייר מה ההידוק הוריד, ולכן אין כאן
    מתמטיקה חדשה שיכולה לסטות מ-v1.
    """
    from relvid import sync as sync_mod
    from captions_build import group_cues, load_words
    import captions_overlay as co
    from PIL import ImageFont

    W = Path(workdir)
    inp = Path(input_file) if input_file else (W / "INPUT.mp4")
    if not inp.exists():
        raise FileNotFoundError(f"אין INPUT: {inp}")
    edl = _jload(W / "edl.json", {}) or {}
    if not edl.get("keep_segments"):
        raise ValueError("edl.json חסר keep_segments")

    tight = _jload(W / "tight_keeps.json", None)
    if tight:
        keeps = sync_mod.tight_keeps_in_source(edl, tight)
        source_of_truth = "tight_keeps→source"
    else:
        keeps = [{"start": float(k["start"]), "end": float(k["end"])}
                 for k in edl["keep_segments"]]
        source_of_truth = "keep_segments"
    keeps = [k for k in keeps if float(k["end"]) - float(k["start"]) > MIN_SEG]
    if not keeps:
        raise ValueError("אין סגמנטים לרינדור")

    # ── ההאצה נמדדת, לא נלקחת משדה ──
    # שורש: `tight_keeps.json` נכתב **לפני** החלת ה-speed בעוד EXPORT_TIGHT.mp4
    # כבר עבר setpts/atempo (זה גם הבאג ש-cut_qa סבל ממנו). שדה `speed` במניפסט/
    # provenance יכול להיות מריצה קודמת. לכן: היחס בין סכום ה-tight_keeps לבין
    # המשך הנמדד של EXPORT_TIGHT **הוא** ההאצה, ואין דרך שהוא יהיה מיושן.
    total_src = sum(float(k["end"]) - float(k["start"]) for k in keeps)
    speed, speed_src = 1.0, "1.0 (אין ציר מהודק למדוד)"
    tight_mp4 = W / "EXPORT_TIGHT.mp4"
    if tight_mp4.exists():
        d = _probe_dur(tight_mp4)
        if d and d > 0.5:
            ratio = total_src / d
            if abs(ratio - 1.0) > 0.01:
                speed, speed_src = round(ratio, 4), f"נמדד מ-EXPORT_TIGHT ({total_src:.2f}/{d:.2f})"
            else:
                speed_src = f"1.0 (נמדד: יחס {ratio:.4f})"
    if speed == 1.0 and speed_src.startswith("1.0 (אין"):
        prov = _jload(W / "FINAL_PROVENANCE.json", {}) or {}
        for cand, nm in ((prov.get("speed"), "provenance"),
                         ((edl.get("review") or {}).get("speed"), "edl.review")):
            try:
                if cand and abs(float(cand) - 1.0) > 0.001:
                    speed, speed_src = float(cand), f"מ-{nm} (לא נמדד)"
                    break
            except (TypeError, ValueError):
                pass

    segments, acc = [], 0.0
    for i, k in enumerate(keeps):
        seg = Segment(src=str(inp), t_in=round(float(k["start"]), 3),
                      t_out=round(float(k["end"]), 3), out_start=round(acc, 3),
                      idx=i, speed=speed)
        segments.append(seg)
        acc += seg.dur

    # כימות הציר המצטבר לפריימים — ראה ההערה ב-Segment.n_frames.
    fps = DELIVER["fps"]
    prev_end_frames = 0
    cum_src = 0.0
    for seg in segments:
        cum_src += seg.dur
        end_frames = int(round((cum_src / max(speed, 0.001)) * fps))
        seg.n_frames = max(1, end_frames - prev_end_frames)
        prev_end_frames = end_frames

    # ── Visual Hook: אותה תוכנית קפואה שגם v1 צורך. רק סגמנטים שה-cue חותך
    # מקבלים IR; השאר נשארים בדיוק כמו בלי הפיצ'ר (כולל מפתח המטמון).
    hook_meta = None
    if hook_plan and hook_plan.get("recipe") not in (None, "NO_OP"):
        from relvid import hook_render as _HR
        total_frames = sum(s.n_frames for s in segments)
        want = int(hook_plan["timeline"]["frame_count"])
        if abs(total_frames - want) > 1:
            raise ValueError(f"HOOK_TIMELINE_MISMATCH: v2 מייצר {total_frames} פריימים, "
                             f"בתוכנית {want}")
        acc_f = 0
        for seg in segments:
            seg.hooks = _HR.compile_for_segment(hook_plan, acc_f, seg.n_frames, speed)
            acc_f += seg.n_frames
        hook_meta = {"plan_digest": hook_plan.get("plan_digest"),
                     "recipe": hook_plan.get("recipe"),
                     "affected_segments": [s.idx for s in segments if s.hooks],
                     "frames_v2": total_frames, "frames_plan": want}

    # ── כתוביות: הקיבוץ והגיאומטריה מיובאים, לא משוחזרים ──
    wf = Path(words_file) if words_file else (W / "words_final.json")
    cues_raw = group_cues(load_words(str(wf))) if wf.exists() else []
    band = {}
    if cues_raw:
        Hh = DELIVER["height"]
        Ww = DELIVER["width"]
        scale = Hh / 1920.0
        fontsize = max(28, round(120 * scale))
        stroke = max(3, round(7 * scale))
        marginv = max(40, round(430 * scale))
        # v9.13 — captions_overlay עבר לפרופילי-מותג אטומיים (3.8.26: BRAND_PROFILES
        # +BRAND_ALIASES) ושבר בשקט את ממשק v2 (co.FONT_TTF / co.BRAND_COLORS כבר
        # לא קיימים) — נתפס רק ב-test_render_v2, כי ברירת המחדל v1 הסתירה את זה.
        # הפונט והמתאר נגזרים מהפרופיל — אותו מקור אמת בדיוק של v1 (co.burn).
        _prof = (co.BRAND_PROFILES.get(co.BRAND_ALIASES.get(brand, brand))
                 or co.BRAND_PROFILES["club"])
        font = ImageFont.truetype(str(_prof["font"]), fontsize)
        y0, band_h = co.band_box(cues_raw, Ww, Hh, font, stroke, marginv)
        band = {"y0": int(y0), "h": int(band_h), "fontsize": fontsize,
                "stroke": stroke, "marginv": marginv,
                "baseline_in_band": (Hh - marginv) - y0,
                "outline": list(_prof["outline"]),
                "font": str(_prof["font"]), "n_cues": len(cues_raw)}
        cue_objs = [Cue(float(c["start"]), max(float(c["end"]), float(c["start"]) + 0.05),
                        str(c["text"])) for c in cues_raw]
        _clip_to_segments(
            cue_objs, segments,
            lambda c: (c.start, c.end),
            lambda seg, c, ls, le, _off: seg.cues.append(Cue(round(ls, 3), round(le, 3), c.text)))

    # ── בירולים ──
    bp = Path(broll_plan_file) if broll_plan_file else (W / "broll_plan.json")
    plan = _jload(bp, {}) or {}
    items = plan.get("plan") or []
    clips = []
    for it in items:
        p = it.get("path")
        if not p or not Path(p).exists():
            continue
        s0 = float(it.get("insert_at", 0))
        e0 = float(it.get("insert_end", s0 + float(it.get("clip_len", 2.8))))
        clips.append(BrollClip(path=p, start=s0, end=e0,
                               src_offset=float(it.get("src_offset", 0) or 0)))
    mark_seam_fades(clips)
    _clip_to_segments(
        clips, segments, lambda c: (c.start, c.end),
        lambda seg, c, ls, le, off: seg.broll.append(broll_fragment(c, ls, le, off)))

    color = probe_color(inp)
    src_overrides = apply_source_overrides(W, segments, inp, color)
    tl = Timeline(workdir=W, input_path=inp, segments=segments, band=band,
                  brand=brand, crf=int(crf or DELIVER["crf"]), speed=speed,
                  color=color)
    for seg in segments:
        seg.key = _segment_key(tl, seg)
    tl_meta = {"source_of_truth": source_of_truth, "engine": ENGINE_VERSION,
               "n_segments": len(segments), "n_cues": band.get("n_cues", 0),
               "n_broll_placements": sum(len(s.broll) for s in segments),
               "speed": speed, "speed_source": speed_src, "dur": tl.dur,
               "color": color, "source_overrides": src_overrides}
    if hook_meta:
        tl_meta["visual_hook"] = hook_meta
    tl.meta = tl_meta            # type: ignore[attr-defined]
    return tl


def apply_source_overrides(W, segments, inp, color):
    """v8.8 — מקור פר-סגמנט, מוצהר במפורש.

    למה זה קיים: בחלק מהפרויקטים הורכב ביניים ביד (EXPORT_with_effect,
    EXPORT_reordered, EXPORT_TIGHT2) ואין דרך אלגוריתמית למפות אותו חזרה לציר
    ה-INPUT. מנוע v2 מרנדר מה-INPUT ולכן פשוט לא ידע עליו — וה-A/B סימן את
    הפרויקטים האלה "לא ישים". הקובץ הזה הוא ההצהרה: איזה סגמנט נלקח מאיזה קובץ.

    segment_sources.json:
      {"schema_version": 1, "note": "למה", "overrides": [
        {"idx": 3, "src": "EXPORT_with_effect.mp4", "t_in": 12.4, "t_out": 15.02}]}

    שתיקה אינה אופציה. הצהרה שמפנה לקובץ שאינו קיים, לחלון באורך שונה, או
    למקור עם תגי צבע אחרים — נכשלת קשה. הפלט של "כמעט נכון" נראה תקין ומכיל
    את הקטע הלא נכון, וזה בדיוק הכשל שהמנוע הזה בא למנוע.
    """
    f = Path(W) / "segment_sources.json"
    if not f.exists():
        return []
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"segment_sources.json פגום: {e}")
    applied = []
    for ov in doc.get("overrides") or []:
        i = int(ov["idx"])
        if not (0 <= i < len(segments)):
            raise ValueError(f"segment_sources: idx {i} מחוץ לטווח (יש {len(segments)} סגמנטים)")
        seg = segments[i]
        src = Path(ov["src"])
        if not src.is_absolute():
            src = Path(W) / src
        if not src.exists():
            raise ValueError(f"segment_sources[{i}]: הקובץ {src} לא קיים")
        has_win = ov.get("t_in") is not None and ov.get("t_out") is not None
        if (ov.get("t_in") is None) != (ov.get("t_out") is None):
            raise ValueError(f"segment_sources[{i}]: צריך t_in ו-t_out ביחד, או אף אחד")
        if has_win:
            ti, to = float(ov["t_in"]), float(ov["t_out"])
            if abs((to - ti) - seg.dur) > 0.02:
                raise ValueError(
                    f"segment_sources[{i}]: חלון באורך {to-ti:.3f}ש מול סגמנט של "
                    f"{seg.dur:.3f}ש — הפרש כזה משנה את משך הפלט")
            seg.t_in, seg.t_out = round(ti, 3), round(to, 3)
        c2 = probe_color(src)
        for k in ("primaries", "trc", "space", "range"):
            if c2.get(k) != color.get(k):
                raise ValueError(
                    f"segment_sources[{i}]: תגי צבע שונים מה-INPUT "
                    f"({k}: {c2.get(k)} מול {color.get(k)}) — לא מתייגים מחדש בלי המרה")
        seg.src = str(src)
        applied.append({"idx": i, "src": src.name,
                        "range": [seg.t_in, seg.t_out], "note": ov.get("note", "")})
    return applied


def _segment_key(tl: Timeline, seg: Segment) -> str:
    """מפתח המטמון — כל מה שמשפיע על הפיקסלים של הסגמנט הזה, ורק זה.

    מה **לא** נכנס: המוזיקה (נוגעת רק באודיו הגלובלי), ה-loudness, שם הפרויקט,
    ומספר הסגמנט. לכן שינוי מוזיקה = אפס רינדור וידאו, והזזת סגמנט בציר לא
    פוסלת אותו."""
    d = {
        "engine": ENGINE_VERSION,
        "deliver": {k: v for k, v in DELIVER.items()},
        "crf": tl.crf,
        "speed": round(tl.speed, 4),
        "src": _file_id(Path(seg.src)),
        "range": [seg.t_in, seg.t_out],
        "n_frames": seg.n_frames,
        "band": tl.band,
        "color": tl.color,
        "cues": [[c.start, c.end, c.text] for c in seg.cues],
        # fade_in/fade_out בתוך המפתח: הם משנים את הפיקסלים בתפר, ומטמון שלא
        # מכיר אותם היה מגיש סגמנט ישן עם ה-fade הישן אחרי התיקון.
        "broll": [[_file_id(Path(b.path)), b.start, b.end, b.src_offset,
                   b.fade, b.fade_in, b.fade_out] for b in seg.broll],
    }
    # Visual Hook — רק בסגמנט מושפע. בלי hooks המילון זהה לחלוטין לזה שלפני
    # הפיצ'ר, ולכן המטמון הקיים ממשיך לשרת (off/NO_OP = אפס רינדור מחדש).
    if seg.hooks:
        d["visual_hook"] = [h["fragment_digest"] for h in seg.hooks]
    return _sha(d)[:24]


# ═══════════════════════════════════════════════════════════ רינדור סגמנט
def probe_color(path) -> dict:
    """תגי הצבע של המקור. **לא ממירים צבע** — רק מוודאים שהתגים לא נופלים.

    למה לא לכפות bt709: נמדד 30.7.26 שקיים לפחות פרויקט אחד שה-INPUT שלו מתויג
    `bt2020` (כלומר מסלול ה-HLG/tonemap.swift לא רץ עליו). לתייג אותו bt709 בלי
    להמיר היה **משנה את הפרשנות** של הצבע — בדיוק ההפך מהכלל "אסור לגעת בצבע
    ב-99%". לכן: מקור מתויג → מעבירים את התגים שלו הלאה בכל שלב; מקור לא-מתויג
    → bt709 (ההנחה הסבירה לתוכן SDR), פעם אחת ומפורש."""
    r = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=color_primaries,color_trc,color_space,color_range",
            "-of", "json", str(path)], timeout=60)
    s = ((_jload_str(r.stdout) or {}).get("streams") or [{}])[0]

    def pick(v, dflt):
        v = (v or "").strip().lower()
        return dflt if v in ("", "unknown", "unspecified", "reserved") else v

    return {"primaries": pick(s.get("color_primaries"), "bt709"),
            "trc": pick(s.get("color_trc"), "bt709"),
            "space": pick(s.get("color_space"), "bt709"),
            "range": pick(s.get("color_range"), "tv"),
            "source_tagged": bool(pick(s.get("color_primaries"), "") )}


def _jload_str(t):
    try:
        return json.loads(t or "{}")
    except Exception:
        return {}


def probe_wh(path):
    """(רוחב, גובה) של זרם הווידאו — לדילוג על סקיילינג מיותר."""
    r = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
           timeout=60)
    try:
        w, h = (r.stdout or "").strip().split("\n")[0].split("x")
        return int(w), int(h)
    except Exception:
        return None, None


_WH_CACHE: dict = {}


def _wh_cached(path):
    p = str(path)
    if p not in _WH_CACHE:
        _WH_CACHE[p] = probe_wh(p)
    return _WH_CACHE[p]


def _vf_normalize(color=None, src_wh=None) -> str:
    """נרמול פעם אחת: רזולוציה, SAR, fps, ותגי צבע.

    שורש הרזולוציה: ב-v1 אין אף שלב שמנרמל ל-1080×1920 — הסקיילינג היחיד הוא של
    רקע הבירול — ו-G5_format חוסם על זה רק בסוף, אחרי 4-7 קידודים.
    שורש הצבע: אפס דגלי צבע בכל הצנרת של v1, ולכן התגים נקבעים אחרת בכל שלב.
    `setparams` הוא הדרך האמינה — הוא קובע את מאפייני ה-frame, שמתפשטים מעצמם
    לקודק ולמכל (דגלי ‎-colorspace לבד לא תפסו במדידה)."""
    w, h = DELIVER["width"], DELIVER["height"]
    # דילוג על scale+pad כשהמקור **כבר** בגיאומטריית המסירה. כל resample מרכך,
    # וגם lanczos על 1080×1920→1080×1920 אינו זהות ביט-לביט (30.7.26).
    if src_wh and tuple(src_wh) == (w, h):
        vf = f"setsar=1,fps={DELIVER['fps']}"
    else:
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,"
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
              f"setsar=1,fps={DELIVER['fps']}")
    c = color or {"primaries": "bt709", "trc": "bt709", "space": "bt709", "range": "tv"}
    vf += (f",setparams=color_primaries={c['primaries']}:color_trc={c['trc']}"
           f":colorspace={c['space']}:range={c['range']}")
    return vf


# ⏱ ראה ההערה ב-`render_segment`. ניתן לדריסה בסביבה לצורך דיבוג.
SEGMENT_TIMEOUT = float(os.environ.get("REL_SEGMENT_TIMEOUT", "240"))

# 🚧 ליקוי פתוח — v2 נתקע על overlay. השורש עדיין לא ידוע.
#
# מה שנמדד ב-31.7.26 (‏v9.7) ומחליף את ההשערה הקודמת:
#   • זו **תקיעת filtergraph**, לא I/O. ‏`sample` על התהליך התקוע: ה-thread
#     הראשי ב-`sch_wait`, כל ה-decoder threads ב-`pthread_cond_wait`, 0% CPU,
#     ואף syscall של read/write. ‏`-loglevel debug` מראה את הפלט קופא על
#     frame 145 (‏4.76ש) בזמן שהקלט הראשי כבר הגיע ל-pts 6.88.
#   • **המפעיל הוא הסגמנט, לא מספר הקליפים.** ‏27.21-34.24 עם *שלושה*
#     בירולים נתקע; 34.85-49.11 עם *שישה* מרנדר ב-9.1ש. בסגמנט הרע **כל**
#     בירול בודד מספיק כדי לתקוע, ובלי בירול כלל הוא מרנדר ב-2.1ש.
#     ⇒ הכלל הישן `MATTRESS_MIN_CLIPS = 3` נשען על הכללה שגויה: הוא גם לא
#     מגן (סגמנט רע עם 2 בירולים נתקע) וגם מוריד לחינם סגמנטים תקינים ל-v1.
#   • נשלל במדידה גם: אורך רצועת הכתוביות (תואם את הסגמנט בדיוק ב-10/10
#     הסגמנטים) · קלט בירול עם אפס פריימים (כולם מפיקים) · אודיו ·
#     ‏`repeatlast=0` · `shortest=0` · בלי `enable=` · `setpts` על ה-base ·
#     ‏`fps` אחרי `setpts` · `-fps_mode cfr` · `filter_threads=1`.
#     (‏tools/bench/ov_variant_sweep.py — כל השמונה נתקעו.)
#
# לכן המדיניות עברה מ**ניחוש לפי ספירה** ל**מדידה פר-סגמנט**: מנסים v2 עם
# תקציב זמן קצר, ומי שנתקע — ורק הוא — יורד ל-v1. ראה `SEGMENT_SOFT_TIMEOUT`.
MATTRESS_MIN_CLIPS = 3          # נשמר לתאימות; אינו בשימוש כשער יותר

# ⏱ תקציב "נסה v2" לסגמנט עם overlay. סגמנט טיפוסי (7ש, 1080×1920, medium)
# מקודד ב-2-10ש; 45ש הוא פי-כמה מזה. חריגה = תקיעה, לא איטיות.
SEGMENT_SOFT_TIMEOUT = float(os.environ.get("REL_SEGMENT_SOFT_TIMEOUT", "45"))


def _caption_pngs(tl: Timeline, seg: Segment, sdir: Path) -> Path | None:
    """מרנדר PNG לכל cue בסגמנט + רשימת concat בזמנים מקומיים.
    רינדור ה-PNG עצמו הוא `captions_overlay.render_cue` — אותו קוד בדיוק
    שמייצר את הכתוביות ב-v1, כולל ה-RTL וה-raqm."""
    if not seg.cues or not tl.band:
        return None
    import captions_overlay as co
    from PIL import Image, ImageFont

    b = tl.band
    font = ImageFont.truetype(b["font"], b["fontsize"])
    outline = tuple(b["outline"])
    Ww, band_h = DELIVER["width"], b["h"]
    blank = sdir / "_blank.png"
    Image.new("RGBA", (Ww, band_h), (0, 0, 0, 0)).save(str(blank), compress_level=1)

    with ThreadPoolExecutor(max_workers=min(6, (os.cpu_count() or 4))) as ex:
        list(ex.map(lambda ic: co.render_cue(ic[1].text, Ww, band_h, font, b["stroke"],
                                            b["baseline_in_band"],
                                            sdir / f"c{ic[0]:04d}.png", outline),
                    list(enumerate(seg.cues))))

    # ⚠️ המרת ציר: ה-cues שמורים בזמנים של הפלט **הסופי** (אחרי האצה), אבל
    # ה-overlay מוחל לפני ה-setpts ולכן חייב זמנים לפני-האצה. מכפילים ב-speed.
    sp = max(seg.speed, 0.001)
    L, t, dur = ["ffconcat version 1.0"], 0.0, seg.dur
    for i, c in enumerate(seg.cues):
        s, e = max(0.0, c.start * sp), min(dur, max(c.end * sp, c.start * sp + 0.05))
        if e <= s:
            continue
        if s > t + 0.002:
            L += ["file '_blank.png'", f"duration {round(s - t, 3)}"]
        L += [f"file 'c{i:04d}.png'", f"duration {round(e - s, 3)}"]
        t = e
    if dur > t + 0.002:
        L += ["file '_blank.png'", f"duration {round(dur - t, 3)}"]
    L.append("file '_blank.png'")
    lst = sdir / "caps.txt"
    lst.write_text("\n".join(L) + "\n", encoding="utf-8")
    return lst


_KF_CACHE: dict = {}


def _kf_before(src, t: float) -> float:
    """חותמת ה-keyframe האחרון שלפני `t` (או `t` עצמו אם אין)."""
    key = (str(src), round(float(t), 3))
    if key in _KF_CACHE:
        return _KF_CACHE[key]
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
         "-show_entries", "frame=pts_time", "-of", "csv=p=0",
         "-read_intervals", f"{max(0.0, t - 15):.2f}%{t:.2f}", str(src)],
        capture_output=True, text=True)
    ks = []
    for x in (r.stdout or "").split():
        try:
            ks.append(float(x.rstrip(",")))
        except ValueError:
            pass
    ks = [k for k in ks if k <= t + 1e-6]
    _KF_CACHE[key] = max(ks) if ks else float(t)
    return _KF_CACHE[key]


def _safe_seek_cmd(cmd, seg):
    """גרסה של הפקודה שעוקפת את **השורש** של התקיעה ב-v2.

    מה נמדד (‏31.7.26, `bench/ov_minimal_repro.py`, ffmpeg 8.1):
      בסיס אמיתי + שכבה **סינתטית** ⇒ נתקע · בסיס סינתטי + שכבה אמיתית ⇒ עובר ·
      בסיס **חתוך-מראש לקובץ** (בלי ‎-ss) + אותה שכבה ⇒ עובר.
    ⇒ המפעיל אינו הבירול, אינו הכתוביות ואינו פרמטרי ה-overlay, אלא
    **ה-seek המדויק על הקלט כשיש overlay בגרף**. הפלט קופא על frame=25.
    נשללו במדידה: filter_complex_threads · threads · genpts · tpad ·
    eof_action=repeat · shortest=0 · ‎-frames:v · בלי כתוביות · ריפוד שקוף ·
    בלי enable · setpts על הבסיס · avoid_negative_ts · trim במקום ‎-to ·
    ‎-ss אחרי ‎-i. **הדבר היחיד שריפא: `-noaccurate_seek`.**

    ‏`-noaccurate_seek` לבדו היה מזיז את נקודת החיתוך ל-keyframe, ולכן כאן
    הוא בא עם `trim` מפצה בגרף (וידאו **ואודיו**) — מדויק פריים-לפריים
    (‏91 פריימים ב-0.7ש ברפרודוקציה).

    ⚠️ **הפונקציה הזאת אינה בשימוש בצנרת** — היא נמדדה על הפקודה האמיתית
    ונכשלה (‏`bench/ov_final_probe.py`), גם אחרי הפשטה מלאה. היא נשארת
    כאן כתיעוד מדויק של מה שנוסה ומה ידוע, ולשימוש הכלים ב-`bench/`.
    התיעוד המלא: `FFMPEG-STALL.md`.
    """
    try:
        i = cmd.index("-filter_complex")
        if cmd[6] != "-ss" or cmd[8] != "-to" or cmd[10] != "-i":
            return None
        src = cmd[11]
        kf = _kf_before(src, seg.t_in)
        delta = max(0.0, float(seg.t_in) - kf)
        dur = float(seg.t_out) - float(seg.t_in)
        new = cmd[:6] + ["-noaccurate_seek", "-ss", f"{kf:.3f}", "-i", src] + cmd[12:]
        j = new.index("-filter_complex") + 1
        g = new[j]
        g = g.replace("[0:v]", f"[0:v]trim=start={delta:.3f}:duration={dur:.5f},"
                               f"setpts=PTS-STARTPTS,", 1)
        g = g.replace("[0:a]", f"[0:a]atrim=start={delta:.3f},"
                               f"asetpts=PTS-STARTPTS,", 1)
        new[j] = g
        return new
    except (ValueError, IndexError, TypeError):
        return None


def render_segment(tl: Timeline, seg: Segment, cache: Path, force=False) -> dict:
    """מרנדר סגמנט אחד לפרמטרי המסירה, עם כתוביות ובירולים צרובים.
    מחזיר {'key','path','cached','secs','stderr'}."""
    out = cache / f"seg_{seg.key}.mkv"
    if out.exists() and not force and out.stat().st_size > 1024:
        return {"key": seg.key, "path": str(out), "cached": True, "secs": 0.0}

    t0 = time.time()
    sdir = cache / f"_w_{seg.key}"
    if sdir.exists():
        shutil.rmtree(sdir, ignore_errors=True)
    sdir.mkdir(parents=True, exist_ok=True)
    try:
        caps = _caption_pngs(tl, seg, sdir)

        cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
               "-ss", f"{seg.t_in:.3f}", "-to", f"{seg.t_out:.3f}", "-i", seg.src]
        for b in seg.broll:
            cmd += ["-ss", f"{max(0.0, b.src_offset):.3f}",
                    "-t", f"{max(0.05, b.end - b.start):.3f}", "-i", b.path]
        if caps is not None:
            cmd += ["-f", "concat", "-safe", "0", "-i", str(caps)]

        n_br = len(seg.broll)
        cap_idx = 1 + n_br if caps is not None else None
        sp = max(seg.speed, 0.001)      # ראה הערת המרת-הציר ב-_caption_pngs

        _hook_chain = "".join("," + h["filter"] for h in (seg.hooks or []))
        parts = [f"[0:v]{_vf_normalize(tl.color, _wh_cached(seg.src))}{_hook_chain}[base]"]
        cur = "base"
        # בירולים: מסך-מלא, mute, fade על האלפא בכניסה/יציאה (הכלל הנעול —
        # fade קשה יצר "קפיצה מוזרה" בסוף כל בירול).
        for i, b in enumerate(seg.broll, start=1):
            bs, be = b.start * sp, b.end * sp      # ציר לפני-האצה
            ln = max(0.05, be - bs)
            fd = min(b.fade, ln / 3.0)
            fd_in = fd if b.fade_in else 0.0
            fd_out = fd if b.fade_out else 0.0
            chain = [_vf_normalize(tl.color, _wh_cached(b.path)), "format=yuva420p"]
            if fd_in > 0:
                chain.append(f"fade=t=in:st=0:d={fd_in:.3f}:alpha=1")
            if fd_out > 0:
                chain.append(f"fade=t=out:st={max(0.0, ln - fd_out):.3f}:"
                             f"d={fd_out:.3f}:alpha=1")
            chain.append(f"setpts=PTS-STARTPTS+{bs:.3f}/TB")
            parts.append(f"[{i}:v]{','.join(chain)}[br{i}]")
            # eof_action=repeat ולא pass — v8.4 (נמדד פריים-פריים): ב-pass,
            # כשהקלט המשני מגיע ל-EOF באמצע פריים, ffmpeg מעביר את **הבסיס**,
            # כלומר פריים אחד של פנים בכל תפר בירול. זה מה שהראל ראה כ"רואים
            # אותי בין בירול לבירול" גם כשהתוכנית הראתה חור=0. repeat מקפיא את
            # הפריים האחרון של הבירול ⇒ חשיפת-פנים בתפר בלתי-אפשרית מבנית.
            # אין דליפה מחוץ לחלון: ה-enable מכבה את ה-overlay ממילא.
            parts.append(f"[{cur}][br{i}]overlay=0:0:eof_action=repeat:"
                         f"enable='between(t,{bs:.3f},{be:.3f})'[ov{i}]")
            cur = f"ov{i}"
        if cap_idx is not None:
            parts.append(f"[{cur}][{cap_idx}:v]"
                         f"overlay=0:{tl.band['y0']}:format=auto:eof_action=pass[vcap]")
            cur = "vcap"
        # ── אכיפת ספירת פריימים מדויקת ──
        # setpts דוחס את הזמנים; fps=30 מחזיר לרשת קבועה; tpad מבטיח שיש **לפחות**
        # n_frames (משכפל את הפריים האחרון אם חסרים 1-2 — בגבול חיתוך זה בלתי-מורגש,
        # ולעולם לא מכניס תוכן שהיה אמור להיחתך, בניגוד להרחבת חלון הקריאה).
        # ‎-frames:v חותך בדיוק ל-n_frames.
        vf_tail = []
        if abs(tl.speed - 1.0) > 0.001:
            vf_tail.append(f"setpts=PTS/{tl.speed}")
        vf_tail += [f"fps={DELIVER['fps']}", "tpad=stop_mode=clone:stop_duration=0.5"]
        parts.append(f"[{cur}]{','.join(vf_tail)}[vout]")
        cur = "vout"

        adur = seg.n_frames / DELIVER["fps"] if seg.n_frames else seg.dur_final
        af = []
        if abs(tl.speed - 1.0) > 0.001:
            af.append(f"atempo={tl.speed}")
        af += ["apad", f"atrim=0:{adur:.5f}", "asetpts=N/SR/TB"]
        parts.append(f"[0:a]{','.join(af)}[aout]")
        amap = "[aout]"

        cmd += ["-filter_complex", ";".join(parts), "-map", f"[{cur}]", "-map", amap]
        if seg.n_frames:
            cmd += ["-frames:v", str(seg.n_frames)]
        cmd += [
            "-c:v", DELIVER["vcodec"], "-crf", str(tl.crf), "-preset", DELIVER["preset"],
            "-pix_fmt", DELIVER["pix_fmt"], "-profile:v", DELIVER["profile"],
            "-level", DELIVER["level"], "-r", str(DELIVER["fps"]),
            # תיוג צבע — ב-v1 אפס דגלי צבע בכל הצנרת, ולכן התגים נקבעים
            # אחרת בכל שלב. כאן פעם אחת, מפורש.
            "-colorspace", tl.color["space"], "-color_primaries", tl.color["primaries"],
            "-color_trc", tl.color["trc"], "-color_range", tl.color["range"],
            # PCM בביניים — כדי שה-concat לא יוסיף דור, וה-AAC היחיד ייווצר במיקס.
            "-c:a", DELIVER["acodec"], "-ar", str(DELIVER["ar"]), "-ac", str(DELIVER["ac"]),
            str(out.with_suffix(".tmp.mkv")),
        ]
        # ⏱ תקציב זמן לסגמנט — לא 1800ש.
        # נמדד 31.7.26: סגמנט עם בירולים נתקע על **0% CPU** ו-`sh` המתין לו
        # חצי שעה בשקט. חצי שעה של שתיקה אינה "עדיין רץ", היא כשל שלא דיווח
        # על עצמו. סגמנט טיפוסי (7ש, 1080×1920, medium) מקודד ב-5-25ש; 240ש
        # הוא פי-עשרה מזה, כלומר תקציב נדיב שעדיין נכשל מהר ובקול.
        # סגמנט עם overlay מקבל תקציב קצר: הוא המועמד היחיד לתקיעה, ותקיעה
        # שם היא מיידית-ומוחלטת (0% CPU), לא "עוד קצת". סגמנט בלי overlay
        # מקבל את התקציב המלא — שם זמן ארוך הוא באמת קידוד כבד.
        budget = SEGMENT_SOFT_TIMEOUT if seg.broll else SEGMENT_TIMEOUT
        r = sh(cmd, timeout=budget)
        tmp = out.with_suffix(".tmp.mkv")
        # ── v9.9 — למה **אין כאן** ניסיון שני עם `-noaccurate_seek` ─────────
        # השורש נמצא (ראה `_safe_seek_cmd`), ו-`-noaccurate_seek`+trim מרפא את
        # הרפרודוקציה המינימלית ב-0.7ש. על **הפקודה האמיתית** הוא נמדד ונכשל
        # (‏bench/ov_safeseek_probe.py — גם בלי כתוביות/אודיו/tpad/frames:v).
        # תיקון שנמדד ולא עבד אינו נשאר בקוד: הוא היה מכפיל את זמן ההמתנה
        # (‏45ש→90ש) בלי להציל דבר. הנפילה ל-v1 היא ה-fallback הפעיל.
        if r.returncode != 0 or not tmp.exists():
            return {"key": seg.key, "path": None, "cached": False,
                    "secs": round(time.time() - t0, 2),
                    # 124 = תקציב הזמן נגמר. מסומן במפורש כדי שהמתזמר יוכל
                    # להבדיל בין "התקיעה הידועה" לבין שגיאת ffmpeg אמיתית.
                    "stalled": r.returncode == 124,
                    "n_broll": len(seg.broll),
                    "stderr": (r.stderr or "")[-700:]}
        os.replace(tmp, out)
        return {"key": seg.key, "path": str(out), "cached": False,
                "secs": round(time.time() - t0, 2)}
    finally:
        shutil.rmtree(sdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════ תזמור
def render(tl: Timeline, out_master: Path, *, jobs=None, force=False,
           on_progress=None) -> dict:
    """מרנדר את כל הסגמנטים (במקביל, עם מטמון) ומשרשר ב--c copy."""
    cache = tl.workdir / CACHE_DIRNAME
    cache.mkdir(parents=True, exist_ok=True)
    n_jobs = jobs or max(2, min(4, (os.cpu_count() or 4) // 2))
    t0 = time.time()

    results = [None] * len(tl.segments)

    def work(i):
        res = render_segment(tl, tl.segments[i], cache, force=force)
        results[i] = res
        if on_progress:
            on_progress(i + 1, len(tl.segments), res)
        return res

    with ThreadPoolExecutor(max_workers=n_jobs) as ex:
        list(ex.map(work, range(len(tl.segments))))

    failed = [r for r in results if not r or not r.get("path")]
    if failed:
        # התקיעה הידועה מסומנת בנפרד משגיאת ffmpeg: היא ניתנת לעקיפה
        # (‏v1 מרנדר את אותו סגמנט בלי בעיה), וזו החלטה של המתזמר ולא כישלון.
        stalled = [r for r in failed if r and r.get("stalled")]
        if stalled:
            return {"ok": False, "stalled": True,
                    "error": f"‏v2 נתקע על {len(stalled)} סגמנטים עם בירול "
                             f"(תקציב {SEGMENT_SOFT_TIMEOUT:.0f}ש). ליקוי ידוע — "
                             f"ראה relvid/render.py.",
                    "stalled_segments": [{"key": r["key"], "n_broll": r.get("n_broll")}
                                         for r in stalled],
                    "segments": results}
        return {"ok": False,
                "error": "רינדור סגמנט נכשל: " + (failed[0].get("stderr", "")[-400:]
                                                  if failed[0] else "לא ידוע"),
                "segments": results}

    lst = cache / "concat.txt"
    lst.write_text("\n".join(f"file '{Path(r['path']).name}'" for r in results) + "\n",
                   encoding="utf-8")
    tmp_master = out_master.with_suffix(".tmp.mkv")
    r = sh(["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", "concat.txt",
            "-c", "copy", str(tmp_master)], cwd=str(cache), timeout=900)
    if r.returncode != 0 or not tmp_master.exists():
        return {"ok": False, "error": "concat נכשל: " + (r.stderr or "")[-400:],
                "segments": results}
    os.replace(tmp_master, out_master)

    n_cached = sum(1 for r in results if r.get("cached"))
    return {"ok": True, "master": str(out_master),
            "n_segments": len(results), "n_cached": n_cached,
            "n_rendered": len(results) - n_cached,
            "encode_secs": round(sum(r.get("secs", 0) for r in results), 1),
            "wall_secs": round(time.time() - t0, 1),
            "jobs": n_jobs,
            "video_generations": 1, "aac_generations_so_far": 0,
            "meta": getattr(tl, "meta", {}),
            "segments": results}


def cache_stats(workdir) -> dict:
    cache = Path(workdir) / CACHE_DIRNAME
    if not cache.is_dir():
        return {"exists": False, "files": 0, "bytes": 0}
    files = list(cache.glob("seg_*.mkv"))
    return {"exists": True, "files": len(files),
            "bytes": sum(f.stat().st_size for f in files),
            "path": str(cache)}


def prune_cache(workdir, keep_keys=None) -> dict:
    """מוחק סגמנטים שאינם בציר הנוכחי. הסגמנטים עצמם זולים לשחזור (הם ניתנים
    לרינדור מחדש מהמפתח), ולכן אין סיכון לאבד מידע — רק זמן."""
    cache = Path(workdir) / CACHE_DIRNAME
    if not cache.is_dir():
        return {"removed": 0, "bytes": 0}
    keep = {f"seg_{k}.mkv" for k in (keep_keys or [])}
    removed, freed = 0, 0
    for f in cache.glob("seg_*.mkv"):
        if keep and f.name in keep:
            continue
        freed += f.stat().st_size
        f.unlink()
        removed += 1
    return {"removed": removed, "bytes": freed}
