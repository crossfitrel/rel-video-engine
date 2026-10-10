#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_director — שכבת הבירול של מנוע ההחלטה (V3, v9.4).

חלוקת העבודה, זהה לזו של שאר המערכת:
    broll_pick --shortlist  = **מי מותר**   (447 קליפים → בריכה מסוננת)
    המודל (פאס `broll`)      = **מה מתאים**  (התאמה פר-משפט + נימוק)
    הקובץ הזה               = **מה נחסם**   (סף ביטחון, ציטוט, כפילות, גבולות)

למה זה קיים בנפרד מ-`broll_pick.py`: שם ההחלטה הייתה ניקוד מול מחרוזת-נושא
אחת של כל הסרטון. נמדד 30.7.26 שזה נכשל בשני כיוונים — מחרוזת ריקה ⇒ אפס
בירולים, ומחרוזת מלאה (התמלול משורשר) ⇒ "ראיון עם מתאמנת" על סרטון שעות
ומחיר. **נושא-על אינו יחידת ההתאמה. המשפט הוא.**

המודל לעולם לא פולט timecodes: הוא מחזיר (חלון, קליפ, ביטחון, נימוק),
והזמנים נגזרים כאן מגבולות המשפט על ציר הפלט.
"""
import json, re
from pathlib import Path

# ── ספים ───────────────────────────────────────────────────────────────────
MIN_CONF = 0.75      # מתחת לזה — אין בירול. לא "בירול חלש".
MIN_CLIP_LEN = 1.8   # v8.2 (הראל 25.7.26): מתחת לזה הצופה לא מפענח — הבהוב.
MAX_CLIP_LEN = 3.5
SAFE_TAIL = 0.08     # v8.4: לא מתכננים עד הפריים האחרון של ה-footage.
CTA_GUARD = 8.0
HOOK_GUARD = 4.0
# v8.2 (הראל 25.7.26, נמדד): "חזרה של 0.3-1.2ש לפנים בין שני בירולים היא לא
# נשימה — היא הבהוב". סוגרים חור קטן מזה בהארכת הקליפ הקודם.
FLASH_GAP = 1.2
# כמה מהקליפ חייב עדיין לנגן **בזמן שהמשפט נאמר**, אחרי החלקה לסגירת הבהוב.
# מתחת לזה הקליפ כבר לא מאויר את המילים שבגללן הוא נבחר.
MIN_ANCHOR_OVERLAP = 1.0

# ── חציית גבול חיתוך (v9.11, הראל 1.8.26) ──────────────────────────────────
# "אם קטע נגמר ב-1.5ש, הבירול חייב להיגמר ב-1.55 ולא ב-1.4, כדי שלא תהיה
#  0.1ש של קפיצה כזו."
#
# כמה צריך לחצות: **שני פריימים ב-30fps**. זה לא מספר עגול אלא אילוץ פיזי של
# מנוע הרינדור — `_clip_to_segments` מוחק שבר קצר מ-0.01ש, ופריים אחד הוא
# 0.033ש, ולכן קצה שנוחת *בדיוק* על הגבול (או חוצה אותו ב-0.01ש) משאיר את
# הפריים שעל הגבול בלי כיסוי. 0.067ש מבטיח כיסוי ונמצא מתחת לסף התפיסה.
CUT_OVERHANG = round(2 / 30.0, 3)

# ── דוקטרינת המרה (הראל 31.7.26) ────────────────────────────────────────────
# "סרטון המרה פונה לקהל שלא מכיר אותנו ולא יודע מה אנחנו מציעים. המבנה צריך
#  להיות 70% בירולים — ישר אחרי המשפט הראשון רצים בירולים אחד אחרי השני בלי
#  לחזור אליי, עד לקריאה לפעולה או קצת לפניה."
#
# למה זה לא סותר את חוק "בירול רק עם נימוק מצטט": בתוכן ערך הצופה **מכיר**
# אותנו ובא ללמוד, ולכן קאטאווי בלי קשר למילים הוא רעש. בקהל קר, **הראייה של
# המקום היא עצמה המסר** — הוא לא יודע איך נראית הרחבה, מי מתאמן בה, ואיך זה
# מרגיש. לכן בהמרה יש שני תפקידים שונים לבירול, ולכל אחד שער משלו:
#   anchor — מאייר מילים ספציפיות. שער: נימוק שמצטט. ביטחון ≥0.75.
#   bed    — רצף שמראה את המקום לקהל שלא מכיר. שער: רצף ולא נקודה, אסור
#            שיסתור את הבריף, ביטחון ≥0.60.
BED_CLIP_LEN = 2.8          # v8.0 — קצב המצע. לא 3.5: רצף של קליפים ארוכים מדי נקרא איטי.
BED_COVERAGE_TARGET = 0.70  # מהמשך הכולל
MIN_CONF_BED = 0.60
# v9.9 — אורך פעימת trust (חזרה מכוונת לפנים בתוך המצע). נגזר מ-BED_CLIP_LEN:
# פעימה קצרה מקליפ מצע נקראת כהבהוב, ארוכה ממנו שוברת את הרצף. **לא מספר
# עגול חדש** — אותו קצב שכבר נמדד, ולכן היא נראית כמו חלק מהמבנה.
TRUST_BEAT_LEN = BED_CLIP_LEN

_PUNCT = re.compile(r"[^\w֐-׿]+")


def norm_words(text):
    """מילים מנורמלות — בלי פיסוק, בלי גרשיים עבריים. הבסיס לבדיקת הציטוט."""
    t = (text or "").replace("׳", "'").replace("״", '"')
    return [w for w in _PUNCT.split(t) if w]


def quoted_span(reason, sentence):
    """הראיה שהנימוק באמת מדבר על **המשפט הזה**, ולא מתאר את הקליפ.

    מחזיר את הצירוף שצוטט, או None. שתי דרכים להיחשב ציטוט:
      * שתי מילים רצופות מהמשפט שמופיעות ברצף בנימוק, או
      * מילה אחת באורך ≥5 (מילת תוכן — לא מילת קישור).

    למה לא "מילה משותפת כלשהי": נמדד שהמשפטים כאן פותחים ב"אתם", "כל",
    "ואצלנו" — מילים שכל נימוק סביר מכיל ממילא. בדיקה כזאת עוברת תמיד
    ולכן אינה שער. צירוף בן שתי מילים הוא ראיה שאי אפשר לייצר במקרה.
    """
    sw = norm_words(sentence)
    rw = norm_words(reason)
    if not sw or not rw:
        return None
    rset = " ".join(rw)
    for i in range(len(sw) - 1):
        bg = f"{sw[i]} {sw[i+1]}"
        if bg in rset:
            return bg
    for w in sw:
        if len(w) >= 5 and w in rset:
            return w
    return None


# ── מיפוי ציר המקור → ציר הפלט ─────────────────────────────────────────────
def map_to_out(t, keeps):
    """כמה שניות נשמרו לפני `t`. מונוטוני; חיתוך מתקפל לנקודה."""
    acc = 0.0
    for k in keeps:
        s, e = float(k["start"]), float(k["end"])
        if t <= s:
            break
        acc += min(t, e) - s
        if t <= e:
            break
    return round(max(0.0, acc), 3)


def kept_span(t0, t1, keeps):
    """החיתוך של [t0,t1] עם מה שנשאר — בציר הפלט. None אם נחתך כולו."""
    parts = [(max(t0, float(k["start"])), min(t1, float(k["end"])))
             for k in keeps
             if min(t1, float(k["end"])) - max(t0, float(k["start"])) > 0.01]
    if not parts:
        return None
    return map_to_out(parts[0][0], keeps), map_to_out(parts[-1][1], keeps)


def cut_boundaries(keeps):
    """גבולות החיתוך בציר הפלט — סוף כל keep, חוץ מהאחרון (שהוא סוף הסרטון).

    נגזר מ-`map_to_out` ולא מסכימה מקבילה: שני חישובים לאותו ציר נפרדים זה
    מזה ברגע שאחד מהם מתוקן, וזה בדיוק איך `boundaries_from_keeps` פספס את
    ה-speed ב-v8.6 והוציא פריימים מאמצע קטעים.
    """
    return [map_to_out(float(k["end"]), keeps) for k in keeps[:-1]]


def surviving_windows(cands, keeps, out_dur,
                      hook_guard=HOOK_GUARD, cta_guard=CTA_GUARD):
    """חלונות הבירול ששרדו את העריכה, בזמני **הפלט**.

    חלון שהמשפט שלו נחתך אינו מוצע למודל בכלל — אחרת הוא בוחר קליפ לרגע
    שכבר לא קיים, וזה נראה כמו החלטה תקינה עד שמסתכלים על התוצר.
    """
    out = []
    for c in cands:
        if c.get("kind") != "broll_window":
            continue
        span = kept_span(float(c["t_start"]), float(c["t_end"]), keeps)
        if not span:
            continue
        s, e = span
        s = max(s, hook_guard)
        e = min(e, out_dur - cta_guard)
        if e - s < MIN_CLIP_LEN:
            continue
        f = c.get("features", {})
        out.append({
            "candidate_id": c["candidate_id"],
            "text": c.get("text", ""),
            "prev_text": c.get("prev_text"),
            "next_text": c.get("next_text"),
            "out_start": round(s, 3), "out_end": round(e, 3),
            "dur_sec": round(e - s, 3),
            "motion_norm": f.get("motion_norm"),
            "is_stalled": bool(f.get("is_stalled")),
        })
    out.sort(key=lambda w: w["out_start"])
    return out


# ── דוקטרינה: המערכת מחליטה איך ניגשים לסרטון הזה ──────────────────────────
def doctrine(content_type, brief, sentences, keeps, out_dur,
             hook_guard=HOOK_GUARD, cta_guard=CTA_GUARD):
    """**מי הקהל קובע את המבנה, לא רק מה נאמר.**

    זה השיקול שחסר למערכת עד 31.7.26: היא ידעה להתאים קליפ למשפט, אבל לא
    שאלה למי הסרטון פונה. סרטון ערך פונה למי שכבר מכיר — קאטאווי בלי קשר
    למילים הוא רעש. סרטון המרה פונה לקהל **קר**, שלא ראה מעולם את הרחבה,
    ולכן הראייה של המקום היא עצמה המסר, לא קישוט מעליו.

    מחזיר את הדוקטרינה כדאטה — נכנס ל-payload של המודל **וגם** מניע את
    האריזה בקוד, כך שאין דרך שהמודל "יסכים" ולא ייצא רצף.
    """
    ct = (content_type or "").strip().lower()
    is_conversion = ct in ("conversion", "המרה")
    if not is_conversion:
        return {"mode": "anchors_only", "content_type": ct or "value",
                "audience_state": "warm",
                "why": "הצופה כבר מכיר את המועדון — בירול נכנס רק כשהוא מאייר "
                       "מילים ספציפיות. רצף בלי קשר למילים הוא רעש."}

    # המצע מתחיל בסוף המשפט הראשון ששרד, לא בשנייה שרירותית.
    first_end = hook_guard
    for s in sorted(sentences, key=lambda x: x["start"]):
        sp = kept_span(float(s["start"]), float(s["end"]), keeps)
        if sp:
            first_end = max(hook_guard, sp[1])
            break
    bed_start = round(first_end, 3)
    bed_end = round(out_dur - cta_guard, 3)
    span = max(0.0, bed_end - bed_start)
    return {
        "mode": "continuous_bed", "content_type": "conversion",
        "audience_state": "cold",
        "audience": (brief or {}).get("audience", ""),
        "bed_start": bed_start, "bed_end": bed_end,
        "bed_span_sec": round(span, 2),
        "coverage_target_pct": round(100.0 * BED_COVERAGE_TARGET),
        "projected_coverage_pct": round(100.0 * span / max(0.01, out_dur)),
        "bed_clips_needed": max(0, int(round(span / BED_CLIP_LEN))),
        "clip_len": BED_CLIP_LEN,
        "why": "קהל קר. הוא לא ראה את הרחבה, לא יודע מי מתאמן בה ואיך זה נראה "
               "— ולכן הראייה של המקום היא המסר, לא קישוט. מצע רציף מסוף "
               "המשפט הראשון ועד ה-CTA, קליפ אחרי קליפ, בלי לחזור לדובר.",
    }


# ── אכיפה ──────────────────────────────────────────────────────────────────
def enforce(placements, windows, clips):
    """מסננת ההחלטות. מחזירה (accepted, rejected) — כל דחייה עם סיבה מפורשת.

    כל כלל כאן הוא כלל שהמודל **לא** יכול לעקוף בניסוח משכנע.
    """
    wmap = {w["candidate_id"]: w for w in windows}
    cmap = {c["clip_id"]: c for c in clips}
    accepted, rejected = [], []
    used_clips, used_labels, used_windows = set(), set(), set()

    for p in sorted(placements or [],
                    key=lambda x: -float(x.get("confidence") or 0)):
        cid = str(p.get("candidate_id") or "")
        clid = str(p.get("clip_id") or "")
        try:
            conf = float(p.get("confidence"))
        except (TypeError, ValueError):
            conf = 0.0
        reason = str(p.get("reason") or "").strip()

        def drop(why):
            rejected.append({"candidate_id": cid, "clip_id": clid,
                             "confidence": conf, "why": why, "reason": reason})

        w, c = wmap.get(cid), cmap.get(clid)
        if w is None:
            drop("חלון לא קיים במרחב (או שהמשפט נחתך בעריכה)"); continue
        if c is None:
            drop("קליפ לא קיים בבריכה המסוננת"); continue
        if conf < MIN_CONF:
            drop(f"ביטחון {conf:.2f} < {MIN_CONF} — אין בירול, וזה תקין"); continue
        if cid in used_windows:
            drop("החלון כבר מכוסה"); continue
        if clid in used_clips:
            drop("הקליפ כבר בשימוש בסרטון הזה"); continue
        label = re.sub(r"\s*\(\d+\)\s*$", "", c.get("label", "")).strip()
        if label and label in used_labels:
            drop(f"קליפ כמעט-זהה כבר בסרטון ({label})"); continue
        q = quoted_span(reason, w["text"])
        if not q:
            drop("הנימוק לא מצטט את המשפט — תיאור של הקליפ אינו נימוק"); continue

        used_windows.add(cid); used_clips.add(clid)
        if label:
            used_labels.add(label)
        accepted.append({**p, "confidence": conf, "reason": reason,
                         "quoted": q, "label": c.get("label"),
                         "clip_dur": c.get("dur")})

    accepted.sort(key=lambda p: wmap[p["candidate_id"]]["out_start"])
    return accepted, rejected


LEAD_IN = 0.30      # כמה להקדים את הקליפ למילים שהוא מאייר
# מתי בכלל שווה להזיז את העוגן אל הציטוט. בחלון שאורכו כאורך הקליפ, הקליפ
# מכסה ממילא כמעט את כל המשפט וההזזה חסרת משמעות — אבל היא כן מזיזה את
# הקליפ ביחס לשכנו, ולכן עלולה לפתוח חור-פנים שסוגר-ההבהוב לא יכול לסגור
# (הוא מזיז רק את הקליפ המוקדם, לעולם לא את הבא). לכן מזיזים רק כשהחלון
# באמת ארוך — שם ההפרש הוא בין "מאייר את המילים" ל"מאייר מילים אחרות".
MIN_WINDOW_FOR_QUOTE_SEEK = 8.0


def _avoid_flash_at_start(start, length, w, bounds):
    """קצה פתיחה של בירול לא יושב במרחק הבהוב מגבול חיתוך גלוי.

    ⚠️ נולד מיד אחרי L34 (17.8.26): ברגע שהעוגן זז אל הציטוט, קצה הפתיחה שלו
    נחת 0.93ש ו-0.58ש **אחרי** גבולות חיתוך לא-מכוסים — והמבקר-קדם דיווח
    שני ממצאי P1_cut_flash. זו בדיוק הקפיצה הכפולה של v9.11, רק שהפעם
    התיקון של מיקום העוגן הוא שיצר אותה.

    ‏`snap_to_cuts` מטפל בקצה שנגמר לפני גבול; כאן הכיוון הפוך — קצה שמתחיל
    אחריו. הכלי היחיד: **למשוך את ההתחלה אחורה כך שהבירול יחצה את הגבול**,
    ואז הקאט מוסתר לגמרי ואין שני אירועים. אם אי אפשר (הגבול לפני תחילת
    החלון) — משאירים ומדווחים, לא מזיזים קדימה: הזזה קדימה מנתקת את הבירול
    מהמילים שבגללן נבחר.
    """
    if not bounds:
        return start
    out_start = float(w["out_start"])
    for b in sorted(bounds):
        if b <= start - 1e-6 and (start - b) <= FLASH_GAP:
            pulled = b - 2.0 / 30.0          # שני פריימים לפני הגבול
            if pulled >= out_start - 1e-6:
                return pulled
    return start


def anchor_start(w, quoted, length, hard_end, bounds=None):
    """איפה בתוך החלון יושב העוגן — על המילים שהוא מצטט.

    ⚠️ עד 17.8.26 העוגן הושם תמיד ב-`w["out_start"]`, כלומר בתחילת המשפט.
    בחלון קצר זה כמעט אותו דבר; בחלון ארוך זה **בירול על מילים אחרות**.
    נמדד על "בריאות-לקום-מכיסא": החלון 5.07-22.81ש (17.74ש), הציטוט שהצדיק
    את הבחירה הוא "לחזק את... תבניות התנועה" שנמצא בסוף המשפט (~20ש) —
    והקליפ נצרב על 5.07-8.57ש, כלומר מעל "הרבה אנשים לא שמים לב לנקודה
    שבה הם מתחילים". שוט של סקוואט על משפט שמדבר על להיעזר בידיים.

    חוק ברזל 6 אומר "מה שנאמר קובע מה נראה", והציטוט הוא התנאי לקבלה —
    אבל הוא לא השפיע על הזמן. כאן הוא משפיע: הקליפ מוצב על הציטוט, עם
    הקדמה קטנה כדי שהתמונה כבר תהיה שם כשהמילה נשמעת.

    ההערכה מיקומית-מילולית ולא מדויקת-לשנייה — לחלון יש רק טקסט וזמני
    התחלה/סוף. זה עדיין קרוב בהרבה מ"תמיד בהתחלה", והשגיאה חסומה בגבולות
    החלון עצמו.
    """
    out_start = float(w["out_start"])
    dur = float(w.get("dur_sec") or 0.0)
    default = out_start
    if not quoted or dur <= 0 or dur < MIN_WINDOW_FOR_QUOTE_SEEK:
        return default
    toks = str(w.get("text") or "").split()
    qtoks = str(quoted).split()
    if not toks or not qtoks:
        return default

    def norm(s):
        return "".join(ch for ch in s if ch.isalpha() or ch == "'")

    ntoks = [norm(t) for t in toks]
    nq = [norm(t) for t in qtoks]
    idx = None
    for i in range(len(ntoks) - len(nq) + 1):
        if ntoks[i:i + len(nq)] == nq:
            idx = i
            break
    if idx is None:                       # ציטוט של מילה בודדת שאולי הוטתה
        for i, t in enumerate(ntoks):
            if nq[0] and (nq[0] in t or t in nq[0]):
                idx = i
                break
    if idx is None:
        return default
    frac = idx / max(1, len(ntoks))
    q_at = out_start + frac * dur
    start = q_at - LEAD_IN
    # לא לפני תחילת המשפט, ולא כך שהקליפ יחרוג מהחלון או מגבול ה-CTA.
    start = max(out_start, start)
    start = min(start, out_start + dur - length, hard_end - length)
    start = max(out_start, start)
    return _avoid_flash_at_start(start, length, w, bounds)


def build_plan(accepted, windows, clips, out_dur, paths,
               cta_guard=CTA_GUARD, keeps=None):
    """החלטות → פריטי `broll_plan.json` בציר הפלט. כאן נגזרים הזמנים.

    `keeps` (אופציונלי) — קטעי החיתוך, כדי שמיקום העוגן יימנע מלנחות במרחק
    הבהוב מגבול חיתוך גלוי. ראה `_avoid_flash_at_start`.
    """
    wmap = {w["candidate_id"]: w for w in windows}
    cmap = {c["clip_id"]: c for c in clips}
    plan, dropped = [], []
    hard_end = out_dur - cta_guard
    bounds = cut_boundaries(keeps) if keeps else None

    for p in accepted:
        w, c = wmap[p["candidate_id"]], cmap[p["clip_id"]]
        footage = max(0.0, float(c.get("dur") or 0) - SAFE_TAIL)
        length = min(MAX_CLIP_LEN, w["dur_sec"], footage,
                     hard_end - w["out_start"])
        start = anchor_start(w, p.get("quoted"), length, hard_end, bounds)
        length = min(length, hard_end - start)
        if length < MIN_CLIP_LEN:
            dropped.append({"candidate_id": p["candidate_id"],
                            "why": f"אחרי העריכה נשאר חלון {length:.2f}ש — "
                                   f"מתחת ל-{MIN_CLIP_LEN}ש, זה הבהוב"})
            continue
        plan.append({
            "id": p["clip_id"], "path": paths.get(p["clip_id"]),
            "file": Path(str(paths.get(p["clip_id"], ""))).name,
            "candidate_id": p["candidate_id"], "role": "anchor",
            "insert_at": round(start, 2),
            "insert_end": round(start + length, 2),
            "clip_len": round(length, 2),
            "src_offset": round(max(0.0, (float(c.get("dur") or 0) - length) / 2.0), 2),
            "confidence": p["confidence"],
            "reason": p["reason"], "quoted": p["quoted"],
            "label": c.get("label"),
            "sentence": w["text"],
            "covers_stall": w["is_stalled"],
            "audio": "mute",
        })

    # ── סגירת הבהוב בין שני בירולים סמוכים ──────────────────────────────────
    # הראל, 25.7.26 (נמדד): "חזרה של 0.3-1.2ש לפנים בין שני בירולים היא לא
    # נשימה — היא הבהוב." שני כלים, בסדר הזה:
    #
    #   1. **החלקה קדימה של הקליפ המוקדם** בתוך החלון של עצמו, כך שהזנב שלו
    #      פוגש את תחילת הבא. חינמי: אורך הקליפ לא משתנה, ולכן אין תלות
    #      ב-footage. התנאי — הוא עדיין **מתחיל בתוך המשפט שבגללו נבחר**,
    #      עם חפיפה של ‎≥MIN_ANCHOR_OVERLAP שניות.
    #   2. **הארכה** של הקליפ המוקדם, ורק בתוך ה-footage שלו.
    #
    # מה שאסור: להזיז את הקליפ **הבא** אחורה. נמדד ב-v8.4 שזה סוגר את החור,
    # אבל הוא מנתק את הקליפ מהמילים שבגללן הוא נבחר — כלומר קונה רצף במחיר
    # בדיוק הדבר שהשכבה הזאת קיימת בשבילו. שארית שנשארת מדווחת, לא מוסתרת.
    face_gaps = []
    for i in range(len(plan) - 1):
        hole = round(plan[i + 1]["insert_at"] - plan[i]["insert_end"], 3)
        if not (0 < hole <= FLASH_GAP):
            continue
        c = cmap[plan[i]["id"]]
        w = wmap[plan[i]["candidate_id"]]
        footage = max(0.0, float(c.get("dur") or 0) - SAFE_TAIL)

        # 1 — החלקה קדימה, בלי לצאת מהעוגן
        latest_start = w["out_end"] - MIN_ANCHOR_OVERLAP
        want_start = plan[i + 1]["insert_at"] - plan[i]["clip_len"]
        new_start = min(want_start, latest_start)
        if new_start > plan[i]["insert_at"] + 0.01:
            plan[i]["insert_at"] = round(new_start, 2)
            plan[i]["insert_end"] = round(new_start + plan[i]["clip_len"], 2)
            plan[i]["slid"] = True

        # 2 — הארכה בתוך ה-footage
        max_end = plan[i]["insert_at"] + footage
        new_end = min(plan[i + 1]["insert_at"], max_end)
        if new_end > plan[i]["insert_end"] + 0.01:
            plan[i]["insert_end"] = round(new_end, 2)
            plan[i]["clip_len"] = round(new_end - plan[i]["insert_at"], 2)
            plan[i]["bridged"] = True

        rest = round(plan[i + 1]["insert_at"] - plan[i]["insert_end"], 3)
        if rest > 0.05:
            face_gaps.append({"after": plan[i]["label"], "at": plan[i]["insert_end"],
                              "gap": rest})
    for p in plan:                                  # אמצע-הקליפ אחרי שינוי אורך
        c = cmap[p["id"]]
        p["src_offset"] = round(max(0.0, (float(c.get("dur") or 0) - p["clip_len"]) / 2.0), 2)
    return plan, dropped, face_gaps


def pack_bed(bed_seq, plan, doc, clips, paths):
    """ממלא את החורים בין העוגנים בקליפי מצע, אחד אחרי השני, בלי לחזור לדובר.

    זה מה שהופך "שני בירולים מדויקים" ל"מבנה של סרטון המרה". שים לב מה
    **לא** קורה כאן: אין ניסיון להתאים קליפ מצע למשפט שמתחתיו. זו הנקודה —
    בקהל קר הרצף עצמו הוא המסר, וההתאמה-בכוח היא בדיוק מה שייצר בעבר
    "ראיון עם מתאמנת" על משפט של מחיר.

    מחזיר (items, used_clip_ids). הקוד מכבד את **סדר** הרשימה שהמודל נתן —
    זה הקצב שהוא תכנן — ומדלג על קליפ שכבר בשימוש כעוגן.
    """
    cmap = {c["clip_id"]: c for c in clips}
    used = {p["id"] for p in plan}
    # ── שלושה שערים שהיו מוצהרים ולא נאכפו (ביקורת Sol, 31.7.26) ──────────
    #   1. `MIN_CONF_BED` הוגדר כקבוע ולא נבדק — סף שאף אחד לא בודק אינו סף.
    #   2. אותו קליפ יכול היה להופיע פעמיים ברצף (הדה-דופ היה מול העוגנים בלבד).
    #   3. תווית כמעט-זהה פעמיים ברצף — הצופה קורא את זה כתקלה.
    queue, seen_lbl = [], {re.sub(r"\s*\(\d+\)\s*$", "", p.get("label") or "").strip()
                           for p in plan}
    for b in bed_seq:
        # פעימת trust אינה קליפ — אין לה clip_id, והיא עוברת את סינון
        # הבריכה כמות שהיא. בלי החריג הזה התפקיד היה נופל בשקט כאן.
        if str(b.get("beat") or "").lower() == "trust":
            queue.append(b)
            continue
        cid = b.get("clip_id")
        if cid not in cmap or cid in used:
            continue
        try:
            if float(b.get("confidence", 1.0)) < MIN_CONF_BED:
                continue
        except (TypeError, ValueError):
            continue
        lbl = re.sub(r"\s*\(\d+\)\s*$", "", cmap[cid].get("label") or "").strip()
        if lbl and lbl in seen_lbl:
            continue
        seen_lbl.add(lbl)
        used.add(cid)          # מונע כפילות **בתוך** הרצף, לא רק מול העוגנים
        queue.append(b)
    if not queue:
        return [], used

    # החורים שצריך למלא: מ-bed_start עד העוגן הראשון, בין עוגנים, ועד bed_end
    anchors = sorted(plan, key=lambda p: p["insert_at"])
    holes, cursor = [], float(doc["bed_start"])
    for a in anchors:
        if a["insert_at"] - cursor >= MIN_CLIP_LEN:
            holes.append((cursor, a["insert_at"]))
        cursor = max(cursor, a["insert_end"])
    if float(doc["bed_end"]) - cursor >= MIN_CLIP_LEN:
        holes.append((cursor, float(doc["bed_end"])))

    items, qi = [], 0
    for h0, h1 in holes:
        t = h0
        while h1 - t >= MIN_CLIP_LEN and qi < len(queue):
            b = queue[qi]; qi += 1
            # ── v9.9 — `trust`: חזרה לפנים **בכוונה**, לא חור ─────────────
            # לא כל 70% צריכים להיות מונטאז' אימונים. שעות · תנאי ביטול ·
            # מחיר הם רגעים שבהם הכוח הוא בפירוט המדויק, ופנים מוכרות אמון
            # טוב יותר מעוד דדליפט. עד כאן כל חזרה לפנים בתוך המצע נספרה
            # כליקוי — כלומר לתפקיד לגיטימי לא הייתה דרך להתקיים.
            if str(b.get("beat") or "").lower() == "trust":
                ln = min(TRUST_BEAT_LEN, h1 - t)
                if ln < MIN_CLIP_LEN:
                    continue
                items.append({
                    "id": None, "path": None, "file": None, "candidate_id": None,
                    "role": "trust", "insert_at": round(t, 2),
                    "insert_end": round(t + ln, 2), "clip_len": round(ln, 2),
                    "confidence": float(b.get("confidence") or 0.7),
                    "reason": str(b.get("reason") or "").strip(),
                    "label": "חזרה לפנים (trust beat)"})
                t = round(t + ln, 3)
                continue
            c = cmap[b["clip_id"]]
            footage = max(0.0, float(c.get("dur") or 0) - SAFE_TAIL)
            length = min(BED_CLIP_LEN, footage, h1 - t)
            # שארית שקטנה מאורך מינימלי לא תישאר כחור-פנים: הקליפ האחרון
            # בכל חור נמתח עד הסוף, בגבול ה-footage שלו.
            if 0 < (h1 - t - length) < MIN_CLIP_LEN:
                length = min(footage, h1 - t)
            if length < MIN_CLIP_LEN:
                qi -= 1
                break
            items.append({
                "id": b["clip_id"], "path": paths.get(b["clip_id"]),
                "file": Path(str(paths.get(b["clip_id"], ""))).name,
                "candidate_id": None, "role": "bed",
                # `proof` (מראה את הטענה) · `texture` (אווירה) — תיעוד התפקיד
                # שהבמאי ייעד, כדי ש-QA של הרצף יוכל לשפוט מבנה ולא רק גיוון.
                "beat": (str(b.get("beat") or "texture").lower()
                         if str(b.get("beat") or "").lower() in ("proof", "texture")
                         else "texture"),
                "insert_at": round(t, 2), "insert_end": round(t + length, 2),
                "clip_len": round(length, 2),
                "src_offset": round(max(0.0, (float(c.get("dur") or 0) - length) / 2.0), 2),
                "confidence": float(b.get("confidence") or 0.7),
                "reason": str(b.get("reason") or "").strip(),
                "label": c.get("label"), "covers_stall": False,
                "audio": "mute",
            })
            used.add(b["clip_id"])
            t = round(t + length, 3)
    return items, used


def close_small_holes(plan, clips, doc):
    """סוגר כל חור-פנים קצר מ-MIN_CLIP_LEN בתוך המצע.

    חור של 0.24ש בין שני בירולים אינו "חזרה לדובר" — הוא הבהוב, ובדיוק
    ההבהוב הזה הוא שהראה את המבט-למטה שהראל דיווח עליו (31.7.26): הבירול
    נגמר 0.17ש לפני סוף המשפט, וברווח הזה הוא מסתכל למטה.
    שני כלים, לפי סדר: הארכת הקודם בתוך ה-footage; ואז הקדמת הבא — חינם
    לקליף מצע (אין לו עוגן סמנטי), ומוגבל ל-0.5ש לעוגן.
    """
    if not plan:
        return plan
    cmap = {c["clip_id"]: c for c in clips}
    plan.sort(key=lambda p: p["insert_at"])
    bed_start = float(doc.get("bed_start", HOOK_GUARD))

    def _pass_holes():
        for i, p in enumerate(plan):
            prev_end = plan[i - 1]["insert_end"] if i else bed_start
            hole = round(p["insert_at"] - prev_end, 3)
            if not (0.01 < hole < MIN_CLIP_LEN):
                continue
            if i:                                    # 1 — הארכת הקודם
                q = plan[i - 1]
                c = cmap.get(q["id"], {})
                max_end = q["insert_at"] + max(0.0, float(c.get("dur") or 0) - SAFE_TAIL)
                new_end = min(p["insert_at"], max_end)
                if new_end > q["insert_end"] + 0.01:
                    q["insert_end"] = round(new_end, 2)
                    q["clip_len"] = round(new_end - q["insert_at"], 2)
                    q["bridged"] = True
                    hole = round(p["insert_at"] - q["insert_end"], 3)
            if hole <= 0.01:
                continue
            budget = hole if p.get("role") == "bed" else min(hole, 0.5)
            if budget > 0.01:                        # 2 — הקדמת הבא
                p["insert_at"] = round(p["insert_at"] - budget, 2)
                p["insert_end"] = round(p["insert_end"] - budget, 2)
                p["pulled_back"] = round(budget, 2)

    _pass_holes()
    # ── הזנב: חור בין הבירול האחרון לסוף המצע ──────────────────────────────
    # נתפס בבדיקה ולא בעין (31.7.26): המעבר על החורים בודק כל פריט מול מה
    # שלפניו, ולכן **אחרי האחרון אין מי שיבדוק**. נשארה הבזקת-פנים של 0.28ש
    # בדיוק לפני ה-CTA — אותה משפחת ליקוי כמו הסליבר שהראל דיווח עליו.
    bed_end = doc.get("bed_end")
    if bed_end is not None and plan:
        last = plan[-1]
        tail = round(float(bed_end) - last["insert_end"], 3)
        if 0.01 < tail < MIN_CLIP_LEN:
            c = cmap.get(last["id"], {})
            footage = max(0.0, float(c.get("dur") or 0) - SAFE_TAIL)
            room = round(last["insert_at"] + footage - last["insert_end"], 3)
            grow = min(tail, max(0.0, room))
            if grow > 0.01:
                last["insert_end"] = round(last["insert_end"] + grow, 2)
                last["clip_len"] = round(last["insert_end"] - last["insert_at"], 2)
                last["bridged"] = True
                tail = round(float(bed_end) - last["insert_end"], 3)
            # מה שנשאר נסגר בהזזת הקליפ האחרון קדימה — חינם לקליף מצע, ולעוגן
            # מותר עד 0.5ש (מעבר לזה הוא מתנתק מהמילים שבגללן נבחר).
            budget = tail if last.get("role") == "bed" else min(tail, 0.5)
            if budget > 0.01:
                last["insert_at"] = round(last["insert_at"] + budget, 2)
                last["insert_end"] = round(last["insert_end"] + budget, 2)
                last["pushed_forward"] = round(budget, 2)
                _pass_holes()   # ההזזה פותחת חור מאחור — סוגרים אותו מיד

    for p in plan:                                   # אמצע-הקליפ אחרי שינויים
        c = cmap.get(p["id"], {})
        p["src_offset"] = round(max(0.0, (float(c.get("dur") or 0) - p["clip_len"]) / 2.0), 2)
    return plan


def _covers_cut(p, b):
    """האם הבירול מכסה את הגבול `b` באמת — כלומר חוצה אותו בשני הכיוונים
    ביותר מ-CUT_OVERHANG. חצייה קטנה מזה אינה כיסוי: מנוע הרינדור מפצל את
    הקליפ בגבול, מוחק שבר קצר מ-0.01ש, והפריים שעל הגבול נשאר חשוף."""
    return (p["insert_at"] <= b - CUT_OVERHANG + 1e-6
            and p["insert_end"] >= b + CUT_OVERHANG - 1e-6)


def snap_to_cuts(plan, keeps, clips, doc, out_dur, cta_guard=CTA_GUARD):
    """מיישר קצה בירול לגבול חיתוך, כך שלא נשארת פיסת-דובר ביניהם.

    **הליקוי מוגדר על הגבול, לא על הקליפ.** גבול חיתוך שאינו מכוסה, ובמרחק
    קצר ממנו יש קצה בירול ⇒ הצופה רואה שני אירועים ויזואליים בשבריר שנייה:
    הבירול נגמר, ומיד הקאט. גבול שהבירול חוצה אותו — הקאט מוסתר לגמרי, אין
    מה ליישר ואין מה לדווח.

    למה `FLASH_GAP` ולא סף חדש: זו אותה מדידה של הראל מ-25.7.26 ("חזרה של
    0.3-1.2ש לפנים בין שני בירולים היא לא נשימה — היא הבהוב"), רק שה"בירול
    הבא" הוחלף בקאט. מבחינת העין זה אותו אירוע, ולכן אותו סף.

    כלי אחד בלבד: **הארכת הקליפ אל מעבר לגבול**, בתוך ה-footage שלו. אין כאן
    הזזה — הזזה שסוגרת סליבר בצד אחד פותחת אותו בצד השני, וזה בדיוק המנגנון
    של "תיקנו ועדיין קופץ". ואין כאן הארכה חלקית: קצה שנעצר לפני הגבול רק
    מזיז את הסליבר ונראה כאילו טופל. מה שה-footage לא מאפשר יוצא כ-`cut_slivers`
    — חוב צילום מדווח, לא כישלון מוסתר.

    מחזיר (plan, slivers).
    """
    if not plan or len(keeps) < 2:
        return plan, []
    cmap = {c["clip_id"]: c for c in clips}
    lo = float(doc.get("bed_start") or HOOK_GUARD)
    hi = float(doc.get("bed_end") or (out_dur - cta_guard))
    plan.sort(key=lambda p: p["insert_at"])
    slivers = []

    for b in cut_boundaries(keeps):
        if not (lo <= b <= hi):
            continue                                  # הוק ו-CTA מוגנים
        if any(_covers_cut(p, b) for p in plan):
            continue                                  # הקאט כבר מוסתר
        best = None                                   # (מרחק, אינדקס, צד)
        for i, p in enumerate(plan):
            if p["insert_end"] < b + CUT_OVERHANG:
                d, side = max(0.0, round(b - p["insert_end"], 3)), "end"
            elif p["insert_at"] > b - CUT_OVERHANG:
                d, side = max(0.0, round(p["insert_at"] - b, 3)), "start"
            else:
                continue
            if d < FLASH_GAP and (best is None or d < best[0]):
                best = (d, i, side)
        if best is None:
            continue        # אין בירול בקרבת הגבול — הקאט עומד בפני עצמו, וזה תקין

        d, i, side = best
        p = plan[i]
        c = cmap.get(p["id"], {})
        need = round(d + CUT_OVERHANG, 3)
        off = float(p.get("src_offset") or 0.0)
        if side == "end":       # מאריכים לתוך זנב ה-footage; הראש לא זז
            room = float(c.get("dur") or 0) - SAFE_TAIL - off - p["clip_len"]
            nxt = plan[i + 1]["insert_at"] if i + 1 < len(plan) else hi + CUT_OVERHANG
            room = min(room, nxt - p["insert_end"])
        else:                   # מאריכים לתוך ראש ה-footage; הזנב לא זז
            room = min(off, p["insert_at"] - (plan[i - 1]["insert_end"] if i else lo))
        if room + 1e-6 < need:
            slivers.append({
                "at_cut": round(b, 2), "side": side, "sec": d,
                "label": p.get("label"), "role": p.get("role"),
                "why": f"חסרים {round(need - max(0.0, room), 2)}ש כדי לחצות את "
                       f"הגבול — הקליפ קצר מדי או שכן צמוד"})
            continue
        if side == "end":
            p["insert_end"] = round(p["insert_end"] + need, 2)
        else:
            p["insert_at"] = round(p["insert_at"] - need, 2)
            p["src_offset"] = round(off - need, 2)
        p["clip_len"] = round(p["insert_end"] - p["insert_at"], 2)
        p["snapped_to_cut"] = round(b, 2)
    return plan, slivers


def coverage(plan, out_dur):
    """אחוז הסרטון שמכוסה בבירול — נמדד על התוכנית, מאוחדת-חפיפות."""
    spans = sorted((p["insert_at"], p["insert_end"]) for p in plan)
    tot, cur_s, cur_e = 0.0, None, None
    for s, e in spans:
        if cur_e is None or s > cur_e + 1e-6:
            if cur_e is not None:
                tot += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        tot += cur_e - cur_s
    return round(100.0 * tot / max(0.01, out_dur), 1)


def face_holes(plan, doc, trust=None):
    """חורי-פנים בתוך חלון המצע. במצב מצע כל חור הוא ליקוי, לא נשימה —
    ולכן הם נמדדים ומדווחים במפורש ולא נבלעים.

    ‏**חריג אחד, v9.9:** פעימת `trust` היא חזרה לפנים שהבמאי ביקש במפורש
    (מחיר · תנאי ביטול · שעות). היא נספרת בציר ככיסוי — אחרת התפקיד הזה
    היה מדווח כליקוי בכל פעם, ואף במאי לא היה בוחר בו.
    """
    if doc.get("mode") != "continuous_bed" or not plan:
        return []
    plan = list(plan) + [t for t in (trust or [])]
    out, cursor = [], float(doc["bed_start"])
    for p in sorted(plan, key=lambda x: x["insert_at"]):
        h = round(p["insert_at"] - cursor, 3)
        if h > 0.05:
            out.append({"from": round(cursor, 2), "to": p["insert_at"], "sec": h})
        cursor = max(cursor, p["insert_end"])
    h = round(float(doc["bed_end"]) - cursor, 3)
    if h > 0.05:
        out.append({"from": round(cursor, 2), "to": doc["bed_end"], "sec": h})
    return out


def shot_list(windows, plan, model_skipped, doc):
    """כל `skipped` הוא **חוב תוכן** לספריית הבירולים, לא רק הערה בדוח.

    (ביקורת Sol, 31.7.26.) משפט שלא מצא קליפ הוא בדיוק המקום שבו הקטלוג
    חסר — ובסרטון הזה זו רשימה קונקרטית: כניסה בטביעת אצבע · רחבה פנויה
    בשעות הצהריים · מתאמן עם אוזניות באימון עצמאי. בלי הרשימה הזאת אותו
    חוסר יחזור בכל סרטון המרה הבא, והמערכת "תסתדר" עם מצע גנרי.
    """
    covered = {p.get("candidate_id") for p in plan if p.get("candidate_id")}
    why = {s.get("candidate_id"): s.get("why", "") for s in (model_skipped or [])}
    out = []
    for w in windows:
        if w["candidate_id"] in covered:
            continue
        out.append({"candidate_id": w["candidate_id"],
                    "sentence": w["text"],
                    "at": w["out_start"],
                    "why_no_clip": why.get(w["candidate_id"], "לא הוחלט"),
                    "needed_shot": f"שוט שמאייר: «{w['text'][:70]}»"})
    return out


def coverage_verdict(cov, doc):
    """שער הכיסוי. `coverage_ok` הישן עבר כבר ב-59.5% מול יעד 70% —
    זו לא בדיקה, זו הנחה (ביקורת Sol). הסף עכשיו הדוק ומדווח בשלוש רמות."""
    target = doc.get("coverage_target_pct")
    if not target:
        return {"ok": True, "level": "n/a"}
    ratio = cov / float(target)
    # 0.85 היה בדיוק המספר שהפך "59.5% מול יעד 70%" לעובר. הסף הועלה ל-0.90
    # כדי שהמילה "עובר" תשמור על משמעות.
    level = "ok" if ratio >= 0.95 else ("warn" if ratio >= 0.90 else "fail")
    return {"ok": level != "fail", "level": level, "coverage_pct": cov,
            "target_pct": target, "ratio": round(ratio, 3),
            "detail": (f"כיסוי {cov}% מול יעד {target}% — "
                       + {"ok": "בתוך היעד",
                          "warn": "מתחת ליעד אך בטווח קביל",
                          "fail": "רחוק מהיעד; מבנה ההמרה לא נבנה"}[level])}


def is_cloud_only(p):
    """קובץ iCloud שלא ירד לדיסק. `st_blocks == 0` על קובץ שגודלו > 0 —
    זו הסימנייה של placeholder, וגם `.<name>.icloud` לצדו."""
    f = Path(p)
    try:
        st = f.stat()
    except OSError:
        return (f.parent / f".{f.name}.icloud").exists()
    return (st.st_size > 0 and st.st_blocks == 0) or \
           (f.parent / f".{f.name}.icloud").exists()


def materialize(paths, timeout=180.0, log=None):
    """מוריד קבצי בירול מ-iCloud **לפני** הרינדור.

    שורש שנמדד 31.7.26: הרינדור נתקע 3.5 דקות על **0% CPU**. זה לא נראה
    ככשל — לא שגיאה, לא לוג, פשוט תהליך שלא מתקדם. הסיבה: ספריית הבירולים
    יושבת ב-iCloud Drive, ו-ffmpeg נחסם על ה-`read()` הראשון עד שהקובץ יורד.
    עם 2 בירולים זה לא נראה כי שניהם היו מקומיים; עם 12 רובם היו בענן.
    **המסקנה: ‏0% CPU לאורך זמן הוא סימפטום של I/O חסום, לא של לולאה.**

    ההורדה כאן סינכרונית ומדודה, כך שהזמן נזקף לשלב שלו ולא נעלם ברינדור.
    """
    import time as _t
    todo = [p for p in dict.fromkeys(paths) if p and is_cloud_only(p)]
    rep = {"checked": len(set(filter(None, paths))), "cloud_only": len(todo),
           "downloaded": 0, "failed": [], "secs": 0.0}
    if not todo:
        return rep
    t0 = _t.time()
    try:
        import subprocess
        subprocess.run(["brctl", "download", *todo], capture_output=True,
                       timeout=max(5.0, timeout / 2))
    except Exception:
        pass                      # brctl הוא זרז; הקריאה למטה היא מה שמבטיח
    for p in todo:
        try:
            with open(p, "rb") as fh:          # קריאה מלאה = מימוש מובטח
                while fh.read(1 << 20):
                    if _t.time() - t0 > timeout:
                        raise TimeoutError(f"מעל {timeout:.0f}ש")
            rep["downloaded"] += 1
        except Exception as e:
            rep["failed"].append({"path": str(p), "err": str(e)[:120]})
    rep["secs"] = round(_t.time() - t0, 1)
    if log is not None:
        log.append(f"materialize: {rep['downloaded']}/{rep['cloud_only']} "
                   f"קבצי בירול הורדו מ-iCloud ב-{rep['secs']}ש")
    return rep


def write_plan(W, plan, meta):
    """`broll_plan.json` — הפורמט שמנוע הרינדור כבר יודע לקרוא.
    `source: director` הוא הסימן לצינור הגימור **לא** להריץ בחירה אוטומטית
    מעל ההחלטה הזאת, גם כשהתוכנית ריקה: אפס בירולים היא החלטה, לא כישלון."""
    doc = {"source": "director", "schema_version": 1, "plan": plan,
           "picked": [p["label"] for p in plan],
           "overlay_args": [x for p in plan
                            for x in ["--overlay", p["path"], str(p["insert_at"]),
                                      str(p["insert_end"]), "--src-offset",
                                      str(p["src_offset"])]],
           **meta}
    (Path(W) / "broll_plan.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc
