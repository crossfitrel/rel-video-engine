#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
director_lessons — התיקונים של הראל נכנסים לפיילוד של הבמאי. למידה מ-n=1.

למה זה נולד
-----------
הראל, 16.8.26: *"טעויות שחוזרות על עצמן כמה פעמים במקום ללמוד ולהשתפר
מהפידבקים"* + *"מערכת שתדע לשפר את דפוסי החשיבה שלה."*

לולאת הלמידה הקיימת (learn_from_edits) מכיילת **ספים** — והיא בכוונה איטית:
‏≥6 ראיות מ-≥3 פרויקטים, regression, אישור. זה נכון לספים; זה לא עוזר לבמאי
שמקבל היום כל פרויקט כאילו הוא הראשון. תיקון אחד של הראל ("החזרת פאוזה לפני
המחיר") הוא כבר דפוס-טעם ששווה להראות לבמאי בפרויקט הבא — בלי לחכות לשש
ראיות, כי הוא לא משנה שום סף: הוא **הקשר**, והבמאי שופט.

מה נכנס לפיילוד
---------------
1. `rules` — הלקחים הקבועים מ-lesson_registry שסומנו director_relevant
   (משפט הכלל בלבד, סדר יציב).
2. `harel_patterns` — דפוסי התיקון של הראל מכל הפרויקטים ב-cohort
   (content_type/brand), מתורגמים למשפט הנחיה + כמה פעמים.

יציבות replay (חוק ברזל 4 — "אסור מטא-דאטה משתנה ב-payload של פאס"):
הקובץ נכתב **פעם אחת לפרויקט** (אם קיים — לא נכתב מחדש), בלי חותמות-זמן
ובלי מונים שמשתנים מריצה לריצה על אותו קלט. עדכון הידע בין פרויקטים הוא
שינוי תוכנית לגיטימי (digest חדש בפרויקט חדש); בתוך פרויקט — הקובץ קפוא.
‏--rebuild דורס במפורש (ומבטל cache של הבמאי במודע).

שימוש
-----
  python3 director_lessons.py --workdir W [--rebuild] [--json]
פלט: {workdir}/lessons_for_director.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from relvid.paths import work_root                             # noqa: E402
import learn_from_edits as LFE                                  # noqa: E402

try:
    import lesson_registry as LR
except Exception:                                               # pragma: no cover
    LR = None

MAX_PATTERNS = 8
MAX_EXAMPLES = 2

# reason_code → מה זה אומר לבמאי, במונחי ההחלטה הבאה שלו.
CODE_GUIDANCE = {
    "RC_SILENCE_RESTORE": "הראל החזיר שקט/פאוזה שנחתכו — סימן לחיתוך-יתר. "
                          "כשאתה מתלבט על פאוזה מכוונת, שמור אותה",
    "RC_TAKE_RESTORE":    "הראל החזיר טייק שנחתך ככפילות — לוודא שהטייק שנשמר "
                          "הוא באמת האחרון והשלם",
    "RC_FILLER_RESTORE":  "הראל החזיר קטע שסווג כמילוי — 'מילוי' אצלו הוא לפעמים "
                          "טקסטורה. להצהיר downside לפני שחותכים תוכן",
    "RC_OTHER_RESTORE":   "הראל ביטל חיתוכים של המערכת — כשהביטחון נמוך, עדיף "
                          "flag מאשר cut",
    "RC_MANUAL_ADD":      "הראל הוסיף חיתוכים שהמערכת לא הציעה — יש דד-אייר/כפילויות "
                          "שנשארים מתחת לספים. להסתכל גם על פערים קצרים עם תמונה קפואה",
    "RC_BOUNDARY_ADJUST": "הראל מזיז גבולות חיתוך — הגבול נוחת קרוב מדי למילה או "
                          "על תנועה. להעדיף פערים עם best_split נוח",
    "RC_ACTIVATE":        "הראל מפעיל הצעות (כתומות) שהמערכת השאירה פתוחות — "
                          "כשהראיה חזקה, אפשר יותר ביטחון בהחלטה עצמה",
    "RC_MERGE":           "הראל ממזג חיתוכים סמוכים — עדיף חיתוך אחד גדול משניים קטנים",
    "RC_HOOK":            "הראל מזיז את הפתיחה — לחפש את ה-Hook האמיתי גם באמצע",
    "RC_TRANSCRIPT":      "הראל מתקן תמליל — להקפיד על פאס ההגהה ועל שמות/מונחים",
    "RC_MUSIC":           "הראל מחליף/מכוון מוזיקה — לכבד את tone הבריף בבחירת ז'אנר",
    "RC_VIDEO_PATCH":     "הראל טילא וידאו ידנית — היה ליקוי ויזואלי שהשערים פספסו",
    "RC_GATE_OVERRIDE":   "הראל עקף שער — השער חסם משהו שהוא רצה; לבדוק את הסף",
}


def collect_patterns(cohort: str) -> list[dict]:
    """סורק corrections.jsonl בכל הפרויקטים (קריאה בלבד), מסנן bursts גס,
    ומחזיר דפוסים ממוינים דטרמיניסטית (ללא חותמות-זמן בפלט)."""
    counts: Counter = Counter()
    projects: dict[str, set] = {}
    WORK = work_root()
    if not WORK.exists():
        return []
    for d in sorted(WORK.iterdir()):
        cj = d / "corrections.jsonl"
        if not d.is_dir() or not cj.exists():
            continue
        if cohort and LFE.cohort_of(d) != cohort:
            continue
        last: dict[str, float] = {}
        for ln in cj.read_text(encoding="utf-8").splitlines():
            try:
                act = json.loads(ln)
            except Exception:
                continue
            code = LFE.classify(act)
            if not code:
                continue
            epoch = LFE._ts_epoch(act.get("ts"))
            prev = last.get(code)
            if epoch is not None and prev is not None and \
                    (epoch - prev) < LFE.BURST_GAP_SEC:
                last[code] = epoch
                continue
            if epoch is not None:
                last[code] = epoch
            counts[code] += 1
            projects.setdefault(code, set()).add(d.name)
    rows = []
    for code, n in counts.items():
        g = CODE_GUIDANCE.get(code)
        if not g:
            continue
        rows.append({"code": code, "guidance": g, "n_events": n,
                     "n_projects": len(projects.get(code, ()))})
    # דטרמיניסטי: קודם לפי שכיחות, ואז לפי שם הקוד.
    rows.sort(key=lambda r: (-r["n_events"], r["code"]))
    return rows[:MAX_PATTERNS]


def build(workdir: str, rebuild: bool = False) -> dict:
    W = Path(workdir).expanduser()
    out = W / "lessons_for_director.json"
    if out.exists() and not rebuild:
        return json.loads(out.read_text(encoding="utf-8"))
    cohort = LFE.cohort_of(W)
    doc = {
        "version": 1,
        "cohort": cohort,
        # משפטי הכלל בלבד, בסדר יציב — בלי מקורות/תאריכים (יציבות digest).
        "rules": (LR.director_lessons() if LR else []),
        "harel_patterns": collect_patterns(cohort),
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    doc = build(a.workdir, rebuild=a.rebuild)
    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=1))
    else:
        print(f"lessons_for_director.json: {len(doc['rules'])} כללים · "
              f"{len(doc['harel_patterns'])} דפוסי-הראל (cohort {doc['cohort']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
