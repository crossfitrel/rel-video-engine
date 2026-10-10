#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_brief_gate — קליפ שסותר את ההבטחה נחסם, גם אם התווית אומרת אחרת.

השורש (הראל + ביקורת Sol, 31.7.26): הסרטון הבטיח **"המקום כולו שלכם,
רחבה פתוחה וכל הציוד זמין, בלי תור ובלי המתנה"**, והמצע הראה שיעור מלא.
הקליפ נקרא "חימום עם מוט מתאמנת" ותויג `יחיד`. **התווית שיקרה, והמערכת
האמינה לה.**

השער הזה לא מאמין לתווית. הוא קורא שתי עובדות:
  1. מה ההבטחה — מתוך `brief.must_keep` / `goal` / `single_cta`.
  2. מה רואים — מתוך `broll_vision_model` (מודל-ראייה, לא גלאי פיקסלים).
ומכריע. סתירה = חסימה, ולא הורדת ניקוד — הבטחה שנסתרת בתמונה שורפת אמון,
וזה לא דבר שמתקזז מול רלוונטיות גבוהה.

**נכשל-סגור:** בתוכן המרה, קליפ **בלי ראיה ויזואלית אינו נכנס למצע**.
אחרת השער דקורטיבי — מספיק לא לסרוק קליפ כדי לעקוף אותו.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import broll_vision_model as VM  # noqa: E402

# ── ניסוחי ההבטחה שמייצרים אילוץ. נגזרו מ-brief.json של האופן-ג'ים ומכל
#    ניסוח שקול שהמועדון משתמש בו בפועל. ביטוי אחד מספיק כדי להפעיל. ──
SOLITUDE_PATTERNS = [
    r"בלי\s*תור", r"בלי\s*המתנה", r"בלי\s*להמתין",
    r"המקום\s*כולו\s*שלכ", r"רחבה\s*פתוחה", r"רחבה\s*פנויה",
    r"הציוד\s*זמין", r"כל\s*הציוד",
    r"שעות\s*שקטות", r"השעות\s*השקטות", r"שקט",
    r"לבד", r"לעצמכ", r"מרחב\s*אישי", r"עצמאי",
    r"open\s*gym", r"אופן\s*ג", r"אימון\s*חופשי",
]

# מה נחשב סתירה להבטחת-שקט. `busy` נכנס בכוונה: 4-8 אנשים ברחבה הם
# בדיוק מה שהצופה יקרא כ"תור", גם אם זה לא שיעור מסודר.
SOLITUDE_FORBIDDEN_CROWDING = {"busy", "full_class"}
SOLITUDE_MAX_PEOPLE = 3


def claims(brief: dict) -> dict:
    """מוציא אילוצים מהבריף. מחזיר דאטה, לא דעה."""
    text = " ".join(str(x) for x in [
        brief.get("goal", ""), brief.get("single_cta", ""),
        brief.get("audience", ""), *(brief.get("must_keep") or [])])
    hits = [p for p in SOLITUDE_PATTERNS if re.search(p, text)]
    return {"solitude": bool(hits), "solitude_evidence": hits[:4]}


def check(vision: dict | None, cl: dict, *, strict: bool) -> tuple[bool, str]:
    """(מותר, סיבה). `strict` = תוכן המרה ⇒ נכשל-סגור בהיעדר ראיה."""
    if not cl.get("solitude"):
        return True, ""
    if vision is None:
        if strict:
            return False, "אין ראיה ויזואלית — בהמרה קליפ לא-סרוק אינו נכנס"
        return True, ""
    if vision.get("crowding") in SOLITUDE_FORBIDDEN_CROWDING:
        return False, (f"סותר את ההבטחה: {vision.get('crowding')} "
                       f"({vision.get('people')} אנשים) מול הבטחת רחבה פנויה")
    if (vision.get("people") or 0) > SOLITUDE_MAX_PEOPLE:
        return False, (f"סותר את ההבטחה: {vision['people']} אנשים בפריים "
                       f"(מקסימום {SOLITUDE_MAX_PEOPLE})")
    return True, ""


def filter_items(items, brief: dict, *, strict: bool):
    """מסנן רשימת פריטי קטלוג. מחזיר (נשארו, נחסמו[{file,why}])."""
    cl = claims(brief)
    if not cl["solitude"]:
        return list(items), []
    keep, blocked = [], []
    for it in items:
        v = None
        try:
            v = VM.lookup(it["path"])
        except OSError:
            v = None
        ok, why = check(v, cl, strict=strict)
        (keep if ok else blocked).append(
            it if ok else {"file": it["file"], "why": why,
                           "vision": v and {k: v[k] for k in
                                            ("people", "crowding", "shot")}})
    return keep, blocked
