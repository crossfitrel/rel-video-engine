#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
illustration_gate — מי מרוויח המחשה ויזואלית, כמה, ואיפה.

למה זה נולד
-----------
הראל, 21.8.26, אחרי שראה את אנימציית הרוטטור קאף על הסרטון של מאסל מן:
*"זה אחלה וצריכים להשתמש בזה בחוכמה ובמינון נכון. בגג פעם אחת או שניים
במקרים חריגים בסרטון ולא בכל סרטון."*

הסכנה כאן אינה איכות — היא **שכיחות**. כלי שנראה טוב נוטה להופיע בכל
סרטון תוך שבועיים, ואז הוא מפסיק להיות אירוע והופך למניירה. לכן המנגנון
הזה אינו "האם אפשר" אלא **"האם זה מרוויח את מקומו, ועל חשבון מה"** —
והוא נכשל-סגור: ברירת המחדל היא **אפס המחשות**, וצריך ראיה כדי לפתוח אותה.

שלוש שכבות, בסדר הזה
--------------------
1. **זכאות** (`eligible`) — סוג תוכן וקהל. המרה לא נוגעים בה בכלל: שם
   הדוקטרינה היא מצע בירולים רציף, והמחשה גרפית שוברת אותה.
2. **מועמדות מדידה** (`candidates`) — משפטים שמזכירים **ישות שאי אפשר
   לצלם**: מבנה פנימי, מנגנון, יחס מספרי, או תהליך על ציר זמן. כל מועמד
   מקבל ציון מפורק לרכיבים, לא מספר קסם.
3. **מינון** (`budget` + `ledger`) — אחת לסרטון. שתיים רק כשהשנייה חוצה סף
   חריגה גבוה בהרבה, ואז זו **החלטה מדווחת** עם נימוק. ומעבר לזה: קצב
   על פני הקטלוג — אם המחשה הופיעה לאחרונה, הסף עולה.

מה שהמנוע הזה **לא** עושה
--------------------------
הוא לא מצייר ולא מרנדר. הוא מחזיר פסק-דין כדאטה: חלון, ישות, ציטוט מהמשפט,
ומה צריך להיות מאויר. הציור עצמו הוא צינור נפרד (`illustration_build`),
והשיפוט המודלי ("האם זה באמת מרוויח את מקומו") רץ אחרי זה בפאס הבמאי.

שערים
-----
  IL1_content_type_eligible   חוסם   סוג תוכן/קהל שאינו זכאי
  IL2_quote_anchor            חוסם   אין ציטוט מהמשפט שמעגן את ההמחשה
  IL3_dosage_budget           חוסם   יותר ממה שהמינון מתיר
  IL4_guard_zones             חוסם   נגיעה ב-Hook או ב-CTA
  IL5_region_verified         חוסם   מיפוי ישות→אזור באיור לא אומת
  IL6_broll_overlap           חוסם   חפיפה לשיבוץ בירול — רעיון ויזואלי אחד בכל רגע

שימוש
-----
  python3 illustration_gate.py --workdir W
  python3 illustration_gate.py --workdir W --json
  python3 illustration_gate.py --explain       # למה סרטון לא קיבל המחשה
  python3 illustration_gate.py --ledger        # קצב השימוש על פני הקטלוג
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "illustration-ledger.json"

# ── מינון. אלה המספרים שהראל נתן, לא ניחוש. ─────────────────────────────
MAX_PER_VIDEO = 1                 # ברירת המחדל המוחלטת
MAX_PER_VIDEO_EXCEPTION = 2       # רק דרך חריגה מנומקת
MIN_WORTH = 62.0                  # סף כניסה למועמד הראשון
MIN_WORTH_SECOND = 84.0           # הסף לחריגה — גבוה בהרבה, בכוונה
MAX_INSERT_SEC = 7.0              # אורך המחשה בודדת
MAX_SHARE_OF_DURATION = 0.12      # סך ההמחשות מתוך אורך הסרטון
MIN_RUN_SEC = 3.0                 # רצף דיבור רציף שמעגן את ההמחשה
HOOK_GUARD = 4.0                  # שניות ראשונות — קדוש
CTA_GUARD = 8.0                   # שניות אחרונות — מוגן

# קצב על פני הקטלוג: אם היו המחשות ב-N הסרטונים האחרונים, הסף עולה.
RECENT_WINDOW = 5                 # כמה סרטונים אחורה נספרים
RECENT_ALLOWANCE = 1              # כמה מהם מותר שיכילו המחשה בלי קנס
RECENT_PENALTY = 9.0              # תוספת לסף על כל חריגה מעבר להקצאה

ELIGIBLE_CONTENT = {"value", "ערך", "education", "חינוכי", "rehab",
                    "שיקום", "podcast", "פודקאסט", "connection", "חיבור"}
BLOCKED_CONTENT = {"conversion", "המרה"}

# ── מה נחשב "ישות שאי אפשר לצלם". זה לב העניין: המחשה מוצדקת כשהמצלמה
#    פיזית לא יכולה להראות את מה שנאמר. אם אפשר לצלם את זה — מצלמים. ──
ENTITY_CLASSES: dict[str, list[str]] = {
    "anatomy": [
        r"שריר", r"שרירים", r"גיד", r"גידים", r"רצוע", r"מפרק", r"סחוס",
        r"חוליה", r"חוליות", r"עמוד\s*שדרה", r"אגן", r"שכמ", r"כתף",
        r"רוט[יי]?טור", r"קאף", r"אינפרספינטוס", r"סופרספינטוס",
        r"סאבסקפולריס", r"טרס\s*מינור", r"דיסק", r"עצב", r"פאשיה",
        r"רקמ", r"ראש\s*עצם", r"עצם\s*הזרוע", r"ליבה\s*עמוקה",
    ],
    "mechanism": [
        r"מנגנון", r"עומס\s*מצטבר", r"טווח\s*תנוע", r"ציר\s*התנוע",
        r"וקטור", r"כוח\s*גזירה", r"מומנט", r"ייצוב", r"לייצב",
        r"קו\s*המשיכ", r"שרשרת\s*קינטית", r"העברת\s*כוח",
    ],
    "process": [
        r"שלב\s*ראשון", r"בשלב\s*הבא", r"אחרי\s*(?:שבוע|חודש|שבועיים)",
        r"לאורך\s*(?:הזמן|החודש|השנה)", r"מחזור\s*של", r"תהליך\s*ה",
        r"ואז\s*מגיע", r"קודם\s*כל.*ואז", r"עקומ",
    ],
    "quantity": [
        r"\b\d+\s*אחוז", r"פי\s*\d+", r"יחס\s*של", r"\b\d+\s*מתוך\s*\d+",
        r"ארבעה?\s*\w+", r"שלושה?\s*\w+", r"חמישה?\s*\w+", r"שני\s*סוגי",
    ],
}

# ספירה מפורשת ("שלושה דברים", "ארבעה שרירים") היא האות החזק ביותר —
# הצופה כבר בנה במוח רשימה, וההמחשה מחזיקה אותה במקום הזיכרון שלו.
ENUMERATION = re.compile(
    r"(שני|שתי|שלוש[הת]?|ארבע[הת]?|חמיש[הת]?|שיש[הת]?)\s+"
    r"(שרירים|דברים|סוגי|שלבים|מבנים|מנגנונים|סיבות|טעויות|עקרונות|חלקים)")


def jload(p, d=None):
    p = Path(p)
    if not p.exists():
        return d
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d


# ═══════════════════════════════════════════════════════════════════════
# שכבה 1 — זכאות
# ═══════════════════════════════════════════════════════════════════════
def eligible(manifest: dict, brief: dict | None = None) -> dict:
    """IL1. סוג תוכן וקהל. נכשל-סגור: מה שלא ברשימה — לא זכאי."""
    ct = str((manifest or {}).get("content_type") or "").strip().lower()
    if not ct:
        ct = str(((brief or {}).get("content_type") or "")).strip().lower()
    if ct in BLOCKED_CONTENT:
        return {"ok": False, "content_type": ct,
                "why": "תוכן המרה — הדוקטרינה שם היא מצע בירולים רציף לקהל קר. "
                       "המחשה גרפית שוברת את הרצף ומחליפה ראייה של המקום "
                       "בסכמה. לא נוגעים."}
    if ct not in ELIGIBLE_CONTENT:
        return {"ok": False, "content_type": ct or "unknown",
                "why": "סוג תוכן שאינו ברשימת הזכאים. ברירת המחדל היא אפס "
                       "המחשות — פותחים רק מה שנמדד שמרוויח."}
    return {"ok": True, "content_type": ct,
            "why": "תוכן ערך/חינוכי — הצופה כאן בא ללמוד, ולכן המחשה של משהו "
                   "שאי אפשר לצלם מוסיפה הבנה ולא קישוט."}


# ═══════════════════════════════════════════════════════════════════════
# שכבה 2 — מועמדות מדידה
# ═══════════════════════════════════════════════════════════════════════
def classify(text: str) -> dict:
    """אילו מחלקות של ישות-שאי-אפשר-לצלם מופיעות במשפט, וכמה פגיעות."""
    hits: dict[str, list[str]] = {}
    for cls, pats in ENTITY_CLASSES.items():
        found = []
        for p in pats:
            m = re.search(p, text)
            if m:
                found.append(m.group(0).strip())
        if found:
            hits[cls] = sorted(set(found))
    return hits


def quote_anchor(text: str, hits: dict) -> str:
    """הציטוט שמעגן את ההמחשה — בדיוק כמו עוגן בירול. בלי ציטוט אין המחשה
    (IL2), כי בלי זה אין דרך לדעת שהתמונה מדברת על מה שנאמר."""
    terms = [t for v in hits.values() for t in v]
    if not terms:
        return ""
    term = max(terms, key=len)
    i = text.find(term)
    if i < 0:
        return ""
    a = max(0, i - 28)
    b = min(len(text), i + len(term) + 28)
    return text[a:b].strip()


def score(sent: dict, hits: dict, run_sec: float, static_frac: float = 0.0,
          broll_overlap: bool = False) -> dict:
    """ציון מפורק לרכיבים. אף רכיב לא "מספר קסם" — כל אחד אומר מה הוא מודד
    ולמה הוא שווה את מה שהוא שווה."""
    text = sent.get("text") or ""
    comp: dict[str, float] = {}

    # מחלקת הישות. אנטומיה ומנגנון הם הליבה — שם המצלמה באמת חסרת אונים.
    weights = {"anatomy": 34.0, "mechanism": 28.0, "process": 20.0, "quantity": 14.0}
    comp["entity"] = max((weights[c] for c in hits), default=0.0)

    # יותר ממחלקה אחת = המשפט באמת מתאר משהו מורכב.
    comp["multi_class"] = 8.0 if len(hits) > 1 else 0.0

    # ספירה מפורשת — האות החזק ביותר שהצופה מחזיק רשימה בראש.
    comp["enumeration"] = 18.0 if ENUMERATION.search(text) else 0.0

    # צפיפות מונחים ייחודיים: "שריר" סתם אינו כמו ארבעה שמות לטיניים.
    n_terms = len({t for v in hits.values() for t in v})
    comp["specificity"] = min(14.0, 3.5 * n_terms)

    # רצף דיבור. מתחת ל-MIN_RUN_SEC אין על מה להלביש המחשה.
    comp["dwell"] = min(12.0, max(0.0, (run_sec - MIN_RUN_SEC) * 3.0))

    # ריק ויזואלי: כשהדובר סטטי, המחשה ממלאת חלל אמיתי במקום להתחרות בפריים.
    comp["visual_void"] = round(10.0 * max(0.0, min(1.0, static_frac)), 2)

    # כפילות: אם בירול כבר מכסה את החלון — רעיון ויזואלי אחד בכל רגע.
    comp["broll_penalty"] = -25.0 if broll_overlap else 0.0

    total = round(sum(comp.values()), 2)
    return {"total": max(0.0, total), "components": comp}


def _static_fraction(sent, vision: dict | None) -> float:
    """כמה מהחלון סומן כסטטי ע"י vision_check. חסר קובץ ⇒ 0, לא ניחוש."""
    if not vision:
        return 0.0
    wins = vision.get("static_windows") or []
    if not wins:
        return 0.0
    s, e = float(sent["start"]), float(sent["end"])
    span = max(0.01, e - s)
    cov = 0.0
    for w in wins:
        a, b = float(w.get("start", 0)), float(w.get("end", 0))
        cov += max(0.0, min(e, b) - max(s, a))
    return max(0.0, min(1.0, cov / span))


def timeline_of(sentences, keeps, out_dur) -> str:
    """באיזה ציר זמן נתונים המשפטים — המקור, או הפלט אחרי החיתוך.

    זה לא פרט טכני: `sentences.json` נכתב בפרויקטים שונים בשני הצירים, ומיפוי
    בציר הלא-נכון מחזיר ספָּאן ריק לכל משפט — כלומר **אפס מועמדים בשקט**,
    שנראה בדיוק כמו "אין מה להמחיש". מחליטים לפי מדידה ומדווחים את ההכרעה.
    """
    if not sentences:
        return "unknown"
    src_end = max(float(k.get("end", 0)) for k in keeps) if keeps else 0.0
    last = max(float(s["end"]) for s in sentences)
    if out_dur and last <= float(out_dur) + 1.0 and last < src_end - 1.0:
        return "output"
    return "source"


def candidates(sentences, keeps, out_dur, broll_items=None, vision=None,
               timeline=None) -> list[dict]:
    """מועמדים ממוינים מהחזק לחלש. ריק היא תשובה תקינה ושכיחה."""
    from broll_director import kept_span  # אותה חשבונאות זמנים כמו הבירול
    broll_items = broll_items or []
    tl = timeline or timeline_of(sentences, keeps, out_dur)
    out = []
    for s in sentences or []:
        text = s.get("text") or ""
        hits = classify(text)
        if not hits:
            continue
        if tl == "output":
            a, b = float(s["start"]), float(s["end"])
        else:
            sp = kept_span(float(s["start"]), float(s["end"]), keeps)
            if not sp:
                continue                   # המשפט לא שרד את החיתוך
            a, b = sp
        run = b - a
        if run < MIN_RUN_SEC:
            continue
        q = quote_anchor(text, hits)
        if not q:
            continue
        # אזורי המגן **גוזמים**, לא פוסלים. משפט שנכנס בקצהו ל-Hook או ל-CTA
        # עדיין מרוויח המחשה על החלק שמחוצה להם — הפסילה הגורפת הפילה בבדיקה
        # (21.8.26) בדיוק את המשפט שהראל אישר להמחיש.
        lo, hi = HOOK_GUARD, max(0.0, float(out_dur) - CTA_GUARD)
        ta, tb = max(a, lo), min(b, hi)
        trimmed = (ta, tb) != (a, b)
        if tb - ta >= MIN_RUN_SEC:
            a, b, run = ta, tb, tb - ta
            in_hook = in_cta = False
        else:
            in_hook, in_cta = a < HOOK_GUARD, b > hi
            trimmed = False
        ov = any(not (float(p.get("end", 0)) <= a or float(p.get("start", 0)) >= b)
                 for p in broll_items)
        sc = score(s, hits, run, _static_fraction(s, vision), ov)
        out.append({
            "start": round(a, 3), "end": round(b, 3), "run_sec": round(run, 2),
            "entity_classes": sorted(hits), "entities": hits,
            "quote": q, "sentence": text,
            "broll_overlap": ov,
            "worth": sc["total"], "components": sc["components"],
            "trimmed_to_guards": trimmed,
            "in_hook": in_hook, "in_cta": in_cta,
        })
    return sorted(out, key=lambda c: -c["worth"])


# ═══════════════════════════════════════════════════════════════════════
# שכבה 3 — מינון
# ═══════════════════════════════════════════════════════════════════════
def recent_rate(ledger_path: Path = LEDGER) -> dict:
    led = jload(ledger_path, {"videos": []}) or {"videos": []}
    vids = (led.get("videos") or [])[-RECENT_WINDOW:]
    used = sum(1 for v in vids if int(v.get("n_illustrations") or 0) > 0)
    over = max(0, used - RECENT_ALLOWANCE)
    return {"window": RECENT_WINDOW, "considered": len(vids), "with_illustration": used,
            "allowance": RECENT_ALLOWANCE, "penalty": round(over * RECENT_PENALTY, 1)}


def budget(out_dur: float) -> dict:
    """המחשה **אחת** תמיד נכנסת בתקציב — אחרת ריל קצר לא יכול לקבל אף
    המחשה, וזה לא המינון שהראל ביקש אלא ביטול. מגבלת האחוז נועדה לחסום את
    ה**שנייה**, ושם היא עושה בדיוק את עבודתה."""
    share = out_dur * MAX_SHARE_OF_DURATION
    cap = min(MAX_INSERT_SEC * MAX_PER_VIDEO_EXCEPTION, share)
    return {"max_per_video": MAX_PER_VIDEO,
            "max_per_video_exception": MAX_PER_VIDEO_EXCEPTION,
            "max_insert_sec": MAX_INSERT_SEC,
            "max_total_sec": round(max(MAX_INSERT_SEC, cap), 2),
            "share_sec": round(share, 2),
            "share_of_duration": MAX_SHARE_OF_DURATION}


def decide(manifest, brief, sentences, keeps, out_dur,
           broll_items=None, vision=None, ledger_path: Path = LEDGER) -> dict:
    """פסק-הדין המלא. כל שער מדווח בנפרד — ההחלטה ניתנת לקריאה, לא רק לציות."""
    gates: list[dict] = []

    def gate(name, ok, detail):
        gates.append({"gate": name, "ok": bool(ok), "detail": detail})
        return ok

    el = eligible(manifest, brief)
    gate("IL1_content_type_eligible", el["ok"], el["why"])
    bud = budget(float(out_dur or 0))
    rate = recent_rate(ledger_path)
    thr = MIN_WORTH + rate["penalty"]

    if not el["ok"]:
        return {"decision": "none", "n": 0, "picks": [], "gates": gates,
                "budget": bud, "recent": rate, "threshold": thr,
                "why": el["why"], "candidates": []}

    tl = timeline_of(sentences, keeps, float(out_dur or 0))
    cands = candidates(sentences, keeps, float(out_dur or 0), broll_items, vision, tl)

    # IL4 — אזורי מגן. נחתך כאן ולא בסוף, כדי שהדוח יראה מה נפסל ולמה.
    guarded = [c for c in cands if c["in_hook"] or c["in_cta"]]
    live = [c for c in cands if not (c["in_hook"] or c["in_cta"])]
    gate("IL4_guard_zones", True,
         f"{len(guarded)} מועמדים נפסלו על Hook/CTA" if guarded
         else "אין מועמד שנוגע ב-Hook או ב-CTA")

    # IL6 — חפיפה לבירול. נענש בציון וגם מדווח כשער.
    ov = [c for c in live if c["broll_overlap"]]
    gate("IL6_broll_overlap", True,
         f"{len(ov)} מועמדים חופפים לשיבוץ בירול (קנס בציון)" if ov
         else "אין חפיפה לבירול")

    # התקציב הוא **אילוץ**, לא דיווח. הבדיקה מ-21.8.26 תפסה שתי המחשות
    # שעברו את סף השניות והשער רק צעק עליהן — שער שלא עוצר אינו שער.
    picks: list[dict] = []
    used = 0.0

    def fits(c):
        return used + min(MAX_INSERT_SEC, c["run_sec"]) <= bud["max_total_sec"] + 1e-6

    for c in live:
        if not picks:
            if c["worth"] >= thr and fits(c):
                picks.append({**c, "rank": 1, "exception": False,
                              "insert_sec": round(min(MAX_INSERT_SEC, c["run_sec"]), 2)})
                used += min(MAX_INSERT_SEC, c["run_sec"])
            continue
        # השני נכנס רק דרך חריגה מנומקת, ורק אם אינו נוגע בראשון ונכנס בתקציב.
        if (len(picks) < MAX_PER_VIDEO_EXCEPTION and c["worth"] >= MIN_WORTH_SECOND
                and fits(c)):
            far = all(c["start"] >= p["end"] + 4.0 or c["end"] <= p["start"] - 4.0
                      for p in picks)
            if far:
                picks.append({**c, "rank": len(picks) + 1, "exception": True,
                              "insert_sec": round(min(MAX_INSERT_SEC, c["run_sec"]), 2),
                              "exception_reason":
                                  f"ציון {c['worth']} חצה את סף החריגה "
                                  f"{MIN_WORTH_SECOND} ומרוחק מההמחשה הראשונה"})
                used += min(MAX_INSERT_SEC, c["run_sec"])

    total_sec = round(used, 2)
    gate("IL3_dosage_budget", total_sec <= bud["max_total_sec"] + 1e-6,
         f"{len(picks)} המחשות · {total_sec}ש מתוך תקציב {bud['max_total_sec']}ש")
    gate("IL2_quote_anchor", all(p.get("quote") for p in picks),
         "לכל המחשה יש ציטוט מהמשפט" if picks else "אין המחשות — אין מה לעגן")

    if not picks:
        best = live[0]["worth"] if live else 0.0
        why = (f"אף מועמד לא חצה את הסף {thr} (הטוב ביותר: {best}). "
               "אפס המחשות היא התשובה השכיחה והתקינה.")
    else:
        why = (f"{len(picks)} המחשה/ות. "
               + " · ".join(f"#{p['rank']} {p['start']}-{p['end']}ש "
                            f"[{','.join(p['entity_classes'])}] ציון {p['worth']}"
                            for p in picks))

    return {"decision": "illustrate" if picks else "none",
            "n": len(picks), "picks": picks, "gates": gates,
            "budget": bud, "recent": rate, "threshold": thr,
            "timeline": tl, "n_candidates": len(cands),
            "total_sec": total_sec, "why": why,
            "candidates": cands[:8]}


# ═══════════════════════════════════════════════════════════════════════
# IL5 — מיפוי ישות→אזור באיור. הלקח מ-21.8.26.
# ═══════════════════════════════════════════════════════════════════════
def region_verified(workdir) -> dict:
    """הראל, 21.8.26: *"הסימונים על השרירים עכשיו לא היו מדויקים כשהוא ציין
    אותם."* השורש: המסכה לשריר נגזרה מהאיור בחלקה ידנית (קו התפר בין שני
    שרירים סמוכים), ואיש לא **אימת** שהאזור שנדלק הוא באמת השריר שנאמר.

    השער הזה נכשל-סגור: בלי `illustration_regions.json` שבו לכל ישות יש
    `verified: true` ותמונת בדיקה שנוצרה — ההמחשה לא מוחלת. אימות שלא נעשה
    אינו "כנראה בסדר"; הוא אימות שלא נעשה."""
    W = Path(workdir)
    f = W / "illustration_regions.json"
    doc = jload(f)
    if not doc:
        return {"ok": False, "gate": "IL5_region_verified",
                "detail": "אין illustration_regions.json — מיפוי ישות→אזור לא אומת"}
    regions = doc.get("regions") or []
    if not regions:
        return {"ok": False, "gate": "IL5_region_verified",
                "detail": "קובץ אימות ריק"}
    bad = [r.get("entity") for r in regions if not r.get("verified")]
    sheet = doc.get("check_sheet")
    missing_sheet = not (sheet and (W / sheet).exists())
    ok = not bad and not missing_sheet
    det = []
    if bad:
        det.append("לא אומתו: " + ", ".join(str(b) for b in bad))
    if missing_sheet:
        det.append("חסרה תמונת בדיקה (check_sheet) שמראה כל אזור על האיור")
    return {"ok": ok, "gate": "IL5_region_verified",
            "detail": " · ".join(det) if det else
                      f"{len(regions)} אזורים אומתו מול האיור + תמונת בדיקה"}


def atlas_registration(workdir) -> dict:
    """IL7 — המסכות נגזרות מ**אטלס**: רינדור שני של אותה קומפוזיציה בצבעי
    מפתח, אחד לכל שריר. הראל, 21.8.26: *"ה-Teres Minor לא מדויק בגיליון."*
    השורש היה שקו התפר בין שני שרירים סמוכים נקרא ידנית מגריד — כי הם
    נוגעים בצבע באיור היפה ולכן אין בו חתך שאלגוריתם יכול למצוא. הפתרון
    אינו אלגוריתם טוב יותר אלא **קלט שניתן להפריד**.

    מה שנשאר לאמת: שהאטלס באמת מיושר לאיור. אטלס שזז מייצר מסכות שנראות
    סבירות ומאירות את המקום הלא-נכון. מדווח בלבד — הסף נשען על מדידה אחת."""
    r = jload(Path(workdir) / "illus" / "atlas_report.json") or \
        jload(Path(workdir) / "atlas_report.json")
    if not r:
        return {"ok": True, "gate": "IL7_atlas_registration",
                "detail": "לא נעשה שימוש באטלס (מסלול נסיגה: תפר ידני)"}
    reg = r.get("registration") or {}
    return {"ok": bool(reg.get("ok")), "gate": "IL7_atlas_registration",
            "detail": f"רישום אטלס↔איור IoU={reg.get('iou')} "
                      f"(סף {reg.get('threshold')})"}


def record(workdir, n, ledger_path: Path = LEDGER) -> dict:
    """רישום לצורך קצב על פני הקטלוג. נקרא אחרי גימור, לא בתכנון."""
    led = jload(ledger_path, {"videos": []}) or {"videos": []}
    name = Path(workdir).name
    led["videos"] = [v for v in led.get("videos", []) if v.get("project") != name]
    led["videos"].append({"project": name, "n_illustrations": int(n),
                          "at": datetime.now().isoformat(timespec="seconds"),
                          "date": date.today().isoformat()})
    led["videos"] = led["videos"][-60:]
    Path(ledger_path).write_text(
        json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    return led


# ═══════════════════════════════════════════════════════════════════════
def from_workdir(workdir) -> dict:
    W = Path(workdir)
    sys.path.insert(0, str(HERE))
    manifest = jload(W / "project_manifest.json", {}) or {}
    brief = jload(W / "brief.json", {}) or {}
    sents = jload(W / "sentences.json", []) or []
    if isinstance(sents, dict):
        sents = sents.get("sentences") or []
    edl = jload(W / "edl.json", {}) or {}
    keeps = edl.get("keep_segments") or []
    out_dur = float(edl.get("kept_dur") or 0)
    bp = jload(W / "broll_plan.json", {}) or {}
    broll_items = bp.get("items") or []
    vision = jload(W / "vision_check.json", {}) or {}
    v = decide(manifest, brief, sents, keeps, out_dur, broll_items, vision)
    v["project"] = W.name
    if v["n"]:
        v["atlas_check"] = atlas_registration(W)
        v["gates"].append({"gate": "IL7_atlas_registration",
                           "ok": v["atlas_check"]["ok"],
                           "detail": v["atlas_check"]["detail"]})
        v["region_check"] = region_verified(W)
        v["gates"].append({"gate": "IL5_region_verified",
                           "ok": v["region_check"]["ok"],
                           "detail": v["region_check"]["detail"]})
        if not v["region_check"]["ok"]:
            v["decision"] = "blocked"
            v["why"] += " · חסום: " + v["region_check"]["detail"]
    return v


def main() -> int:
    ap = argparse.ArgumentParser(description="מי מרוויח המחשה ויזואלית, כמה, ואיפה")
    ap.add_argument("--workdir")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--ledger", action="store_true")
    ap.add_argument("--record", type=int, metavar="N")
    a = ap.parse_args()

    if a.ledger:
        print(json.dumps(recent_rate(), ensure_ascii=False, indent=1))
        return 0
    if not a.workdir:
        ap.error("--workdir נדרש")
    if a.record is not None:
        record(a.workdir, a.record)
        print(f"נרשם: {Path(a.workdir).name} · {a.record} המחשות")
        return 0

    v = from_workdir(a.workdir)
    if a.json:
        print(json.dumps(v, ensure_ascii=False, indent=1))
        return 0

    print(f"■ {v['project']} — {v['decision']} ({v['n']})")
    print(f"  {v['why']}")
    print(f"  סף: {v['threshold']} (בסיס {MIN_WORTH} + קנס קצב {v['recent']['penalty']})")
    print(f"  תקציב: עד {v['budget']['max_total_sec']}ש · "
          f"{v['budget']['max_per_video']} לסרטון (חריגה: {v['budget']['max_per_video_exception']})")
    for g in v["gates"]:
        print(f"   {'✓' if g['ok'] else '✗'} {g['gate']} — {g['detail']}")
    if a.explain:
        print("\n  מועמדים:")
        for c in v["candidates"]:
            flags = []
            if c["in_hook"]:
                flags.append("Hook")
            if c["in_cta"]:
                flags.append("CTA")
            if c["broll_overlap"]:
                flags.append("בירול")
            print(f"   {c['worth']:6.1f}  {c['start']:6.2f}-{c['end']:6.2f}  "
                  f"[{','.join(c['entity_classes'])}]"
                  f"{' ⟨' + ','.join(flags) + '⟩' if flags else ''}")
            print(f"           ציטוט: {c['quote'][:70]}")
            print(f"           רכיבים: " + " ".join(
                f"{k}={val}" for k, val in c["components"].items() if val))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
