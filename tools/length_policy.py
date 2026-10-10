#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
length_policy — מדיניות האורך של הריל, לפי סוג התוכן. מקור אמת יחיד (v9.25, 19.9.26).

למה זה נולד
-----------
הראל, 19.9.26: *"לא כל סרטון חייב להיות מוגבל עד 60 שניות."*
תקרת ה-60ש (23.7.26) נאכפה בחמישה מקומות שונים עם מספרים קשיחים
(qa_gates / canon_lint / preflight / edit_plan / local_finish_pipeline + review-app),
כולל האצה אוטומטית 1.05-1.15 רק כדי להיכנס מתחת ל-60. המדידה אומרת שזה הלוחץ הלא-נכון:

  • מדידה פנימית — 40 ריילס של @crossfitrel (יוני-ספט׳ 2026, Metricool):
      אורך ↔ reach:          rho=+0.10  (p=0.53)  — אין קשר
      אורך ↔ avg watch time: rho=+0.50  (p=0.001) — ארוך = יותר שניות צפייה
      אורך ↔ retention %:    rho=-0.49  (p=0.001) — ארוך = אחוז צפייה נמוך יותר
      view-rate 3ש ↔ reach:  rho=+0.83  (p<0.001) — ההוק הוא הלוחץ, לא האורך
    שני האפקטים של האורך מקזזים זה את זה. ריל אישי של 67ש (@harel_hayon, 11.9.26)
    הגיע ל-15,550 reach — מעל התקרה הישנה.
  • Socialinsider (6M ריילס של מותגים, ינו׳-יוני 2026): חציון צפיות 45-60ש = 10,374 ·
    60-90ש = 9,790 · 120-180ש = 9,000 · 180ש+ = 4,428. אין "צוק" ב-60ש; יש צוק ב-3 דק׳.
  • Mosseri (22.1.25): שלושת האותות המובילים — watch time, likes, sends; sends
    חשובים יותר לתוכן לא-מחובר (קהל קר). ריילס עד 3 דק׳, "עדיין ממוקדים בקצר".

העיקרון: **האורך נקבע ע"י התוכן — הכי קצר שמנחית את הרעיון במלואו.** האורך לא
מקבל שער חוסם על סף שלא נמדד (עיקרון 1 + "אין שער חוסם עם סף לא-מדוד").
חוסמים רק שני דברים שהם עובדה: מתחת ל-12ש (תקלת חיתוך — יש CTA מוגן 8ש)
ומעל 180ש (מעל 3 דק׳ אינסטגרם לא מפיץ לקהל חדש; החציון נחתך פי 2).

הגדרת הראל 19.9.26 (ערב): ריל שיווקי/הוק ≈20-45ש · סיפור/הסבר/חיבור/ערך 45-90ש תקין לגמרי ·
מעל 90ש צריך סיבה אמיתית שהצופה ירצה להמשיך (length_reason) — לכל סוג, כולל המרה
(v9.26: סף הנימוק להמרה עלה 60→90 כדי ליישר למספר של הראל; 45-90 בהמרה = מחוץ ליעד, אזהרה רכה).
פודקאסט (120) לא נכלל בהגדרה של הראל ונשאר כפי שנמדד.

שלוש רמות לכל סוג תוכן
----------------------
  target        — הטווח שהבמאי מכוון אליו. מחוץ לו = אזהרה רכה בלבד.
  reason_above  — מעל זה הסרטון חייב נימוק אורך (length_reason במניפסט):
                  לולאה פתוחה / סיפור עם מתח / הדגמה שלא מתקצרת. בלי נימוק = אזהרה
                  בינונית בפרה-פלייט (לא חוסם — ההכרעה של הראל).
  HARD_MIN/MAX  — חוסם (G1).

שימוש
-----
  python3 length_policy.py                       # טבלת המדיניות
  python3 length_policy.py --eval 72 --type value [--reason "..."]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HARD_MIN = 12.0
HARD_MAX = 180.0

_VALUE = {"target": (45.0, 90.0), "reason_above": 90.0,
          "label": "ערך / הסבר מקצועי",
          "why": "הצופה נשאר כשיש מה ללמוד; 45-90ש = אזור השיא במחקר (9.8K-10.4K חציון)"}
_STORY = {"target": (45.0, 90.0), "reason_above": 90.0,
          "label": "סיפור / חיבור / אישי",
          "why": "מתח וקשת סיפור מחזיקים; ריל אישי 67ש הגיע ל-15.5K"}

BANDS: dict[str, dict] = {
    "conversion": {"target": (20.0, 45.0), "reason_above": 90.0,
                   "label": "המרה / הוק — קהל קר",
                   "why": "קהל קר מחליט ב-3 שניות ומופץ לפי sends; view-rate 3ש מנבא reach "
                          "(rho=0.83). מספיק: Hook + הוכחה + CTA 8ש"},
    "value": _VALUE,
    "throwdown_value": _VALUE,
    "story": _STORY,
    "personal": _STORY,
    "connection": _STORY,
    "podcast": {"target": (45.0, 90.0), "reason_above": 120.0,
                "label": "קטע פודקאסט",
                "why": "רעיון שלם אחד מתוך שיחה; מעל 2 דק׳ רק כשהקטע הוא סיפור אחד רציף"},
}
DEFAULT_TYPE = "value"


def band(content_type: str | None) -> dict:
    ct = (content_type or DEFAULT_TYPE).strip().lower()
    b = BANDS.get(ct) or BANDS[DEFAULT_TYPE]
    return dict(b, content_type=ct if ct in BANDS else DEFAULT_TYPE)


def evaluate(dur: float, content_type: str | None = None,
             length_reason: str | None = None) -> dict:
    """הכרעת אורך אחת לכל השכבות (QA / canon / preflight / plan / app)."""
    b = band(content_type)
    lo, hi = b["target"]
    dur = float(dur or 0.0)
    reason = (length_reason or "").strip()
    hard_ok = HARD_MIN <= dur <= HARD_MAX
    in_target = lo <= dur <= hi
    needs_reason = dur > b["reason_above"]
    reason_ok = (not needs_reason) or bool(reason)
    if not hard_ok:
        level, msg = "hard", (f"{dur:.1f}ש מחוץ לגבול הקשיח {HARD_MIN:.0f}-{HARD_MAX:.0f}ש")
    elif not reason_ok:
        level, msg = "reason", (f"{dur:.1f}ש מעל {b['reason_above']:.0f}ש ל{b['label']} "
                                f"בלי length_reason — מה ישאיר את הצופה עד הסוף?")
    elif not in_target:
        level, msg = "soft", (f"{dur:.1f}ש מחוץ ליעד {lo:.0f}-{hi:.0f}ש ל{b['label']}"
                              + (f" (נימוק: {reason[:60]})" if reason and needs_reason else ""))
    else:
        level, msg = "ok", f"{dur:.1f}ש בתוך יעד {lo:.0f}-{hi:.0f}ש ל{b['label']}"
    return {"dur": round(dur, 2), "content_type": b["content_type"], "label": b["label"],
            "target": [lo, hi], "reason_above": b["reason_above"],
            "hard_min": HARD_MIN, "hard_max": HARD_MAX,
            "hard_ok": hard_ok, "in_target": in_target, "needs_reason": needs_reason,
            "reason_ok": reason_ok, "length_reason": reason or None,
            "level": level, "message": msg}


def from_workdir(W) -> tuple[str, str | None]:
    """content_type + length_reason מתוך project_manifest.json / APPROVAL.json."""
    W = Path(W)
    ct, reason = None, None
    for name in ("project_manifest.json", "APPROVAL.json"):
        p = W / name
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        ct = ct or d.get("content_type")
        reason = reason or d.get("length_reason")
    return (ct or DEFAULT_TYPE), reason


def policy_table() -> dict:
    return {"hard_min": HARD_MIN, "hard_max": HARD_MAX,
            "bands": {k: {"target": list(v["target"]), "reason_above": v["reason_above"],
                          "label": v["label"], "why": v["why"]} for k, v in BANDS.items()}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", type=float)
    ap.add_argument("--type", default=None)
    ap.add_argument("--reason", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.eval is not None:
        print(json.dumps(evaluate(a.eval, a.type, a.reason), ensure_ascii=False, indent=1))
        return 0
    if a.json:
        print(json.dumps(policy_table(), ensure_ascii=False, indent=1))
        return 0
    print(f"גבול קשיח: {HARD_MIN:.0f}-{HARD_MAX:.0f}ש (חוסם)")
    for k, v in BANDS.items():
        lo, hi = v["target"]
        print(f"  {k:16} יעד {lo:.0f}-{hi:.0f}ש · נימוק חובה מעל {v['reason_above']:.0f}ש · {v['label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
