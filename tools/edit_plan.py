#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""edit_plan.py — פאס 3: אימות תוכנית עריכה וקומפילציה ל-EDL (V2).

התפקיד כאן הוא **ביצוע בלבד — אפס שיפוט**. התוכנית (`edit_plan.json`) מגיעה
מה-Director; כאן היא נבדקת מול הפיזיקה והקאנון, ואז מקומפלת ל-`edl.json`
בסכמה הקיימת. מרגע ה-EDL והלאה — `edl_cut`, `tighten`, מנוע הרינדור,
`review-app`, revisions ונעילות — **הכל נשאר כמו שהוא**. זו נקודת התאימות
שמאפשרת להחליף את מנוע ההחלטה בלי לגעת במנוע הביצוע.

═══════════════════════════════════════════════════════════════════════════
למה validator ולא "לסמוך על המודל"
═══════════════════════════════════════════════════════════════════════════
הקאנון של המערכת נכתב מדם: "silencedetect לבד לא מספיק לגבול-קאט ידני" —
הרחבת cut על סמך אנרגיה בלבד חתכה את סוף המילים "חושבים" ו"אחרת". הכלל
שנקבע: **כל גבול-קאט חייב להצטלב מול תזמוני-מילה, מרווח ביטחון ≥0.1ש.**
מודל לא פוטר מזה — הוא מגדיל את הצורך. לכן כל תוכנית עוברת כאן שער קשיח
לפני שנוגעים במדיה, והכשל הוא exit≠0, לא אזהרה.

exit: 0 = תקין · 1 = הפרות קשיחות · 2 = שגיאת קלט

שימוש:
  python3 tools/edit_plan.py validate --workdir W
  python3 tools/edit_plan.py compile  --workdir W [--out edl.json] [--backup]
  python3 tools/edit_plan.py report   --workdir W        # EDITING_REPORT.md
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

WORD_MARGIN = 0.10      # מרווח ביטחון מגבול מילה — הלקח מ-20.7
MIN_CUT = 0.06          # cut קצר מזה נזרק (תואם edl_build)
MIN_KEEP = 0.10         # keep קצר מזה = sliver יתום
MAX_JUMPS_PER_5S = 2    # מגבלת צפיפות הקאנון
CTA_GUARD = 8.0
AUTO_APPLY_CONF = 0.85  # מעל זה מוחל אוטומטית
SUGGEST_CONF = 0.60     # מתחת לזה — הצעה בלבד, לא מוחל
# ── תקציב השקט — נגזר ממדידה של 19 סרטונים שהראל אישר ופרסם (30.7.26) ──
# הניסיון הראשון שלי היה 8%/12%. זה היה ניחוש, והמדידה הפריכה אותו: הוא גם
# בלתי-אפשרי פיזית (30 פערים × רצפה 0.20ש = 6.0ש ⇒ 11.7% במקרה הטוב) וגם לא
# מתאר את מה שהראל בפועל מאשר.
#
#   19 סרטונים מאושרים · silencedetect ‎-40dB/0.15ש על EXPORT_TIGHT:
#     חציון שקט 21.6% · טווח 13.2%–31.7%
#     הטובים:  מי-אמר-שמאוחר 13.2% (ארוכה 0.44ש) · סקאלת-הבריאות 14.7% (0.66ש)
#     שנדחה:   התוצר שלי 28.1% (ארוכה 0.88ש)
#
# **המבחין החזק אינו האחוז אלא הפאוזה הארוכה.** בכל הסרטונים הטובים היא
# ≤0.66ש; בכל אלה שנשמעים כבדים היא 0.84-1.10ש. לכן היא שער בפני עצמה.
# ⚠️ תיקון סף (30.7.26, אחרי שהשערים נכנסו לסתירה):
# הספים לעיל נמדדו על **התוצר** (‏silencedetect ‎-40dB, שכולל את ריפוד הדעיכה
# משני צידי כל פער). הצבתי אותם כמות-שהם על **התוכנית**, שמודדת פערי-מילים
# נקיים. זה שני דברים שונים — פער-מילים של 0.60ש נמדד בתוצר כ-0.70ש בערך.
# התוצאה: השער דרש 22% בתוכנית כדי להשיג 22% בתוצר, וזה בלתי אפשרי יחד עם
# תקציב התפרים. הספים כאן הם צד-תוכנית; האימות האמיתי הוא המדידה על הפלט.
# הטווח שהראל מאשר בפועל: 13.2%-31.7%, חציון 21.6%.
PAUSE_BUDGET_WARN_PCT = 19.0    # מתחת לחציון שלו
PAUSE_BUDGET_HARD_PCT = 26.0    # הרבע העליון של מה שהוא כן אישר
MAX_KEPT_GAP = 0.78             # ‎~0.65 בתוצר אחרי ריפוד הדעיכה
# ── רציפות תנוחה (30.7.26) ──
# נמדד על 25 חיתוכים בתוצר שהראל דיווח עליו "יש רגע שאני מסתכל למטה":
# חציון pose_delta 0.018 · אחוזון-90 0.094 · החיתוך שלפני ה-CTA 0.104.
POSE_JUMP_WARN = 0.075
POSE_JUMP_HARD = 0.130
# פאוזה על תמונה קפואה נתפסת כתקיעה. נמדד: אזור ה"תקיעה" שדווח היה
# תנועה 2.04-2.27 מול חציון 3.84 ⇒ ‎~0.57 מהחציון.
STALL_MOTION_NORM = 0.70
STALL_MIN_PAUSE = 0.25
# ── פער שהדובר זז לאורך כולו הוא שוט, לא שתיקה (17.8.26) ──
# MAX_KEPT_GAP נגזר מ-19 סרטונים לפי "פאוזות שנשמעו כבדות". כל אותן פאוזות
# היו **שקט על תמונה כמעט סטטית**. פער שבו הגוף עובר מסלול רציף הוא ההפך
# הגמור: יש בו מה לראות, והוא נקרא כפעולה ולא כהשתהות.
# השורש: "בריאות-לקום-מכיסא" gap_0003 — הדובר קם מהכיסא בתוך הפער, והראש
# עולה בפריים ברצף מונוטוני (y: 0.417→0.478→0.398→0.283→0.163→0.108).
# מכיוון שהמסלול רציף, **ככל שמשאירים פחות אוויר הקפיצה גדלה**: 0.268 ב-0.55ש,
# 0.146 ב-0.60-0.78ש, 0.087 ב-0.82ש. כלומר שני השערים דחפו לכיוונים הפוכים
# ולא נשאר אף ערך חוקי — שלושה סבבי במאי בלי תוכנית.
# הרחבה זהירה בלבד: רק כשהתנועה מוכחת (pose_range מעל פי-10 מהחציון הטיפוסי
# 0.02), רק עד KEEP_NUDGE מעל התקרה, ורק כששער התנוחה עצמו עובר. פער שקט
# על תמונה קפואה לא נהנה מזה לעולם — שם התקרה נשארת 0.78 והרצפה 0.25.
MOVING_GAP_POSE_RANGE = 0.25
MAX_KEPT_GAP_MOVING = 0.84
# כמה מותר לקוד לשנות את אורך הפאוזה שהבמאי ביקש, כדי למזער קפיצת תנוחה.
# 0.06ש אינן נשמעות; 0.11 בתנוחה נראות.
KEEP_NUDGE = 0.06
# ── תקציב תפרים — נגזר מאותם סרטונים מאושרים (30.7.26) ──
# המדידה שהפריכה את ההנחה שלי: מדדתי שיא הבדל-פריים בכל תפר, ביחס לחציון
# הסרטון. אצל הראל: 1.0-6.3 (‏2-12 חיתוכים לסרטון). אצלי: **חציון 7.9, מקס
# 35.4, עם 24 חיתוכים ב-47ש**. אופטימיזציה לאחוז-שקט דחפה אותי לגזום כל פער,
# וכל גזימה של 0.2ש היא תפר נראה על שוט דיבור סטטי.
#   0.038 · 0.072 · 0.081 · 0.094 · 0.115 · 0.178 · 0.191  ← חיתוכים/שנייה אצלו
# **קיצוץ 0.43→0.22 חוסך 0.21ש ועולה תפר. זו עסקה גרועה.**
CUTS_PER_SEC_WARN = 0.16
CUTS_PER_SEC_HARD = 0.24
MIN_SAVING_PER_CUT = 0.50       # מתחת לזה — לא שווה תפר
# ── תפר מתחת למיטת בירול אינו תפר נראה (21.8.26, פידבק אלי) ──
# אלי על 8 סרטוני הממומן: "כל שנייה שאתם לא מדברים ועושים תנועה סתם בלי דיבור.
# יש שתיקות יותר מדי של מילי שנייה כזה, לא צריך."
# מדידה על אותם 8: אפס פערים מעל 0.6ש, אבל **29 פערים בטווח 0.25-0.48ש**
# שמצטברים ל-10.1 שניות אוויר מת. מתוכם — **17 (6.1ש) נופלים מתחת למיטת
# הבירול** ו-12 (4.1ש) חשופים על פני הדובר.
# השורש: כל הרציונל של CUTS_PER_SEC ו-MIN_SAVING_PER_CUT הוא "כל תפר הוא
# קפיצה נראית על שוט דיבור סטטי" — וזה כויל על סרטוני **ערך**. בתוכן המרה
# רצה דוקטרינת continuous_bed, ושם התפר מוסתר מאחורי הבירול. המערכת שילמה
# מחיר של תפר-נראה על 17 חיתוכים שבהם אין מה לראות, ולכן ויתרה עליהם.
# לכן: תפר שנופל בתוך מיטת הבירול לא נספר בתקציב התפרים, וסף החיסכון שלו
# יורד. תפר חשוף ממשיך בדיוק כמו קודם — שם הקליברציה של הראל תקפה.
MIN_SAVING_PER_CUT_COVERED = 0.18   # תפר מוסתר — שווה גם על חיסכון קטן
BED_EDGE_MARGIN = 0.20              # תפר קרוב לקצה המיטה עדיין עלול להיחשף

ACTIONS = {"cut", "keep", "tighten_to", "keep_last", "move_to_open", "broll", "suggest_only"}
REQUIRED = ("candidate_id", "action", "reason", "confidence")


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def _bed_intervals(W):
    """מקטעי הבירול בציר התוצר. ריק = אין כיסוי ⇒ כל תפר נחשב חשוף.

    v9.20 (פידבק אלי 21.8.26). מקור: broll_plan.json שכבר קיים בתיקייה במעבר
    השני. במעבר הראשון הקובץ עדיין לא קיים והפונקציה מחזירה [] — כלומר
    ההתנהגות זהה לחלוטין לקודם. אין כאן הימור על כיסוי עתידי.
    """
    bp = jload(Path(W) / "broll_plan.json") or {}
    out = []
    for p in bp.get("plan", []) or []:
        try:
            s, e = float(p["start"]), float(p["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if e - s > 2 * BED_EDGE_MARGIN:
            out.append((s + BED_EDGE_MARGIN, e - BED_EDGE_MARGIN))
    return out


def _in_bed(t, bed):
    return any(s <= t <= e for s, e in bed)


def _cut_seam_covered(cut_start, keeps, bed):
    """האם התפר שנוצר מהחיתוך הזה נופל מתחת לבירול (בציר התוצר)."""
    if not bed:
        return False
    acc = 0.0
    for k in keeps:
        ks = float(k["start"] if isinstance(k, dict) else k[0])
        ke = float(k["end"] if isinstance(k, dict) else k[1])
        if ks >= cut_start:
            break
        acc += ke - ks
    return _in_bed(round(acc, 3), bed)


def load(workdir):
    W = Path(workdir)
    plan = jload(W / "edit_plan.json")
    cands = jload(W / "candidates.json")
    # ⚠️ חייב להיות **אותו** מקור-מילים ש-`candidates.py` בנה ממנו את המרחב.
    # אם המרחב נבנה על גבולות מוצמדים-לאנרגיה והאימות נעשה על הגבולות המרופדים
    # של Whisper — כל חיתוך תקין ייפסל כ"נוחת בתוך מילה", וזה כשל שקט שמחזיר
    # את המערכת בדיוק לנקודה שממנה יצאנו.
    words = jload(W / "words_snapped.json") or jload(W / "whisper_raw.json") or []
    if not plan:
        raise SystemExit("[2] אין edit_plan.json")
    if not cands:
        raise SystemExit("[2] אין candidates.json")
    return W, plan, cands, sorted(words, key=lambda w: float(w["start"]))


# ═══════════════════════════════════════════════════════ validator
def validate(workdir, verbose=True):
    W, plan, cands, words = load(workdir)
    by_id = {c["candidate_id"]: c for c in cands["candidates"]}
    total = float(cands["source"]["total_dur"])
    hard, warn = [], []

    def H(msg):
        hard.append(msg)

    def Wn(msg):
        warn.append(msg)

    decs = plan.get("decisions") or []
    if not decs:
        H("התוכנית ריקה — אין decisions")

    seen = set()
    for i, d in enumerate(decs):
        tag = f"decision[{i}] {d.get('candidate_id', '?')}"
        for k in REQUIRED:
            if d.get(k) in (None, ""):
                H(f"{tag}: חסר שדה חובה '{k}' — כל החלטה חייבת נימוק וביטחון")
        cid = d.get("candidate_id")
        if cid not in by_id:
            H(f"{tag}: candidate_id לא קיים ב-candidates.json")
            continue
        if cid in seen:
            H(f"{tag}: החלטה כפולה על אותו מועמד")
        seen.add(cid)
        act = d.get("action")
        if act not in ACTIONS:
            H(f"{tag}: action לא חוקי '{act}'")
        try:
            conf = float(d.get("confidence", -1))
        except (TypeError, ValueError):
            conf = -1
        if not (0.0 <= conf <= 1.0):
            H(f"{tag}: confidence חייב להיות 0..1")
        if len(str(d.get("reason", ""))) < 12:
            Wn(f"{tag}: נימוק קצר מדי — 'הסבר כל חיתוך' הוא חוק, לא המלצה")
        if act == "tighten_to":
            v = d.get("value")
            c = by_id[cid]
            if v is None:
                H(f"{tag}: tighten_to בלי value")
            else:
                gap = float(c["features"].get("gap_sec", 0))
                if float(v) > gap + 0.001:
                    H(f"{tag}: tighten_to {v}ש גדול מהפער עצמו ({gap}ש)")
                # ── רצפת הפיזיקה ──
                # ה-keep מתחלק לשני הצדדים, ולכן כל צד מקבל v/2. אם v/2 קטן
                # מ-WORD_MARGIN, גבול החיתוך נוחת קרוב מדי למילה השכנה — בדיוק
                # הכשל שהקאנון מתעד ("silencedetect לבד לא מספיק"). המשמעות:
                # **הערך המינימלי הוא 2×WORD_MARGIN.** זה גם ההסבר לכך ש-v1
                # בחר 0.22ש כברירת מחדל — זו הרצפה הפיזית ועוד 0.02 מרווח,
                # לא מספר שרירותי.
                if 0 <= float(v) < 2 * WORD_MARGIN:
                    H(f"{tag}: tighten_to {v}ש מתחת לרצפה הפיזית "
                      f"({2 * WORD_MARGIN}ש = 2×{WORD_MARGIN} מרווח מילה) — "
                      f"כל צד היה מקבל {float(v)/2:.3f}ש בלבד")
                if float(v) < 0:
                    H(f"{tag}: tighten_to שלילי")

    # ── פיזיקה: אף **גבול** לא נוחת בתוך מילה ──
    # ההבחנה קריטית ונלמדה מכשל של ה-validator עצמו: חיתוך שמכיל מילים בשלמותן
    # הוא הסרת תוכן מכוונת (משפט שלם), ואילו גבול שנוחת *בתוך* מילה הוא הבאג
    # שהקאנון מתעד — קאט שחתך את סוף המילים "חושבים" ו"אחרת". לכן:
    #   · חפיפה חלקית (גבול בתוך מילה)  → HARD
    #   · הכלה מלאה של מילים            → מותר, אבל חייב להיות מוצהר
    #   · גבול קרוב מדי למילה שכנה      → HARD (מרווח WORD_MARGIN)
    cuts = plan_to_cuts(plan, by_id)
    dec_by_id = {d["candidate_id"]: d for d in decs}
    for (s, e, cid) in cuts:
        if e - s < MIN_CUT:
            Wn(f"{cid}: חיתוך זניח ({e - s:.3f}ש) — ייזרק")
        contained = []
        for w in words:
            ws, we = float(w["start"]), float(w["end"])
            if we <= s or ws >= e:
                # לא בתוך החיתוך — נבדק רק המרווח מהגבול
                # ‏EPS: השוואת צפים. `best_split` מייצר גבול במרחק **בדיוק**
                # WORD_MARGIN, ו-0.09999999999999964 < 0.10 היה פוסל אותו.
                if (0 < s - we < WORD_MARGIN - 1e-6) or (0 < ws - e < WORD_MARGIN - 1e-6):
                    d = dec_by_id.get(cid, {})
                    if d.get("action") != "cut":
                        H(f"{cid}: גבול חיתוך {s:.2f}-{e:.2f} קרוב מדי למילה "
                          f"'{w['word']}' ({ws:.2f}-{we:.2f}) — נדרש ≥{WORD_MARGIN}ש")
                        break
                continue
            if ws < s < we or ws < e < we:
                H(f"{cid}: גבול חיתוך {s:.2f}-{e:.2f} נוחת **בתוך** המילה "
                  f"'{w['word']}' ({ws:.2f}-{we:.2f}) — זה הבאג שחתך את סוף המילים "
                  f"'חושבים'/'אחרת' ב-20.7")
                break
            contained.append(str(w["word"]))
        if contained:
            d = dec_by_id.get(cid, {})
            declared = (d.get("action") == "cut"
                        and (by_id[cid]["kind"] == "sentence_span"
                             or d.get("t_start") is not None))
            if not declared:
                H(f"{cid}: החיתוך מוחק {len(contained)} מילים בשלמותן "
                  f"({' '.join(contained[:5])}…) אבל אינו מוצהר כהסרת תוכן")
            else:
                Wn(f"{cid}: הסרת תוכן מוצהרת — {len(contained)} מילים "
                   f"({' '.join(contained[:6])}…)")

    # ── קאנון ──
    # "Hook קדוש" — אבל **שקט לפני המילה הראשונה אינו הוק.** להפך: קיצור שלו
    # מקדים את ההוק במקום לפגוע בו. נמדד 30.7.26 — 0.68ש דד-אייר פתחו את התוצר,
    # והכלל הזה הוא שחסם את הבמאי מלגעת בהם. החריג צר בכוונה: החיתוך חייב
    # להסתיים **לפני** תחילת המילה הראשונה.
    first_word = float(words[0]["start"]) if words else 0.0
    hook_cut = [c for c in cuts if c[0] < 0.5 and c[1] > first_word + 1e-6]
    if hook_cut:
        H(f"Hook קדוש — יש חיתוך שמתחיל ב-{hook_cut[0][0]:.2f}ש ונכנס לדיבור")
    pre_speech = [c for c in cuts if c[0] < 0.5 and c[1] <= first_word + 1e-6]
    for c in pre_speech:
        Wn(f"{c[2]}: קוצץ {c[1]-c[0]:.2f}ש שקט פתיחה לפני המילה הראשונה "
           f"({first_word:.2f}ש) — מותר, ההוק עצמו לא נגע")
    cta0 = total - CTA_GUARD
    for (s, e, cid) in cuts:
        if e > cta0 and (e - s) > 0.8:
            Wn(f"{cid}: חיתוך של {e - s:.2f}ש באזור ה-CTA ({CTA_GUARD}ש אחרונות)")

    keeps = cuts_to_keeps(total, cuts)
    for k in keeps:
        if k["end"] - k["start"] < MIN_KEEP:
            H(f"sliver יתום {k['start']:.2f}-{k['end']:.2f} — למזג עם השכן")
    for i in range(len(keeps) - 1):
        if keeps[i + 1]["start"] < keeps[i]["end"] - 0.001:
            H("keep_segments אינם מונוטוניים")

    # צפיפות קפיצות
    bounds = sorted(c[0] for c in cuts)
    for i, b in enumerate(bounds):
        n = len([x for x in bounds if b <= x < b + 5.0])
        if n > MAX_JUMPS_PER_5S:
            Wn(f"צפיפות: {n} קפיצות בחלון 5ש שמתחיל ב-{b:.1f}ש (מקס {MAX_JUMPS_PER_5S})")

    # ── תקציב השקט (30.7.26 — הראל: "יותר מדי שתיקות והכל") ──
    # שני ממצאים שהובילו לשער הזה, שניהם נמדדו על תוצר אמיתי:
    #   1. תוצר של הבמאי יצא **28.1% שקט ב-30 מקטעים** — 15.43ש מתוך 54.97ש.
    #   2. "המוזיקה רועשת מדי" הוא אותו ליקוי: המוזיקה יושבת 21.5dB מתחת לדיבור
    #      (מפלס תקין), אבל היא נחשפת במלואה ב-21 פערים ≥0.35ש. פחות שקט =
    #      פחות מוזיקה חשופה. לכן זה שער אחד ולא שניים.
    # הביקורת של המבקר לא מספיקה כאן — שיפוט על "יותר מדי שקט" הוא בדיוק מה
    # שצריך להיות מספר. שער, לא הערה.
    kept_gaps = []
    for c in cands["candidates"]:
        if c["kind"] != "inter_word_gap":
            continue
        cs, ce = float(c["t_start"]), float(c["t_end"])
        # כמה מהפער הזה שרד את החיתוכים
        remain = ce - cs
        for (s, e, _) in cuts:
            remain -= max(0.0, min(ce, e) - max(cs, s))
        if remain > 0.01:
            # פער שהגוף עובר בו מסלול רציף אינו שתיקה אלא שוט — התקרה שחלה
            # עליו רחבה יותר. ראה MOVING_GAP_POSE_RANGE. הוא עדיין נספר
            # במלואו בתקציב השקט; ההקלה היא על התקרה הנקודתית בלבד.
            pr = (c.get("features") or {}).get("pose_range_in_gap")
            moving = pr is not None and float(pr) >= MOVING_GAP_POSE_RANGE
            kept_gaps.append((cs, round(remain, 3), moving))
    pause_total = round(sum(g for _, g, _ in kept_gaps), 2)

    kept = round(sum(k["end"] - k["start"] for k in keeps), 2)
    pause_pct = round(100.0 * pause_total / kept, 1) if kept else 0.0
    longest = max([g for _, g, _ in kept_gaps], default=0.0)
    # החריגה הנמדדת: הארוך מבין הפערים ביחס לתקרה **שלו**.
    gap_over = [(g, MAX_KEPT_GAP_MOVING if mv else MAX_KEPT_GAP, cs, mv)
                for cs, g, mv in kept_gaps
                if g > (MAX_KEPT_GAP_MOVING if mv else MAX_KEPT_GAP)]
    gap_over.sort(key=lambda x: x[0] - x[1], reverse=True)
    moving_kept = [(cs, g) for cs, g, mv in kept_gaps
                   if mv and g > MAX_KEPT_GAP]
    if pause_pct > PAUSE_BUDGET_HARD_PCT:
        H(f"תקציב שקט: {pause_total}ש פאוזה מתוך {kept}ש = {pause_pct}% "
          f"(מקסימום {PAUSE_BUDGET_HARD_PCT}%). זה הליקוי שהראל דיווח עליו כ"
          f"'יותר מדי שתיקות' וכ'מוזיקה רועשת מדי' — אותו דבר. לקצר פאוזות "
          f"מסוג dead_time אל 0.20-0.25ש ולהשאיר beat ארוך רק ב-2-3 נקודות.")
    elif pause_pct > PAUSE_BUDGET_WARN_PCT:
        Wn(f"תקציב שקט: {pause_total}ש = {pause_pct}% (יעד ≤{PAUSE_BUDGET_WARN_PCT}%)")
    # ── רציפות תנוחה בגבולות שנבחרו ──
    # השורש של "יש רגע שאני מסתכל למטה". הפיצול כבר נבחר למזעור הקפיצה
    # (`best_split`); כאן מודדים מה נשאר ומדווחים. חוסם רק כשגם הפיצול
    # הטוב ביותר לא הצליח — כלומר הגוף זז לאורך **כל** הפער.
    # חיתוך שחוצה שינוי סצנה (גבול בין קליפים) הוא מעבר שוט, לא קפיצת-חיתוך:
    # "התנוחה" בשני צידיו שייכת לשני שוטים שונים, ולכן המדד לא חל עליו
    # (נמדד 22.10.26: שני גבולות קליפ נחסמו ב-0.236/0.188 בלי שום ג'אמפ-קאט).
    _scenes = [float(t) for t in (((cands.get("measurement") or {})
                                   .get("scene_changes") or {}).get("times") or [])]
    jumps = []
    for (s, e, cid) in cuts:
        if any(s - 0.05 <= t <= e + 0.05 for t in _scenes):
            continue
        pj = pose_jump(by_id.get(cid), s, e)
        if pj is not None:
            jumps.append((pj, cid, s))
    worst = max(jumps, default=(0.0, "", 0.0))
    if jumps:
        res_pose = {"n_measured": len(jumps),
                    "median": round(sorted(j[0] for j in jumps)[len(jumps) // 2], 4),
                    "worst": round(worst[0], 4), "worst_cid": worst[1]}
        over = [j for j in jumps if j[0] > POSE_JUMP_HARD]
        for pj, cid, s in over:
            H(f"{cid}: קפיצת תנוחה {pj:.3f} בגבול {s:.2f}ש — מעל {POSE_JUMP_HARD}. "
              f"הגוף זז לאורך כל הפער, ולכן אין פיצול שמסתיר את זה. "
              f"האפשרויות: לקצר את הפאוזה, להאריך אותה, או לכסות בבירול.")
        near = [j for j in jumps if POSE_JUMP_WARN < j[0] <= POSE_JUMP_HARD]
        for pj, cid, s in near:
            Wn(f"{cid}: קפיצת תנוחה {pj:.3f} בגבול {s:.2f}ש (סף אזהרה {POSE_JUMP_WARN})")
    else:
        res_pose = {"n_measured": 0}

    # ── פאוזה על תמונה קפואה = תקיעה ──
    # "יש איזושהי תקיעה בסוף לפני אם בא לכם" (הראל 30.7.26). הפאוזה שם הייתה
    # 0.40ש — בדיוק כמו שני ה-beats האחרים שלא הפריעו לו. ההבדל היחיד: התנועה
    # סביבה הייתה 2.04-2.27 מול חציון 3.84, כלומר כחצי. **אותה פאוזה, תפיסה
    # אחרת.** לכן תקציב הפאוזות לא יכול להיות עיוור לתמונה.
    stalls = []
    for c in cands["candidates"]:
        if c["kind"] != "inter_word_gap":
            continue
        kept_here = next((g for cs0, g, _mv in kept_gaps
                          if abs(cs0 - float(c["t_start"])) < 1e-6), 0.0)
        mn = c["features"].get("motion_around_norm")
        if kept_here >= STALL_MIN_PAUSE and mn is not None and mn < STALL_MOTION_NORM:
            stalls.append((c["candidate_id"], kept_here, mn))
    for cid, g, mn in stalls:
        Wn(f"{cid}: פאוזה {g:.2f}ש על תמונה כמעט קפואה (תנועה {mn:.2f} מהחציון) — "
           f"זה נתפס כתקיעה ולא כ-beat. לקצר ל-≤0.25ש או לכסות בבירול.")

    # ── תקציב תפרים ──
    # ⚠️ תפר נראה = גבול בין שני קטעים שנשמרו, לא החלטת חיתוך (17.8.26).
    # `cuts` הוא רשימת חיתוכים לפי החלטה, ושתי החלטות צמודות (פער שקוצץ +
    # המשפט שאחריו שהוסר) הן **חיתוך אחד** על המסך. הצופה לא סופר החלטות,
    # הוא רואה קפיצות. נמדד על "דקה-להורים": 48 החלטות חיתוך שהתמזגו ל-12
    # קטעים, כלומר 11 תפרים בפועל — והשער דיווח 1.099/ש במקום 0.252/ש,
    # פי ארבעה. כל הרציונל של השער הוא "כל תפר הוא קפיצה נראית", ולכן
    # המונה חייב להיות מספר הקפיצות.
    # (גם ההשוואה עצמה מחייבת את זה: הטווח 0.038-0.191 נמדד מספירת תפרים
    # בווידאו של סרטונים מאושרים, לא מספירת החלטות בתוכנית.)
    n_seams = max(0, len(keeps) - 1)
    # v9.20: תפר שנופל בתוך מיטת הבירול מוסתר — הוא לא "קפיצה נראית", ולכן
    # לא נספר בתקציב שכויל על שוט דיבור חשוף. מיקום התפר בציר **התוצר** הוא
    # הסכום המצטבר של הקטעים ששרדו לפניו.
    bed = _bed_intervals(W)
    seam_pos, acc = [], 0.0
    for k in keeps[:-1]:
        acc += float(k["end"]) - float(k["start"])
        seam_pos.append(round(acc, 3))
    covered = [p for p in seam_pos if _in_bed(p, bed)]
    n_exposed = n_seams - len(covered)
    cps = round(n_exposed / kept, 3) if kept else 0.0
    if covered:
        Wn(f"{len(covered)} מתוך {n_seams} התפרים נופלים מתחת למיטת הבירול "
           f"ולא נספרים בתקציב — תפר מוסתר אינו קפיצה נראית (לקח אלי 21.8.26). "
           f"תקציב מחושב על {n_exposed} תפרים חשופים.")
    if cps > CUTS_PER_SEC_HARD:
        H(f"צפיפות תפרים: {n_seams} תפרים ({len(cuts)} החלטות חיתוך) ב-{kept}ש = {cps}/ש "
          f"(מקסימום {CUTS_PER_SEC_HARD}). בסרטונים שהראל אישר: 0.038-0.191. "
          f"כל תפר הוא קפיצה נראית על שוט דיבור סטטי — עדיף פחות חיתוכים "
          f"גדולים מהרבה קיצוצים קטנים.")
    elif cps > CUTS_PER_SEC_WARN:
        Wn(f"צפיפות תפרים: {cps}/ש (יעד ≤{CUTS_PER_SEC_WARN}, אצל הראל עד 0.191)")
    # ספי החיסכון נפרדים: חיתוך שהתפר שלו מוסתר מתחת לבירול נמדד מול סף נמוך.
    _cov = set(covered)
    tiny = []
    for (s, e, cid) in cuts:
        floor_ = MIN_SAVING_PER_CUT_COVERED if _cut_seam_covered(s, keeps, bed) \
                 else MIN_SAVING_PER_CUT
        if (e - s) < floor_:
            tiny.append((cid, e - s, floor_))
    if tiny:
        Wn(f"{len(tiny)} חיתוכים חוסכים פחות מהסף שלהם "
           f"({', '.join(c for c, _, _ in tiny[:6])}…) — התפר עולה יותר ממה שנחסך "
           f"(סף חשוף {MIN_SAVING_PER_CUT}ש · סף מוסתר {MIN_SAVING_PER_CUT_COVERED}ש)")

    if gap_over:
        g, cap, cs, mv = gap_over[0]
        H(f"הפאוזה הארוכה ששרדה היא {g:.2f}ש ב-{cs:.2f}ש — מעל {cap}ש. "
          f"זה המדד שהבחין בפועל בין הסרטונים שהראל אישר (≤0.66ש) לבין אלה "
          f"שנשמעו כבדים (0.84-1.10ש). לקצר אותה, או להצהיר עליה כ-beat "
          f"מוצהר יחיד לפני מחיר/CTA."
          + (" (זה כבר פער-בתנועה, שהתקרה שלו רחבה יותר)" if mv else ""))
    for cs, g in moving_kept:
        # לא שער — דיווח. הצופה רואה פה פעולה, אבל הראל צריך לדעת שהפאוזה
        # הזאת חורגת מהתקרה הרגילה ולמה הותר לה.
        Wn(f"פאוזה {g:.2f}ש ב-{cs:.2f}ש מעל {MAX_KEPT_GAP}ש — הותרה כפער-בתנועה "
           f"(pose_range ≥{MOVING_GAP_POSE_RANGE}): הדובר זז לאורך כל הפער, "
           f"ולכן זה נקרא כשוט ולא כשתיקה. שער התנוחה עדיין חל עליה במלואו.")
    # v9.25 (הראל 19.9.26): אין תקרת 60ש. אורך לפי סוג תוכן (length_policy).
    import length_policy as LP
    _lp = LP.evaluate(kept, *LP.from_workdir(W))
    if _lp["level"] == "hard":
        H(f"משך צפוי {_lp['message']}")
    elif _lp["level"] in ("reason", "soft"):
        Wn(f"משך צפוי {_lp['message']}")

    res = {"ok": not hard, "hard": hard, "warn": warn,
           "n_decisions": len(decs), "n_cuts": len(cuts),
           "kept_dur": kept, "n_segments": len(keeps),
           "pause_total": pause_total, "pause_pct": pause_pct,
           "longest_gap": round(longest, 3), "pose": res_pose,
           "cuts_per_sec": cps, "tiny_cuts": len(tiny),
           "auto_applied": len([d for d in decs
                                if float(d.get("confidence", 0)) >= AUTO_APPLY_CONF]),
           "suggest_only": len([d for d in decs
                                if float(d.get("confidence", 0)) < SUGGEST_CONF])}
    if verbose:
        print(f"{'✅' if res['ok'] else '❌'} validator: {len(decs)} החלטות → {len(cuts)} חיתוכים · "
              f"{kept}ש ב-{len(keeps)} קטעים · שקט {pause_total}ש ({pause_pct}%) · "
              f"פאוזה ארוכה {longest:.2f}ש · "
              f"קפיצת תנוחה חציון {res_pose.get('median', 0):.3f} / מקס "
              f"{res_pose.get('worst', 0):.3f}")
        for m in hard:
            print(f"   ❌ {m}")
        for m in warn:
            print(f"   ⚠️  {m}")
    return res


def _pose_at_rel(profile, rel):
    """התנוחה בהיסט rel מתחילת הפער, מתוך `pose_profile` של המועמד."""
    if not profile:
        return None
    best, bd = None, 1e9
    for p in profile:
        d = abs(p[0] - rel)
        if d < bd:
            best, bd = p, d
    return None if best is None or bd > 0.25 else (best[1], best[2], best[3])


def best_split(cand, s, e, keep):
    """איפה בתוך הפער נופל החיתוך — הפיצול שממזער את קפיצת התנוחה.

    ═══════════════════════════════════════════════════════════════════════
    זה התיקון לשורש של "יש רגע שאני מסתכל למטה" (הראל, 30.7.26)
    ═══════════════════════════════════════════════════════════════════════
    עד כה ה-keep התחלק **חצי-חצי** בין שני צידי החיתוך. זה מספר שרירותי:
    הוא מגן על גבולות המילים, אבל מתעלם לגמרי ממה שקורה לגוף בתוך הפער.
    נמדד על התוצר שנדחה: הראל מתחיל להוריד את הראש **בתוך** הפער שלפני
    ה-CTA (71.07, בעוד הפער הוא 70.78→72.29). הפיצול חצי-חצי הניח את הגבול
    בדיוק כך שלפניו הראש למעלה ואחריו כבר למטה — pose_delta 0.104, השני
    בגודלו מבין 25 החיתוכים (חציון 0.018).

    **הפער הוא שקט — לכן כל פיצול שלו נשמע זהה.** אין שום סיבה לבחור חצי-חצי
    ולא את הפיצול שבו הגוף ממשיך את עצמו. אותו אורך פאוזה בדיוק, קפיצה קטנה
    יותר. זו החלטה שהקוד מחשב, לא שיפוט של המודל.
    """
    half = keep / 2.0
    default = (round(s + half, 3), round(e - half, 3))
    prof = (cand or {}).get("pose_profile") or []
    gap = e - s
    if not prof or keep >= gap or gap <= 0:
        return default

    # נוסף על בחירת **המיקום**, מותר לגעת ב**אורך** הפאוזה עד KEEP_NUDGE.
    # נמדד 30.7.26 על הפער שלפני ה-CTA: keep=0.26 ⇒ קפיצה 0.110, keep=0.32 ⇒
    # קפיצה 0.000. הפרש של 0.06ש אינו נשמע — הפרש של 0.11 בתנוחה נראה.
    # נוף האפשרויות בדיד ולא מונוטוני (‏Haar מזהה בפריימים בודדים), ולכן
    # סורקים אותו במקום להניח שקצר יותר = טוב יותר.
    def scan(k):
        lo = WORD_MARGIN + 0.01
        hi = max(lo, k - WORD_MARGIN - 0.01)
        if hi <= lo:
            return None
        best, best_d = None, 1e9
        a = lo
        while a <= hi + 1e-6:
            cs, ce = s + a, e - (k - a)
            if ce - cs >= MIN_CUT:
                pa = _pose_at_rel(prof, a)
                pb = _pose_at_rel(prof, gap - (k - a))
                if pa and pb:
                    d = (((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5
                         + abs(pa[2] - pb[2]) * 0.5)
                    if d < best_d - 1e-6:
                        best, best_d = (round(cs, 3), round(ce, 3)), d
            a += 0.02
        return None if best is None else (best, best_d)

    # ⚠️ ה-nudge חייב לכבד את כלל התקיעה. בלי זה הוא "מתקן" קפיצת תנוחה
    # ע"י הארכת פאוזה — ובאזור שבו התמונה קפואה זה בדיוק הליקוי שהראל דיווח
    # עליו. נמדד: הנודג' האריך שתי פאוזות מ-0.22 ל-0.28 בדיוק באזור שבו
    # התנועה 0.63-0.65 מהחציון. באזור קפוא מותר רק לקצר.
    mn = (cand or {}).get("features", {}).get("motion_around_norm")
    k_hi = keep + KEEP_NUDGE
    if mn is not None and mn < STALL_MOTION_NORM:
        k_hi = min(k_hi, max(keep, STALL_MIN_PAUSE))
    # ⚠️ והנודג' חייב לכבד גם את תקרת הפאוזה. בלי זה הוא מייצר מצב שאין ממנו
    # יציאה: הבמאי מבקש 0.76, ה-nudge מאריך ל-0.82 כדי למזער קפיצת תנוחה,
    # וה-validator נכשל קשיח על "הפאוזה הארוכה 0.82 מעל 0.78" — כשל שהבמאי
    # לא יכול לתקן באף ערך של tighten_to, כי הוא לא שולט במה שה-nudge עושה
    # אחריו. נמדד 17.8.26 על "בריאות-לקום-מכיסא" gap_0003: כל בקשה ≤0.74
    # החזירה קפיצה 0.146 (מעל 0.130), וכל בקשה ≥0.76 החזירה פאוזה 0.82
    # (מעל 0.78). שני שערים חוסמים, אפס ערכים חוקיים, שלושה סבבי במאי.
    # הכלל: קוד שמותר לו לשנות ערך אחראי לכך שהערך יישאר חוקי.
    pr = (cand or {}).get("features", {}).get("pose_range_in_gap")
    cap = (MAX_KEPT_GAP_MOVING
           if pr is not None and float(pr) >= MOVING_GAP_POSE_RANGE
           else MAX_KEPT_GAP)
    k_hi = min(k_hi, cap)

    cands_k = []
    k = max(2 * WORD_MARGIN + 0.02, keep - KEEP_NUDGE)
    while k <= min(k_hi, gap - MIN_CUT) + 1e-6:
        r = scan(k)
        if r:
            cands_k.append((r[1], abs(k - keep), r[0]))
        k += 0.02
    if not cands_k:
        return default
    # ממזערים קפיצה; בתיקו — האורך הקרוב ביותר למה שהבמאי ביקש.
    cands_k.sort(key=lambda x: (round(x[0], 4), x[1]))
    return cands_k[0][2]


def pose_jump(cand, cs, ce):
    """קפיצת התנוחה בפועל בגבול שנבחר — None כשאין מדידה."""
    prof = (cand or {}).get("pose_profile") or []
    if not prof:
        return None
    s, e = float(cand["t_start"]), float(cand["t_end"])
    pa, pb = _pose_at_rel(prof, cs - s), _pose_at_rel(prof, ce - s)
    if not pa or not pb:
        return None
    return round(((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5
                 + abs(pa[2] - pb[2]) * 0.5, 4)


# ═══════════════════════════════════════════════════════ compile
def plan_to_cuts(plan, by_id):
    """החלטות → רשימת חיתוכים (start, end, candidate_id) בציר המקור."""
    cuts = []
    for d in plan.get("decisions") or []:
        cid, act = d.get("candidate_id"), d.get("action")
        c = by_id.get(cid)
        if not c:
            continue
        conf = float(d.get("confidence", 0) or 0)
        if conf < SUGGEST_CONF or act in ("keep", "suggest_only", "broll", "move_to_open"):
            continue
        s, e = float(c["t_start"]), float(c["t_end"])
        # דריסת גבולות מפורשת — כשמסירים משפט שלם, לוקחים איתו את האוויר שסביבו
        # ומשאירים beat אחד נקי, במקום להשאיר שני פערים יתומים משני הצדדים
        # (ה"sliver-רפאים" המתועד). מותר רק כי ה-validator בודק נגיעה במילה.
        if d.get("t_start") is not None:
            s = float(d["t_start"])
        if d.get("t_end") is not None:
            e = float(d["t_end"])
        if act == "cut":
            cuts.append((round(s, 3), round(e, 3), cid))
        elif act == "tighten_to":
            keep = float(d.get("value", 0))
            cs, ce = best_split(c, s, e, keep)
            if ce - cs >= MIN_CUT:
                cuts.append((cs, ce, cid))
        elif act == "keep_last":
            cuts.append((round(s, 3), round(e, 3), cid))
    return sorted(cuts, key=lambda x: x[0])


def cuts_to_keeps(total, cuts):
    keeps, pos = [], 0.0
    for s, e, _ in sorted(cuts, key=lambda x: x[0]):
        if s > pos + 0.001:
            keeps.append({"start": round(pos, 3), "end": round(s, 3)})
        pos = max(pos, e)
    if pos < total - 0.001:
        keeps.append({"start": round(pos, 3), "end": round(total, 3)})
    return [k for k in keeps if k["end"] - k["start"] > 0.001]


def compile_edl(workdir, out=None, backup=True):
    W, plan, cands, words = load(workdir)
    v = validate(workdir, verbose=False)
    if not v["ok"]:
        print("❌ התוכנית לא עברה אימות — לא מקמפלים:", file=sys.stderr)
        for m in v["hard"]:
            print("   " + m, file=sys.stderr)
        sys.exit(1)
    by_id = {c["candidate_id"]: c for c in cands["candidates"]}
    total = float(cands["source"]["total_dur"])
    cuts = plan_to_cuts(plan, by_id)
    keeps = cuts_to_keeps(total, cuts)

    dec_by_id = {d["candidate_id"]: d for d in plan["decisions"]}
    auto, manual = [], []
    for s, e, cid in cuts:
        d = dec_by_id[cid]
        conf = float(d.get("confidence", 0))
        rec = {"start": s, "end": e, "reason": d["reason"][:200],
               "source": "director", "active": True,
               "confidence": ("high" if conf >= AUTO_APPLY_CONF
                              else "medium" if conf >= SUGGEST_CONF else "low"),
               # v2: המספר עצמו נשמר לצד התווית — האפליקציה תוכל לצבוע heatmap
               "confidence_value": round(conf, 3),
               "action": d.get("action"),
               "expected_benefit": d.get("expected_benefit"),
               "downside": d.get("downside"),
               "plan_id": plan.get("plan_id")}
        (auto if conf >= AUTO_APPLY_CONF else manual).append(rec)

    edl_path = Path(out) if out else (W / "edl.json")
    old = jload(edl_path, {}) or {}
    if backup and edl_path.exists():
        bak = W / f"edl.pre-v2-{time.strftime('%Y%m%d-%H%M%S')}.json"
        bak.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")

    edl = dict(old)
    edl.update({
        "total_dur": total,
        "keep_segments": keeps,
        "kept_dur": round(sum(k["end"] - k["start"] for k in keeps), 2),
        "auto_cuts": auto,
        "manual_review_cuts": manual,
        "review": {"cuts": [dict(c) for c in auto + manual],
                   "hook_move": (old.get("review") or {}).get("hook_move"),
                   "speed": (old.get("review") or {}).get("speed", 1.0)},
        "engine": "v2-director",
        "plan_id": plan.get("plan_id"),
        "prompt_version": plan.get("prompt_version"),
        "compiled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    edl["kept_dur_at_speed"] = round(edl["kept_dur"] / float(edl["review"]["speed"] or 1.0), 2)
    tmp = edl_path.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(edl_path)
    print(f"✅ קומפילציה: {len(cuts)} חיתוכים ({len(auto)} אוטומטיים, {len(manual)} להכרעה) · "
          f"{edl['kept_dur']}ש ב-{len(keeps)} קטעים → {edl_path.name}")
    return edl


# ═══════════════════════════════════════════════════════ report
def report(workdir):
    W, plan, cands, _ = load(workdir)
    by_id = {c["candidate_id"]: c for c in cands["candidates"]}
    decs = plan.get("decisions") or []
    und = jload(W / "understanding.json", {}) or {}
    score = jload(W / "quality_score.json", {}) or {}

    L = [f"# דוח עריכה — {W.name}", "",
         f"*נוצר {time.strftime('%Y-%m-%d %H:%M')} · מנוע החלטה V2 · "
         f"פרומפט {plan.get('prompt_version', '?')} · plan {plan.get('plan_id', '?')}*", ""]

    if und.get("story", {}).get("sections"):
        L += ["## מבנה הסיפור", ""]
        for s in und["story"]["sections"]:
            L.append(f"- **{s.get('role')}** {s.get('t_start')}–{s.get('t_end')}ש "
                     f"(עוצמה {s.get('strength')}): {s.get('summary', '')}")
        L.append("")
    if und.get("hook"):
        h = und["hook"]
        L += ["## הוק", "",
              f"- איכות: **{h.get('quality')}** · סוג: {h.get('type')}",
              f"- 3 השניות הראשונות: {h.get('first_3s_verdict', '')}", ""]

    applied = [d for d in decs if float(d.get("confidence", 0)) >= SUGGEST_CONF
               and d.get("action") in ("cut", "tighten_to", "keep_last")]
    kept = [d for d in decs if d.get("action") == "keep"]
    sugg = [d for d in decs if d.get("action") == "suggest_only"
            or float(d.get("confidence", 0)) < SUGGEST_CONF]

    L += [f"## מה נחתך ({len(applied)})", "",
          "| זמן | פעולה | ביטחון | למה | רווח | סיכון |", "|---|---|---|---|---|---|"]
    for d in sorted(applied, key=lambda x: float(by_id[x["candidate_id"]]["t_start"])):
        c = by_id[d["candidate_id"]]
        val = f" {d.get('value')}ש" if d.get("action") == "tighten_to" else ""
        L.append(f"| {c['t_start']:.2f}–{c['t_end']:.2f} | {d['action']}{val} | "
                 f"{float(d['confidence']):.0%} | {d['reason']} | "
                 f"{d.get('expected_benefit', '—')} | {d.get('downside', '—')} |")

    L += ["", f"## מה **נשקל ונשמר** ({len(kept)})", "",
          "*השכבה שאין לה ייצוג ב-v1: למה **לא** חתכנו.*", "",
          "| זמן | למה נשמר | ביטחון |", "|---|---|---|"]
    for d in sorted(kept, key=lambda x: float(by_id[x["candidate_id"]]["t_start"])):
        c = by_id[d["candidate_id"]]
        L.append(f"| {c['t_start']:.2f}–{c['t_end']:.2f} | {d['reason']} | "
                 f"{float(d['confidence']):.0%} |")

    if sugg:
        L += ["", f"## הצעות שלא הוחלו ({len(sugg)}) — דורשות הכרעה שלך", ""]
        for d in sugg:
            c = by_id[d["candidate_id"]]
            L.append(f"- **{c['t_start']:.2f}–{c['t_end']:.2f}** ({float(d['confidence']):.0%}): "
                     f"{d['reason']} · סיכון: {d.get('downside', '—')}")

    if und.get("retention_risks"):
        L += ["", "## סיכוני נטישה", ""]
        for r in und["retention_risks"]:
            L.append(f"- {r.get('t_start')}–{r.get('t_end')}ש (סיכון {r.get('risk')}): {r.get('why')}")

    if plan.get("open_questions"):
        L += ["", "## שאלות פתוחות", ""]
        for q in plan["open_questions"]:
            L.append(f"- {q.get('why')} ({q.get('candidate_id')})")

    if score:
        L += ["", "## ציון איכות", "", "| ממד | ציון | הערה |", "|---|---|---|"]
        for k, v in (score.get("scores") or {}).items():
            if isinstance(v, dict):
                L.append(f"| {k} | **{v.get('score')}**/10 | {v.get('note', '')} |")
        L += ["", f"**ציון כולל: {score.get('overall')}/10** — {score.get('verdict', '')}"]

    confs = [float(d["confidence"]) for d in decs if d.get("confidence") is not None]
    if confs:
        L += ["", "## התפלגות ביטחון", "",
              f"- מוחל אוטומטית (≥{AUTO_APPLY_CONF:.0%}): "
              f"{len([c for c in confs if c >= AUTO_APPLY_CONF])}",
              f"- מסומן לבדיקה ({SUGGEST_CONF:.0%}–{AUTO_APPLY_CONF:.0%}): "
              f"{len([c for c in confs if SUGGEST_CONF <= c < AUTO_APPLY_CONF])}",
              f"- הצעה בלבד (<{SUGGEST_CONF:.0%}): "
              f"{len([c for c in confs if c < SUGGEST_CONF])}",
              f"- ביטחון ממוצע: {sum(confs) / len(confs):.0%}"]

    L += ["", "---", "",
          f"*מרחב ההחלטות: {cands['n_candidates']} מועמדים "
          f"({cands['counts']}) · נמדד ב-{cands.get('measure_secs')}ש*"]
    p = W / "EDITING_REPORT.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"✅ {p}")
    return p


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "compile", "report"):
        s = sub.add_parser(name)
        s.add_argument("--workdir", required=True)
        if name == "compile":
            s.add_argument("--out", default=None)
            s.add_argument("--no-backup", action="store_true")
    a = ap.parse_args()
    if a.cmd == "validate":
        sys.exit(0 if validate(a.workdir)["ok"] else 1)
    if a.cmd == "compile":
        compile_edl(a.workdir, a.out, backup=not a.no_backup)
    if a.cmd == "report":
        report(a.workdir)


if __name__ == "__main__":
    main()
