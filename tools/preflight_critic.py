#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preflight_critic — הצפייה של הראל, לפני הראל.

למה זה נולד
-----------
הראל, 16.8.26: *"מספר רב של עריכות מחדש במקום לקבל מוצר מוגמר או כמעט מוגמר
כבר מהתחלה."*

לכל ליקוי שהראל דיווח עליו יש היום שער — אבל השערים פזורים על תריסר דוחות,
רובם מדווחים (בצדק — אלה מדדי טעם, לא חוקי פיזיקה), ואף אחד לא עונה על
השאלה האחת שקובעת אם יהיה סבב תיקונים: **"אם הראל צופה בזה עכשיו — מה הוא
מתקן?"** התוצאה: תוצר שעבר את כל השערים החוסמים מגיע אליו עם ליקוי שכבר
מדווח באחד הדוחות, ואיש לא הרים אותו.

הקובץ הזה הוא המבקר האחרון: הוא קורא את **התוכנית שהוחלה בפועל** ואת כל
הדוחות שכבר נכתבו, מריץ את בדיקות-הכאב שהראל דיווח עליהן במילים שלו (קפיצה
כפולה בגבול חיתוך · הבהוב בין בירולים · בירול בלי הקשר · Hook/CTA), ומחזיר
פסק-דין אחד: `ready_for_harel` + רשימת ממצאים ממוינת לפי חומרה, כל אחד עם
"למה" ועם "מה לתקן".

הוא **לא חוסם** (הממצאים הקשים כבר חסומים במעלה הזרם; כאן מדדי-צפייה) —
אבל הוא כן קובע מה כתוב בשורה הראשונה של הדיווח להראל: "מוכן" או
"צפוי סבב תיקונים על X". מוצר שמגיע להראל עם ממצא high פתוח = החלטה מודעת
שמדווחת, לא תקלה שקטה.

שימוש
-----
  python3 preflight_critic.py --workdir W [--json] [--strict]
  (--strict: exit 1 כשהפסק-דין אינו ready — לריצות CI, לא לצנרת)

פלט: {workdir}/PREFLIGHT.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import broll_director as BD                                   # noqa: E402

try:
    import gate_registry as GR
except Exception:                                              # pragma: no cover
    GR = None

HIGH, MED, LOW = "high", "medium", "low"


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def _why(check):
    if GR is None:
        return {}
    return {"why": GR.annotate("preflight", check)}


def F(check, severity, detail, fix):
    return {"check": check, "severity": severity,
            "detail": detail, "fix": fix, **_why(check)}


# ═══════════════════════════════════════════════════════════════════════
# הבדיקות — כל אחת נולדה ממשפט של הראל, והמשפט מצוטט בה.
# ═══════════════════════════════════════════════════════════════════════
def load_keeps(W: Path):
    """הציר שעליו התוכנית הוחלה בפועל: tight_keeps אם יש, אחרת keep_segments."""
    tk = jload(W / "tight_keeps.json")
    if isinstance(tk, dict) and tk.get("keeps"):
        return tk["keeps"], "tight_keeps.json"
    if isinstance(tk, list) and tk:
        return tk, "tight_keeps.json"
    edl = jload(W / "edl.json", {}) or {}
    return edl.get("keep_segments") or [], "edl.json"


def load_plan(W: Path):
    doc = jload(W / "broll_plan.json", {}) or {}
    plan = [p for p in (doc.get("plan") or [])
            if p.get("insert_at") is not None and p.get("insert_end") is not None]
    # v9.34 (23.9.26): התוכנית שבתיקייה ≠ מה שנצרב. גימור עם --no-broll משאיר
    # broll_plan.json על הדיסק, ו-P1 דיווח HIGH על "קפיצה כפולה" מבירול שלא קיים
    # ב-FINAL (ניפוץ-מיתוסים). מקור האמת = finish_prefs.broll.items_applied (v7.6).
    if (W / "FINAL.mp4").exists():
        man = jload(W / "project_manifest.json", {}) or {}
        br = ((man.get("finish_prefs") or {}).get("broll") or {})
        if "items_applied" in br and isinstance(br["items_applied"], list):
            applied = br["items_applied"]
            ids = {a.get("id") for a in applied if isinstance(a, dict)}
            if not applied:
                plan = []
            elif None not in ids:
                plan = [p for p in plan if p.get("id") in ids]
    return doc, sorted(plan, key=lambda p: float(p["insert_at"]))


def check_cut_flash(findings, keeps, plan, out_dur, speed=1.0):
    """הראל 1.8.26: "אם קטע נגמר ב-1.5ש, הבירול חייב להיגמר ב-1.55 ולא ב-1.4,
    כדי שלא תהיה 0.1ש של קפיצה כזו." — אותה בדיקה של snap_to_cuts, אבל על
    התוכנית **שהוחלה בפועל**: חגורה-ושלייקס נגד הלקח שנסוג בהחלפת מנוע."""
    if not plan or len(keeps) < 2:
        return
    try:
        bounds = BD.cut_boundaries(keeps)
    except Exception:
        return
    # 23.9.26 (חלבון, --speed 1.1): tight_keeps בציר שלפני ההאצה, התוכנית בציר ה-FINAL ⇒ שלושה
    # P1 HIGH מדומים (35.05 מול חיתוך אמיתי ב-31.86). אותו שורש של boundaries_from_keeps ב-v8.6.
    sp = float(speed) if speed and float(speed) > 0 else 1.0
    bounds = [b / sp for b in bounds]
    for b in bounds:
        if any(float(p["insert_at"]) <= b - BD.CUT_OVERHANG + 1e-6
               and float(p["insert_end"]) >= b + BD.CUT_OVERHANG - 1e-6
               for p in plan):
            continue                                  # הקאט מוסתר — מצוין
        for p in plan:
            s, e = float(p["insert_at"]), float(p["insert_end"])
            d = min(abs(b - e), abs(s - b))
            if d < BD.FLASH_GAP and not (s <= b <= e):
                findings.append(F(
                    "P1_cut_flash", HIGH,
                    f"גבול חיתוך ב-{b:.2f}ש אינו מכוסה, וקצה בירול "
                    f"({p.get('label') or p.get('id', '?')}) במרחק {d:.2f}ש — "
                    f"שני אירועים ויזואליים בשבריר שנייה (הקפיצה הכפולה שהראל דיווח)",
                    "להאריך את הבירול אל מעבר לגבול (CUT_OVERHANG) בתוך ה-footage; "
                    "אם אין footage — זה cut_sliver: חוב צילום, ולשקול הזזת החיתוך"))
                break


def check_broll_shape(findings, plan):
    """אורך מינימלי (הבהוב) ופערי-הבהוב בין בירולים סמוכים — הראל 25.7.26."""
    for p in plan:
        ln = float(p["insert_end"]) - float(p["insert_at"])
        if ln < BD.MIN_CLIP_LEN - 1e-6:
            findings.append(F(
                "P2_broll_min_len", HIGH,
                f"בירול {p.get('label') or p.get('id', '?')} באורך {ln:.2f}ש "
                f"(<{BD.MIN_CLIP_LEN}ש) — הצופה לא מפענח, זה הבהוב",
                "להאריך בתוך ה-footage או להסיר. לא ממלאים כדי שיהיה"))
    for a, b in zip(plan, plan[1:]):
        gap = float(b["insert_at"]) - float(a["insert_end"])
        if 0.01 < gap < BD.FLASH_GAP:
            findings.append(F(
                "P3_adjacent_blink", HIGH,
                f"חזרה לפנים של {gap:.2f}ש בין שני בירולים "
                f"({a.get('label', '?')} → {b.get('label', '?')}) — הבהוב, לא נשימה",
                "להחליק את הקליפ המוקדם קדימה ולהאריך בתוך ה-footage; "
                "הקליפ הבא לא זז לעולם"))


def check_hook_cta(findings, doc, plan, out_dur):
    """Hook/CTA מוגנים — אבל דוקטרינת המרה מוצהרת גוברת: מצע רציף רץ "עד
    ה-CTA או קצת לפניה" (הראל 31.7.26), והבמאי מצהיר bed_end בתוכנית. קליפ
    bed שמסתיים עד bed_end המוצהר אינו ליקוי — לדגול אותו היה מעניש את
    הסרטון על החלטה מנומקת (בדיוק "בינארי במקום שיפוט")."""
    doctrine = doc.get("doctrine") or {}
    bed_end = float(doctrine.get("bed_end") or 0.0)
    for p in plan:
        if float(p["insert_at"]) < BD.HOOK_GUARD - 1e-6:
            findings.append(F(
                "P4_hook_cta_guard", HIGH,
                f"בירול {p.get('label', '?')} מתחיל ב-{float(p['insert_at']):.2f}ש — "
                f"בתוך ה-Hook (חלון {BD.HOOK_GUARD}ש)", "Hook קדוש — להזיז/להסיר"))
        if not out_dur:
            continue
        limit = out_dur - BD.CTA_GUARD
        if (p.get("role") or "anchor") == "bed" and bed_end:
            limit = max(limit, bed_end)          # הדוקטרינה המוצהרת גוברת
        if float(p["insert_end"]) > limit + 1e-6:
            findings.append(F(
                "P4_hook_cta_guard", HIGH,
                f"בירול {p.get('label', '?')} נגמר ב-{float(p['insert_end']):.2f}ש — "
                f"בתוך חלון ה-CTA ({BD.CTA_GUARD}ש אחרונות)", "CTA מוגן — לקצר/להסיר"))


def check_anchor_context(findings, doc, plan):
    """בירול בלי הקשר: עוגן חייב נימוק שמצטט. picked_by=topic = המסלול הישן
    שנמדד ונפסל (\"ראיון עם מתאמנת\" על משפט מחיר) — ממצא, לא ברירת מחדל."""
    src = (doc.get("source") or doc.get("picked_by") or "").lower()
    if src == "topic" or doc.get("topic_scored"):
        findings.append(F(
            "P5_anchor_without_quote", HIGH,
            "התוכנית נבחרה לפי מחרוזת-נושא (picked_by=topic) — המסלול שיצר "
            "בירולים בלי הקשר. המשפט הוא יחידת ההתאמה, לא נושא-על",
            "להריץ דרך הבמאי (--director) או broll_pick עם עיגון-תמלול פר-משפט"))
    for p in plan:
        role = p.get("role") or "anchor"
        if role != "anchor":
            continue
        reason = (p.get("reason") or p.get("why") or "").strip()
        sent = (p.get("sent_text") or p.get("sentence") or "").strip()
        if not reason:
            findings.append(F(
                "P5_anchor_without_quote", MED,
                f"בירול-עוגן {p.get('label') or p.get('id', '?')} בלי נימוק רשום — "
                "אי אפשר לדעת אם הוא בהקשר",
                "נימוק שמצטט את המשפט הוא תנאי כניסה; בלי נימוק — להסיר או לתעד"))
        elif sent:
            try:
                if not BD.quoted_span(reason, sent):
                    findings.append(F(
                        "P5_anchor_without_quote", HIGH,
                        f"בירול-עוגן {p.get('label') or p.get('id', '?')}: הנימוק "
                        f"אינו מצטט את המשפט — חשד לבירול מחוץ להקשר",
                        "להחליף לקליפ שהנימוק שלו מצטט את המילים, או להסיר (0 זו תשובה)"))
            except Exception:
                pass


def check_duration(findings, out_dur, content_type=None, length_reason=None):
    """v9.25 (הראל 19.9.26): האורך נשפט לפי סוג התוכן (length_policy), לא מול 50-65.
    מחוץ ליעד = LOW (האורך אינו הלוחץ של reach — ההוק כן). מעל סף-הנימוק בלי
    length_reason = MED: 'מה ישאיר את הצופה עד הסוף?'. מחוץ לקשיח = HIGH."""
    if not out_dur:
        return
    import length_policy as LP
    lp = LP.evaluate(out_dur, content_type, length_reason)
    if lp["level"] == "hard":
        findings.append(F("P6_duration", HIGH, f"משך {lp['message']}",
                          "G1 אמור היה לחסום — לבדוק למה לא"))
    elif lp["level"] == "reason":
        findings.append(F("P6_duration", MED, lp["message"],
                          "לרשום length_reason במניפסט (לולאה פתוחה / סיפור / הדגמה) "
                          "או לקצר בתוכנית עד שהרעיון נוחת בלי עודף"))
    elif lp["level"] == "soft":
        findings.append(F("P6_duration", LOW, lp["message"],
                          "לא חוסם; האורך נקבע ע\"י התוכן — הכי קצר שמנחית את הרעיון"))


def rollup_reports(findings, W):
    """מרים את מה שכבר מדווח בדוחות הקיימים — הליקויים שהיסטורית הגיעו להראל
    למרות שהיו כתובים. לא ממציא מדידות חדשות; מרכז."""
    qa = jload(W / "qa_report.json", {}) or {}
    for g in qa.get("gates", []):
        if not g.get("pass") and not g.get("hard"):
            findings.append(F("P7_advisory_gate_open", MED,
                              f"{g.get('gate')}: {str(g.get('detail', ''))[:140]}",
                              "שער מדווח פתוח — להכריע במודע לפני מסירה, לא לגלות אחרי"))
    cq = jload(W / "cut_qa_report.json", {}) or {}
    for b in cq.get("boundaries", []):
        for fl in (b.get("flags") or []):
            findings.append(F("P8_cut_visual", MED,
                              f"גבול {b.get('time', b.get('t', '?'))}ש: {fl}",
                              "לבדוק את הפריימים ב-cut_qa_sheet.jpg; חשד לקאט לא הגיוני"))
    sq = jload(W / "broll_sequence_report.json", {}) or {}
    for i in sq.get("issues", []):
        findings.append(F("P9_sequence", LOW,
                          f"{i.get('check')}: {str(i.get('detail', ''))[:140]}",
                          "רצף מצע — לרוב חוב בריכה, לא ליקוי בסרטון"))
    sm = jload(W / "broll_seam_report.json", {}) or {}
    for i in (sm.get("exposures") or sm.get("issues") or []):
        findings.append(F("P10_seam_exposure", HIGH,
                          str(i)[:160],
                          "תפר בירול חושף את הדובר — בדיוק הליקוי של v9.11; לתקן לפני מסירה"))
    prof = jload(W / "output_profile.json", {}) or {}
    es = (prof.get("envelope_score") or {})
    score = es.get("score")
    if score is not None and score < 7.0:
        findings.append(F("P11_envelope", MED,
                          f"envelope_score {score}/10 מול מעטפת 16 המאושרים — "
                          f"{str(es.get('detail', es))[:140]}",
                          "לבדוק איזה רכיב הוריד; זה המדד הקרוב ביותר לעין של הראל"))
    cov = jload(W / "cover_report.json", {}) or {}
    if cov and not cov.get("ok", True):
        findings.append(F("P12_cover", HIGH,
                          f"דוח קאבר: {str(cov)[:140]}",
                          "קאבר דרך cover_make בלבד, מ-EXPORT נקי, 2 שורות"))
    check_vision(findings, W)
    check_caption_vision(findings, W)
    check_broll_vision(findings, W)
    check_fix_verify(findings, W)


CAPTION_VISION_FIX = {
    "reversed": "כתובית הפוכה (RTL כפול) — לבדוק RAQM ו-get_display ב-captions_overlay",
    "missing": "cue בלי כתובית בפריים — ציר המילים לא תואם ל-FINAL (קובץ מילים/היסט פתיח)",
    "garbled": "הגליפים לא תואמים לרינדור הצפוי — מילה אחרת/פונט/shaping; לפתוח את הגיליון",
    "garbled_cue": "g1 נמוך — מילה אחרת/גליף שבור ב-cue הזה (לא רקע עמוס); ≥3 חוסם. לפתוח את הגיליון",
    "tofu": "תו בלי גליף בפונט הכתוביות — להחליף את התו או להוסיף לפונט",
    "extra_ink": "דיו-כתובית מחוץ למקום הצפוי — כתובית כפולה או טקסט צרוב במקור",
    "clipped": "מילה חורגת מרוחב הפריים — לפצל את ה-cue",
    "face": "הכתובית חותכת פנים (מאומת ב-2 עיניים) — לשקול marginv נמוך יותר לסרטון (330 ניקה 4/4 בגל 6)",
    "punct": "נקודה/פסיק בכתובית — הפרת קאנון",
    "brand": "צבע המתאר שנצרב ≠ מותג המניפסט (פרופיל מותג אטומי)",
}


def check_caption_vision(findings, W: Path):
    """P20 — V7 על הפיקסלים (v9.29, 22.9.26). דגל חוסם כבר עצר את הגימור;
    כאן עולים הדגלים המדווחים, עם הגיליון שמראה פריים מול צפוי."""
    cv = jload(W / "CAPTION_VISION.json", {}) or {}
    if not cv:
        return
    if cv.get("measured") is False:
        findings.append(F("P20_caption_vision", LOW,
                          f"V7 כתוביות לא נמדד: {cv.get('why', '')}",
                          "tools/caption_vision.py --workdir W"))
        return
    # v9.34 (23.9.26): HIGH רק כש-caption_vision עצמו חצה את סף החסימה (blocking_hits).
    # קודם: כל דגל מסוג "חוסם" עלה HIGH גם מתחת לסף (garbled_cue ×2 כשהסף ≥3) —
    # 2 פרויקטים נעצרו כ-NOT-READY על false positive שנקרא בגיליון. פסיקה מתועדת
    # (CAPTION_VISION_VERDICT.json verdict=false_positive, אחרי Read של הגיליון) מורידה ל-LOW.
    blocking_hits = cv.get("blocking_hits")
    if isinstance(blocking_hits, dict):
        blocking = set(k for k, v in blocking_hits.items() if v)
    else:  # פלט ישן בלי blocking_hits — נשארים זהירים
        blocking = set(cv.get("blocking_flags") or [])
    verdict = jload(W / "CAPTION_VISION_VERDICT.json", {}) or {}
    ruled_fp = verdict.get("verdict") == "false_positive" and bool(verdict.get("evidence"))
    sheet = cv.get("sheet") or "caption_vision_sheet.jpg"
    for flag, n in sorted((cv.get("counts") or {}).items()):
        if flag == "no_frame":
            continue
        sev = HIGH if flag in blocking else (MED if flag in ("garbled", "garbled_cue", "extra_ink",
                                                               "clipped", "brand") else LOW)
        if ruled_fp and sev != LOW:
            sev = LOW
        findings.append(F("P20_caption_vision", sev,
                          f"{flag} ×{n} מתוך {cv.get('n_measured')} cues "
                          f"(f חציון {cv.get('f_ok_median')})",
                          f"{CAPTION_VISION_FIX.get(flag, 'לפתוח את הגיליון')} · Read {Path(sheet).name}"))


BROLL_VISION_FIX = {
    "not_landed": "הקליפ שנרשם כנצרב לא נראה בחלון שלו ב-FINAL — לבדוק overlay/היסט פתיח",
    "harel_in_club": "בירול של הראל בתוכן מועדון (הראל 25.7.26: להפריד) — להחליף או לאשר במפורש",
    "burned_text": "חשד לטקסט גרפי צרוב בקליפ — לפתוח את הקליפ (הגלאי מדווח בלבד)",
    "not_anchored": "פסיקת עיגון: הבירול לא מאייר את המשפט שמעליו — להחליף או להסיר",
}


def check_broll_vision(findings, W: Path):
    """P21 — בירולים כפי שנחתו ב-FINAL (v9.30). דגל חוסם כבר עצר את הגימור; כאן
    עולים המדווחים + מצב פסיקת העיגון (B4): בלי פסיקה = לא נמדד, לא PASS."""
    bv = jload(W / "BROLL_VISION.json", {}) or {}
    if not bv or bv.get("measured") is False:
        return
    blocking = set(bv.get("blocking_flags") or [])
    for flag, n in sorted((bv.get("counts") or {}).items()):
        sev = HIGH if flag in blocking or flag == "harel_in_club" else MED
        findings.append(F("P21_broll_vision", sev, f"{flag} ×{n} מתוך {bv.get('n_broll')} בירולים",
                          BROLL_VISION_FIX.get(flag, "לפתוח את broll_anchor_sheet.jpg")))
    b4 = (bv.get("B4") or {}).get("status")
    if b4 in ("not_measured", "stale"):
        findings.append(F("P21_broll_vision", LOW,
                          f"עיגון בירול למשפט: {'אין פסיקה' if b4 == 'not_measured' else 'פסיקה ישנה (FINAL השתנה)'}",
                          "broll_vision_qa.py anchor-request → Read על broll_anchor_sheet.jpg → anchor-apply"))


def check_vision(findings, W: Path):
    """P13 — חוק הראייה: אי אפשר לומר על תוצר משהו בלי שנפתחו העיניים.

    לא בודק *מה* נראה — את זה קורא מי שמדווח, בגיליונות המגע. בודק את העובדה
    היחידה שכן ניתנת לבדיקה אוטומטית: שקיים bundle ראייה טרי ל-FINAL, ושהשערים
    המדודים בו לא נכשלו. שער עם סף לא-מדוד מדווח בלבד (עקרון 1).
    """
    vis = jload(W / "VISION.json", {}) or {}
    if not vis:
        findings.append(F(
            "P13_vision_bundle", MED,
            "אין VISION.json — ה-FINAL לא נפתח בעיניים לפני המסירה",
            "python3 tools/vision_check.py --video FINAL.mp4 --workdir W ואז "
            "Read על כל contact_*.jpg"))
        return
    if not vis.get("bundle_is_fresh", False):
        findings.append(F(
            "P13_vision_bundle", HIGH,
            f"bundle הראייה במצב '{vis.get('bundle_mode')}' — ישן מה-FINAL "
            f"או חסר; המספרים מתארים קובץ אחר",
            "להריץ vision_check שוב על ה-FINAL הנוכחי"))
    for cid in vis.get("blocking_failures", []):
        c = next((x for x in vis.get("checks", []) if x["id"] == cid), {})
        findings.append(F(
            "P13_vision_bundle", HIGH,
            f"{cid} נכשל מול המעטפת הנמדדת: {c.get('detail', '')}",
            "לתקן בחותמת הזמן שבפירוט"))
    for cid in vis.get("reported_failures", []):
        c = next((x for x in vis.get("checks", []) if x["id"] == cid), {})
        findings.append(F(
            "P13_vision_bundle", LOW,
            f"{cid} מחוץ לסף העגול (לא-מדוד): {c.get('detail', '')}",
            "שיקול דעת. להפוך למדוד: vision_check.py --build-reference"))


def check_fix_verify(findings, W: Path):
    """P14 — סבב תיקונים לא מגיע להראל בלי אימות קלאוד (v9.18, הראל 18.8.26:
    "מה שלוקח לי הכי הרבה זמן זה לעבור כל סרטון... ולוודא שהכל פיקס").

    גרסה שנחתמו בה תיקונים (fixes) חייבת FIX_VERIFY תואם + פסיקת קלאוד לכל
    תיקון. מדווח, לא חוסם — אבל תיקון שקלאוד עצמו מצא כלא-נכנס הוא ממצא
    high: לשלוח אותו להראל זה לבזבז לו את הצפייה בידיעה.
    """
    try:
        from relvid import artifacts as art_mod
        from relvid import changelog as cl_mod
    except Exception:
        return
    try:
        arts = art_mod.list_artifacts(W)
    except Exception:
        return
    if not arts:
        return
    last = arts[-1]
    fixes = last.get("fixes") or []
    cmt_items = ["cmt_" + f["comment_id"] for f in fixes if f.get("comment_id")]
    if not cmt_items:
        return
    fv = jload(W / "FIX_VERIFY.json", {}) or {}
    if fv.get("artifact_id") != last.get("artifact_id"):
        findings.append(F(
            "P14_fixes_unverified", MED,
            f"בגרסה {last.get('version')} נחתמו {len(cmt_items)} תיקונים ואין "
            f"FIX_VERIFY תואם — הראל יצטרך לאמת בעצמו את מה שקלאוד היה אמור",
            "python3 tools/fix_verify.py --workdir W ואז Read על הגיליונות "
            "ו-fix-verdict פר-פריט"))
        return
    ch = (cl_mod.load_checks(W) or {}).get(last["artifact_id"], {})
    missing = [i for i in cmt_items
               if (ch.get(i, {}).get("claude") or {}).get("state") in (None, "pending")]
    flagged = [i for i in cmt_items
               if (ch.get(i, {}).get("claude") or {}).get("state") == "not_fixed"]
    if missing:
        findings.append(F(
            "P14_fixes_unverified", MED,
            f"{len(missing)} מתוך {len(cmt_items)} תיקונים בגרסה "
            f"{last.get('version')} עדיין בלי פסיקת קלאוד (הגיליונות לא נקראו?)",
            "Read על sheet_*.jpg של הפריטים החסרים + fix-verdict"))
    if flagged:
        findings.append(F(
            "P14_fixes_unverified", HIGH,
            f"{len(flagged)} תיקונים שקלאוד עצמו פסק שלא נכנסו לגרסה "
            f"{last.get('version')} — לתקן ולרנדר לפני שהראל צופה",
            "ההערות כבר חזרו לתור; לטפל ולהריץ גימור, לא למסור כך"))


def check_illustration(findings, W: Path):
    """P15 — המחשה ויזואלית: מינון ואימות (v9.20, הראל 21.8.26).

    שני ליקויים שכבר קרו והמבקר לא היה יכול לתפוס:
      • **סימון שנדלק על השריר הלא-נכון** — המסכה נגזרת מהאיור ולכן אינה
        יודעת מה שמו. בלי `illustration_regions.json` מאומת, ההמחשה לא
        אמורה להיות בתוצר בכלל.
      • **המחשה בסרטון שלא הרוויח אותה** — הסיכון כאן הוא שכיחות, לא איכות.
    """
    plan = jload(W / "illustration_plan.json")
    if not plan:
        return
    picks = plan.get("picks") or []
    if not picks:
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import illustration_gate as IG
        rc = IG.region_verified(W)
    except Exception as e:                                  # pragma: no cover
        findings.append(F("P15_illustration", HIGH,
                          f"לא ניתן לאמת מיפוי ישות→אזור: {e}",
                          "python3 tools/illustration_gate.py --workdir W"))
        return
    if not rc["ok"]:
        findings.append(F(
            "P15_illustration", HIGH,
            f"{len(picks)} המחשות בתוצר ומיפוי ישות→אזור לא אומת — {rc['detail']}. "
            "זה בדיוק הליקוי שהראל דיווח עליו (21.8.26): הסימון נדלק על שריר "
            "שאינו זה שנאמר",
            "לפתוח את illustration_check.png, לאשר כל ישות, ואז verified=true"))
    if len(picks) > IG.MAX_PER_VIDEO and not all(
            p.get("exception_reason") for p in picks[IG.MAX_PER_VIDEO:]):
        findings.append(F(
            "P15_illustration", MED,
            f"{len(picks)} המחשות בסרטון אחד בלי נימוק חריגה — המינון שנקבע "
            f"הוא {IG.MAX_PER_VIDEO} (חריגה עד {IG.MAX_PER_VIDEO_EXCEPTION})",
            "להוריד את החלשה, או לרשום exception_reason מפורש"))


def check_visual_hook(findings, W: Path):
    """P16 (v9.23) — מה הראל יראה בפתיחה. דיווח בלבד, בלי טענת שיפור שימור.
    הדוח נקרא רק אם הוא של הריצה הנוכחית (חדש מרשומת המקור) או תואם לה ב-digest."""
    rep = jload(W / "visual_hook_report.json")
    if not rep:
        return
    prov_p = W / "FINAL_PROVENANCE.json"
    prov = jload(prov_p, {}) or {}
    rp = W / "visual_hook_report.json"
    fresh = (not prov_p.exists()) or rp.stat().st_mtime >= prov_p.stat().st_mtime
    bound = (prov.get("visual_hook") or {}).get("plan_digest") == rep.get("plan_digest")
    if not (fresh or bound):
        return
    qa = jload(W / "visual_hook_qa.json") or {}
    appr = rep.get("approval") or {}
    if appr.get("error"):
        findings.append(F("P16_visual_hook", MED,
                          f"התצוגה שאושרה מיושנת ({appr['error']}) — הטיפול לא הוחל",
                          "להכין תצוגת פתיחה מחדש באפליקציה, או 'ללא שינוי'"))
    elif rep.get("applied"):
        if qa and not qa.get("pass"):
            findings.append(F("P16_visual_hook", HIGH,
                              f"QA פתיחה חזותית נכשל: {', '.join(qa.get('hard_failures') or [])}",
                              "לכבות את הפתיחה החזותית ולגמור מחדש"))
        else:
            findings.append(F("P16_visual_hook", LOW,
                              f"{rep.get('label_he')} · טיפול אחד בתמונה בלבד (דיבור/כתוביות/משך ללא שינוי) · "
                              f"אושר {'עם' if appr.get('comparison_seen') else 'בלי'} השוואה · אין טענת שיפור שימור שנמדדה",
                              "להשוות בגודל טלפון; 'ללא שינוי' אם מסיח"))
    elif rep.get("shadow") and rep.get("recipe") not in (None, "NO_OP"):
        findings.append(F("P16_visual_hook", LOW,
                          f"הצעה בצל, לא הוחלה: {rep.get('suggestion_label_he')} ({', '.join(rep.get('why') or [])[:80]})",
                          "להכין תצוגה ולהשוות באפליקציה אם רוצים לנסות"))


# ═══════════════════════════════════════════════════════════════════════
# P18/P19 — שומרי הגלם (v9.26, ארכיון Throwdown 2026). הלוגיקה ב-intake_guard.
# ═══════════════════════════════════════════════════════════════════════
def check_hook_anchor(findings, W: Path):
    """P22 (v9.44, 8.10.26) — עוגן מוחשי בשנייה 0-2.

    הרטרו של 8.10.26: VR (נשארים אחרי 3ש) מנבא חשיפה r=0.83/0.94. גיליונות 48 ריילס:
    פעולה/סצנה בפריים 0 = VR חציוני 42.6%, מדבר-למצלמה בלי פעולה = 30.3% (p=0.00006).
    הבמאי מצהיר ב-HOOK_PLAN.json (טכניקה מ-tools/hook_toolbox.json + מה רואים ב-0/1/2ש),
    בודק על HOOK_SHEET.jpg, וקושר לקובץ. בלי הצהרה / בלי עוגן / כרטיס כותרת / פריים שחור /
    'פרק N' בפתיחה = high (לא מוכן להראל). פנייה גאוגרפית אורגנית / פתיח קבוע לפני ההוק = medium.
    הממצאים עצמם מחושבים ב-hook_plan.evaluate (מקור יחיד גם ל-`hook_plan.py check`)."""
    try:
        import hook_plan as HP
    except Exception as e:                                     # pragma: no cover
        findings.append(F("P22_hook_anchor", MED, f"hook_plan לא נטען: {e}", "לבדוק tools/hook_plan.py"))
        return
    try:
        for x in HP.evaluate(W):
            findings.append(F("P22_hook_anchor", x["severity"], x["detail"], x["fix"]))
    except Exception as e:                                     # גלאי שנופל בשקט גרוע מגלאי שאין
        findings.append(F("P22_hook_anchor", MED, f"P22 לא נמדד: {e}", "להריץ hook_plan.py check ידנית"))


def check_caption_density(findings, W: Path):
    """P18 (L70): turbo+VAD זורק דיבור רועש ⇒ קטע נשמר כמעט בלי מילים ⇒ חור בכתוביות.
    הסף 0.6 מילים/ש לא נמדד מול מאושרים ⇒ MED, לא HIGH."""
    try:
        import intake_guard as IG
        r = IG.density_from_workdir(W)
    except Exception as e:                                     # pragma: no cover
        findings.append(F("P18_caption_density", LOW, f"לא נמדד ({e})", "להריץ intake_guard density"))
        return
    if not r.get("measured"):
        return
    gaps = r.get("gaps") or []
    if gaps:
        spots = " · ".join(f"{g['start']:.1f}-{g['end']:.1f}ש ({g['words']} מילים)" for g in gaps[:5])
        findings.append(F("P18_caption_density", MED,
                          f"{len(gaps)} קטעים שנשמרו כמעט בלי תמלול (<{IG.DENSITY_MIN_RATE} מילים/ש, ציר INPUT): {spots}",
                          "לצפות בקטע: יש דיבור? ⇒ intake_guard relisten על הקליפ (large-v3 בלי VAD) "
                          "ולהזריק את המילים; אין דיבור (קהל/מוזיקה) ⇒ להתעלם"))


def check_orientation_output(findings, W: Path):
    """P19 (L69): הדמות על הצד בתוצר. אותו שופט של I1, על הקובץ שהראל יראה."""
    vid = next((W / n for n in ("FINAL.mp4", "FINAL_PENDING.mp4", "EXPORT.mp4")
                if (W / n).exists()), None)
    if vid is None:
        return
    try:
        import intake_guard as IG
        r = IG.check_orientation(vid)
    except Exception as e:                                     # pragma: no cover
        findings.append(F("P19_orientation", LOW, f"לא נמדד ({e})", "intake_guard orient"))
        return
    if not r["measured"]:
        findings.append(F("P19_orientation", LOW, f"{vid.name}: {r['detail']}",
                          "להתקין opencv עם haarcascade (system_doctor)"))
    elif r["sideways"]:
        # MED ולא HIGH: haar נותן 2.7% חיובי-שגוי (IG.ORIENT_EVIDENCE) — חשד לבדיקה בעין
        findings.append(F("P19_orientation", MED, f"{vid.name}: חשד — {r['detail']}",
                          "לפתוח פריים (חוק הראייה). הפוך באמת ⇒ לתקן במקור ולבנות מחדש — "
                          "I2 ירענן את העותק"))


# ═══════════════════════════════════════════════════════════════════════
# P17 — סרטוני "הראל חיון" על בניית אפליקציות/פרומפטים עם AI (v9.23, 12.9.26)
# ═══════════════════════════════════════════════════════════════════════
AI_APP_DEPT = "הראל חיון"
AI_APP_MARKERS = ("קלוד", "claude", "פרומפט", "אפליקצי", "ארטיפקט", "artifact")
AI_TOOL_WORDS = ("קלוד", "claude", "chatgpt", "צ'אט ג'יפיטי", "בינה מלאכותית",
                 "איי איי", " ai ")
AI_OPENING_WINDOW = 4.0     # אותו חלון של מגן ה-Hook — שם נמדדת הפתיחה
AI_CTA_WINDOW = 12.0        # אזור ה-CTA שבו מילת המפתח חייבת להיאמר


def _ai_words(W: Path):
    d = jload(W / "words_final.json")
    if d is None:
        d = jload(W / "words.json") or []
    if isinstance(d, dict):
        d = d.get("words") or []
    return [w for w in d if isinstance(w, dict) and w.get("word")]


def _ai_norm(s) -> str:
    return (str(s or "").replace("״", '"').replace("׳", "'")
            .strip(" ,.!?:;\"'()[]"))


def check_ai_app_video(findings, W: Path, out_dur: float | None):
    """P17 — סרטון "הראל חיון" שבו הוא בונה אפליקציה/פרומפט עם AI.

    הראל, 12.9.26 (אחרי שריל "אפליקציית קניות" שבר שיא): התוכן הזה מפעיל
    שרשרת שלמה — תגובה במילת מפתח ⇒ DM אוטומטי (Metricool Flows) עם הלינק,
    ובמקביל אותו לינק יושב בדף הקישורים בביו. **אם ה-CTA בסרטון אומר מילה
    אחת וה-Flow מאזין למילה אחרת — כל השרשרת מתה בשקט**, והסרטון נראה מצוין.

    לכן הבדיקה הזאת אינה על טעם אלא על **התאמה בין דברים שנמדדים**: מילת
    המפתח שהוצהרה מול מה שנאמר בפועל בתמליל, קטע "הוספה למסך הבית" ליד ה-CTA,
    בירול הצ'אט, שני ערוצי המסירה, וכלל הפתיחה בבעיה (v9.23, חוקי ברזל 23-25).

    דיווח בלבד — כמו כל preflight. הוא קובע מה כתוב בשורה הראשונה להראל.
    """
    mani = jload(W / "project_manifest.json", {}) or {}
    words = _ai_words(W)
    text = " ".join(_ai_norm(w["word"]) for w in words)
    low = " " + text.lower() + " "
    hits = [m for m in AI_APP_MARKERS if m in low]
    brief = jload(W / "ai_app_brief.json")
    is_dept = (mani.get("dept") or "") == AI_APP_DEPT
    detected = is_dept and len(hits) >= 2
    if brief is None and not detected:
        return                                   # לא סרטון מהסוג הזה

    if not isinstance(brief, dict):
        findings.append(F(
            "P17_ai_app", HIGH,
            f"זוהה סרטון AI-אפליקציה במחלקת \"{AI_APP_DEPT}\" "
            f"(סימנים בתמליל: {', '.join(hits[:4])}) — אבל אין `ai_app_brief.json`. "
            "בלי בריף אין מילת מפתח מוצהרת, וה-Flow האוטומטי לא יודע למה להאזין",
            "לכתוב ai_app_brief.json בשלב 1.5: keyword · cta_text · "
            "home_screen · chat_broll · delivery{dm_flow,smartlink} · app_link"))
        return

    # ── 1. מילת המפתח נאמרת בפועל, ובאזור ה-CTA (חוק ברזל 24) ──────────
    kw = _ai_norm(brief.get("keyword"))
    if not kw:
        findings.append(F(
            "P17_ai_app", HIGH,
            "הבריף בלי `keyword` — ה-Flow של Metricool מאזין למילה, "
            "וסרטון בלי מילה מוצהרת הוא סרטון בלי מסירה",
            "לקבוע מילה עברית אחת שהיא **התוצאה** (״קניות״, ״מעקב״) "
            "ולא הפעולה (״לינק״, ״פרומפט״), ולרשום אותה בבריף ובקפשן"))
    else:
        kw_low = kw.lower()
        spoken = [w for w in words if kw_low in _ai_norm(w["word"]).lower()]
        if not spoken:
            findings.append(F(
                "P17_ai_app", HIGH,
                f"מילת המפתח ״{kw}״ לא נאמרת בתמליל אף פעם — "
                "הצופה מתבקש להגיב מילה שהוא לא שמע",
                "לומר את המילה בקול ב-CTA וגם להציג אותה על המסך; "
                "אם היא לא הוקלטה — זה חוב צילום, לא נושא לפתרון בעריכה"))
        elif out_dur:
            last = max(float(w.get("end") or 0.0) for w in spoken)
            if last < out_dur - AI_CTA_WINDOW:
                findings.append(F(
                    "P17_ai_app", MED,
                    f"מילת המפתח ״{kw}״ נאמרת לאחרונה ב-{last:.1f}ש מתוך "
                    f"{out_dur:.1f}ש — מחוץ לאזור ה-CTA "
                    f"({AI_CTA_WINDOW:.0f}ש אחרונות)",
                    "לחזור על המילה בסיום; מי שגולל לסוף הוא מי שמגיב"))
    cta_text = _ai_norm(brief.get("cta_text"))
    if kw and cta_text and kw.lower() not in cta_text.lower():
        findings.append(F(
            "P17_ai_app", HIGH,
            f"ה-CTA שהוצהר (״{cta_text[:60]}״) אינו מכיל את מילת המפתח ״{kw}״ — "
            "זו בדיוק ההתאמה שה-Flow נשען עליה",
            "ליישר את שלושתם: מילת ה-Flow = הטקסט על המסך = מה שנאמר בקול"))

    # ── 2. כלל הפתיחה בבעיה (חוק ברזל 23) ─────────────────────────────
    head = " " + " ".join(
        _ai_norm(w["word"]) for w in words
        if float(w.get("start") or 0.0) < AI_OPENING_WINDOW).lower() + " "
    tool_in_head = [t for t in AI_TOOL_WORDS if t.strip() and t in head]
    if head.strip() and tool_in_head:
        findings.append(F(
            "P17_ai_app", MED,
            f"הפתיחה ({AI_OPENING_WINDOW:.0f}ש ראשונות) פותחת בשם הכלי "
            f"({', '.join(tool_in_head)}) ולא בבעיה — "
            "\"בעיה קונקרטית בגוף ראשון → מה בניתי → מה זה פתר\"",
            "להתחיל מהבעיה האמיתית בבית/במועדון; שם הכלי אחרי שהצופה כבר "
            "מזהה את הכאב. אם לא הוקלטה פתיחת-בעיה — לסמן shot_debt"))

    # ── 3. קטע "הוספה למסך הבית" ליד ה-CTA (חוק ברזל 25) ───────────────
    hs = brief.get("home_screen") or {}
    if not hs.get("asset") and not hs.get("planned"):
        findings.append(F(
            "P17_ai_app", MED,
            "אין קטע \"הוספה למסך הבית\" — הצופה מקבל לינק ולא יודע "
            "שזה הופך לאפליקציה על הטלפון שלו",
            "5-10ש של צילום מסך/אנימציה ליד רגע ה-CTA. "
            "אם החומר חסר — shot_debt, לא ויתור שקט"))
    else:
        dur = float(hs.get("dur") or 0.0)
        if dur and not (5.0 <= dur <= 10.0):
            findings.append(F(
                "P17_ai_app", LOW,
                f"קטע \"הוספה למסך הבית\" באורך {dur:.1f}ש — "
                "המעטפת שנקבעה היא 5-10ש",
                "לקצר/להאריך; ארוך מדי גונב מה-CTA, קצר מדי לא נקרא"))
        at = hs.get("at")
        if at is not None and out_dur and float(at) < out_dur - 25.0:
            findings.append(F(
                "P17_ai_app", LOW,
                f"קטע \"הוספה למסך הבית\" ב-{float(at):.1f}ש מתוך "
                f"{out_dur:.1f}ש — רחוק מרגע ה-CTA",
                "להצמיד לרגע שבו נאמרת מילת המפתח"))

    # ── 4. בירול הצ'אט עם קלוד ─────────────────────────────────────────
    cb = brief.get("chat_broll") or {}
    st = cb.get("status")
    if st not in ("present", "shot_debt", "not_needed"):
        findings.append(F(
            "P17_ai_app", MED,
            "בירול הצ'אט עם קלוד לא הוכרע (present / shot_debt / not_needed) — "
            "הספרייה \"הראל חיון\" לא מכילה אותו נכון ל-12.9.26",
            "אם צולם — לרשום את הקליפ; אם לא — status=shot_debt "
            "ופריט צילום בבורד הסושיאל, כדי שזה לא ייעלם"))
    elif st == "shot_debt":
        findings.append(F(
            "P17_ai_app", LOW,
            "בירול הצ'אט רשום כחוב צילום — הסרטון יוצא בלעדיו במודע",
            "לתאם צילום עם הראל: הקלטת מסך של כתיבת/הדבקת הפרומפט"))

    # ── 5. שני ערוצי המסירה — DM + לינק בביו ──────────────────────────
    dl = brief.get("delivery") or {}
    if not dl.get("dm_flow"):
        findings.append(F(
            "P17_ai_app", MED,
            "לא הוצהר Flow ל-DM אוטומטי — מילת המפתח בלי Flow היא "
            "בקשה לתגובה בלי מסירה",
            "להגדיר את ה-Flow ב-Metricool על אותה מילה, ולרשום dm_flow בבריף"))
    if not dl.get("smartlink"):
        findings.append(F(
            "P17_ai_app", MED,
            "האפליקציה לא נרשמה בדף הקישורים בביו (הראל 12.9.26: "
            "\"תוכל להכניס את שליחת הערך בנוסף לאוטומציה גם בלינק בביו\") — "
            "מי שלא הגיב לא מגיע אליה לעולם",
            "להוסיף כרטיס ל-SmartLink ב-Metricool ולרשום את הכתובת ב-smartlink"))
    if not brief.get("app_link"):
        findings.append(F(
            "P17_ai_app", HIGH,
            "אין `app_link` — אין מה למסור",
            "לקבע לינק ציבורי לאפליקציה לפני התזמון"))


def media_stamp(W: Path, name: str) -> dict:
    f = W / name
    if not f.exists():
        return {}
    st = f.stat()
    return {"file": name, "size": st.st_size, "mtime": int(st.st_mtime)}


def apply_waivers(findings, W: Path):
    """v9.34 (23.9.26) — פסיקה מתועדת על ממצא, אחרי Read של גיליון (חוק הראייה).

    PREFLIGHT_WAIVERS.json = [{check, match, evidence, sheet, media, by, at}].
    ממצא שה-check שלו תואם ו-match מופיע ב-detail יורד ל-LOW ומסומן "[נפסק]".
    הפסיקה תקפה רק כש: יש evidence, הגיליון קיים, וה-media (גודל+mtime) זהה
    לקובץ הנוכחי — קלט שהשתנה מבטל כל נגזרת (עקרון 15).
    נולד מ: V5 'שתיקה' שהיא תשובה בהצבעה (מי-יותר-ממי), ו-P20 garbled שנקרא בגיליון.
    """
    ws = jload(W / "PREFLIGHT_WAIVERS.json", []) or []
    for wv in ws:
        if not (wv.get("check") and wv.get("evidence") and wv.get("sheet")):
            continue
        sheet = Path(wv["sheet"])
        sheet = sheet if sheet.is_absolute() else W / sheet
        if not sheet.exists():
            continue
        m = wv.get("media") or {}
        if not m or media_stamp(W, m.get("file", "")) != m:
            continue
        for f in findings:
            if f["check"] == wv["check"] and wv.get("match", "") in f["detail"] \
                    and f["severity"] != LOW:
                f["severity"] = LOW
                f["detail"] = f"[נפסק: {wv['evidence'][:80]}] " + f["detail"]


def run(workdir: str, out_dur: float | None = None) -> dict:
    W = Path(workdir).expanduser()
    findings: list[dict] = []
    keeps, keeps_src = load_keeps(W)
    doc, plan = load_plan(W)
    if out_dur is None:
        out_dur = sum(max(0.0, float(k["end"]) - float(k["start"])) for k in keeps) or None
        prov = jload(W / "FINAL_PROVENANCE.json", {}) or {}
        out_dur = prov.get("final_dur") or out_dur
        # v9.22 (10.9.26): הרצה ידנית בלי --out-dur סכמה את ה-keeps בלי האצה —
        # "איך הכרנו" ב-speed 1.175 דווח 70.5ש (high) כשה-FINAL היה 60.0ש.
        # קודם מדידת הקובץ עצמו; אחרת חלוקה ב-speed מרשומת המקור.
        _fin = W / "FINAL.mp4"
        _measured = None
        if _fin.exists():
            try:
                import subprocess as _sp
                _r = _sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(_fin)],
                             capture_output=True, text=True, timeout=30)
                _measured = float(_r.stdout.strip())
            except Exception:
                _measured = None
        if _measured:
            out_dur = _measured
        elif out_dur and float(prov.get("speed") or 1.0) > 1.0:
            out_dur = out_dur / float(prov["speed"])

    # מקור האמת להאצה שהוחלה = cut_qa_report (נמדד על EXPORT_TIGHT); FINAL_PROVENANCE רושם 1.0 גם ב---speed
    _spd = float((jload(W / "cut_qa_report.json", {}) or {}).get("speed") or 0) or \
        float((jload(W / "FINAL_PROVENANCE.json", {}) or {}).get("speed") or 1.0)
    # v9.38 — סרטון MG מלא (motion_plan opaque + MOTION_REPORT ok): השכבה האטומה מכסה את כל הפריים,
    # ולכן מבנה הבירול/הבהובי-פנים שמתחתיה לא נראה בכלל — P1-P4 על בירול שקוף לצופה הם רעש (דמו "בעל מועדון").
    _mp, _mr = jload(W / "motion_plan.json", {}) or {}, jload(W / "MOTION_REPORT.json", {}) or {}
    if plan and _mp.get("opaque") and _mr.get("ok"):
        findings.append(F("P1_broll_hidden_by_full_mg", LOW,
                          f"סרטון MG מלא — {len(plan)} בירולים מתחת לשכבה אטומה, בדיקות מבנה הבירול לא רלוונטיות",
                          "אין"))
        plan = []
    if plan:
        check_cut_flash(findings, keeps, plan, out_dur, speed=_spd)
        check_broll_shape(findings, plan)
        check_hook_cta(findings, doc, plan, out_dur or 0.0)
        check_anchor_context(findings, doc, plan)
    import length_policy as _LP
    _ct, _lr = _LP.from_workdir(W)
    check_duration(findings, out_dur, _ct, _lr)
    check_illustration(findings, W)
    check_visual_hook(findings, W)
    check_hook_anchor(findings, W)
    check_ai_app_video(findings, W, out_dur)
    check_caption_density(findings, W)
    check_orientation_output(findings, W)
    rollup_reports(findings, W)
    apply_waivers(findings, W)

    order = {HIGH: 0, MED: 1, LOW: 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["check"]))
    n_high = sum(1 for f in findings if f["severity"] == HIGH)
    n_med = sum(1 for f in findings if f["severity"] == MED)
    verdict = {
        "ready_for_harel": n_high == 0,
        "n_high": n_high, "n_medium": n_med,
        "n_low": len(findings) - n_high - n_med,
        "keeps_source": keeps_src,
        "broll_items": len(plan),
        "out_dur": round(out_dur, 2) if out_dur else None,
        "summary": ("מוכן להראל — אפס ממצאי high" if n_high == 0 else
                    f"צפוי סבב תיקונים: {n_high} ממצאי high — "
                    + " | ".join(f["check"] for f in findings
                                 if f["severity"] == HIGH)[:160]),
    }
    doc_out = {"verdict": verdict, "findings": findings}
    (W / "PREFLIGHT.json").write_text(
        json.dumps(doc_out, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--out-dur", type=float, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    doc = run(a.workdir, a.out_dur)
    v = doc["verdict"]
    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=1))
    else:
        icon = "✅" if v["ready_for_harel"] else "🔴"
        print(f"{icon} {v['summary']} · {v['n_medium']} medium · "
              f"{v['n_low']} low · PREFLIGHT.json נכתב")
        for f in doc["findings"]:
            if f["severity"] != LOW:
                print(f"  [{f['severity']}] {f['check']}: {f['detail'][:120]}")
    return (0 if v["ready_for_harel"] else 1) if a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
