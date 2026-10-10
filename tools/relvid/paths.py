#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relvid.paths — מקור אמת אחד לנתיב תיקיית העבודה (v8.6, P0-11).

שורש הבעיה: `_work` ישבה בתוך iCloud Drive (11GB, 38 פרויקטים). שלוש תוצאות
נמדדו: (1) `cleanup_work.py` מזהיר במפורש על eviction באמצע גימור — קובץ ביניים
שאפל מחליטה להעלות ולפנות בזמן שה-ffmpeg כותב אליו; (2) כל טעינת דף באפליקציה
סורקת ~38 תיקיות ×4 קבצי JSON על filesystem מסונכרן; (3) 100-200 קבצי PNG של
כתוביות נכתבים ונמחקים בכל גימור — כלומר סנכרון מיותר של אלפי קבצים.

הפתרון: הביניים עוברים לדיסק המקומי; התוצרים הסופיים ממשיכים להיתייק ל-iCloud
דרך `resolve_output_path` בדיוק כמו קודם. שום דבר שהראל צריך לפתוח מהטלפון לא
זז — רק תיקיית העבודה.

סדר הכרעה (הראשון שקיים מנצח):
  1. משתנה סביבה `REL_WORK_ROOT` — לבדיקות ולהרצה חד-פעמית על נתיב אחר.
  2. `tools/paths.json` → `{"work_root": "~/rel-video-work"}` (~ מורחב).
  3. ברירת מחדל היסטורית: `<SYSDIR>/_work` — כלומר בלי paths.json שום דבר
     לא משתנה, וזו הסיבה שאפשר להטמיע את המודול הזה בלי מיגרציה בכלל.

הנתיב נפתר בכל קריאה (בלי cache) כדי שבדיקות שמזריקות REL_WORK_ROOT יעבדו.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
TOOLS = PKG_DIR.parent
SYSDIR = TOOLS.parent
CONFIG = TOOLS / "paths.json"
LEGACY_WORK = SYSDIR / "_work"


def _from_config():
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return None
    v = (cfg or {}).get("work_root")
    if not v:
        return None
    p = Path(str(v)).expanduser()
    return p if p.is_absolute() else (SYSDIR / p)


def work_root(create: bool = False) -> Path:
    """תיקיית העבודה הפעילה."""
    env = os.environ.get("REL_WORK_ROOT")
    p = Path(env).expanduser() if env else (_from_config() or LEGACY_WORK)
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def index_dir() -> Path:
    return work_root() / ".index"


def trash_dir() -> Path:
    return work_root() / "_trash"


def is_on_icloud(p: Path | None = None) -> bool:
    """iCloud Drive על מק תמיד תחת ~/Library/Mobile Documents."""
    p = p or work_root()
    return "Mobile Documents" in str(p)


def describe() -> dict:
    p = work_root()
    return {"work_root": str(p), "exists": p.is_dir(), "on_icloud": is_on_icloud(p),
            "source": ("env" if os.environ.get("REL_WORK_ROOT")
                       else ("paths.json" if _from_config() else "default")),
            "config_file": str(CONFIG), "legacy": str(LEGACY_WORK),
            "legacy_still_present": LEGACY_WORK.is_dir() and LEGACY_WORK != p}


if __name__ == "__main__":
    print(json.dumps(describe(), ensure_ascii=False, indent=1))
