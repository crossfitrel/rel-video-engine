#!/usr/bin/env python3
"""מחיל את תוצאות האימות הוויזואלי (v9.7) על הקונפיג וה-overrides.

מקור האמת של הסקריפט הזה הוא **פריימים שנצפו**, לא שמות קבצים. המספרים
מתייחסים ל-`~/rel-video-work/.gender-audit/index.json` (מועמדים) ול-
`~/rel-video-work/.gender-pool/index.json` (הבריכה המאומתת הקיימת).

  python3 tools/bench/apply_gender_audit.py [--dry-run]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
CFG = TOOLS / "broll-catalog-config.json"
OVR = TOOLS / "broll-tags-override.json"
AUDIT = TOOLS / "broll-gender-audit.json"

WORK = Path("~/rel-video-work").expanduser()
SINCE = "2026-07-31"

# ── גברים שאומתו: 3 פריימים לקליפ, ואומתו מול גיליון-ייחוס של הראל ──
MEN = [28, 34, 44, 51, 61, 64, 74, 82, 89, 104, 131, 136,
       143, 162, 170, 174, 186, 206, 215, 1, 21, 260]

# ── פסק-דין של הראל, 31.7.26, על גיליון האימות: "ב-28, 34, 44 זה לא אני" ──
# כלומר 27, 31, 36 **כן** הוא. שלושתם מאותה משפחה: **הפנים אינן בפריים**
# (עמידת ידיים הפוכה · טבעות ממרחק · מתח מהגב). הלקח: כשאין פנים, "לא
# הראל" אינו ניתן לאימות — בגד ומבנה גוף אינם ראיה. אותה זהירות שהוחלה
# על AMBIGUOUS הייתה צריכה לחול גם כאן.
HAREL = {
    27: "הראל 31.7.26 — עמידת ידיים על הקיר, הפנים הפוכות ולא מזוהות",
    31: "הראל 31.7.26 — מאסל-אפ בטבעות, צולם ממרחק בלי פנים",
    36: "הראל 31.7.26 — מתח בריג, מצולם מהגב",
    # סבב שני על אותה משפחה — הפעם נשאל מראש ולא נוחש. 51 אושר כמתאמן.
    46: "הראל 31.7.26 — עמידת ידיים מול הקיר, הפנים הפוכות ולא מזוהות",
}

# כלל שנגזר מהתיקון: **קליפ שהפנים בו אינן בפריים אינו נכנס לבריכה בלי
# פסק-דין מפורש של הראל.** ארבעה מתוך ארבעה שפספסתי היו כאלה.
FACELESS_NEEDS_RULING = True

# ── נצפו ונפסלו: דמיון מספיק להראל כדי שהוספה תהיה הימור ──
AMBIGUOUS = {
    2: "אמבט קרח — הדמות הקדמית מזוקנת וכהת-שיער, לא ניתן לשלול הראל",
    40: "מתח בריג — זקן וגוון שיער דומים להראל",
    56: "דחיקה מעל הראש בחולצת R.E.L בז' — הפריט הכי דומה לייחוס",
    84: "דדליפט בחולצה בז' — פנים חלקיות, דמיון להראל",
    120: "ניקוי בארבל — פנים חלקיות, דמיון להראל",
    191: "קפיצת קופסה — זקן וקעקועים דומים להראל",
}

# ── ממצאים בבריכה המאומתת הקיימת (מספרי .gender-pool) ──
POOL_FIX = {33: ["נשים"], 34: ["ילדים"]}
POOL_NOTES = {
    33: "ראיון עם מתאמנת — קליפ דיבור-למצלמה בתוך בריכת הבירול. "
        "is_cutaway חוסם אותו בזמן בחירה, אבל הוא מנפח את הבריכה.",
    34: "שיעור ילדים — **לא מתאמנת בוגרת**, ונספר עד היום כ'נשים'. "
        "הטענה '34 מתוך 34 נשים' לא הייתה מדויקת.",
}


def load(p: Path) -> dict | list:
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    dry = "--dry-run" in sys.argv
    cand = {i["n"]: i for i in load(WORK / ".gender-audit" / "index.json")}
    pool = {i["n"]: i for i in load(WORK / ".gender-pool" / "index.json")}
    cfg, ovr = load(CFG), load(OVR)

    men_files = [cand[n]["file"] for n in MEN]

    # פסק-דין של הראל גובר על האימות שלי: הוצאה מהבריכה + כניסה לרשימת
    # "הראל בפריים", כדי שהקליפ לא ייבחר שוב בריצה הבאה.
    harel_files = {cand[n]["file"]: why for n, why in HAREL.items() if n in cand}
    cfg["verified_member_files"] = [f for f in cfg["verified_member_files"]
                                    if f not in harel_files]
    have = {d.get("file") for d in cfg.get("harel_present_files", [])}
    for f, why in harel_files.items():
        if f not in have:
            cfg.setdefault("harel_present_files", []).append(
                {"file": f, "why": why, "since": SINCE})
    for f in harel_files:
        ovr.pop(f, None)

    new = [f for f in men_files if f not in cfg["verified_member_files"]]

    # 1) people על הגברים החדשים
    for f in men_files:
        e = ovr.setdefault(f, {"tags": [], "audience": []})
        e["people"] = ["גברים"]
        e["people_verified"] = SINCE
    # 2) people על הבריכה הקיימת — נשים כברירת מחדל, למעט מה שנצפה אחרת
    for n, it in pool.items():
        e = ovr.setdefault(it["file"], {"tags": [], "audience": []})
        e["people"] = POOL_FIX.get(n, ["נשים"])
        e["people_verified"] = SINCE
        if n in POOL_NOTES:
            e["people_note"] = POOL_NOTES[n]
    # 3) הרחבת הבריכה
    cfg["verified_member_files"] = cfg["verified_member_files"] + new

    audit = {
        "_doc": "אימות ויזואלי של מגדר-בפריים בספריית המועדון (v9.7, 31.7.26). "
                "המקור הוא פריימים שנצפו — לא שמות קבצים. הרקע: הראל, 31.7: "
                "'יש בירולים רק של נשים? מה עם קצת גברים.'",
        "date": SINCE,
        "candidates_reviewed": len(cand),
        "verified_pool_reviewed": len(pool),
        "men_added": new,
        "rejected_as_possible_harel": {
            cand[n]["file"]: why for n, why in AMBIGUOUS.items() if n in cand},
        "removed_by_harel_ruling": harel_files,
        "lesson": "שלושת הקליפים שהראל זיהה כשלו הם בדיוק אלה ש**הפנים אינן "
                  "בפריים** (עמידת ידיים · טבעות ממרחק · מתח מהגב). כשאין "
                  "פנים, 'לא הראל' אינו ניתן לאימות — בגד ומבנה גוף אינם "
                  "ראיה. קליפ בלי פנים נכנס לבריכה רק באישור מפורש.",
        "pool_corrections": {pool[n]["file"]: POOL_NOTES[n] for n in POOL_NOTES},
        "method": "gender_audit_sheets.py → 13 גיליונות · "
                  "harel_reference_sheet.py → ייחוס · "
                  "verify_picks_sheet.py → 3 פריימים לכל נבחר",
    }

    print(f"גברים חדשים: {len(new)} · בריכה: "
          f"{len(cfg['verified_member_files'])} · נדחו כהראל-אפשרי: {len(AMBIGUOUS)}")
    if dry:
        print("dry-run — לא נכתב כלום")
        return 0
    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    OVR.write_text(json.dumps(ovr, ensure_ascii=False, indent=1), encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    print("נכתב: broll-catalog-config.json · broll-tags-override.json · "
          "broll-gender-audit.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
