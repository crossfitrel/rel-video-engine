#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cleanup_work.py — v7.8 · ניקוי ביניים ב-_work (dry-run כברירת מחדל)
====================================================================
מדידה 25.7.26: `_work` = 9.9GB, מתוכם ~3.9GB קבצי ביניים. כל בית אלה מסתנכרן
דרך iCloud בכל ריצה — זה גם מקום וגם רוחב פס וגם סיכון ל-eviction באמצע גימור.

**מה נמחק (ניתן לשחזור מלא בריצת גימור):**
  cue_*.png · caplist.txt · _blank.png   — פריימי כתוביות זמניים (1669 קבצים!)
  MIXED.mp4 · EXPORT+BROLL.mp4           — ביניים בין מוזיקה לכתוביות
  ROUGH.mp4 · CAPTIONED.mp4              — שרידי עידן Descript, לא בזרימה
  PREVIEW.mp4                            — נוצר מחדש באפליקציה בלחיצה
  FINAL_prev_*.mp4 מעבר ל-N האחרונים     — היסטוריית FINAL (ברירת מחדל: שומר 2)

**מה לעולם לא נוגעים בו:**
  INPUT.mp4 · FINAL.mp4 · edl.json · revisions/ · comments.json · runs/ ·
  project_manifest.json · words_final.json · תמלילים ·
  **EXPORT.mp4 + EXPORT_TIGHT.mp4 + whisper_export_tight.json** — הציר המהודק
  הוא התנאי ל"גימור מהיר" (--refinish) ולהחלפת בירול על EXPORT נקי. מחיקתם
  הופכת כל תיקון קטן לריצה מלאה. אפשר לכלול אותם במפורש רק בפרויקטים שכבר
  פורסמו, עם --include-axis.

שימוש:
  python3 tools/cleanup_work.py                      # דוח בלבד (לא מוחק)
  python3 tools/cleanup_work.py --apply              # מוחק בפועל
  python3 tools/cleanup_work.py --keep-finals 3 --older-than 14 --apply
  python3 tools/cleanup_work.py --project "שם" --apply
"""
import argparse, json, os, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys as _sys; _sys.path.insert(0, str(HERE))
from relvid.paths import work_root as _work_root   # v8.6 (P0-11)
WORK = _work_root()

ALWAYS = ["cue_*.png", "_blank.png", "caplist.txt", "MIXED.mp4", "EXPORT+BROLL.mp4",
          "ROUGH.mp4", "CAPTIONED.mp4", "PREVIEW.mp4", "FINAL_PENDING.mp4",
          "seg_*.mp4", "*.tmp.mp4", "*.loud.mp4"]
AXIS = ["EXPORT.mp4", "EXPORT_TIGHT.mp4"]
NEVER = {"INPUT.mp4", "FINAL.mp4", "edl.json", "project_manifest.json"}

# v9.4 — artifacts/ הוא היסטוריית הווידאו של הפרויקט. שום מסלול בכלי הזה לא
# נוגע בו: לא ה-glob (שכולם לא-רקורסיביים ולכן ממילא לא נכנסים לתת-תיקייה),
# ולא כל תוספת עתידית — is_inside_artifacts הוא שומר סף מפורש לפני כל unlink.
# שורש: לפני התיקון, ברירת המחדל של הכלי מחקה FINAL_prev מעבר ל-2 — כלומר
# מחקה גרסאות וידאו מוצלחות. עכשיו FINAL_prev שכבר נלכד ב-artifact נחשב
# "כפילות" ומחיקתו בטוחה (hardlink — התוכן חי ב-artifact), ו-FINAL_prev שלא
# נלכד **לא נמחק בברירת מחדל** אלא רק עם --prune-unarchived.
ARTIFACTS_DIRNAME = "artifacts"


def _archived_checksums(d):
    """checksums של כל התוצרים ששמורים לצמיתות בפרויקט (ריק אם אין artifacts)."""
    try:
        from relvid import artifacts as art_mod
        return {a.get("checksum") for a in art_mod.list_artifacts(d) if a.get("checksum")}
    except Exception:
        return set()


def _is_archived(p, archived):
    if not archived:
        return False
    try:
        from relvid import sha256_file
        return sha256_file(p, quick=False) in archived
    except Exception:
        return False


def human(n):
    return f"{n/1e9:.2f} GB" if n >= 1e9 else f"{n/1e6:.0f} MB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="מחיקה בפועל (בלי זה — דוח בלבד)")
    ap.add_argument("--keep-finals", type=int, default=2, help="כמה FINAL_prev לשמור לכל פרויקט")
    ap.add_argument("--older-than", type=int, default=0,
                    help="לגעת רק בפרויקטים שלא נגעו בהם N ימים (0=כולם)")
    ap.add_argument("--project", help="פרויקט יחיד")
    ap.add_argument("--include-axis", action="store_true",
                    help="למחוק גם EXPORT/EXPORT_TIGHT — ⚠️ מבטל את היכולת לגימור מהיר")
    ap.add_argument("--prune-unarchived", action="store_true",
                    help="⚠️ למחוק גם FINAL_prev שלא נשמרו ב-artifacts (איבוד גרסה)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    cutoff = time.time() - a.older_than * 86400 if a.older_than else None
    plan, total, errors = [], 0, []
    kept_unarchived = 0
    total_linked = 0
    dirs = [WORK / a.project] if a.project else sorted(d for d in WORK.iterdir()
                                                       if d.is_dir() and not d.name.startswith("_")
                                                       and not d.name.startswith("."))
    for d in dirs:
        if not d.is_dir():
            continue
        if cutoff and d.stat().st_mtime > cutoff:
            continue
        victims = []
        for pat in ALWAYS + (AXIS if a.include_axis else []):
            victims += [p for p in d.glob(pat) if p.name not in NEVER]
        # FINAL_prev: נמחק רק אם התוכן כבר שמור לצמיתות ב-artifacts/ (ואז זו
        # כפילות hardlink ולא איבוד), או אם ביקשו במפורש --prune-unarchived.
        archived = _archived_checksums(d)
        prevs = sorted(d.glob("FINAL_prev_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in prevs[a.keep_finals:]:
            if _is_archived(p, archived) or a.prune_unarchived:
                victims.append(p)
            else:
                kept_unarchived += 1
        victims = [p for p in victims if ARTIFACTS_DIRNAME not in p.parts]   # שומר סף
        # מקום שמשתחרר **בפועל**: קובץ שמקושר (hardlink) גם מתוך artifacts/ לא
        # מפנה ולו בית אחד כשמוחקים אותו — התוכן ממשיך לחיות בגרסה השמורה.
        # לדווח עליו כ"שוחרר" זה דיווח שקרי, בדיוק כמו הבאג של 25.7.
        size = sum(p.stat().st_size for p in victims
                   if p.exists() and p.stat().st_nlink == 1)
        dup = sum(p.stat().st_size for p in victims
                  if p.exists() and p.stat().st_nlink > 1)
        if victims:
            row = {"project": d.name, "files": len(victims), "bytes": size,
                   "linked_bytes": dup}
            plan.append(row)
            total += size
            total_linked += dup
            if a.apply:
                # כשל מחיקה **לא** נבלע (לקח 25.7.26: הרצה מתוך הסנדבוקס דיווחה
                # "נמחקו 1.8GB" בזמן שכל הקבצים נשארו — המאונט חוסם unlink וה-except
                # הבליע את זה. דיווח שקרי גרוע מכשל.) להריץ תמיד מהמק.
                failed = []
                for p in victims:
                    try:
                        p.unlink()
                    except Exception as e:
                        failed.append(f"{p.name}: {e}")
                if failed:
                    row["failed"] = len(failed)
                    row["first_error"] = failed[0]
                    errors.extend(failed)

    if a.json:
        print(json.dumps({"applied": a.apply, "total_bytes": total,
                          "linked_bytes": total_linked,
                          "errors": len(errors), "plan": plan,
                          "kept_unarchived_finals": kept_unarchived},
                         ensure_ascii=False, indent=1))
        return
    for row in sorted(plan, key=lambda r: -r["bytes"]):
        extra = f"  (+{human(row['linked_bytes'])} כפילויות מקושרות)" if row.get("linked_bytes") else ""
        print(f"{row['project'][:38]:40} {row['files']:5} קבצים  {human(row['bytes'])}{extra}")
    print("-" * 62)
    verb = "נמחקו" if a.apply else "יימחקו (הרצה יבשה — הוסף --apply)"
    print(f"סה\"כ {verb}: {human(total)} ב-{len(plan)} פרויקטים")
    if total_linked:
        print(f"בנוסף {human(total_linked)} קובצי FINAL_prev שכבר שמורים כגרסאות — מחיקתם "
              f"מנקה סדר בלבד ולא מפנה מקום (hardlink: התוכן חי ב-artifacts/).")
    if errors:
        print(f"\n❌ {len(errors)} מחיקות נכשלו — שום דבר לא נמחק בפועל שם.")
        print(f"   דוגמה: {errors[0]}")
        print("   הרץ מהמק (Desktop Commander), לא מהסנדבוקס — המאונט חוסם unlink.")
        raise SystemExit(2)
    if kept_unarchived:
        print(f"🛡  {kept_unarchived} קובצי FINAL_prev לא נמחקו — הם לא שמורים ב-artifacts/.")
        print("   הרץ `python3 tools/migrate_artifacts.py --apply` כדי לשמר אותם כגרסאות,")
        print("   ורק אז ניקוי יפנה אותם. (--prune-unarchived מוחק בלי לשמר — איבוד גרסה.)")
    if not a.apply and total:
        print("הציר המהודק (EXPORT/EXPORT_TIGHT) נשמר — גימור מהיר ימשיך לעבוד.")
    print("artifacts/ מחוץ לתחום הכלי הזה — היסטוריית הווידאו לעולם לא נמחקת כאן.")


if __name__ == "__main__":
    main()
