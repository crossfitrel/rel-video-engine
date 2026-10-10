#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_intake.py — R.E.L Social Video Editing System
====================================================
המוח של "תדע לאיזו תיקייה לגשת". משייך פריטי בורד סושיאל בסטטוס
"מוכן לעריכה" לתיקיות / קבצי הגלם המקומיים, באופן דטרמיניסטי.

הזרימה (שלב 0.5 בסקיל):
  1. הסוכן מושך ממאנדיי (MCP) את הפריטים ב"מוכן לעריכה" → כותב items.json.
  2. מריץ את הכלי הזה. הוא סורק את CONTENT_ROOT/{מחלקה}/{חודש}/ ומשייך כל פריט
     לתיקייה/קובץ הכי תואם בשם (התאמה מדויקת → מנורמלת → fuzzy).
  3. מחזיר מיפוי: matched / needs_review / missing / orphans.
     - matched      = ביטחון גבוה + יש קובץ וידאו → אפשר לרוץ.
     - needs_review = התאמה דו-משמעית או בלי וידאו → הראל מכריע (לא לנחש!).
     - missing      = פריט בורד בלי תיקייה/וידאו תואם.
     - orphans      = תיקייה/קובץ גלם שאף פריט "מוכן לעריכה" לא תפס.

מקור-אמת למחלקות/חודשים: folder-routing.json (דרך resolve_output_path).

קלט items.json — מערך של:
  { "id": "123", "name": "טיפ אחד - חתירה", "dept": "קרוספיט אריאל",
    "month": "יולי 2026" }            # או "date": "2026-07-03" במקום month

שימוש:
  python3 match_intake.py --items items.json
  python3 match_intake.py --items items.json --pretty
"""
import argparse
import datetime
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from resolve_output_path import load_routing, resolve_dept, sanitize, HE_MONTHS  # noqa: E402

VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
MATCH_STRONG = 0.80   # ומעלה + יש וידאו → matched
MATCH_WEAK = 0.55     # בין WEAK ל-STRONG → needs_review


def norm(s):
    """נרמול שם להשוואה: עברית נשמרת, מקפים/קו-תחתון/רווחים מתאחדים, 'סופי' בסוף יורד."""
    s = sanitize(s or "")
    s = s.replace("–", "-").replace("—", "-")        # – —  → -
    s = re.sub(r"[\s\-_]+", " ", s).strip().lower()
    s = re.sub(r"\s*-?\s*סופי$", "", s).strip()
    return s


def dept_base_folder(routing, dept, year=None):
    d = resolve_dept(routing, dept) if dept else None
    if not d:
        return None, None
    folder = str(d["folder"]).replace("{year}", str(year or datetime.date.today().year))
    return d, folder


def month_str(item, fallback=None):
    if item.get("month"):
        return item["month"].strip()
    if item.get("date"):
        dt = datetime.date.fromisoformat(str(item["date"])[:10])
        return f"{HE_MONTHS[dt.month]} {dt.year}"
    return fallback


# תיקיות "דלי" שאינן שם-סרטון — הוידאו שבהן שייך לתיקיית-האב (תיקיית הסרטון)
GENERIC_BUCKETS = {"raw", "broll", "b-roll", "בירול", "בירולים", "_work", "work"}


def videos_in(d):
    """קבצי וידאו ישירים בתיקייה d בלבד (לא רקורסיבי), בלי סופיים/לוואי."""
    out = []
    try:
        entries = os.listdir(d)
    except OSError:
        return out
    for f in sorted(entries):
        p = os.path.join(d, f)
        if os.path.isfile(p) and not f.startswith("._") \
           and os.path.splitext(f)[1].lower() in VIDEO_EXT and "סופי" not in f:
            out.append(p)
    return out


def scan_dir(target_dir):
    """
    אוסף מועמדי-סרטון מתחת ל-target_dir בכל עומק (תומך גם ב-{קמפיין}/{סרטון}
    של אירועים וגם ב-{סרטון}/raw/). מועמד = תיקייה שמכילה וידאו ישירות או ב-raw/,
    ושמה הוא שם-הסרטון. דליי גנריים (raw/broll/_work) לא מועמדים בעצמם —
    הווידאו שלהם נספר לתיקיית-האב. + קבצי וידאו רופפים ישירות ב-target.
    """
    cands = []
    if not os.path.isdir(target_dir):
        return cands
    for root, dirs, _files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]   # דלג מוסתרים
        base = os.path.basename(root)
        if root == target_dir:
            for p in videos_in(root):                          # קבצים רופפים ישירות בתיקיית היעד
                cands.append({"type": "file", "name": os.path.splitext(os.path.basename(p))[0],
                              "path": p, "videos": [p]})
            continue
        if base.lower() in GENERIC_BUCKETS:                    # raw/ וכו' — נספר דרך האב
            continue
        vids = videos_in(root)
        raw = os.path.join(root, "raw")
        if os.path.isdir(raw):
            vids = vids + videos_in(raw)
        if vids:
            cands.append({"type": "folder", "name": base, "path": root, "videos": vids})
    return cands


def score_candidates(item_name, cands):
    tgt = norm(item_name)
    scored = []
    for c in cands:
        cn = norm(c["name"])
        r = difflib.SequenceMatcher(None, tgt, cn).ratio()
        if tgt and cn and (tgt in cn or cn in tgt):   # בונוס להכלה
            r = max(r, 0.90)
        scored.append((r, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def main():
    ap = argparse.ArgumentParser(description="שיוך פריטי 'מוכן לעריכה' לתיקיות גלם מקומיות")
    ap.add_argument("--items", required=True, help="JSON: [{id,name,dept,month|date}]")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    routing = load_routing()
    # REL_CONTENT_ROOT מאפשר להריץ גם מסביבת sandbox (mount) וגם מה-Mac (נתיב אמיתי)
    croot = os.environ.get("REL_CONTENT_ROOT") or routing["content_root"]
    items = json.load(open(args.items, encoding="utf-8"))

    matched, needs_review, missing = [], [], []
    scanned = {}          # dir → candidates (cache)
    referenced = set()    # paths שנתפסו ע"י matched/needs_review

    for it in items:
        dept = it.get("dept")
        d, base = dept_base_folder(routing, dept)
        if not base:
            missing.append({**it, "reason": "dept_unresolved"})
            continue
        mon = month_str(it)
        if d.get("month_based", True):
            if not mon:
                missing.append({**it, "reason": "month_missing"})
                continue
            target = os.path.join(croot, base, mon)
        else:
            target = os.path.join(croot, base)        # אירועים: בלי חודש

        cands = scanned.setdefault(target, scan_dir(target))
        if not cands:
            missing.append({**it, "reason": "no_candidates_in_dir", "dir": target})
            continue

        scored = score_candidates(it["name"], cands)
        r, c = scored[0]
        rec = {
            "id": it.get("id"), "item_name": it["name"], "dept": dept, "month": mon,
            "match_type": c["type"], "folder": c["path"],
            "video_files": c["videos"], "confidence": round(r, 2),
        }
        if r >= MATCH_STRONG and c["videos"]:
            matched.append(rec)
            referenced.add(c["path"])
        elif r >= MATCH_WEAK:
            rec["reason"] = "low_confidence" if c["videos"] else "match_but_no_video_file"
            rec["candidates"] = [
                {"name": x[1]["name"], "path": x[1]["path"], "score": round(x[0], 2),
                 "videos": x[1]["videos"]} for x in scored[:3]
            ]
            needs_review.append(rec)
            referenced.add(c["path"])
        else:
            missing.append({
                **it, "reason": "no_good_match", "dir": target,
                "closest": [{"name": x[1]["name"], "score": round(x[0], 2)} for x in scored[:3]],
            })

    # יתומים: מועמדים עם וידאו שאף פריט לא תפס
    orphans = []
    for mdir, cands in scanned.items():
        for c in cands:
            if c["videos"] and c["path"] not in referenced:
                orphans.append({"name": c["name"], "path": c["path"], "videos": c["videos"], "dir": mdir})

    out = {
        "summary": {"matched": len(matched), "needs_review": len(needs_review),
                    "missing": len(missing), "orphans": len(orphans)},
        "matched": matched, "needs_review": needs_review, "missing": missing, "orphans": orphans,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
