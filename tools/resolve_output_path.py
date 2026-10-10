#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_output_path.py — R.E.L Social Video Editing System
==========================================================
מחשב את תיקיית היעד הקנונית של תוצר סופי לפי:
  מחלקה (עמודת Monday 'סטטוס מחלקה') + חודש פרסום + שם הסרטון.

מבנה היעד (כמו שהראל מארגן ידנית):
  {content_root}/{base}/{חודש שנה}/{שם הסרטון}/{שם הסרטון - סופי.mp4}
  אירועים (Throwdown/Community Games): {content_root}/{base}/{שם הנושא}/...

הסקריפט **רק מחשב** נתיבים (pure) — הוא לא יוצר תיקיות ולא מזיז קבצים,
כי תיקיות היעד נמצאות מחוץ ל-mount של ה-sandbox (בתיקיית האב "תוכן שיווקי").
התיוק עצמו (mkdir + move) נעשה ע"י הסוכן דרך Desktop Commander, לפי הפלט כאן.

מקור אמת למפת המחלקות: folder-routing.json (באותה תיקייה).

שימוש:
  python3 resolve_output_path.py --dept "קרוספיט אריאל" --name "מאמן לא רק סופר חזרות" --month "יוני 2026"
  python3 resolve_output_path.py --dept 1 --name "טיפ חתירה" --date 2026-07-03
  python3 resolve_output_path.py --dept "REL Throwdown" --name "רמז למקצה 2"   # אירוע, בלי חודש
"""

import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUTING = os.path.join(HERE, "folder-routing.json")

HE_MONTHS = {1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל", 5: "מאי", 6: "יוני",
             7: "יולי", 8: "אוגוסט", 9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"}


def load_routing():
    return json.load(open(ROUTING, encoding="utf-8"))


def sanitize(name):
    """שומר עברית; מסיר תווים אסורים לשם תיקייה/קובץ ומכווץ רווחים."""
    name = (name or "").strip()
    name = re.sub(r'[\\/:*?"<>|]+', " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def resolve_dept(routing, dept):
    dept_s = str(dept).strip()
    depts = routing["departments"]
    for d in depts:                                   # 1) label מדויק
        if dept_s == d["label"]:
            return d
    for d in depts:                                   # 2) id / index
        if dept_s == str(d.get("id")) or dept_s == str(d.get("index")):
            return d
    low = dept_s.lower()
    for d in depts:                                   # 3) aliases / הכלה
        if low == d["label"].lower():
            return d
        for a in d.get("aliases", []):
            if low == a.lower():
                return d
    return None


def month_folder(args):
    if args.month:
        return args.month.strip()
    dt = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    year = args.year or dt.year
    return f"{HE_MONTHS[dt.month]} {year}"


def main():
    p = argparse.ArgumentParser(description="ניתוב תוצר סופי לתיקיית מחלקה/חודש/סרטון")
    p.add_argument("--dept", required=True, help="label או id/index של עמודת המחלקה")
    p.add_argument("--name", required=True, help="שם הסרטון = שם פריט Monday")
    p.add_argument("--date", help="תאריך פרסום ISO YYYY-MM-DD (לקביעת החודש)")
    p.add_argument("--month", help="חודש מפורש 'יוני 2026' (גובר על --date)")
    p.add_argument("--year", type=int, help="שנה מפורשת (לאירועים / override)")
    p.add_argument("--ext", default="mp4")
    args = p.parse_args()

    routing = load_routing()
    d = resolve_dept(routing, args.dept)
    if not d:
        print(json.dumps({"ok": False, "error": f"מחלקה לא מזוהה: {args.dept}",
                          "known": [x["label"] for x in routing["departments"]]},
                         ensure_ascii=False, indent=2))
        return 2

    year = args.year or (datetime.date.fromisoformat(args.date).year if args.date
                         else datetime.date.today().year)
    leaf = sanitize(args.name)
    base = d["folder"].replace("{year}", str(year))
    suffix = routing.get("final_suffix", " - סופי")

    parts = [routing["content_root"], base]
    mid = ""
    if d.get("month_based"):
        mid = month_folder(args)
        parts.append(mid)
    scan_dir = os.path.join(*parts)        # ההורה של תיקיית-הסרטון — לסריקת תיקייה קיימת
    dest_dir = os.path.join(scan_dir, leaf)
    final_name = f"{leaf}{suffix}.{args.ext}"

    out = {
        "ok": True,
        "department": d["label"],
        "base_folder": base,
        "month_folder": mid,
        "video_folder": leaf,
        "scan_dir": scan_dir,                      # DC list_directory כאן → התאמה לתיקייה שהראל יצר
        "dest_dir": dest_dir,                      # אם אין התאמה → DC create_directory
        "final_filename": final_name,
        "dest_path": os.path.join(dest_dir, final_name),
        "work_dir": os.path.join(routing["work_root"], leaf),
        "hint": "1) DC list_directory(scan_dir) ואתר תיקייה קיימת תואמת לשם. "
                "2) אם אין — DC create_directory(dest_dir). "
                "3) DC move_file(הקובץ הסופי מה-_work → dest_path)."
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
