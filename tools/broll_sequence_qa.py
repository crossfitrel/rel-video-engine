#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_sequence_qa — דקדוק חזותי של המצע: לא רק **כמה** רואים, אלא **איך**.

עד v9.7 ה-QA של הבירול מדד כיסוי (‏`coverage_pct`) ותפרים (‏`broll_seam_qa`).
שניהם שואלים "האם יש בירול ואם הוא חושף את הדובר". אף אחד מהם לא שואל
אם **הרצף עצמו נקרא טוב**: שלושה שוטים בינוניים ברצף, שתי תנועות זהות
זו אחרי זו, או קפיצת בהירות בין קליפ מואר לקליפ חשוך — כל אלה נראים
לצופה כעריכה רשלנית, וכולם עוברים את השערים הקיימים.

הכלי הזה נשען על פאס הראייה (`broll_vision_model`) ועל מדידת בהירות
מהווידאו עצמו — **לא על שמות קבצים**.

בדיקות:
  shot_variety     — ‏≤3 קליפים רצופים באותו סוג שוט
  movement_repeat  — אין שתי קטגוריות תנועה זהות ברצף
  crowding_variety — המצע לא כולו אותה צפיפות
  brightness_jump  — קפיצת בהירות בין קליפים סמוכים
  camera_repeat    — ‏≤3 קליפים רצופים באותה תנועת מצלמה

    python3 broll_sequence_qa.py --workdir W [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import broll_vision_model as VM  # noqa: E402

try:
    import gate_registry as GR  # noqa: E402
except Exception:               # pragma: no cover
    GR = None

MAX_SAME_SHOT = 3        # ‏4 ברצף = הצופה מפסיק לקרוא שינוי
MAX_SAME_CAMERA = 3
BRIGHTNESS_JUMP = 60.0   # דלתא ממוצע-לומה (0-255) שנקראת כ"הבזק"


def mean_luma(path: str, at: float = 1.0) -> float | None:
    """בהירות ממוצעת בפריים אחד. נמדד מהווידאו, לא משוער מהתגיות."""
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{at:.2f}",
         "-i", path, "-frames:v", "1", "-vf", "scale=64:64,format=gray",
         "-f", "rawvideo", "-"], capture_output=True)
    if r.returncode or not r.stdout:
        return None
    data = r.stdout[:64 * 64]
    return sum(data) / max(1, len(data))


def analyze(plan: dict, *, with_brightness=True) -> dict:
    items = [p for p in plan.get("plan", []) if p.get("role") != "anchor"]
    seq = []
    for p in items:
        v = None
        try:
            v = VM.lookup(p["path"])
        except OSError:
            v = None
        seq.append({
            "file": Path(p["path"]).name,
            "path": p["path"],
            "category": Path(p["path"]).parent.name,
            "shot": (v or {}).get("shot"),
            "crowding": (v or {}).get("crowding"),
            "camera": (v or {}).get("camera"),
        })

    issues = []

    def run_len(key, limit, label):
        """הערה **אחת לכל רצף**, לא אחת לכל קליפ בתוכו. דיווח שמתנפח
        עם אורך הרצף מסתיר את גודל הבעיה במקום להראות אותו."""
        i = 0
        while i < len(seq):
            cur = seq[i].get(key)
            j = i
            while j + 1 < len(seq) and cur is not None \
                    and seq[j + 1].get(key) == cur:
                j += 1
            n = j - i + 1
            if cur is not None and n > limit:
                issues.append({
                    "check": label, "level": "WARN", "at": i, "run": n,
                    "detail": f"{n} קליפים רצופים עם {key}={cur} (מקס {limit}) "
                              f"— {seq[i]['file']} … {seq[j]['file']}"})
            i = j + 1

    run_len("shot", MAX_SAME_SHOT, "shot_variety")
    run_len("camera", MAX_SAME_CAMERA, "camera_repeat")

    for i in range(1, len(seq)):
        if seq[i]["category"] and seq[i]["category"] == seq[i - 1]["category"]:
            issues.append({
                "check": "movement_repeat", "level": "WARN", "at": i,
                "detail": f"שתי קטגוריות זהות ברצף: {seq[i]['category']} "
                          f"({seq[i - 1]['file']} → {seq[i]['file']})"})

    crowds = {s["crowding"] for s in seq if s["crowding"]}
    if len(seq) >= 5 and len(crowds) <= 1:
        issues.append({"check": "crowding_variety", "level": "WARN", "at": -1,
                       "detail": f"כל המצע באותה צפיפות ({crowds}) — "
                                 f"תמונה אחת שחוזרת אינה תמונה"})

    if with_brightness:
        for s in seq:
            s["luma"] = mean_luma(s["path"])
        for i in range(1, len(seq)):
            a, b = seq[i - 1].get("luma"), seq[i].get("luma")
            if a is None or b is None:
                continue
            if abs(a - b) > BRIGHTNESS_JUMP:
                issues.append({
                    "check": "brightness_jump", "level": "WARN", "at": i,
                    "detail": f"קפיצת בהירות {abs(a - b):.0f} "
                              f"({seq[i - 1]['file']} → {seq[i]['file']})"})

    # למה זה מדווח ולא חוסם — כדאטה בדוח, לא כהערה בקוד. הבריכה עצמה
    # 47/56 `medium`, ולכן שער חוסם היה מכשיל סרטונים תקינים במקום להצביע
    # על **חוב הצילום** האמיתי. `fallback` כאן הוא רשימת השוטים החסרים.
    if GR:
        for i in issues:
            i["why"] = GR.annotate("broll_sequence_qa", i["check"])

    return {"n_bed": len(seq), "issues": issues,
            "result": "PASS" if not issues else "PASS_WITH_WARNINGS",
            "shot_debt": shot_debt(seq, issues),
            "sequence": seq}


def shot_debt(seq: list[dict], issues: list[dict]) -> list[dict]:
    """מה חסר בבריכה כדי שהרצף הזה היה נקרא טוב — לא מה פסול בסרטון.

    זה ההבדל בין שער שאומר "לא" לשער שמסיים את העבודה: הליקוי הוא שאין
    שוטים רחבים של הרחבה, וזה חוב **צילום**. הפלט הזה זורם לבורד הסושיאל
    (`broll_shot_debt.py`) כפריט צילום עם נימוק ומקור.
    """
    debt = []
    shots = [s["shot"] for s in seq if s.get("shot")]
    if shots and "wide" not in shots:
        debt.append({"need": "wide", "why": f"אפס שוטים רחבים ב-{len(shots)} "
                     f"קליפי מצע — הצופה לא רואה את הרחבה, רק פרטים",
                     "n_seen": len(shots)})
    if shots and "close" not in shots and "detail" not in shots:
        debt.append({"need": "detail", "why": "אין שוט פרט — אין לאן להתקרב "
                     "אחרי רחב/בינוני", "n_seen": len(shots)})
    runs = [i for i in issues if i["check"] in ("shot_variety", "camera_repeat")]
    for r in runs:
        debt.append({"need": "variety", "why": r["detail"], "run": r.get("run")})
    return debt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--json", dest="out_json")
    ap.add_argument("--no-brightness", action="store_true")
    a = ap.parse_args()
    W = Path(a.workdir).expanduser()
    bp = W / "broll_plan.json"
    if not bp.exists():
        print("אין broll_plan.json — אין רצף לבדוק")
        return 0
    rep = analyze(json.loads(bp.read_text(encoding="utf-8")),
                  with_brightness=not a.no_brightness)
    out = Path(a.out_json) if a.out_json else (W / "broll_sequence_report.json")
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    mark = "✅" if rep["result"] == "PASS" else "⚠️"
    print(f"{mark} רצף מצע: {rep['n_bed']} קליפים · {len(rep['issues'])} הערות")
    for i in rep["issues"][:8]:
        print(f"   ⚠️  {i['check']}: {i['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
