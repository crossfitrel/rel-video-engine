#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edl_utils — לוגיקת EDL משותפת (הוצא מ-review-app/server.py כדי שיהיה ניתן
לבדיקה ב-unit tests ולשימוש מה-CLI). ההתנהגות זהה 1:1 לגרסת v6.1.
"""


MIN_KEEP_GAP = 0.04  # כל רווח בין שני cuts קטן מזה לא שורד כ-keep segment עצמאי (למטה)


def derive_keep(total, cuts, hook_move):
    """active cuts (זמן מקורי) → keep_segments; hook_move מזיז טווח לפתיחה.

    תיקון 23.7.26 (הראל): סף המיזוג בין שני cuts סמוכים חייב להיות >= MIN_KEEP_GAP
    (סף ה"בליעה" למטה) — אחרת שני cuts במרחק 0.02-0.04ש לא התמזגו, אבל ה-sliver
    שנשאר ביניהם *כן* נבלע כ-keep קטן מדי → "קאט רפאים" לא מתוכנן בדיוק בגבול הזה,
    שנראה כקפיצת-פריים/מאית-שנייה בווידאו הסופי. שני הספים משתמשים עכשיו באותו קבוע
    כדי שלעולם לא יישאר sliver יתום — הוא תמיד נבלע לתוך ה-cut שמסביבו, לא נופל בין הכיסאות.
    """
    act = sorted([c for c in cuts if c.get("active")], key=lambda c: c["start"])
    merged = []
    for c in act:
        if merged and c["start"] <= merged[-1]["end"] + MIN_KEEP_GAP:
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
        else:
            merged.append({"start": max(0.0, c["start"]), "end": min(total, c["end"])})
    keep, pos = [], 0.0
    for c in merged:
        if c["start"] > pos + MIN_KEEP_GAP:
            keep.append({"start": round(pos, 3), "end": round(c["start"], 3)})
        pos = max(pos, c["end"])
    if pos < total - MIN_KEEP_GAP:
        keep.append({"start": round(pos, 3), "end": round(total, 3)})
    if hook_move and hook_move.get("start") is not None:
        hs, he = float(hook_move["start"]), float(hook_move["end"])
        front, rest = [], []
        for k in keep:
            s, e = k["start"], k["end"]
            inter = (max(s, hs), min(e, he))
            if inter[0] < inter[1] - 0.04:
                if s < inter[0] - 0.04:
                    rest.append({"start": s, "end": round(inter[0], 3)})
                front.append({"start": round(inter[0], 3), "end": round(inter[1], 3)})
                if e > inter[1] + 0.04:
                    rest.append({"start": round(inter[1], 3), "end": e})
            else:
                rest.append(k)
        keep = front + rest
    return keep


def cuts_diff(cuts_a, cuts_b, eps=0.05):
    """השוואת שתי רשימות cuts: added / removed / changed (לפי חפיפת גבולות)."""
    def key(c):
        return (round(c.get("start", 0), 2), round(c.get("end", 0), 2))

    def active(cs):
        return [c for c in (cs or []) if c.get("active")]

    a, b = active(cuts_a), active(cuts_b)
    added, removed, changed = [], [], []
    used_a = set()
    for cb in b:
        match = None
        for i, ca in enumerate(a):
            if i in used_a:
                continue
            if abs(ca["start"] - cb["start"]) <= eps and abs(ca["end"] - cb["end"]) <= eps:
                match = i
                break
        if match is None:
            # גבול קרוב אבל שונה = changed
            for i, ca in enumerate(a):
                if i in used_a:
                    continue
                overlap = min(ca["end"], cb["end"]) - max(ca["start"], cb["start"])
                if overlap > 0:
                    match = i
                    changed.append({"from": {"start": ca["start"], "end": ca["end"]},
                                    "to": {"start": cb["start"], "end": cb["end"]}})
                    break
            if match is None:
                added.append({"start": cb["start"], "end": cb["end"],
                              "reason": cb.get("reason", "")})
        if match is not None:
            used_a.add(match)
    for i, ca in enumerate(a):
        if i not in used_a:
            removed.append({"start": ca["start"], "end": ca["end"],
                            "reason": ca.get("reason", "")})
    return {"added": added, "removed": removed, "changed": changed}


def edl_change_summary(edl_a, edl_b):
    """סיכום שינוי בין שני snapshots של edl: דלתת משך + שינויי cuts."""
    ka = float(edl_a.get("kept_dur") or 0)
    kb = float(edl_b.get("kept_dur") or 0)
    diff = cuts_diff((edl_a.get("review") or {}).get("cuts"),
                     (edl_b.get("review") or {}).get("cuts"))
    return {
        "kept_dur_from": ka, "kept_dur_to": kb,
        "kept_dur_delta": round(kb - ka, 2),
        "cuts_added": len(diff["added"]), "cuts_removed": len(diff["removed"]),
        "cuts_changed": len(diff["changed"]), "detail": diff,
        "hook_move_from": (edl_a.get("review") or {}).get("hook_move"),
        "hook_move_to": (edl_b.get("review") or {}).get("hook_move"),
    }


def map_words_to_keeps(words, keeps, min_overlap=0.5):
    """v7.9 — ממפה מילים מציר המקור (INPUT) לציר החתוך (EXPORT) לפי keep_segments.

    למה זה קיים: עד v7.8 הפייפליין הריץ Whisper **שוב** על ה-EXPORT החתוך. זה גם
    יקר (20-60ש) וגם מסוכן — נמדד 25.7.26 על "ניפוץ מיתוסים": התמלול על ה-INPUT
    היה מושלם, אבל הריצה השנייה על אותו תוכן חתוך **השמיטה משפט שלם**
    ("ותכלס, זה גם פשוט מרגיש טוב...") והכתוביות איבדו 3.3 שניות של דיבור.
    החיתוך הוא טרנספורמציה ידועה ודטרמיניסטית — אין שום סיבה לשאול מודל שוב.

    מילה שנופלת כולה בתוך קטע שנחתך — יורדת. מילה שנחתכת חלקית נשמרת רק אם
    נותר ממנה `min_overlap` (ברירת מחדל 50%), עם זמנים מקוצצים.
    מחזיר (words_mapped, stats).
    """
    # ⚠️ **בלי מיון** — הסדר של keep_segments הוא סדר ההרכבה בפועל ב-edl_cut.
    # מרגע ש-v7.9 מזיז את פתיח-הפורמט למקומו הנכון, הרשימה כבר לא ממוינת לפי זמן,
    # ומיון כאן היה מחשב offsets לפי הציר המקורי ⇒ כל הכתוביות מוסטות.
    ks = [{"start": float(k["start"]), "end": float(k["end"])} for k in keeps]
    # offset מצטבר לכל keep: כמה זמן קדם לו בציר הפלט
    acc, offs = 0.0, []
    for k in ks:
        offs.append(acc)
        acc += k["end"] - k["start"]
    out, dropped, clipped = [], 0, 0
    for w in words:
        ws, we = float(w["start"]), float(w["end"])
        dur = max(1e-6, we - ws)
        best = None
        for k, off in zip(ks, offs):
            ov_s, ov_e = max(ws, k["start"]), min(we, k["end"])
            if ov_e - ov_s <= 0:
                continue
            if best is None or (ov_e - ov_s) > (best[1] - best[0]):
                best = (ov_s, ov_e, k, off)
        if best is None:
            dropped += 1
            continue
        ov_s, ov_e, k, off = best
        if (ov_e - ov_s) / dur < min_overlap:
            dropped += 1
            continue
        if (ov_e - ov_s) < dur - 1e-3:
            clipped += 1
        out.append({**w,
                    "start": round(off + (ov_s - k["start"]), 3),
                    "end": round(off + (ov_e - k["start"]), 3)})
    # אחרי מיפוי — סדר המילים הוא סדר ה**פלט**, לא סדר המקור. כשמזיזים קטע
    # (פתיח-פורמט) הקטע שהיה בסוף מנוגן באמצע, ולכן חייבים למיין לפי הזמן החדש
    # לפני אכיפת המונוטוניות. בלי זה הכתוביות של הקטע שהוזז נדחסות למאיות שנייה.
    out.sort(key=lambda w: (w["start"], w["end"]))
    # מונוטוניות (הגנה מפני חפיפות קצה)
    for i in range(1, len(out)):
        if out[i]["start"] <= out[i - 1]["start"]:
            out[i]["start"] = round(out[i - 1]["start"] + 0.02, 3)
        if out[i]["end"] < out[i]["start"] + 0.08:
            out[i]["end"] = round(out[i]["start"] + 0.12, 3)
    return out, {"in": len(words), "out": len(out), "dropped": dropped, "clipped": clipped}
