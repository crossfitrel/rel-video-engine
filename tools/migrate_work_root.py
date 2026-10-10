#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""migrate_work_root.py — העברת תיקיית העבודה מ-iCloud לדיסק מקומי (v8.6, P0-11).

למה: `_work` בתוך ~/Library/Mobile Documents (iCloud Drive). שלוש עלויות נמדדו:
  1. eviction באמצע גימור — אפל יכולה לפנות קובץ ביניים בזמן שה-ffmpeg כותב
     אליו. `cleanup_work.py:6-7` מזהיר על זה במפורש. אין הגנה בקוד.
  2. `/api/projects` סורק ~38 תיקיות × 4 קבצי JSON + hash, בכל טעינת דף,
     על filesystem מסונכרן.
  3. 100-200 PNG של כתוביות נכתבים ונמחקים בכל גימור ⇒ אלפי אירועי סנכרון.

מה **לא** משתנה: התוצרים הסופיים ממשיכים להיתייק ל-iCloud דרך
`resolve_output_path` בדיוק כמו קודם ({מחלקה}/{חודש}/{סרטון}/). רק תיקיית
העבודה זזה. המשמעות היחידה: פרויקט *בעבודה* לא נגיש ממכשיר אחר.

בטיחות:
  * dry-run כברירת מחדל.
  * מסרב לרוץ אם קיימת נעילת גימור פעילה (`.finish.lock`).
  * rsync (העתקה), לא mv — המקור נשאר שלם עד שהאימות עובר.
  * אימות: כל תיקיית פרויקט קיימת, אותה ספירת קבצים, אותו סך בתים.
  * paths.json נכתב **רק אחרי** שהאימות עבר.
  * `--archive-legacy` משנה את שם המקור ל-`_work.MIGRATED-<ts>` (לא מוחק) —
    כדי שתהיה חזרה אחורה. מחיקה בפועל היא החלטה של הראל, אחרי כמה ימי עבודה.

שימוש:
  python3 tools/migrate_work_root.py                       # דוח בלבד
  python3 tools/migrate_work_root.py --apply
  python3 tools/migrate_work_root.py --apply --archive-legacy
  python3 tools/migrate_work_root.py --rollback            # חזרה ל-_work ב-iCloud
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from relvid.paths import CONFIG, LEGACY_WORK, SYSDIR, describe, work_root  # noqa: E402

DEFAULT_TARGET = Path.home() / "rel-video-work"


def tree_stats(root: Path):
    n_files, n_bytes, dirs = 0, 0, []
    for p in root.rglob("*"):
        try:
            if p.is_dir():
                if p.parent == root:
                    dirs.append(p.name)
            elif p.is_file():
                n_files += 1
                n_bytes += p.stat().st_size
        except OSError:
            pass
    return n_files, n_bytes, sorted(dirs)


def human(n):
    return f"{n/1e9:.2f} GB" if n >= 1e9 else f"{n/1e6:.0f} MB"


def active_locks(root: Path):
    return [p.parent.name for p in root.glob("*/.finish.lock") if p.is_dir()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=str(DEFAULT_TARGET))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--archive-legacy", action="store_true",
                    help="לשנות שם המקור ל-_work.MIGRATED-<ts> אחרי אימות (לא מוחק)")
    ap.add_argument("--rollback", action="store_true", help="מוחק paths.json — חזרה ל-_work")
    a = ap.parse_args()

    if a.rollback:
        if CONFIG.exists():
            bak = CONFIG.with_name(f"paths.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
            CONFIG.replace(bak)
            print(f"✅ paths.json הוסר (גובה ל-{bak.name}) — תיקיית העבודה חזרה ל-{LEGACY_WORK}")
        else:
            print("אין paths.json — כבר על ברירת המחדל")
        print(json.dumps(describe(), ensure_ascii=False, indent=1))
        return

    src = work_root()
    dst = Path(a.target).expanduser()

    if "Mobile Documents" not in str(src):
        print(f"תיקיית העבודה כבר מחוץ ל-iCloud: {src} — אין מה להעביר.")
        return
    if not src.is_dir():
        sys.exit(f"[!] תיקיית המקור לא קיימת: {src}")

    locks = active_locks(src)
    if locks:
        sys.exit(f"[!] יש גימור פעיל ({', '.join(locks)}) — לא מעבירים תיקיית עבודה "
                 f"תוך כדי ריצה. לחכות לסיום או לבטל באפליקציה.")

    n_files, n_bytes, projects = tree_stats(src)
    free = shutil.disk_usage(str(dst.parent if dst.parent.exists() else Path.home())).free
    print("=" * 64)
    print(f"מקור : {src}")
    print(f"יעד  : {dst}")
    print(f"תוכן : {len(projects)} תיקיות · {n_files} קבצים · {human(n_bytes)}")
    print(f"פנוי ביעד: {human(free)}")
    print("=" * 64)
    if free < n_bytes * 1.15:
        sys.exit("[!] אין מספיק מקום פנוי ביעד (דרוש 115% מגודל המקור)")
    if not a.apply:
        print("הרצה יבשה. להעברה בפועל: --apply  (ולשמירת גיבוי: --archive-legacy)")
        return

    dst.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print("▶ מעתיק (rsync)…", flush=True)
    r = subprocess.run(["rsync", "-a", "--delete", f"{src}/", f"{dst}/"],
                       capture_output=True, text=True, timeout=7200)
    if r.returncode != 0:
        sys.exit(f"[!] rsync נכשל: {r.stderr[-500:]}")
    print(f"✅ הועתק ב-{time.time()-t0:.0f}ש", flush=True)

    # אימות
    d_files, d_bytes, d_projects = tree_stats(dst)
    problems = []
    missing = sorted(set(projects) - set(d_projects))
    if missing:
        problems.append(f"תיקיות חסרות ביעד: {missing[:5]}")
    if d_files != n_files:
        problems.append(f"ספירת קבצים: מקור {n_files} מול יעד {d_files}")
    if abs(d_bytes - n_bytes) > 1024:
        problems.append(f"סך בתים: מקור {n_bytes} מול יעד {d_bytes}")
    # אימות תוכן ממשי על קבצי המפתח של כל פרויקט
    for name in projects:
        for key in ("edl.json", "project_manifest.json"):
            s, t = src / name / key, dst / name / key
            if s.exists() and (not t.exists() or s.stat().st_size != t.stat().st_size):
                problems.append(f"{name}/{key} לא תואם")
    if problems:
        print("❌ האימות נכשל — paths.json לא נכתב, שום דבר לא השתנה:")
        for p in problems[:10]:
            print(f"   · {p}")
        sys.exit(1)
    print(f"✅ אימות עבר: {d_files} קבצים · {human(d_bytes)} · {len(d_projects)} תיקיות")

    CONFIG.write_text(json.dumps(
        {"_doc": "נתיב תיקיית העבודה. הועבר מ-iCloud לדיסק מקומי (v8.6, P0-11) — "
                 "eviction באמצע גימור + סריקה איטית. תוצרים סופיים ממשיכים ל-iCloud. "
                 "לחזרה אחורה: python3 tools/migrate_work_root.py --rollback",
         "work_root": str(dst), "migrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
         "migrated_from": str(src)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ נכתב {CONFIG}")

    if a.archive_legacy:
        arch = src.with_name(f"_work.MIGRATED-{time.strftime('%Y%m%d-%H%M%S')}")
        src.rename(arch)
        print(f"📦 המקור שונה ל-{arch.name} (לא נמחק — מחיקה היא החלטה שלך)")

    print()
    print(json.dumps(describe(), ensure_ascii=False, indent=1))
    print("\n⚠️ להפעיל מחדש את review-app כדי שיקרא את הנתיב החדש:")
    print("   lsof -ti:5112 | xargs kill; nohup ~/.rel-whisper/bin/python "
          "review-app/server.py > review-app/server.log 2>&1 &")


if __name__ == "__main__":
    main()
