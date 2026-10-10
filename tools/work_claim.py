#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
work_claim.py — תיאום בין צ'אטים מקבילים על אותו קוד (v9.30-eff, 22.9.26)
=====================================================================
הבעיה שנמדדה: ב-22.9.26 שלושה צ'אטים עבדו במקביל על המערכת (שערי ראייה,
קנון לקחים, ספריית הסקילים), ו-gate_registry.py / lesson_registry.py /
system_doctor.py / SKILL.md נערכו ע"י יותר מאחד באותו יום (גיבויי
.bak-canon-exc · .bak-l60 · .bak-v929 · .bak-v930 בהפרש של דקות). אין מנגנון
שאומר לצ'אט "מישהו אחר באמצע הקובץ הזה" — הגילוי היה ידני, מתוך mtime.

שני ערוצים:
  1. תביעה מפורשת — claim/release עם TTL (ברירת מחדל 3 שעות), ב-handoff/claims.json.
  2. זיהוי פעילות — גם בלי תביעה: קבצים שנערכו ב-N הדקות האחרונות, מקובצים לפי
     תגית הגיבוי (.bak-vXXX) שנוצרה איתם — זה מה שחושף צ'אט מקביל ששכח לתבוע.

  work_claim.py claim FILE... --by "נושא הצ'אט" [--ttl-min 180] [--note "..."]
  work_claim.py release [FILE...] --by "נושא"     # בלי קבצים = כל התביעות של הנושא
  work_claim.py check FILE... [--by "נושא"]       # exit 3 אם קובץ תבוע ע"י נושא אחר
  work_claim.py list [--active-min 45] [--json]   # תביעות + פעילות אחרונה
"""
from __future__ import annotations

import argparse
import fcntl
import json
import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
CLAIMS = PROJECT / "handoff" / "claims.json"
SKIP_DIRS = {"_work", "_td26_vision", "_archive", "archive", "__pycache__", ".git", "בירולים",
             "brand-assets", "_hf_demo", "_work.MIGRATED-20260730-143827", "_carnival_work", "_cmp", "dist"}
BAK_TAG = re.compile(r"\.bak-([A-Za-z0-9_-]+?)(?:-\d{6,8}(?:-\d{4,6})?)?$")


def rel(p: str) -> str:
    q = Path(p)
    try:
        return str((q if q.is_absolute() else (Path.cwd() / q)).resolve().relative_to(PROJECT))
    except ValueError:
        return p


@contextmanager
def locked():
    CLAIMS.parent.mkdir(parents=True, exist_ok=True)
    with open(CLAIMS.with_suffix(".lock"), "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        data = json.loads(CLAIMS.read_text(encoding="utf-8")) if CLAIMS.exists() else {"claims": []}
        now = time.time()
        data["claims"] = [c for c in data["claims"] if c["expires"] > now]
        yield data
        tmp = CLAIMS.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(CLAIMS)


def active(minutes: int) -> dict:
    """קבצים שנערכו לאחרונה, מקובצים לפי תגית גיבוי שנוצרה באותו חלון."""
    cutoff = time.time() - minutes * 60
    edited, tags = [], {}
    stack = [PROJECT]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.is_dir():
                if p.name not in SKIP_DIRS and not p.name.startswith("."):
                    stack.append(p)
                continue
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if m < cutoff or p.name == ".DS_Store" or p.suffix == ".pyc":
                continue
            r = str(p.relative_to(PROJECT))
            t = BAK_TAG.search(p.name)
            if t:
                tags.setdefault(t.group(1), []).append(r.split(".bak-")[0])
            elif not r.startswith(("handoff/claims", "handoff/.baseline")):
                edited.append((m, r))
    edited.sort(reverse=True)
    return {"edited": [r for _m, r in edited], "backup_tags": tags}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["claim", "release", "check", "list"])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--by", default="")
    ap.add_argument("--ttl-min", type=int, default=180)
    ap.add_argument("--note", default="")
    ap.add_argument("--active-min", type=int, default=45)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    files = [rel(f) for f in a.files]

    if a.cmd == "claim":
        if not a.by or not files:
            ap.error("claim דורש קבצים ו---by")
        with locked() as data:
            clash = [c for c in data["claims"] if c["file"] in files and c["by"] != a.by]
            now = time.time()
            data["claims"] = [c for c in data["claims"] if not (c["file"] in files and c["by"] == a.by)]
            for f in files:
                data["claims"].append({"file": f, "by": a.by, "note": a.note,
                                       "since": time.strftime("%Y-%m-%d %H:%M"), "expires": now + a.ttl_min * 60})
        for c in clash:
            print(f"⚠️ {c['file']} תבוע גם ע\"י «{c['by']}» מ-{c['since']} — לתאם לפני עריכה")
        print(f"✅ נתבעו {len(files)} קבצים ע\"י «{a.by}» ל-{a.ttl_min} דק'")
        return 3 if clash else 0

    if a.cmd == "release":
        with locked() as data:
            before = len(data["claims"])
            data["claims"] = [c for c in data["claims"]
                              if not (c["by"] == a.by and (not files or c["file"] in files))]
            n = before - len(data["claims"])
        print(f"✅ שוחררו {n} תביעות של «{a.by}»")
        return 0

    with locked() as data:
        claims = list(data["claims"])

    if a.cmd == "check":
        hit = [c for c in claims if c["file"] in files and c["by"] != a.by]
        for c in hit:
            left = int((c["expires"] - time.time()) / 60)
            print(f"⛔ {c['file']} — «{c['by']}» (עוד {left} דק') {c.get('note', '')}")
        if not hit:
            print("✅ פנוי")
        return 3 if hit else 0

    act = active(a.active_min)
    if a.json:
        print(json.dumps({"claims": claims, "activity": act}, ensure_ascii=False, indent=1))
        return 0
    if claims:
        print(f"תביעות פעילות ({len(claims)}):")
        by = {}
        for c in claims:
            by.setdefault(c["by"], []).append(c["file"])
        for who, fs in by.items():
            print(f"  «{who}»: " + ", ".join(fs[:8]) + (f" (+{len(fs) - 8})" if len(fs) > 8 else ""))
    else:
        print("אין תביעות פעילות.")
    if act["backup_tags"]:
        print(f"גיבויים שנוצרו ב-{a.active_min} הדק' האחרונות (סימן לצ'אט פעיל):")
        for t, fs in act["backup_tags"].items():
            print(f"  .bak-{t}: " + ", ".join(sorted(set(fs))[:8]))
    if act["edited"]:
        print(f"נערכו ב-{a.active_min} הדק' האחרונות ({len(act['edited'])}): " + ", ".join(act["edited"][:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
