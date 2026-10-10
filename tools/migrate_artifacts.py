#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_artifacts.py — מיגרציה לא-הרסנית של תוצרי וידאו קיימים ל-Artifact Store.
===============================================================================
קורא את מה שכבר קיים על הדיסק — `FINAL.mp4`, `FINAL_prev_*.mp4`, `runs/run_*.json`,
`FINAL_PROVENANCE.json`, `revisions/`, `project_manifest.json` — ובונה מהם אינדקס
גרסאות קבוע תחת `artifacts/`.

**dry-run כברירת מחדל.** בלי `--apply` שום קובץ לא נוצר, לא זז ולא נמחק —
מודפס בדיוק מה ייווצר.

כללי ההתאמה (אין ניחושים):
  * קובץ ↔ ריצה מותאמים כשיש **התאמת checksum** לרשומת ריצה, או כש-mtime
    של הקובץ נופל בתוך חלון הריצה (started_at..finished_at + 90ש) ו**רק ריצה
    אחת** מתאימה. שתי מועמדות ⇒ לא מתאימים.
  * `FINAL.mp4` הנוכחי מקבל גם את `FINAL_PROVENANCE.json` (שנכתב עבורו).
  * קובץ שלא הותאם לריצה **עדיין נשמר כגרסה** (הווידאו הוא הנכס) אבל מסומן
    `matched=false` — לא ממציאים לו run_id.
  * ריצה מוצלחת שאין לה קובץ בכלל נרשמת ב-`unmatched_runs` כ**תקלה**
    ("הווידאו אינו זמין"), ולא כגרסה תקינה.

הרצה חוזרת אידמפוטנטית: התאמה לפי checksum מלא — קובץ שכבר נשמר לא נשמר שוב.

שימוש:
  python3 tools/migrate_artifacts.py                      # דוח בלבד
  python3 tools/migrate_artifacts.py --project "שם"        # פרויקט יחיד
  python3 tools/migrate_artifacts.py --apply              # יצירה בפועל
  python3 tools/migrate_artifacts.py --apply --json
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from relvid import read_json, sha256_file                      # noqa: E402
from relvid.paths import work_root as _work_root               # noqa: E402
from relvid import artifacts as art                            # noqa: E402

WORK = _work_root()
RUN_WINDOW_SLACK = 90.0          # שניות אחרי finished_at שעדיין נחשבות לאותה ריצה


def _ts(s):
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def candidate_files(d: Path):
    """כל קובצי הווידאו הסופיים שקיימים בפועל, מהישן לחדש."""
    out = []
    for p in sorted(d.glob("FINAL_prev_*.mp4"), key=lambda p: p.stat().st_mtime):
        out.append(p)
    f = d / "FINAL.mp4"
    if f.exists():
        out.append(f)
    return [p for p in out if p.stat().st_size > 0]


def match_run(path: Path, runs, used):
    """מתאים קובץ לרשומת ריצה — או None אם ההתאמה אינה ודאית."""
    csum = None
    for r in runs:
        if r.get("output_hash") and r.get("status") == "done":
            csum = csum or sha256_file(path, quick=True)
            if r["output_hash"] == csum and r["run_id"] not in used:
                return r, "checksum"
    mt = path.stat().st_mtime
    hits = []
    for r in runs:
        if r.get("status") != "done" or r["run_id"] in used:
            continue
        s, e = _ts(r.get("started_at") or ""), _ts(r.get("finished_at") or "")
        if s and e and s <= mt <= e + RUN_WINDOW_SLACK:
            hits.append(r)
    if len(hits) == 1:
        return hits[0], "time_window"
    return None, ("ambiguous" if len(hits) > 1 else "no_run")


def plan_project(d: Path):
    runs = []
    rd = d / "runs"
    if rd.exists():
        for f in sorted(rd.glob("run_*.json")):
            r = read_json(f)
            if r and r.get("run_id"):
                runs.append(r)
    done_runs = [r for r in runs if r.get("status") == "done"]
    prov = read_json(d / "FINAL_PROVENANCE.json", {}) or {}
    prior = art.list_artifacts(d)
    existing = {a.get("checksum") for a in prior}
    # ריצה שכבר יוצגה ע"י artifact קיים אינה "אבודה" בהרצה חוזרת. בלי השורה
    # הזו, ההרצה השנייה (שבה כל הקבצים מדולגים) הייתה מסמנת את *כל* הריצות
    # המוצלחות כ-media_missing — דיווח שקרי על אובדן שלא קרה.
    rows, used = [], {a.get("run_id") for a in prior if a.get("run_id")}
    for p in candidate_files(d):
        full = sha256_file(p, quick=False)
        if full in existing:
            rows.append({"file": p.name, "action": "skip",
                         "reason": "כבר שמור כ-artifact", "checksum": full})
            continue
        r, how = match_run(p, done_runs, used)
        if r:
            used.add(r["run_id"])
        is_live = (p.name == "FINAL.mp4")
        rows.append({
            "file": p.name, "action": "create", "matched": bool(r), "match_by": how,
            "run_id": r.get("run_id") if r else None,
            "revision_id": (r or {}).get("revision_id") or (prov.get("revision_id") if is_live else None),
            "edl_hash": (r or {}).get("edl_hash") or (prov.get("edl_hash") if is_live else None),
            "input_hash": (r or {}).get("input_hash"),
            "size_bytes": p.stat().st_size, "checksum": full,
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime)),
            "is_live_final": is_live,
        })
    orphan_runs = [{"run_id": r["run_id"], "finished_at": r.get("finished_at"),
                    "output_hash": r.get("output_hash"),
                    "fault": "media_missing",
                    "detail": "ריצה הסתיימה בהצלחה אך קובץ הווידאו שלה כבר אינו על הדיסק"}
                   for r in done_runs if r["run_id"] not in used]
    return {"project": d.name, "path": str(d), "rows": rows,
            "unmatched_runs": orphan_runs,
            "runs_done": len(done_runs), "files_found": len(candidate_files(d))}


def apply_project(pl):
    d = Path(pl["path"])
    created = []
    # מהישן לחדש — כך שמספרי הגרסאות עולים בסדר כרונולוגי אמיתי
    for row in pl["rows"]:
        if row["action"] != "create":
            continue
        rec = art.create_artifact(
            d, d / row["file"], run_id=row.get("run_id"),
            revision_id=row.get("revision_id"), edl_hash=row.get("edl_hash"),
            input_hash=row.get("input_hash"), actor="migration",
            summary=("מיגרציה — " + ("הותאם לריצה " + row["run_id"]
                                     if row.get("matched") else "לא הותאם לריצה")),
            extra={"migrated": True, "migrated_from": row["file"],
                   "matched": bool(row.get("matched")), "match_by": row.get("match_by")},
            make_candidate=False)
        created.append({"artifact_id": rec["artifact_id"], "version": rec["version"],
                        "from": row["file"]})
    arts = art.list_artifacts(d)
    if arts:
        # המועמד האחרון = ה-FINAL החי (אם זוהה), אחרת הגרסה החדשה ביותר.
        live = art.artifact_of_live_final(d)
        art.set_pointer(d, "latest_candidate", live or arts[-1]["artifact_id"],
                        actor="migration", note="מיגרציה — זיהוי הגרסה הפעילה")
        # אין קביעת approved_final אוטומטית: אישור הוא פעולה של הראל בלבד.
        art.reindex(d)
    if pl["unmatched_runs"]:
        art.adir(d, create=True)
        (art.adir(d) / "unmatched.json").write_text(
            json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "unmatched_runs": pl["unmatched_runs"]},
                       ensure_ascii=False, indent=1), encoding="utf-8")
    return created


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="יצירה בפועל (בלי זה — דוח בלבד)")
    ap.add_argument("--project", help="פרויקט יחיד")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--work-root", help="עקיפת תיקיית העבודה (לבדיקות)")
    a = ap.parse_args()

    root = Path(a.work_root).expanduser() if a.work_root else WORK
    dirs = ([root / a.project] if a.project else
            sorted(d for d in root.iterdir()
                   if d.is_dir() and not d.name.startswith(("_", "."))))
    plans = []
    for d in dirs:
        if not d.is_dir() or not (d / "edl.json").exists():
            continue
        pl = plan_project(d)
        if pl["rows"] or pl["unmatched_runs"]:
            plans.append(pl)

    if a.apply:
        for pl in plans:
            pl["created"] = apply_project(pl)

    tot_create = sum(1 for pl in plans for r in pl["rows"] if r["action"] == "create")
    tot_skip = sum(1 for pl in plans for r in pl["rows"] if r["action"] == "skip")
    tot_lost = sum(len(pl["unmatched_runs"]) for pl in plans)

    if a.json:
        print(json.dumps({"applied": a.apply, "work_root": str(root),
                          "to_create": tot_create, "already": tot_skip,
                          "unmatched_runs": tot_lost, "projects": plans},
                         ensure_ascii=False, indent=1))
        return

    verb = "נוצרו" if a.apply else "ייווצרו (הרצה יבשה — הוסף --apply)"
    for pl in plans:
        creates = [r for r in pl["rows"] if r["action"] == "create"]
        if not creates and not pl["unmatched_runs"]:
            continue
        print(f"\n▸ {pl['project']}   ({pl['runs_done']} ריצות מוצלחות · "
              f"{pl['files_found']} קובצי וידאו על הדיסק)")
        for r in creates:
            tag = ("↔ " + r["run_id"]) if r.get("matched") else "⚠️ לא הותאם לריצה"
            print(f"   + גרסה מ-{r['file']:32} {r['mtime']}  {r['size_bytes']/1e6:6.1f}MB  {tag}")
        for r in [x for x in pl["rows"] if x["action"] == "skip"]:
            print(f"   = {r['file']:32} כבר שמור")
        for u in pl["unmatched_runs"]:
            print(f"   ✖ {u['run_id']} ({u.get('finished_at') or '?'}) — {u['detail']}")
    print("\n" + "-" * 70)
    print(f"סה\"כ {verb}: {tot_create} גרסאות · {tot_skip} כבר שמורות")
    if tot_lost:
        print(f"⚠️ {tot_lost} ריצות מוצלחות שהווידאו שלהן אבד לפני המיגרציה — "
              f"נרשמות כתקלה (artifacts/unmatched.json), לא כגרסה תקינה.")
    if not a.apply:
        print("שום קובץ לא נוצר, לא זז ולא נמחק. להחלה: --apply")


if __name__ == "__main__":
    main()
