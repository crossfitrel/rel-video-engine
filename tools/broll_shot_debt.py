#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_shot_debt — מה שהמערכת **מציעה במקום** לחסום.

שער שאומר רק "לא" לא סיים את העבודה. שלושה מקורות במערכת כבר יודעים מה
חסר, ואף אחד מהם לא הגיע לאדם שמצלם:

  1. `broll_plan.shot_list` — משפט שלא נמצא לו עוגן, עם הציטוט.
     (נמדד באופן-ג'ים: 6 חובות — אוזניות · שעות · תנאי ביטול · מחיר)
  2. `broll_sequence_report.shot_debt` — הרצף לא נקרא טוב.
  3. **הבריכה עצמה** — הליקוי החמור ביותר, וזה שאף שער לא יכול לתקן:
     נמדד 31.7.26 על בריכת האופן-ג'ים: `medium` 30 · `close` 1 · **`wide` 0**.
     שער חוסם כאן היה מפיל כל סרטון המרה, כי אין מה לבחור.

הפלט הוא פריטי צילום — עם הנימוק ועם הסרטון שמהם נולדו — שנכנסים לבורד
הסושיאל. **דיווח בלבד; לא כותב ל-Monday.** הכתיבה נעשית בשכבה שיש לה
הרשאות, כדי שהכלי הזה יישאר ניתן להרצה בלי מפתחות.

    python3 broll_shot_debt.py --workdir W [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# גודל שוט שכל בריכה בריאה חייבת להחזיק. הרשימה קצרה בכוונה — היא נגזרת
# מדקדוק העריכה (רחב→בינוני→פרט) ולא מטקסונומיה שאפתנית.
NEEDED_SHOTS = {
    "wide": "שוט רחב של הרחבה — הצופה הקר צריך לראות **איפה** הוא, "
            "לפני שהוא רואה מה קורה שם",
    "close": "שוט פרט — ידיים על המוט, משקולת, ציוד. אין לאן להתקרב "
             "אחרי רחב ובינוני",
}
MIN_SHARE = 0.10   # פחות מ-10% מהבריכה בגודל שוט = חוסר, לא מקריות


def pool_gaps(shortlist: dict) -> list[dict]:
    """מה חסר **בבריכה**, לא בסרטון. זה החוב שאף עריכה לא תפתור."""
    try:
        import broll_vision_model as VM
    except Exception:                                   # pragma: no cover
        return []
    paths = (shortlist or {}).get("_paths") or {}
    seen, n_scanned = Counter(), 0
    for p in paths.values():
        try:
            v = VM.lookup(p)
        except OSError:
            v = None
        if v and v.get("shot"):
            seen[v["shot"]] += 1
            n_scanned += 1
    if n_scanned < 5:            # בריכה קטנה מדי מכדי להסיק ממנה חוסר
        return []
    out = []
    for shot, why in NEEDED_SHOTS.items():
        n = seen.get(shot, 0)
        if n / n_scanned < MIN_SHARE:
            out.append({
                "kind": "pool", "need": shot, "why": why,
                "evidence": f"{n} מתוך {n_scanned} קליפים בבריכה הם {shot} "
                            f"({n / n_scanned:.0%}) · ההתפלגות: "
                            + " · ".join(f"{k} {v}" for k, v in seen.most_common()),
                "severity": "high" if n == 0 else "medium"})
    return out


def collect(workdir: str | Path) -> dict:
    W = Path(workdir).expanduser()

    def j(name, default=None):
        p = W / name
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:                               # noqa: BLE001
            return default

    plan = j("broll_plan.json", {}) or {}
    seq = j("broll_sequence_report.json", {}) or {}
    sl = j("broll_shortlist.json", {}) or {}
    manifest = j("project_manifest.json", {}) or {}
    # שם קריא לאדם שמצלם. `project_id` הוא זהות המערכת ולא כותרת —
    # פריט בורד בשם prj_942bdcbb127f אינו אומר לאף אחד מאיזה סרטון הוא בא.
    project = manifest.get("name") or manifest.get("title") or W.name
    dept = manifest.get("dept") or ""
    monday_item = manifest.get("monday_item_id")

    sentence_debt = [{
        "kind": "sentence", "need": "illustration",
        "at": s.get("at"), "sentence": s.get("sentence"),
        "why": s.get("why_no_clip"), "severity": "medium",
    } for s in (plan.get("shot_list") or [])]

    seq_debt = [dict(d, kind="sequence", severity="low")
                for d in (seq.get("shot_debt") or [])
                if d.get("need") == "variety"]
    # `wide`/`detail` מדוח הרצף מתארים את **הסרטון**; החוב האמיתי הוא של
    # הבריכה, והוא נמדד ישירות למטה. בלי ההפרדה הזאת אותו חוב מדווח פעמיים.

    return {"project": project, "dept": dept, "monday_item_id": monday_item,
            "workdir": str(W),
            "pool": pool_gaps(sl), "sentences": sentence_debt,
            "sequence": seq_debt,
            "n_bed": seq.get("n_bed"), "pool_size": sl.get("pool_size")}


def board_items(debt: dict) -> list[dict]:
    """פריטי צילום מוכנים לבורד הסושיאל — שם, מה דרוש, מטרה.

    פריט **אחד** לכל חוב-בריכה (חוצה-סרטונים, חי לאורך זמן), ופריט אחד
    מרוכז לכל סרטון. שישה פריטים נפרדים לסרטון אחד הם רעש, לא רשימה.
    """
    items = []
    for g in debt["pool"]:
        items.append({
            "name": f"חוב צילום — {NEEDED_SHOTS[g['need']].split('—')[0].strip()}",
            "need": g["need"], "severity": g["severity"],
            "what": f"{g['why']}\n\nנמדד: {g['evidence']}",
            "goal": "בלי זה כל מצע בירולים במועדון ייראה אותו דבר — "
                    "אין ממה לבנות מבנה חזותי (רחב→בינוני→פרט)",
            "source": debt["project"]})
    if debt["sentences"]:
        lines = [f"• {s['sentence']}\n  ↳ {s['why']}" for s in debt["sentences"]]
        items.append({
            "name": f"חוב צילום — {debt['project']}",
            "need": "illustration", "severity": "medium",
            "what": "משפטים שנשארו בלי שוט שמאייר אותם:\n\n" + "\n".join(lines),
            "goal": "כל אחד מאלה הוא משפט שהצופה שומע ולא רואה. "
                    "צילום שלהם פותר אותם גם בסרטונים הבאים",
            "source": debt["project"]})
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--json", dest="out_json")
    a = ap.parse_args()
    debt = collect(a.workdir)
    debt["board_items"] = board_items(debt)
    out = Path(a.out_json) if a.out_json else (Path(a.workdir).expanduser()
                                               / "shot_debt.json")
    out.write_text(json.dumps(debt, ensure_ascii=False, indent=1), encoding="utf-8")

    n = len(debt["board_items"])
    print(f"📸 חוב צילום — {debt['project']}: {n} פריטים לבורד "
          f"(בריכה {len(debt['pool'])} · משפטים {len(debt['sentences'])} · "
          f"רצף {len(debt['sequence'])})")
    for it in debt["board_items"]:
        print(f"\n▸ {it['name']}  [{it['severity']}]")
        for ln in it["what"].splitlines()[:6]:
            print(f"   {ln}")
    print(f"\n📄 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
