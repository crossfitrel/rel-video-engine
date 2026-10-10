#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""he_lexicon.py — לקסיקון עברי מצטבר לאכיפת כתוביות (V3, 30.7.26).

═══════════════════════════════════════════════════════════════════════════
למה זה קיים
═══════════════════════════════════════════════════════════════════════════
הראל: "הכתוביות לא טובות. מלאות בשגיאות כתיב. ולא בעברית תקינה."
בפועל נצרבו על המסך: "אתם מתאמנים **ועל כל צפוף** מטר על מטר" (בהוק עצמו),
"כל **הציעות** זמין", "**בשוט** הצהריים". שום שער לא בדק אם המילה שנצרבת היא
בכלל מילה בעברית.

═══════════════════════════════════════════════════════════════════════════
למה הלקסיקון אינו השופט אלא ההדק
═══════════════════════════════════════════════════════════════════════════
נמדד: לקסיקון של 1,017 מילים מ-18 תמלולים מתוקנים-ידנית **תופס את שלוש
השגיאות** — אבל מסמן גם "אצבע", "קהילה", "טביעת" כלא-מוכרות. אוצר מילים קטן
⇒ false positives. לכן:

    לקסיקון = מי חייב להיבדק.   מודל = מה התשובה.   קוד = מה נחסם.

כל מילה שאושרה במפורש נכנסת ללקסיקון המצטבר, ולכן **רשימת ההדק מתכווצת עם
כל סרטון** — המערכת מדייקת מעצמה מהריצה הבאה.

⚠️ **אסור לבנות לקסיקון מ-`whisper_raw.json`.** נמדד: "הציעות" מופיעה ב-7
פרויקטים ו-"בשוט" ב-8 — כי אותו סרטון מקור הועתק לתיקיות בדיקה. תדירות
בקורפוס גולמי אינה ראיה לתקינות. רק טקסט שאדם תיקן (`edited.txt` /
`correct_transcript.txt`) נחשב מקור.

שימוש:
  python3 tools/he_lexicon.py build            # בונה מחדש מהקורפוס המתוקן
  python3 tools/he_lexicon.py check <words.json|text>
  python3 tools/he_lexicon.py approve <מילה> [<מילה> ...] --why "..."
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

HE_WORD = re.compile(r"[֐-׿']+")
LEX_PATH = HERE / "he-lexicon.json"
GLOSSARY = HERE / "asr-glossary.json"

# מונחי המועדון — שמות מותג ומונחים מקצועיים שלא יופיעו בתמלול כללי
CLUB_TERMS = [
    "קרוספיט", "אריאל", "מטקון", "מטקונים", "ברפי", "ברפיז", "סנאץ'", "קלין",
    "ג'רק", "דדליפט", "סקוואט", "וודבול", "בוקס", "ריג", "קטלבל", "וורמאפ",
    "אופן", "ג'ים", "דוספיט", "פילאטיס", "מוביליטי", "רהאב", "אמראפ",
    "טאבטה", "היירוקס", "throwdown", "wod",
]


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def norm(w: str) -> str:
    """ליבת המילה — בלי ניקוד, פיסוק, מקף מוביל/נגרר.

    ⚠️ הגרש העברי (U+05F3 ׳) והגרשיים (U+05F4 ״) מנורמלים לאפוסטרוף ASCII.
    שורש (30.7.26): "ג׳ים" בתמלול נכתב בגרש עברי בעוד CLUB_TERMS החזיק "ג'ים"
    באפוסטרוף — אותה מילה בדיוק, שתי מחרוזות שונות, והשער חסם מונח מותג תקין.
    """
    w = re.sub(r"[֑-ׇ]", "", str(w or ""))
    w = w.replace("׳", "'").replace("״", '"').replace("’", "'")
    w = "".join(ch for ch in w if ch.isalpha() or ch == "'")
    return w.strip("'")


def build(work_root=None, verbose=True):
    """בונה את הלקסיקון מהמקורות הלגיטימיים בלבד."""
    from relvid.paths import work_root as _wr
    root = Path(work_root) if work_root else _wr()
    words, sources = {}, {"corrected_files": 0, "glossary_targets": 0, "club": 0}

    for pat in ("*/edited.txt", "*/correct_transcript.txt"):
        for f in sorted(root.glob(pat)):
            sources["corrected_files"] += 1
            for m in HE_WORD.findall(f.read_text(encoding="utf-8", errors="replace")):
                k = norm(m)
                if len(k) >= 2:
                    words.setdefault(k, "corrected_corpus")

    g = jload(GLOSSARY, {}) or {}
    for v in (g.get("corrections") or {}).values():
        for m in HE_WORD.findall(str(v)):
            k = norm(m)
            if len(k) >= 2 and k not in words:
                words[k] = "glossary_target"
                sources["glossary_targets"] += 1

    for t in CLUB_TERMS:
        k = norm(t)
        if k and k not in words:
            words[k] = "club_term"
            sources["club"] += 1

    prev = jload(LEX_PATH, {}) or {}
    for k, rec in (prev.get("approved") or {}).items():
        words.setdefault(k, "approved")

    doc = {
        "_readme": "לקסיקון עברי לאכיפת כתוביות. ראה he_lexicon.py. "
                   "מקורות: תמלולים שאדם תיקן + יעדי asr-glossary + מונחי מועדון "
                   "+ מילים שאושרו במפורש בפאס ה-proofreader. "
                   "אסור לבנות מ-whisper_raw — הקורפוס הגולמי מכיל את השיבושים עצמם.",
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sources": sources,
        "n_words": len(words),
        "words": sorted(words),
        "approved": prev.get("approved") or {},
    }
    LEX_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    if verbose:
        print(f"✅ לקסיקון: {len(words)} מילים · {sources}")
    return doc


def load():
    d = jload(LEX_PATH)
    if not d:
        d = build(verbose=False)
    return set(d.get("words") or []), d


def unknown(tokens):
    """מחזיר את המילים שאינן בלקסיקון — רשימת ההדק לפאס ה-proofreader."""
    lex, _ = load()
    out = []
    for t in tokens:
        k = norm(t)
        if len(k) < 2:
            continue
        if k not in lex and k not in out:
            out.append(k)
    return out


def approve(words, why="", actor="claude"):
    """מוסיף מילים שאושרו במפורש. זה מה שמצמצם את רשימת ההדק בריצה הבאה."""
    d = jload(LEX_PATH) or build(verbose=False)
    app = d.setdefault("approved", {})
    added = []
    for w in words:
        k = norm(w)
        if len(k) >= 2 and k not in app:
            app[k] = {"why": why, "actor": actor, "at": time.strftime("%Y-%m-%d %H:%M")}
            added.append(k)
    allw = set(d.get("words") or []) | set(app)
    d["words"] = sorted(allw)
    d["n_words"] = len(allw)
    LEX_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return added


def _cli():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").add_argument("--work-root", default=None)
    c = sub.add_parser("check")
    c.add_argument("path")
    a2 = sub.add_parser("approve")
    a2.add_argument("words", nargs="+")
    a2.add_argument("--why", default="")
    a3 = sub.add_parser("promote")
    a3.add_argument("workdir")
    a3.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "promote":
        # קידום מפורש: אישורי המגיה מהפרויקט → הלקסיקון הגלובלי.
        # נפרד מהפאס עצמו כדי שהקלט של הפאס יישאר דטרמיניסטי (ראה edit_director).
        fix = jload(Path(a.workdir) / "transcript_fix.json", {}) or {}
        ws = [x.get("w") for x in (fix.get("approved") or []) if x.get("w")]
        if a.dry_run:
            print(f"היו נוספות {len(ws)} מילים: {ws}")
            return 0
        added = approve(ws, why=f"promote {Path(a.workdir).name}")
        print(f"✅ קודמו {len(added)} מילים ללקסיקון: {added}")
        return 0
    if a.cmd == "build":
        build(a.work_root)
        return 0
    if a.cmd == "check":
        p = Path(a.path)
        raw = p.read_text(encoding="utf-8")
        toks = ([str(x.get("word", "")) for x in json.loads(raw)]
                if p.suffix == ".json" else HE_WORD.findall(raw))
        u = unknown(toks)
        print(f"{len(u)} מילים לא בלקסיקון:")
        for w in u:
            print("  " + w)
        return 1 if u else 0
    if a.cmd == "approve":
        print("נוספו:", approve(a.words, a.why))
        return 0


if __name__ == "__main__":
    sys.exit(_cli())
