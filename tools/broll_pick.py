#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_pick.py — בחירת בירולים דטרמיניסטית מהקטלוג + תכנון מיקומי שיבוץ.

חוקים קשיחים (קאנון R.E.L):
- **v7.8: בירול מותר בכל סוגי התוכן** (הוסרה ההגבלה ל-conversion). במקומה שער
  רלוונטיות `--min-relevance` — אין קליפ שקשור לנושא ⇒ אין בירול, וזה תקין.
- קליפי Throwdown נכנסים רק לתוכן Throwdown (28 מתוך 59 בקטלוג — היו מציפים הכול).
- קהל דוספיט → רק בירולי דוספיט (ולפי מגדר אם צוין).
- שיבוץ: מתחיל אחרי סוף המשפט הראשון (+0.2ש); כל קליפ 2.5-3.5ש; לא מכסה CTA (8ש אחרונות).
- rotation: קנס על בירול שהיה בשימוש לאחרונה (usage.json).

הרצה:
  python3 broll_pick.py --topic "כוח ומסגרת" --content-type conversion --n 2 \
      [--sentences sentences.json] [--video-dur 58] [--audience דוספיט] [--dept "קרוספיט אריאל"] \
      [--json broll_plan.json] [--commit]
sentences.json = [{"start":..,"end":..,"text":".."}] (מ-edl_build.py) — אופציונלי.
פלט broll_plan.json תואם ל-animation_overlay.py (--overlay FILE START END) ולפרומפט ה-agent.
"""
import argparse, json, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent

_VISION_CACHE: dict = {}


def _vision_of(item) -> dict:
    """מה **רואים** בקליפ, מפאס הראייה. `{}` כשאין ראיה — לא ניחוש.

    ‏`clip_key` מפתחו file|mtime|size ⇒ אותו קובץ מחזיר אותה תשובה בין
    ריצות, ולכן זה בטוח ל-payload של פאס. קליפ שנסרק בפעם הראשונה **כן**
    מזיז את ה-digest — וזה נכון: הקלט לתוכנית באמת השתנה.
    """
    p = item.get("path")
    if not p:
        return {}
    if p not in _VISION_CACHE:
        try:
            import broll_vision_model as _VM
            _VISION_CACHE[p] = _VM.lookup(p) or {}
        except Exception:                              # noqa: BLE001
            _VISION_CACHE[p] = {}
    return _VISION_CACHE[p]

def _portable(p):
    """L158 (1.11.26): catalog_path/usage_path בקונפיג הם נתיבי מק (/Users/hayon/...); ב-runner ממפים
    לפי המקטע שאחרי 'Social Video Editing System' או העוגן 'בירולים' מתחת לשורש הריפו."""
    P = Path(p)
    if P.exists():
        return P
    parts = P.parts
    for anchor in ("Social Video Editing System", "rel-video-cloud"):
        if anchor in parts:
            cand = HERE.parent.joinpath(*parts[parts.index(anchor) + 1:])
            if cand.exists():
                return cand
    if "בירולים" in parts:
        cand = HERE.parent.joinpath(*parts[parts.index("בירולים"):])
        if cand.exists():
            return cand
    return P

def load(p):
    return json.loads(_portable(p).read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# v8.0 — הפרדת מחלקות + דוקטרינת צפיפות (הראל 25.7.26)
# ─────────────────────────────────────────────────────────────────────────────
# "שלא יהיה בירולים של הראל במועדון אלא אם ביקשתי אחרת. וגם להיפך."
# הספרייה נגזרת מהנתיב בתוך בירולים/<ספרייה>/<קטגוריה>/קובץ.mp4
LIBRARIES = ("הראל חיון", "קרוספיט אריאל", "כללי-ומגוון")
LIB_PERSONAL, LIB_CLUB, LIB_GENERAL = LIBRARIES

def library_of(path):
    """שם הספרייה שאליה שייך הקליפ, או '' לקליפים ותיקים שמחוץ למבנה."""
    parts = str(path).replace("\\", "/").split("/")
    for i, p in enumerate(parts):
        if p == "בירולים" and i + 1 < len(parts):
            nxt = parts[i + 1]
            return nxt if nxt in LIBRARIES else ""
    return ""

# מחלקה → אילו ספריות מותרות. כללי-ומגוון (טבע/אוכל/כלבים) ניטרלי ומותר לשתיהן.
# '' (ותיקים, לפני הפיצול) נשארים זמינים לתוכן המועדון בלבד.
DEPT_LIBRARIES = {
    "הראל חיון":      [LIB_PERSONAL, LIB_GENERAL],
    "קרוספיט אריאל":  [LIB_CLUB, LIB_GENERAL, ""],
    "שיקום בתנועה":   [LIB_CLUB, LIB_GENERAL, ""],
    "REL Performance": [LIB_CLUB, LIB_GENERAL, ""],
    "ילדים":          [LIB_CLUB, LIB_GENERAL, ""],
    "קבוצות נפרדות":  [LIB_CLUB, LIB_GENERAL, ""],
    "REL Throwdown":  [LIB_CLUB, LIB_GENERAL, ""],
}
DEFAULT_LIBRARIES = [LIB_CLUB, LIB_GENERAL, ""]

# ─── v8.4 (הראל 26.7.26) — סימן-מתאמן מפורש ─────────────────────────────────
# "אל תשלב בירולים אישיים שלי מתאמן, אלא של מתאמנים מהמועדון רק."
# שורש התקלה החוזרת: הפילטר personal_tags נשען על **תיוג** של הקליפ, והתיוג
# חלקי — 117 קליפים מתויגים 'הראל-חיון' אבל בפועל יש עוד קליפים שלו בספריית
# המועדון בלי התג. כל פעם שנבחר "מרים סולו לא מזוהה" יש סיכוי טוב שזה הראל,
# ואז חוזרת בדיוק אותה הערה. לכן ההיגיון התהפך מ-blacklist ל-whitelist:
# בתוכן מועדון נכנס רק קליפ שיש בו **עדות חיובית** שמדובר במתאמנים
# (מתאמן/מתאמנת/קבוצה/שיעור/קהילה/נשים/גברים/ילדים). קליפ סולו אנונימי בלי
# עדות כזו לא נכנס — גם אם לא הוכח שהוא הראל. נמדד על הקטלוג: 198 מתוך 271
# קליפים במאגר המועדון עוברים ⇒ המאגר לא מתרוקן.
MEMBER_TAGS = {"מתאמן", "מתאמנת", "מתאמנים", "קבוצה", "שיעור",
               "קהילה", "נשים", "גברים", "ילדים"}

# v8.4 — זנב-ביטחון: לא מתכננים חלון בירול עד הפריים האחרון ממש של ה-footage.
# ב-30fps הפריים האחרון של קליפ 3.6ש מוצג ב-3.567, ו-ffmpeg מגיע ל-EOF בקלט
# המשני לפני סוף החלון. 0.08ש ≈ 2.4 פריימים — מרווח שמבטיח שתמיד יש פריים
# בירול להציג בכל נקודה בחלון. (השכבה השנייה היא eof_action=repeat ב-
# animation_overlay; שתיהן יחד = אפס חשיפת-פנים בתפר.)
SAFE_TAIL = 0.08

# דוקטרינת צפיפות לפי סוג תוכן (הראל 25.7.26):
#   המרה  = "אחרי ההוק ועד ה-CTA יש בירולים" — מצע כמעט-רציף, קליפ אחרי קליפ.
#   חיבור/ערך = בירול לפי הצורך ולפי התמלול — נקודתי, רק כשיש התאמה אמיתית.
DENSITY_PROFILES = {
    "conversion":  {"n": 8, "gap": 0.0, "clip_len": 2.8, "min_relevance": 1.0,
                    "rel_ratio": 0.25, "anchor": "flow", "fill": True, "bridge_gap": 2.5,
                    "continuous": True, "require_member": True, "require_verified": True,
                    "_doc": "מצע בירולים **רציף לגמרי** מסוף ההוק ועד שמירת ה-CTA "
                            "(הראל 26.7.26: 'בין בירול לבירול לא צריך לראות אותי, "
                            "זה צריך להיות מעבר רציף ביניהם'). gap=0 בכוונה: כל "
                            "קליפ מתחיל בדיוק בסוף הקודם ⇒ אפס פריימים של פנים "
                            "ביניהם ⇒ animation_overlay מזהה סמיכות ועושה קאט חד "
                            "בלי fade. require_member: בתוכן מועדון נכנסים רק "
                            "קליפים עם סימן-מתאמן מפורש (ראה MEMBER_TAGS)"},
    "throwdown_value": {"n": 6, "gap": 0.0, "clip_len": 3.0, "min_relevance": 1.0,
                    "rel_ratio": 0.3, "anchor": "flow", "fill": True, "bridge_gap": 2.0,
                    "continuous": True},
    "value":       {"n": 2, "gap": 8.0, "clip_len": 3.0, "min_relevance": 2.0,
                    "rel_ratio": 0.5, "anchor": "transcript",
                    "_doc": "נקודתי — נצמד למשפט שהכי מתאים לקליפ"},
    "community":   {"n": 2, "gap": 8.0, "clip_len": 3.0, "min_relevance": 2.0,
                    "rel_ratio": 0.5, "anchor": "transcript"},
    "testimonial": {"n": 1, "gap": 10.0, "clip_len": 3.0, "min_relevance": 2.5,
                    "rel_ratio": 0.5, "anchor": "transcript"},
    "rehab":       {"n": 2, "gap": 7.0, "clip_len": 3.0, "min_relevance": 2.0,
                    "rel_ratio": 0.5, "anchor": "transcript"},
    "kids":        {"n": 3, "gap": 5.0, "clip_len": 2.8, "min_relevance": 1.5,
                    "rel_ratio": 0.4, "anchor": "transcript"},
    "dossfit":     {"n": 3, "gap": 5.0, "clip_len": 2.8, "min_relevance": 1.5,
                    "rel_ratio": 0.4, "anchor": "transcript"},
    "muscle_man":  {"n": 3, "gap": 4.0, "clip_len": 2.8, "min_relevance": 1.5,
                    "rel_ratio": 0.4, "anchor": "flow"},
}
DEFAULT_PROFILE = {"n": 2, "gap": 6.0, "clip_len": 3.0, "min_relevance": 2.0,
                   "rel_ratio": 0.5, "anchor": "transcript"}

def clip_label(it):
    """תווית קריאה-לאדם לקליפ. **לא** `desc` — נמדד 30.7.26 שהשדה הזה מכיל
    שברי תאריך ('-08-22') בגלל פיצול שם-הקובץ, ולכן כל ניקוד שנשען עליו שקול
    לרעש. השם הקנוני הוא שם הקובץ בלי הקידומת 'בירול' ובלי התאריך."""
    lab = re.sub(r"^\s*בירול\s*-\s*", "", it.get("file", ""))
    lab = re.sub(r"\.\w+$", "", lab)
    lab = re.sub(r"\s*-?\s*20\d\d-\d\d-\d\d\s*$", "", lab).strip()
    return lab or it.get("file", "")


# ─── v9.4 — קליפים שאסור להם להיות בירול, לא משנה מה נאמר במשפט ──────────────
# בירול הוא **קאטאווי**: משהו לראות בזמן שממשיכים לשמוע את הדובר. קליפ שיש בו
# אדם מדבר-למצלמה (ראיון/עדות) הוא שוט דיבור שני — הצופה מנסה לקרוא שפתיים,
# מבין שהאודיו לא שייך, ונופל מהסרטון. זה שער קשיח ולא שיפוט של המודל.
NON_BROLL_TAGS = {"interview", "ראיון", "עדות", "talking-head", "מדבר-למצלמה"}


def is_cutaway(it):
    tags = {str(t).strip() for t in (it.get("tags") or [])}
    blob = f"{it.get('file','')} {it.get('category','')} {it.get('event','')}"
    if tags & NON_BROLL_TAGS:
        return False
    return not any(t in blob for t in ("ראיון", "עדות", "interview"))


def sentence_affinity(it, sent_text, smap=None):
    """כמה המשפט הזה 'מבקש' את הקליפ הזה — לשיבוץ לפי התמלול (anchor=transcript).

    v8.1 (הראל 25.7.26): "תפעיל תמיד את הקישור בין מה שנאמר בסרטון למה שצריך
    לראות בויזואל. אני מדבר על זוגיות — תמונה מהחתונה. שני כלבים — תמונה של
    הכלבים. לנהל צוות — כשאני מדבר מול קבוצה. זה צריך להיות ממש היסוד."

    לפני כן ההתאמה הייתה substring בלבד: "זוגיות" תפס כי במקרה זו גם תגית,
    אבל "צוות של מעל 10 עובדים" לא תפס שום דבר כי אין תגית "עובדים" בקטלוג.
    `smap` (sentence_tag_map בקונפיג) הוא גשר סמנטי: מילה בתמליל → תגיות
    בקטלוג. תגית סגולית ששודכה דרך הגשר שווה יותר מהתאמת-מילה מקרית."""
    blob = f"{it['desc']} {it['event']} {' '.join(it['tags'])}"
    words = {w for w in re.split(r"[\s,.\-!?]+", sent_text or "") if len(w) >= 3}
    hits = sum(1 for w in words if w in blob)
    tag_hits = sum(1 for t in it["tags"] if len(t) >= 3 and t in (sent_text or ""))
    aff = hits + 2.0 * tag_hits
    if smap:
        tags = set(it["tags"]) | {it["event"]}
        want = set()
        for key, mapped in smap.items():
            if key in (sent_text or ""):
                want.update(mapped)
        matched = tags & want
        aff += 6.0 * len(matched & SPECIFIC_TAGS) + 3.0 * len(matched - SPECIFIC_TAGS)
    return aff


def pick_by_transcript(items, sentences, smap, usage, now, n, min_aff,
                       dur_cap, cta_guard, clip_len, hook_guard):
    """v8.1 — בחירה שמתחילה מהתמליל, לא מנושא-על של הסרטון.

    שורש הבאג שהראל זיהה: הבחירה דירגה קליפים מול מחרוזת-נושא אחת של כל
    הסרטון, ורק *אחר כך* שיבצה אותם למשפטים. לכן קליפ שהוא התאמה מושלמת
    למשפט אחד ("זוגיות" → חתונה) לא נבחר בכלל — הנושא הגלובלי ("בריאות,
    כושר, עסקים") לא העלה אותו לצמרת. כאן ההיגיון הפוך: עוברים משפט-משפט,
    שואלים "מה צריך לראות כשנאמרות המילים האלה", ולוקחים רק זוגות שעוברים סף.

    מחזיר [(anchor_time, item, affinity)] ממוין לפי זמן."""
    cands = []
    for si, sent in enumerate(sentences):
        if si == 0:                                   # Hook קדוש
            continue
        st = float(sent["start"])
        if st < hook_guard or st > dur_cap - cta_guard - clip_len:
            continue
        for it in items:
            aff = sentence_affinity(it, sent.get("text", ""), smap)
            if aff >= min_aff:
                # שובר-שוויון: usage.json = id → חותמת השימוש האחרון. בהתאמה
                # זהה עדיף הקליפ שלא היה בשימוש הכי הרבה זמן (LRU).
                cands.append((aff, usage.get(it["id"], 0), si, it))
    cands.sort(key=lambda x: (-x[0], x[1]))
    chosen, used_sent, used_desc = [], set(), set()
    for aff, _, si, it in cands:
        if si in used_sent or len(chosen) >= n:
            continue
        base = re.sub(r"\s*\d+$", "", it["desc"]).strip() or it["file"]
        if base in used_desc:
            continue
        used_sent.add(si); used_desc.add(base)
        chosen.append((float(sentences[si]["start"]) + 0.1,
                       dict(it, _relevance=round(aff, 1)), aff))
    chosen.sort(key=lambda x: x[0])
    return chosen

# תגיות סגוליות: תנועה + ציוד. אלה שקובעות אם קליפ *באמת* מתאים לנושא.
SPECIFIC_TAGS = {
    "דדליפט","דדליפט-סומו","דדליפט-קונבנציונלי","בק-סקוואט","פרונט-סקוואט",
    "אוברהד-סקוואט","סקוואט","פרונט-ראק","ניקוי","חטיפה","דחיקה","הרמה-אולימפית",
    "מעל-הראש","קטלבל","סווינג-קטלבל","דמבל","תרסטר","לאנג","וול-בול","כדור-כוח",
    "שק-חול","מזחלת","מתח","מאסל-אפ","רגליים-למוט","טבעות","מקבילים","עמידת-ידיים",
    "טיפוס-חבל","קפיצת-קופסה","ברפי","קפיצה-בחבל","דאבל-אנדרס","חתירה","מכונת-חתירה",
    "אופני-אוויר","ריצה","שכיבות-שמיכה","ליבה","מתיחות","מוביליטי","גומייה",
    "אמבט-קרח","פילאטיס","טיפול","שיקום","אנטומיה","בארבל","ריג","קופסה",
    "פודקאסט","משרד","מול-הלוח","תדריך","ילדים","תחרות","מקצה","חתונה","כלבים",
    "deadlift","sumo-deadlift","back-squat","front-squat","overhead-squat","squat",
    "clean","snatch","press","pull-up","muscle-up","toes-to-bar","rings","dips",
    "handstand","rope-climb","box-jump","burpee","double-unders","row-erg","bike-erg",
    "run","kettlebell","wallball","thruster","barbell","dumbbell","rig",
}

def relevance(it, want_tags, topic_words, dept_tags=frozenset()):
    """v7.8 — **רלוונטיות בלבד**: כמה הקליפ באמת קשור לנושא הסרטון.
    מופרד מציון האיכות/רוטציה כדי שיהיה אפשר לשים עליו סף. בלי ההפרדה,
    קליפ אנכי באורך נוח היה מקבל ציון גבוה גם בלי שום קשר לתוכן — וזה בדיוק
    מה שהופך בירול אוטומטי ל"סתם וידאו באמצע".

    `dept_tags` = בונוס לפי מחלקת הסרטון (dept_tag_map בקונפיג). נמדד 25.7.26:
    סרטון של "שיקום בתנועה" על מתיחות וכאב שרירים בחר קליפי בארבל, בזמן
    שבקטלוג היו 15 קליפי טיפול/שיקום מדויקים. בונוס, לא סינון — סרטון שיקומי
    עדיין יכול להראות אימון, אבל בתיקו הקליפ מהמחלקה עצמה מנצח."""
    tags = set(it["tags"]) | {it["event"]} | set(it.get("audience", []))
    hit = tags & want_tags
    # v8.0 — משקל לפי סגוליות. באג שנמדד 25.7.26: סרטון על "מתח strict" בחר
    # "ברפיז בשיעור" לפני "מתח בריג", כי תגיות גנריות (שיעור/מסגרת/אווירה) +
    # בונוס מחלקה הצטברו ל-14 מול 11. תנועה וציוד = הסיבה שהקליפ מתאים; אווירה
    # וקהילה = רקע. מפרידים ביניהם במשקל, לא בסינון.
    r = 5.0 * len(hit & SPECIFIC_TAGS) + 1.5 * len(hit - SPECIFIC_TAGS)
    dtext = f"{it['desc']} {it['event']} {' '.join(it['tags'])}"
    r += sum(1.0 for w in topic_words if w and w in dtext)
    r += min(4.0, 2.0 * len(tags & set(dept_tags)))  # בונוס מחלקה — עם תקרה
    return r


def score_item(it, want_tags, topic_words, usage, now, dept_tags=frozenset()):
    s = relevance(it, want_tags, topic_words, dept_tags)
    # התאמת משך: אידיאל 2.5-3.5ש (חיתוך "אמצע הקליפ" אפשרי כשארוך יותר)
    if 2.0 <= it["dur"] <= 6.0:
        s += 1.5
    elif it["dur"] > 6.0:
        s += 0.8  # אפשר לחתוך אמצע
    if it.get("vertical"):
        s += 1.0
    # rotation: שימוש אחרון (קנס דועך על פני 6 שבועות)
    last = usage.get(it["id"], 0)
    if last:
        weeks = max(0.0, (now - last) / 604800)
        s -= max(0.0, 4.0 - weeks * 0.7)
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog")
    ap.add_argument("--config", default=str(HERE / "broll-catalog-config.json"))
    ap.add_argument("--topic", default="", help="טקסט חופשי: נושא הסרטון / מילות מפתח")
    ap.add_argument("--content-type", required=True,
                    help="conversion | value | community | testimonial | rehab | dossfit | kids | muscle_man | throwdown_value")
    ap.add_argument("--audience", default="", help="דוספיט / נשים / גברים / ריק")
    ap.add_argument("--dept", default="")
    ap.add_argument("--brand", default="rel", choices=["rel", "personal", "oshia"],
                    help="rel = תוכן מועדון (בירולי הראל מסוננים החוצה, v7.10); "
                         "personal = המותג האישי (בירולי הראל מועדפים)")
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--sentences", help="sentences.json מ-edl_build (לתכנון מיקומים)")
    ap.add_argument("--video-dur", type=float, default=0.0)
    ap.add_argument("--min-clip-len", type=float, default=1.8,
                    help="v8.2 — אורך מינימלי לבירול. מתחת לזה הצופה לא מספיק "
                         "לפענח מה הוא רואה (נמדד: 0.90ש על 'זוגיות' — הבהוב).")
    ap.add_argument("--bridge-gap", type=float, default=1.5,
                    help="v8.2 — חור קטן מזה בין שני בירולים סמוכים מגושר: "
                         "הקליפ הקודם מתארך עד תחילת הבא במקום חזרה קצרה לפנים. "
                         "0 = בלי גישור.")
    ap.add_argument("--min-affinity", type=float, default=3.0,
                    help="v8.1 — סף ההתאמה בין מה שנאמר במשפט למה שנראה בקליפ. "
                         "מתחת לסף לא משבצים בירול על המשפט הזה בכלל — עדיף בלי "
                         "בירול מאשר בירול שלא קשור למילים. 3.0 = לפחות התאמה "
                         "סמנטית אמיתית אחת דרך sentence_tag_map, לא מקריות מילים.")
    ap.add_argument("--cta-guard", type=float, default=8.0, help="שניות סוף בלי בירול (CTA)")
    ap.add_argument("--hook-guard", type=float, default=4.0,
                    help="מינימום שניות פתיחה בלי בירול. v8.0: תמליל עם משפט ראשון "
                         "קטוע (1.4ש) הכניס בירול על ההוק — ההוק קדוש.")
    ap.add_argument("--clip-len", type=float, default=3.0)
    ap.add_argument("--gap", type=float, default=4.0, help="מרווח מינימלי בין בירולים")
    ap.add_argument("--allow-throwdown-value", action="store_true")
    ap.add_argument("--min-relevance", type=float, default=2.0,
                    help="סף רלוונטיות מינימלי לקליפ (v7.8). 0 = כל קליפ מותר (התנהגות "
                         "ישנה, לא מומלץ). 2.0 = ברירת מחדל, כוילה על 6 נושאים אמיתיים: "
                         "1.0 הכניס קליפ 'טיפולים' לסרטון על קפיצת קופסה; 3.0 כבר פסל "
                         "'פגישת יעדים' לסרטון על הצטרפות. אין התאמה ⇒ אין בירול, וזה תקין.")
    ap.add_argument("--rel-ratio", type=float, default=0.5,
                    help="קליפ שני ואילך חייב להגיע לפחות לאחוז הזה מהרלוונטיות של "
                         "הראשון (v7.9, 'הבירול השני לא ברור'). 0 = מבטל.")
    ap.add_argument("--density", default="auto",
                    choices=["auto", "dense", "sparse", "manual"],
                    help="auto (ברירת מחדל) = פרופיל לפי סוג התוכן; dense = מצע בירולים "
                         "רציף; sparse = נקודתי לפי התמלול; manual = מכבד את --n/--gap שנשלחו")
    ap.add_argument("--library", default="auto",
                    help="auto = לפי --dept (הפרדת מחלקות). אפשר גם: 'הראל חיון' / "
                         "'קרוספיט אריאל' / 'כללי-ומגוון' / 'all'")
    ap.add_argument("--allow-private", action="store_true",
                    help="אפשר בירולים פרטיים (בית/חצר/חתונה/כלבים) גם בתוכן מועדון — "
                         "רק בבקשה מפורשת של הראל")
    ap.add_argument("--cross-library", action="store_true",
                    help="ביטול מפורש של הפרדת המחלקות — בירולים אישיים בתוכן מועדוני ולהיפך")
    ap.add_argument("--shortlist", action="store_true",
                    help="v9.4 — **לא בוחר**: מחיל את כל הסינונים הקשיחים ומחזיר את "
                         "הבריכה עם תוויות קריאות, כדי שהבמאי יבחר פר-משפט. "
                         "זה התפקיד הנכון של הקובץ הזה — 447 קליפים → רשימה קצרה.")
    # v9.7 — תיקיית הפרויקט. משם נקרא `brief.json` לשער סתירה-לבריף.
    # בלי זה השער לא רץ (ומדווח שלא רץ) — הוא לא מנחש הבטחות מהנושא.
    ap.add_argument("--workdir", help="תיקיית הפרויקט — מקור brief.json")
    ap.add_argument("--json", dest="out_json")
    ap.add_argument("--commit", action="store_true", help="רשום שימוש ב-usage.json")
    a = ap.parse_args()

    cfg = load(a.config)
    # ─── v8.0: פרופיל צפיפות לפי סוג תוכן (ניתן לדריסה בקונפיג) ───
    profiles = dict(DENSITY_PROFILES)
    for k, v in (cfg.get("density_profiles") or {}).items():
        profiles[k] = {**profiles.get(k, DEFAULT_PROFILE), **v}
    prof = dict(DEFAULT_PROFILE)
    prof.update(profiles.get(a.content_type.strip(), {}))
    if a.density == "dense":
        prof.update(profiles.get("conversion", {}))
    elif a.density == "sparse":
        prof.update(profiles.get("value", {}))
    if a.density != "manual":
        a.n = int(prof["n"]); a.gap = float(prof["gap"])
        a.clip_len = float(prof["clip_len"])
        a.min_relevance = float(prof["min_relevance"])
        a.rel_ratio = float(prof["rel_ratio"])
        # v8.3 (הראל 26.7.26) — bridge_gap לפי סוג תוכן, לא קבוע גלובלי אחד.
        # בלי זה "gap":1.0 של המרה נשבר על ה-bridge_gap הכללי (1.5) ברגע שהעוגן
        # נצמד לתחילת המשפט הבא (יכול לרחוק 3-9ש) — התוצאה קפיצות פנים-בירול-
        # פנים-בירול במקום מצע רציף, בדיוק הפוך מהתיעוד. ערכי טיפול/ערך נשארים
        # על ברירת המחדל (1.5) — שם הפסקות-פנים בין קליפים הן חלק מהכוונה.
        a.bridge_gap = float(prof.get("bridge_gap", a.bridge_gap))
    anchor_mode = prof.get("anchor", "transcript")
    # v8.0 — "fill": מלא את החלון הוק→CTA בבירולים במקום מספר קבוע.
    # בלי זה, המרה של 58ש קיבלה מצע עד שנייה 35 ואז 15ש ריקות — ההפך מהכוונה.
    if prof.get("fill") and a.density != "manual" and a.video_dur > 0:
        window = a.video_dur - a.cta_guard - 6.0
        a.n = max(1, min(14, int(window // (a.clip_len + a.gap))))
    catalog = load(a.catalog or cfg["catalog_path"])
    usage_path = _portable(cfg.get("usage_path", HERE / "broll-usage.json"))
    usage = load(usage_path) if usage_path.exists() else {}
    now = int(time.time())

    # ─── סוג תוכן ───
    # v7.8 (החלטת הראל 25.7.26): **הוסרה ההגבלה "בירול רק ב-conversion"**. היא נקבעה
    # כשהיה יקר לייצר בירול לכל סרטון; עכשיו הקטלוג מתרחב והמטרה הפוכה — בירול בכל
    # סרטון שיש לו קליפ *מתאים*. במקום שער סוג-תוכן יש שער **רלוונטיות** (--min-relevance):
    # אין התאמה תוכנית אמיתית ⇒ אין בירול. עדיף בלי מאשר "סתם וידאו באמצע".
    ct = a.content_type.strip()
    if ct == "throwdown_value" and not a.allow_throwdown_value:
        ct = "conversion"  # throwdown_value מותר תמיד בפועל — התאמת-הקשר

    # ─── קליפים שנפסלו ידנית (v7.9) ───
    disabled = {d.get("file") for d in cfg.get("disabled_files", []) if d.get("file")}
    items = [it for it in catalog["items"] if it.get("file") not in disabled]
    n_disabled = len(catalog["items"]) - len(items)

    # ─── L171 (3.11.26): קליפ שבקטלוג אבל הקובץ שלו לא בענף libs ⇒ canon_lint:broll_files_exist נופל אחרי גימור מלא
    # (6 קליפים כאלה; ריל 1 גיפט קארד נכשל על זה). בוחרים רק מה שקיים על הדיסק.
    def _exists(it):
        pth = it.get("path") or ""
        if not pth:
            return True
        P = Path(pth)
        if P.exists():
            return True
        root = Path(__file__).resolve().parent.parent
        for anchor in ("בירולים", "brand-assets", "מיכאל לוי", "תוצרי-אנימציה"):
            if anchor in P.parts and root.joinpath(*P.parts[P.parts.index(anchor):]).exists():
                return True
        return False
    _before = len(items); items = [it for it in items if _exists(it)]
    if len(items) < _before:
        print(f"[broll_pick] {_before - len(items)} קליפים בקטלוג בלי קובץ על הדיסק — לא נבחרים", file=sys.stderr)

    # ─── v8.0: הפרדת מחלקות (חוק קשיח) ───
    dept_lib_map = {**DEPT_LIBRARIES, **(cfg.get("dept_libraries") or {})}
    if a.cross_library or a.library == "all":
        allowed_libs = None
    elif a.library != "auto":
        allowed_libs = [x.strip() for x in a.library.split(",")]
    else:
        allowed_libs = dept_lib_map.get(a.dept.strip(), DEFAULT_LIBRARIES)
    n_lib_filtered = 0
    if allowed_libs is not None:
        before = len(items)
        items = [it for it in items if library_of(it["path"]) in allowed_libs]
        n_lib_filtered = before - len(items)

    # ─── v8.1: תוכן פרטי לא נכנס לתוכן מועדון (הראל 25.7.26) ───
    # "אימון בחצר שלנו עם הכלבים — תקף להראל, לא לקרוספיט."
    # התג `פרטי` נגזר מ-GPS (מרחק מהבית) + הקשר בשם. קליפ שצולם *במועדון*
    # לעולם לא פרטי, גם אם יש בו כלב.
    n_private_filtered = 0
    club_context = allowed_libs is not None and LIB_PERSONAL not in allowed_libs
    if club_context and not a.allow_private:
        before = len(items)
        items = [it for it in items if "פרטי" not in it.get("tags", [])]
        n_private_filtered = before - len(items)

    # ─── v7.10: הפרדת מותג — בירולי הראל לא נכנסים לתוכן המועדון ───
    # (הראל 25.7.26: "עדיף לא לשלב בירולים של הראל בסרטונים שנוגעים לקרוספיט,
    # להפריד ביניהם"). ב-brand=personal ההיגיון מתהפך: הם דווקא מועדפים.
    # שכבה משלימה להפרדת-הספריות: קליפ שיושב בספריית המועדון אבל **הראל מופיע בו**
    # (תגיות בעל-המועדון/הראל-חיון) עדיין נחשב "בירול של הראל". זה בדיוק המקרה
    # שנתפס 25.7.26 — סרטון שיקום על מתיחות קיבל את הראל עושה סקוואט כבד.
    # ‎--cross-library מבטל גם את זה (בקשה מפורשת). אם הסינון מרוקן את המאגר —
    # נסוגים, כדי שלא ניפול ל"אין בירול בכלל" בגלל כלל-הפרדה.
    ptags = set(cfg.get("personal_tags", []))
    n_personal = 0
    # v8.4 — פסקי-דין של הראל על קליפים ספציפיים ("זה רק אני") נשמרים כדאטה
    # בקונפיג, לא בצ'אט. בלי זה אותו קליפ נבחר שוב בריצה הבאה וההערה חוזרת.
    harel_files = {d.get("file") for d in cfg.get("harel_present_files", [])
                   if isinstance(d, dict) and d.get("file")}
    harel_files |= {f for f in cfg.get("harel_present_files", []) if isinstance(f, str)}
    if ptags and not a.cross_library:
        if not club_context:
            pref_p = [it for it in items if (ptags & set(it["tags"]))
                      or it.get("file") in harel_files]
            items = pref_p or items
        else:
            kept = [it for it in items
                    if not (ptags & set(it["tags"]))
                    and it.get("file") not in harel_files]
            if kept:
                n_personal = len(items) - len(kept)
                items = kept

    # ─── v8.4: סימן-מתאמן מפורש בתוכן מועדון (whitelist) ───
    n_no_member = 0
    if club_context and prof.get("require_member") and not a.cross_library:
        kept = [it for it in items if MEMBER_TAGS & set(it.get("tags", []))]
        if kept:
            n_no_member = len(items) - len(kept)
            items = kept

    # ─── v8.5 (הראל 26.7.26) — רק קליפים שאומתו ויזואלית ───
    # "זה בירול של הראל ולא של קרוספיט אריאל... תפתור את זה סופית."
    # שער v8.4 (require_member) לא הספיק כי **התיוג עצמו שגוי**: שני קליפים
    # של הראל נשאו 'מתאמן' ולכן עברו. כל פילטר שנשען על התגיות ייכשל שוב.
    # לכן בתוכן המרה עוברים ל-allowlist אנושי: נכנסים רק קבצים שמישהו הסתכל
    # עליהם ואישר שהם מתאמני מועדון. מאגר לא-מאומת = לא נכנס, נקודה.
    # ⚠️ בלי נסיגה (fallback) בכוונה — עדיף בלי בירול מאשר הראל בתוכן מועדון.
    n_unverified = 0
    verified = set(cfg.get("verified_member_files", []))
    if club_context and prof.get("require_verified") and not a.cross_library and verified:
        before = len(items)
        items = [it for it in items if it.get("file") in verified]
        n_unverified = before - len(items)

    # ─── v9.7 — שער סתירה-לבריף (מה רואים מול מה הבטחנו) ───
    # התווית שיקרה פעם אחת ("חימום עם מוט מתאמנת" = יחיד, בפועל שיעור מלא)
    # והמערכת האמינה לה. כאן ההכרעה נשענת על מודל-ראייה ולא על מחרוזות.
    # רץ **אחרי** הסינון המאומת כדי שהמדידה תהיה על הבריכה שבאמת נכנסת.
    n_brief_conflict, brief_blocked = 0, []
    if club_context and prof.get("require_verified") and not a.cross_library:
        try:
            import broll_brief_gate as BG
            _bp = Path(a.workdir) / "brief.json" if getattr(a, "workdir", None) else None
            _brief = (json.loads(_bp.read_text(encoding="utf-8"))
                      if _bp and _bp.exists() else {})
            if _brief:
                items, brief_blocked = BG.filter_items(
                    items, _brief, strict=(ct == "conversion"))
                n_brief_conflict = len(brief_blocked)
        except Exception as _e:                       # noqa: BLE001
            brief_blocked = [{"file": "-", "why": f"שער הבריף לא רץ: {_e}"}]

    # ─── סינון קשיח לפי קהל ───
    if a.audience == "דוספיט" or ct == "dossfit":
        items = [it for it in items if "דוספיט" in it.get("audience", [])]
    else:
        items = [it for it in items if "דוספיט" not in it.get("audience", [])]
    # קליפים ספציפיים-לאירוע (Throwdown = 28 מתוך 59 בקטלוג!) לא נכנסים לתוכן רגיל —
    # צילומי תחרות באמצע "טיפ אחד" הם ההפך מהשתלבות. נכנסים רק כשזה באמת Throwdown.
    is_throwdown = (a.dept == "REL Throwdown" or ct == "throwdown_value"
                    or "throwdown" in a.topic.lower())
    if not is_throwdown:
        items = [it for it in items
                 if "Throwdown" not in it["tags"] and "Throwdown" not in it["event"]]
    # v10 (22.10.26, ממומן ילדים): הפרדת מחלקות קשיחה גם בקהל. עד היום מחלקת "ילדים"
    # קיבלה את כל בריכת המועדון (54 קליפים — דדליפט, אמבט קרח, מיכאל לוי) ורק קליפ
    # ילדים אחד. סרטון ילדים = בירול ילדים בלבד; לכן מסננים לפי audience/category.
    if a.dept.strip() == "ילדים" or a.audience == "ילדים":
        items = [it for it in items
                 if "ילדים" in (it.get("audience") or []) or it.get("category") == "ילדים"]
    if a.audience in ("נשים", "גברים"):
        items = [it for it in items
                 if not it.get("audience") or a.audience in it["audience"] or
                 ("נשים" not in it["audience"] and "גברים" not in it["audience"])]
    if is_throwdown:
        pref = [it for it in items if "Throwdown" in it["tags"] or "Throwdown" in it["event"]]
        items = pref or items

    # ─── v9.4: קליפי דיבור-למצלמה אינם בירול (שער קשיח, לא שיפוט) ───
    before = len(items)
    items = [it for it in items if is_cutaway(it)]
    n_talking_head = before - len(items)

    if not items:
        print(json.dumps({"error": "אין בירולים תואמים בקטלוג אחרי סינון", "plan": []}, ensure_ascii=False))
        sys.exit(2)

    # ═══ v9.4 — מצב shortlist: מסננים, לא בוחרים ═══════════════════════════
    # שורש הליקוי (נמדד 30.7.26 על V3-לולאה): הבחירה דירגה 447 קליפים מול
    # **מחרוזת-נושא אחת** לכל הסרטון. ב-V3 המחרוזת הגיעה מ-`intent_card.md`
    # שהצינור החדש כלל לא כותב ⇒ `topic=""` ⇒ רלוונטיות 0 לכל 35 הקליפים
    # בבריכה ⇒ `plan: []`. ובפרויקט קודם, כשהמחרוזת כן הייתה מלאה, היא הייתה
    # התמלול כולו משורשר — ולכן נבחר "ראיון עם מתאמנת" לסרטון על שעות ומחיר.
    # **שתי התקלות הן אותו שורש: נושא-על אינו יחידת ההתאמה. המשפט הוא.**
    # לכן הקובץ הזה מפסיק להכריע ומחזיר בריכה; ההתאמה פר-משפט עוברת לבמאי.
    if a.shortlist:
        pool = sorted(items, key=lambda it: (it.get("category", ""), clip_label(it)))
        out = {
            "mode": "shortlist", "content_type": ct, "dept": a.dept,
            "audience": a.audience, "brand": a.brand,
            "pool_size": len(pool),
            "libraries_allowed": ("all" if allowed_libs is None else allowed_libs),
            "filtered": {"disabled": n_disabled, "library": n_lib_filtered,
                         "private": n_private_filtered, "personal": n_personal,
                         "no_member_signal": n_no_member, "unverified": n_unverified,
                         "talking_head": n_talking_head,
                         "brief_conflict": n_brief_conflict},
            # ⚠️ הסתירות נשמרות **עם הנימוק והראיה** ולא כמספר בלבד: קליפ
            # שנחסם הוא חוב תוכן (חסר לנו שוט של רחבה פנויה), לא רק פסילה.
            "brief_conflicts": brief_blocked[:20],
            # v9.9 — `shot`/`crowding` נכנסים לכרטיס. עד כאן הפרומפט ביקש
            # מהבמאי "פותחים ברחב, ממשיכים לפרטים" בזמן ש**גודל השוט לא הופיע
            # בכרטיס בכלל** — כלומר ביקשנו ממנו לבנות מבנה חזותי בעיניים
            # עצומות. נמדד בסרטון שאושר: 12 קליפי מצע, כולם `medium`, 11 ברצף.
            # המקור הוא פאס הראייה (`broll_vision_model`), לא שם הקובץ, ולא
            # התווית — אותה הפרדה שחסמה את "חימום עם מוט מתאמנת".
            # ל-payload: המטמון מפתחו file|mtime|size, כלומר יציב בין ריצות.
            # קליפ שטרם נסרק מקבל null ולא ניחוש — "לא יודע" הוא תשובה.
            "clips": [{"clip_id": it["id"], "label": clip_label(it),
                       "category": it.get("category", ""),
                       "dur": it.get("dur"),
                       "vertical": bool(it.get("vertical")),
                       "shot": _vision_of(it).get("shot"),
                       "crowding": _vision_of(it).get("crowding"),
                       "tags": sorted(set(it.get("tags") or []))[:12]}
                      # ⚠️ **בלי `last_used_days`.** זה היה `now - usage[id]`,
                      # כלומר מספר שמשתנה בכל שנייה ⇒ payload אחר בכל ריצה ⇒
                      # digest אחר ⇒ `--backend replay` נשבר. שלישית באותה
                      # משפחה ב-31.7.26 (‏גודל קובץ · רשימת שערים · והפעם זמן).
                      # **הכלל: אם ערך משתנה בלי שהתוכנית השתנתה — הוא לא נכנס
                      # ל-payload של פאס.** רוטציה נאכפת ב-`score_item`, בקוד.
                      for it in pool],
            "_paths": {it["id"]: it["path"] for it in pool},
        }
        txt = json.dumps(out, ensure_ascii=False, indent=1)
        if a.out_json:
            Path(a.out_json).write_text(txt, encoding="utf-8")
        print(txt)
        return 0

    # ─── ניקוד ───
    tmap = cfg.get("topic_tag_map", {})
    topic_words = [w for w in re.split(r"[\s,.\-!?]+", a.topic) if len(w) >= 2]
    want_tags = set()
    for w in topic_words:
        for key, tags in tmap.items():
            if key in w or w in key:
                want_tags.update(tags)
    dept_tags = set(cfg.get("dept_tag_map", {}).get(a.dept, []))
    smap = cfg.get("sentence_tag_map", {})

    # v8.1 — התמליל קודם לנושא. טוענים משפטים כאן (ולא רק בשלב התכנון) כדי
    # שהבחירה עצמה תוכל להישען עליהם.
    sentences = []
    if a.sentences and Path(a.sentences).exists():
        sentences = load(a.sentences) or []
    _dur_cap = a.video_dur or (float(sentences[-1]["end"]) if sentences else 60.0)
    transcript_first = []
    if anchor_mode == "transcript" and len(sentences) > 1:
        transcript_first = pick_by_transcript(
            items, sentences, smap, usage, now, a.n, a.min_affinity,
            _dur_cap, a.cta_guard, a.clip_len, a.hook_guard)

    ranked = sorted(items, key=lambda it: -score_item(it, want_tags, topic_words, usage, now, dept_tags))
    # v7.8 — שער רלוונטיות: קליפ נכנס רק אם יש לו קשר תוכני אמיתי לסרטון
    # (תג תואם או מילה מהנושא בתיאור). בלי זה, "בירול בכל סרטון" היה הופך לקליפ אקראי.
    # v7.9 — "בירול שני מיותר" (הראל 25.7): קליפ נוסף נכנס רק אם הוא באותה ליגה
    # של הראשון. אם הטוב ביותר קיבל 32 והבא 5 — השני הוא רעש, לא ערך.
    skipped_low, skipped_weak = [], []
    top_rel = None
    picks, seen_desc = [], set()
    for it in ranked:
        rel = relevance(it, want_tags, topic_words, dept_tags)
        if rel < a.min_relevance:
            skipped_low.append({"file": it["file"], "relevance": round(rel, 1)})
            continue
        if top_rel is not None and rel < top_rel * a.rel_ratio:
            skipped_weak.append({"file": it["file"], "relevance": round(rel, 1),
                                 "top": round(top_rel, 1)})
            continue
        base = re.sub(r"\s*\d+$", "", it["desc"]).strip() or it["file"]
        if base in seen_desc:
            continue
        it = dict(it, _relevance=round(rel, 1))
        if top_rel is None:
            top_rel = rel
        picks.append(it); seen_desc.add(base)
        if len(picks) >= a.n:
            break

    # v8.1 — אם הבחירה מהתמליל הניבה זוגות שעברו סף, היא גוברת על הדירוג
    # הגלובלי. הדירוג הגלובלי נשאר כרשת ביטחון: סרטון בלי משפטים, בלי גשר
    # סמנטי מתאים, או anchor=flow (המרה).
    picked_by = "topic"
    if transcript_first:
        picks = [x[1] for x in transcript_first]
        picked_by = "transcript"

    # ─── תכנון מיקומים ───
    plan = []
    first_end = float(sentences[0]["end"]) if sentences else 0.0
    start_at = max((first_end + 0.2) if first_end else 6.0, a.hook_guard)
    dur_cap = a.video_dur or (sentences[-1]["end"] if sentences else 60.0)
    cursor = start_at
    # v8.0 — anchor=transcript: כל קליפ נצמד למשפט שהכי "מבקש" אותו, לא לפי סדר.
    if transcript_first:
        anchor_times = [x[0] for x in transcript_first]   # v8.1 — כבר עוגן בבחירה
    elif anchor_mode == "transcript" and sentences and len(sentences) > 1:
        used = set()
        ordered = []
        for it in picks:
            best, best_i = None, None
            for si, sent in enumerate(sentences[1:], start=1):
                if si in used:
                    continue
                if float(sent["start"]) > dur_cap - a.cta_guard - a.clip_len:
                    continue
                aff = sentence_affinity(it, sent.get("text", ""))
                if best is None or aff > best:
                    best, best_i = aff, si
            if best_i is not None:
                used.add(best_i)
                ordered.append((float(sentences[best_i]["start"]) + 0.1, it, best))
        if ordered:
            ordered.sort(key=lambda x: x[0])
            picks = [x[1] for x in ordered]
            anchor_times = [x[0] for x in ordered]
        else:
            anchor_times = None
    else:
        anchor_times = None

    for i, it in enumerate(picks):
        if anchor_times:
            cursor = max(cursor, anchor_times[i])
        clip_len = min(a.clip_len, max(2.0, it["dur"] - SAFE_TAIL))
        # v8.1 — כשהבירול עוגן למשפט מסוים, המשפט קובע את האורך, לא הפרופיל.
        # אחרת קליפ של 3ש שמעוגן ל"זוגיות" (0.74ש) גולש לתוך "שני כלבים"
        # ומבטל בדיוק את הקישור שבגללו הוא נבחר.
        if transcript_first and i < len(transcript_first):
            nxt = (transcript_first[i + 1][0] if i + 1 < len(transcript_first)
                   else dur_cap - a.cta_guard)
            sent_end = next((float(s["end"]) for s in sentences
                             if abs(float(s["start"]) + 0.1 - anchor_times[i]) < 0.2), None)
            room = min(nxt - 0.10, sent_end if sent_end else nxt) - cursor
            # v8.2 (הראל 25.7): "הבירולים היו טיפה קצרים, לא מספיקים להבין מה זה"
            # — נמדד על "זוגיות" (0.90ש) ו"כלבים" (1.33ש). מתחת ל---min-clip-len
            # הצופה לא מספיק לפענח מה הוא רואה, והבירול הופך להבהוב. גבול המשפט
            # כבר לא מקצץ מתחת לסף: עדיף שהקליפ יגלוש מעט למשפט הבא (הגישור
            # ממילא מכסה את זה) מאשר תמונה שאי אפשר לקרוא.
            if room >= a.min_clip_len:
                clip_len = min(clip_len, room)
            else:
                clip_len = max(a.min_clip_len, min(clip_len, it["dur"]))
        # התאמת-הקשר: אם יש משפטים — הצמד לתחילת משפט קרוב.
        # v8.0: כש-anchor_times פעיל, המיקום *כבר* תחילת משפט שנבחר לפי התאמה
        # לתמליל — הצמדה נוספת דוחפת קדימה למשפט הבא ומאבדת את הקליפ (נמדד:
        # בירול שני נעלם בסרטון 34ש).
        # v8.3 (הראל 26.7.26) — שורש "קפיצות במקום מצע רציף": ההצמדה לתחילת-משפט
        # הבאה חלה עד עכשיו גם ב-anchor=flow (המרה), ודרסה את ה-gap הקטן (1.0)
        # של הפרופיל בכל פעם שמשפטים היו רחוקים זה מזה (5-9ש בסרטון הזה) — בדיוק
        # הפוך מ"מצע כמעט-רציף". הצמדה למשפט שייכת רק ל-anchor=transcript, ששם
        # היא הנקודה כולה (דיוק סמנטי); ב-flow העוגן היחיד הוא רצף-קליפים+gap.
        if sentences and not anchor_times and anchor_mode != "flow":
            cand = [s for s in sentences[1:] if s["start"] >= cursor - 0.3]
            if cand:
                cursor = max(cursor, float(cand[0]["start"]) + 0.1)
        end = cursor + clip_len
        if end > dur_cap - a.cta_guard:
            break  # לא נוגעים ב-CTA
        src_off = max(0.0, (it["dur"] - clip_len) / 2.0)  # אמצע-הקליפ
        plan.append({
            "id": it["id"], "path": it["path"], "file": it["file"],
            "insert_at": round(cursor, 2), "insert_end": round(end, 2),
            "src_offset": round(src_off, 2), "clip_len": round(clip_len, 2),
            "relevance": it.get("_relevance"),
            "reason": f"tags={sorted(set(it['tags']) & want_tags) or it['tags'][:3]}",
            "audio": "mute",
        })
        # v8.1 — ה-gap של הפרופיל נועד למנוע ספאם כשהמיקום שרירותי (anchor=flow).
        # כשהתמליל הוא שקבע את המיקום, gap=8 היה דוחף את הבירול השני והשלישי
        # אל מעבר לסוף הסרטון — כלומר מוחק בדיוק את ההתאמות המדויקות. שם
        # התמליל מנצח, ונשאר רק מרווח נשימה מינימלי בין קליפים.
        cursor = end + (0.10 if transcript_first else a.gap)

    # ── v8.2 — גישור בין בירולים סמוכים (הראל 25.7) ──────────────────────────
    # "בגלל שיש הרבה בירולים שמשלבים בסרטון, הייתי כבר מגשר ביניהם במקום כל פעם
    # לחזור אליי. זה מייצר הרבה עומס ומלא מעברים."
    # חזרה של 0.3-1.2ש לפנים בין שני בירולים היא לא "נשימה" — היא הבהוב. במקום
    # face→broll→face→broll, מאריכים את הקליפ הקודם עד תחילת הבא ומקבלים רצף
    # אחד. מספר המעברים יורד בחצי, והעין נחה. מעל bridge_gap כן חוזרים לפנים —
    # שם זה באמת מקטע נפרד ולא הבהוב.
    bridged = 0
    continuous = bool(prof.get("continuous")) and not transcript_first
    for i in range(len(plan) - 1):
        hole = plan[i + 1]["insert_at"] - plan[i]["insert_end"]
        if 0 < hole <= a.bridge_gap:
            # v8.3 (הראל 26.7.26) — לא לגשר מעבר לאורך הקליפ המקורי בפועל.
            # באג נעול: bridge_gap גבוה (המרה) האריך clip_len ל-6.6/8.6ש על
            # קליפים גולמיים של 3.6ש — ffmpeg פשוט נתקע/קופא בחלק העודף.
            # מגשרים עד שיא ה-footage הזמין; שארית שלא מתכסה נשארת פער אמיתי.
            it_dur = next((x["dur"] for x in items if x["id"] == plan[i]["id"]), plan[i]["clip_len"])
            max_end = plan[i]["insert_at"] + max(0.0, it_dur - SAFE_TAIL)
            new_end = min(plan[i + 1]["insert_at"], max_end)
            if new_end > plan[i]["insert_end"]:
                plan[i]["insert_end"] = round(new_end, 2)
                plan[i]["clip_len"] = round(plan[i]["insert_end"] - plan[i]["insert_at"], 2)
                bridged += 1
            # v8.4 (הראל 26.7.26) — "בין בירול לבירול לא צריך לראות אותי, זה
            # צריך להיות מעבר רציף ביניהם."
            # שורש התקלה שנשארה אחרי v8.3: המתיחה של הקליפ הקודם חסומה באורך
            # ה-footage שלו (3.6ש). כשנשארה שארית — ‎0.2ש בסרטון אופן-ג'ים —
            # היא בדיוק חלון של ~6 פריימים שבו נחשפות הפנים, וגם מפילה את
            # מבחן-הסמיכות ב-animation_overlay (eps 0.05) ⇒ מקבלים גם fade
            # שחושף עוד יותר. מתיחה היא הכלי הלא-נכון; **הזזה** של הקליפ הבא
            # אחורה היא חינמית — לקליפ יש footage משלו והחלון פשוט זז שמאלה,
            # בלי לגעת ב-CTA. לכן: סוגרים כל שארית בהזזה, והתוצאה חור=0 מדויק.
            hole = round(plan[i + 1]["insert_at"] - plan[i]["insert_end"], 3)
            if continuous and hole > 0:
                shift = hole
                plan[i + 1]["insert_at"] = round(plan[i + 1]["insert_at"] - shift, 2)
                plan[i + 1]["insert_end"] = round(plan[i + 1]["insert_end"] - shift, 2)
            plan[i]["bridged_to_next"] = (
                plan[i + 1]["insert_at"] - plan[i]["insert_end"] <= 0.01)
    for p in plan:      # src_offset מחדש אחרי שינוי אורך — אמצע הקליפ
        it_dur = next((x["dur"] for x in items if x["id"] == p["id"]), p["clip_len"])
        p["src_offset"] = round(max(0.0, (it_dur - p["clip_len"]) / 2.0), 2)

    # ── v8.4 — שער בדיקה עצמית: אין חורי-פנים בתוך רצף ──────────────────────
    # התקלה הזאת חזרה שלוש פעמים (25.7 ×2, 26.7) כי אף אחד לא **מדד** את
    # התוצאה — הקוד "ניסה" לגשר ואם לא הצליח, שתק. מעכשיו כל חור שנשאר בתוך
    # רצף מדווח מפורשות בתוכנית ובפלט, כדי שייראה גם בלי לצפות בסרטון.
    face_gaps = []
    for i in range(len(plan) - 1):
        h = round(plan[i + 1]["insert_at"] - plan[i]["insert_end"], 3)
        if 0 < h <= a.bridge_gap:
            face_gaps.append({"after": plan[i]["file"], "at": plan[i]["insert_end"],
                              "gap": h})

    # overlay_args = רשימת argv טוקנים אמיתית (לא מחרוזת מצוטטת-של) — זה מה ש-
    # local_finish_pipeline.py מצרף ישירות ל-subprocess argv (בלי shell, בלי shlex).
    # באג נעול (23.7.26): גרסה קודמת בנתה כאן מחרוזת אחת מצוטטת ל-shell, ו-
    # local_finish_pipeline עשה `[...] + args` — list+str מתפוצץ ב-TypeError לא-מטופל
    # בכל פעם שהיו בירולים בפועל בתוכנית (broll תמיד "נעלם" בלי דיווח כשל ברור).
    overlay_argv = []
    for p in plan:
        overlay_argv += ["--overlay", p["path"], str(p["insert_at"]), str(p["insert_end"]),
                          "--src-offset", str(p["src_offset"])]
    overlay_display = " ".join(
        f'--overlay "{p["path"]}" {p["insert_at"]} {p["insert_end"]} --src-offset {p["src_offset"]}'
        for p in plan)
    out = {
        "content_type": ct, "audience": a.audience, "topic": a.topic,
        "picked_by": picked_by, "min_affinity": a.min_affinity,
        "bridged": bridged, "min_clip_len": a.min_clip_len, "bridge_gap": a.bridge_gap,
        "picked": [p["file"] for p in plan],
        "plan": plan,
        "pool_size": len(items),
        "density": a.density, "density_profile": {k: v for k, v in prof.items() if not k.startswith("_")},
        "anchor_mode": anchor_mode,
        "libraries_allowed": ("all" if allowed_libs is None else allowed_libs),
        "library_filtered_out": n_lib_filtered,
        "private_filtered_out": n_private_filtered,
        "picked_locations": sorted({t for p in plan for t in ("במועדון","מחוץ-לאריאל","בבית-ובחצר","אריאל-מחוץ-למועדון","מחוץ-למועדון") if t in next((i["tags"] for i in items if i["file"]==p["file"]), [])}),
        "picked_libraries": sorted({library_of(p["path"]) or "(ותיק)" for p in plan}),
        "disabled_filtered": n_disabled,
        "personal_filtered": n_personal,
        "no_member_signal_filtered": n_no_member,
        "continuous": continuous,
        "face_gaps": face_gaps,
        "dept": a.dept, "dept_tags": sorted(dept_tags),
        "min_relevance": a.min_relevance,
        "skipped_low_relevance": len(skipped_low),
        "skipped_weak_second": skipped_weak[:5],
        "no_match_reason": (None if plan else
                            ("אין קליפ בקטלוג עם רלוונטיות ≥"
                             f"{a.min_relevance} לנושא הזה — עדיף בלי בירול")),
        "overlay_args": overlay_argv,           # רשימת argv — לשימוש ישיר ע"י local_finish_pipeline.py
        "overlay_args_display": overlay_display,  # מחרוזת קריאה לבני-אדם/דיבוג (shell-style)
        "rule_reminders": ["audio mute תמיד", "לא מכסה Hook/פתיחה", "לא מכסה CTA",
                           "כל סוגי התוכן (v7.8) — בכפוף לסף רלוונטיות",
                           "v8.0 הפרדת מחלקות: בירולי הראל לא נכנסים לתוכן מועדון ולהיפך",
                           "v8.0 המרה = מצע בירולים רציף הוק→CTA; ערך/חיבור = נקודתי לפי התמלול",
                           "v8.1 תוכן פרטי (בית/חצר/חתונה) — הראל בלבד, לא בתוכן מועדון",
                           "fade 0.12 בכניסה/יציאה"],
    }
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    if a.out_json:
        Path(a.out_json).write_text(txt, encoding="utf-8")
    print(txt)

    if a.commit and plan:
        for p in plan:
            usage[p["id"]] = now
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        usage_path.write_text(json.dumps(usage, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"USAGE committed → {usage_path}", file=sys.stderr)

if __name__ == "__main__":
    main()
