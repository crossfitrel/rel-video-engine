#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lessons_canon.py — קנון לקחים אחד (v9.30, 22.9.26)
=================================================

הבעיה: ~133 קבצי feedback בזיכרון הפרויקט, חלקם SUPERSEDED, חלקם כפולים, חלקם
חיים רק שם — ו-lesson_registry (76 לקחים) לא ידע עליהם. לקח שחי רק בזיכרון הוא
נוהל, ונוהל נשכח בהחלפת המנוע (L26).

הפתרון: טבלת מיפוי אחת (lessons_canon_data.py) — לכל קובץ feedback:
  L          → לקח/ים ב-lesson_registry, והאוכפים שלהם נבדקים שם (--audit)
  superseded → מה מחליף אותו (לקח או כלל תפעולי) — ההחלפה עצמה חייבת להתקיים
  ops        → כלל לסוכן (Metricool/Monday/קופי/צ'אט). האוכף: שורה בטבלת
               "כללי תפעול" ב-SKILL.md שמכילה את ה-slug — שם הסוכן קורא.
ו-docs/LESSONS-CANON.md **נגזר** מהרשומה (--render), לא נכתב ידנית.

  python3 lessons_canon.py --audit
  python3 lessons_canon.py --render        # docs/LESSONS-CANON.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
sys.path.insert(0, str(HERE))
import lesson_registry as LR          # noqa: E402
import lessons_canon_data as D        # noqa: E402

SKILL = SYSDIR / "skills" / "rel-social-video-editor" / "SKILL.md"
OUT = SYSDIR / "docs" / "LESSONS-CANON.md"
OPS_HEADER = "## כללי תפעול מהזיכרון (קנון v9.30)"


def audit() -> tuple[bool, list[str]]:
    probs: list[str] = []
    skill = SKILL.read_text(encoding="utf-8") if SKILL.exists() else ""
    ops_block = skill.split(OPS_HEADER, 1)[1] if OPS_HEADER in skill else ""
    if not ops_block:
        probs.append(f"❌ אין בסקיל את הסעיף '{OPS_HEADER}'")
    for slug, r in D.C.items():
        st = r["status"]
        if st == "L":
            if not r["ids"]:
                probs.append(f"❌ {slug}: status L בלי לקח")
            for i in r["ids"]:
                if i not in LR.LESSONS:
                    probs.append(f"❌ {slug}: הלקח {i} לא קיים ב-lesson_registry")
        elif st == "superseded":
            for i in r["ids"]:
                if i.startswith("ops:"):
                    tgt = i[4:]
                    if D.C.get(tgt, {}).get("status") != "ops":
                        probs.append(f"❌ {slug}: מוחלף ע\"י {tgt} שאינו כלל תפעולי במיפוי")
                elif i not in LR.LESSONS:
                    probs.append(f"❌ {slug}: מוחלף ע\"י {i} שלא קיים")
        elif st == "ops":
            if f"`{slug}`" not in ops_block:
                probs.append(f"❌ {slug}: כלל תפעולי שאין לו שורה בסקיל (האוכף חסר)")
        else:
            probs.append(f"❌ {slug}: status לא מוכר {st}")
    lr_ok, lr_probs = LR.audit()
    probs += [p for p in lr_probs if p.startswith("❌")]
    return (not any(p.startswith("❌") for p in probs)), probs


def ops_table() -> str:
    rows = [f"| `{s}` | {r['rule']} |" for s, r in sorted(D.C.items()) if r["status"] == "ops"]
    return (OPS_HEADER + "\n\nכללים לסוכן שאינם קוד — כל שורה נבדקת ב-`tools/lessons_canon.py --audit`. "
            "מקורם בקבצי ה-feedback של זיכרון הפרויקט; הלקחים שנאכפים בקוד חיים ב-`lesson_registry`.\n\n"
            "| slug | הכלל |\n|---|---|\n" + "\n".join(rows) + "\n")


def render() -> str:
    by_layer: dict[str, list] = {}
    for lid, rec in LR.LESSONS.items():
        by_layer.setdefault(rec["layer"], []).append((lid, rec))
    back: dict[str, list] = {}
    for slug, r in D.C.items():
        for i in r["ids"]:
            back.setdefault(i, []).append((slug, r["status"]))
    n = {k: sum(1 for r in D.C.values() if r["status"] == k) for k in ("L", "superseded", "ops")}
    debts = [(s, r["debt"]) for s, r in sorted(D.C.items()) if r.get("debt")]
    out = ["# קנון הלקחים — מערכת עריכת הסושיאל",
           "",
           "> **נגזר אוטומטית** מ-`tools/lesson_registry.py` + `tools/lessons_canon_data.py` "
           "(`python3 tools/lessons_canon.py --render`). לא לערוך ידנית.",
           "",
           f"**{len(LR.LESSONS)} לקחים אכופים** · {len(D.C)} קבצי feedback ממופים: "
           f"{n['L']} מכוסים בלקח · {n['superseded']} הוחלפו · {n['ops']} כללי תפעול (בסקיל).",
           ""]
    if debts:
        out += ["## חובות גלויים (לקח קיים, אכיפה חלקית)", ""]
        out += [f"- `{s}` — {d}" for s, d in debts]
        out.append("")
    for layer in sorted(by_layer):
        out += [f"## {layer}", ""]
        for lid, rec in sorted(by_layer[layer]):
            enf = ", ".join(
                (e.get("file") or e.get("gate") or "").split("/")[-1] + (f" ({e['kind']})")
                for e in rec["enforced_by"])
            src = ", ".join(f"{s}" + (" ⟲" if st == "superseded" else "") for s, st in back.get(lid, []))
            out.append(f"- **{lid}** — {rec['lesson']}")
            out.append(f"  - אוכפים: {enf}")
            if src:
                out.append(f"  - מקורות בזיכרון: {src}")
        out.append("")
    out += ["## הוחלפו (היסטוריה — לא ליישם)", ""]
    out += [f"- `{s}` → {', '.join(r['ids'])}" for s, r in sorted(D.C.items()) if r["status"] == "superseded"]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--ops-table", action="store_true")
    a = ap.parse_args()
    if a.ops_table:
        print(ops_table()); return 0
    if a.render:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(render(), encoding="utf-8")
        print(f"✅ נכתב {OUT}"); return 0
    ok, probs = audit()
    for p in probs:
        print(p)
    print(f"{'✅' if ok else '❌'} קנון לקחים: {len(D.C)} קבצי feedback ממופים · "
          f"{len(LR.LESSONS)} לקחים · {sum(1 for p in probs if p.startswith('❌'))} בעיות")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
