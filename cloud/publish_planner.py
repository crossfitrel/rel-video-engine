#!/usr/bin/env python3
"""publish_planner — קובע תאריך ושעת פרסום לריל כבר בשלב ההפקה (L163, הראל 1.11.26).

"המטרה שאתה תסדר את התאריכי פרסום לבד, בסדר בריא והגיוני עם פריסה נכונה, כבר בשלב שבו אתה מייצר את התכנים."
מחליף את הכלל הישן "לא בוחרים תאריך לבד". דטרמיניסטי, בלי מודל:
  · פינה קבועה ⇒ אותו טווח ימים בכל חודש (נמדד 11.9.26): בריאות 1-5 · טיפ אחד 9-13 · דקה להורים 17-20 · על הלוח 19-25 · מאסל מן 1-5 ב-22:00
  · שעה: פינות ותוכן מועדון 19:00, מאסל מן 22:00
  · אף פעם לא 7.10 · לא היום ולא מחר (אופק קצר) · עד 35 יום קדימה
  · יום שכבר יש בו פרסום ערב (15:00 ואילך, גאנט או Metricool) תפוס; פרסום בוקר (פודקאסט/קרוסלה 10:00) לא חוסם ערב
  · שישי רק אם אין יום אחר בטווח
  · בתוך הטווח בוחרים את היום הכי רחוק מפרסומי ערב קיימים
"""
from __future__ import annotations
import datetime as dt

CORNERS = [  # (קידומת בכותרת, ימי חודש, שעה)
    ("בריאות לחיים האמיתיים", (1, 5), "19:00"),
    ("טיפ אחד", (9, 13), "19:00"),
    ("דקה להורים", (17, 20), "19:00"),
    ("על הלוח", (19, 25), "19:00"),
    ("מאסל מן", (1, 5), "22:00"),
    ("המאסל מן", (1, 5), "22:00"),
]
BLACKOUT = {(10, 7)}          # 7.10 בכל שנה, בכל מותג
MIN_LEAD_DAYS = 2
HORIZON_DAYS = 35
DEFAULT_TIME = "19:00"


def corner_for(title: str):
    t = (title or "").strip()
    for prefix, rng, hhmm in CORNERS:
        if t.startswith(prefix):
            return prefix, rng, hhmm
    return None, None, DEFAULT_TIME


def plan(title: str, taken: set[dt.date], today: dt.date) -> tuple[dt.date, str, str]:
    """מחזיר (תאריך, שעה מקומית HH:MM, נימוק)."""
    _, rng, hhmm = corner_for(title)
    start = today + dt.timedelta(days=MIN_LEAD_DAYS)
    days = [start + dt.timedelta(days=i) for i in range(HORIZON_DAYS - MIN_LEAD_DAYS + 1)]
    days = [d for d in days if (d.month, d.day) not in BLACKOUT]
    if rng:
        cand = [d for d in days if rng[0] <= d.day <= rng[1]]
        why = f"פינה קבועה, טווח {rng[0]}-{rng[1]} בחודש"
    else:
        cand = days
        why = "תוכן לא-פינתי, היום הפנוי הרחוק ביותר מפרסומים קיימים"
    def ok(pool):
        return [d for d in pool if d not in taken and d.weekday() != 4] or [d for d in pool if d not in taken]
    free = ok(cand) or ok(days) or days

    def gap(d):
        return min((abs((d - t).days) for t in taken), default=99)
    # הכי רחוק מפרסומים קיימים; בשוויון, המוקדם (שהתוכן לא יתיישן)
    best = sorted(free, key=lambda d: (-min(gap(d), 3), d))[0]
    return best, hhmm, why


def to_monday_utc(d: dt.date, hhmm: str) -> tuple[str, str]:
    from zoneinfo import ZoneInfo
    h, m = map(int, hhmm.split(":"))
    local = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo("Asia/Jerusalem"))
    u = local.astimezone(dt.timezone.utc)
    return u.strftime("%Y-%m-%d"), u.strftime("%H:%M:%S")
