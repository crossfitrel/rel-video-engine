#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canon_lint.py — Policy-as-Code (v7): בודק את חוקי הקאנון על פרויקט לפני אישור/תזמון.
===================================================================================
שלוש רמות: HARD_FAIL (חוסם) / WARNING / INFO. לא משנה שום קובץ — דוח בלבד.

הכרעות ספים (AUDIT-v7 §4, מתועד — לא נבחר בשקט):
  * דד-אייר: הסף התקף הוא 0.6ש (edl-policy v6.3 + qa_gates), התיעוד 1.5 היה stale.
  * TP: יעד -1.0, סף קשיח -0.8 (טולרנס מדידה).
  * משך: לפי length_policy (v9.25) — קשיח 12-180 (G1), יעד רך לפי סוג תוכן (G1b).
  * fps: קשיח 24-60, יעד מותג 30 (G5b, רך).

שימוש:
  python3 canon_lint.py --workdir "_work/{שם}" [--content-type value] [--brand rel]
      [--out canon_report.json]
exit: 0 = אין HARD_FAIL · 1 = יש HARD_FAIL
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
MUSIC_DIR = SYSDIR / "brand-assets" / "music"

sys.path.insert(0, str(HERE))
try:
    import gate_registry as GR      # הנימוק נכנס לדוח כדאטה (ראה gate_registry)
except Exception:                   # pragma: no cover
    GR = None

checks = []


def add(rule, level, ok, detail=""):
    rec = {"rule": rule, "level": "PASS" if ok else level,
           "detail": str(detail)[:200]}
    if GR:
        rec["why"] = GR.annotate("canon_lint", rule)
    checks.append(rec)


def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def ffprobe(p):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                            "-show_format", "-show_streams", str(p)],
                           capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout)
    except Exception:
        return {}



def _hook_retake_start(W, horizon=30.0):
    """v9.22 (L55, 10.9.26): טייק שגוי בפתיחה אינו ההוק.
    אם 3 המילים הראשונות בתמליל (ציר ה-INPUT) חוזרות ברצף בתוך horizon שניות —
    הדובר התחיל מחדש, וההוק הוא הטייק החוזר. מחזיר את זמן תחילתו, או None."""
    ws = None
    for key in ("words_corrected.json", "whisper_raw.json"):
        p = Path(W) / key
        if p.exists():
            try:
                ws = json.loads(p.read_text(encoding="utf-8"))
                ws = ws.get("words", ws) if isinstance(ws, dict) else ws
                break
            except Exception:
                ws = None
    if not ws:
        return None
    ws = sorted(ws, key=lambda w: float(w["start"]))
    toks = [re.sub(r"[^\w]", "", str(w.get("word") or w.get("text") or "")) for w in ws]
    head = toks[:3]
    if len(head) < 3 or not all(head):
        return None
    t0 = float(ws[0]["start"])
    for i in range(3, len(ws)):
        if float(ws[i]["start"]) - t0 > horizon:
            break
        if toks[i:i + 3] == head:
            return float(ws[i]["start"])
    return None


# ── חריגות קאנון מוצהרות (v9.23, 21.9.26) ─────────────────────────────────
# CANON_EXCEPTIONS_V1
# שער קאנון נכשל לפעמים על מקרה שהוא צודק לגביו אבל אין לו דרך לדעת עליו.
# המקרה שהוליד את זה: חלון הפתיחה של «אחרי-הריצה-עקפתי-את-פיין» צילם אנשים
# שאינם המרואיין באזור החלפה, ולכן היה חייב לרדת במלואו — ו-hook_protected
# חסם, בצדק, כי מבחינתו נמחק ההוק.
#
# חריגה נרשמת ב-project_manifest.json:
#   "canon_exceptions": {"hook_protected": {
#       "reason": "...", "approved_by": "הראל", "at": "2026-09-21",
#       "evidence": "..."}}
#
# היא מורידה HARD_FAIL ל-WARNING. לעולם לא ל-PASS, והנימוק נכנס לדוח.
# רשימת ההיתר צרה בכוונה: חריגה גורפת היא ביטול השער.
CANON_EXCEPTABLE = frozenset({"hook_protected"})
_CANON_EXC_REQUIRED = ("reason", "approved_by", "at")


def _canon_exceptions(W):
    """{rule: exc} לחריגות תקפות, ו-list הודעות על חריגות שנפסלו."""
    import json as _json
    from pathlib import Path as _Path
    p = _Path(W) / "project_manifest.json"
    if not p.exists():
        return {}, []
    try:
        man = _json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {}, ["canon_exceptions: מניפסט לא קריא (%s)" % e]
    raw = man.get("canon_exceptions") or {}
    if not isinstance(raw, dict):
        return {}, ["canon_exceptions: מבנה לא תקין — מצופה אובייקט"]
    good, rejected = {}, []
    for rule, exc in raw.items():
        if rule not in CANON_EXCEPTABLE:
            rejected.append("canon_exceptions: «%s» אינו ניתן לחריגה — מתעלם "
                            "(מותר: %s)" % (rule, ", ".join(sorted(CANON_EXCEPTABLE))))
            continue
        if not isinstance(exc, dict):
            rejected.append("canon_exceptions[%s]: מבנה לא תקין" % rule)
            continue
        missing = [k for k in _CANON_EXC_REQUIRED if not str(exc.get(k) or "").strip()]
        if missing:
            rejected.append("canon_exceptions[%s]: חסר %s — אישור שלא נרשם "
                            "אינו אישור" % (rule, "/".join(missing)))
            continue
        if len(str(exc["reason"]).strip()) < 20:
            rejected.append("canon_exceptions[%s]: הנימוק קצר מדי — נימוק שאי "
                            "אפשר לבדוק אינו נימוק" % rule)
            continue
        good[rule] = exc
    return good, rejected

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--content-type", default=None)
    ap.add_argument("--brand", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    W = Path(a.workdir).resolve()

    appr = read_json(W / "APPROVAL.json", {}) or {}
    mani = read_json(W / "project_manifest.json", {}) or {}
    # v9.7: ברירת המחדל "value" הייתה **שקטה ומטעה**. נמדד על האופן-ג'ים:
    # ‏`broll_plan.doctrine` אמר `conversion` (הוא נגזר מהבריף), בעוד canon
    # שפט את אותו סרטון כ-`value` — כלומר חלק מהכללים נבדקו מול סוג התוכן
    # הלא-נכון. הדוקטרינה היא המקור הקרוב ביותר לבריף, ולכן היא קודמת
    # לברירת המחדל; ברירת המחדל נשארת אחרונה ומדווחת.
    _doc_ct = ""
    try:
        _bp = W / "broll_plan.json"
        if _bp.exists():
            _doc_ct = (json.loads(_bp.read_text(encoding="utf-8"))
                       .get("doctrine") or {}).get("content_type") or ""
    except Exception:
        _doc_ct = ""
    ct = a.content_type or appr.get("content_type") or _doc_ct or "value"
    brand = a.brand or appr.get("brand") or "rel"
    dept = mani.get("dept") or ""
    edl = read_json(W / "edl.json", {}) or {}
    final = W / "FINAL.mp4"
    target = final if final.exists() else (W / "FINAL_PENDING.mp4")

    # --- מותג וסוג תוכן מוגדרים ---
    add("brand_defined", "WARNING", brand in ("rel", "personal", "oshia"), brand)
    add("content_type_defined", "WARNING", ct in ("value", "conversion", "connection"), ct)

    # --- B-roll (v7.8: מותר בכל סוגי התוכן — החלטת הראל 25.7.26) ---
    # הכלל הישן "בירול רק ב-conversion" בוטל: הקטלוג גדל (484 קליפים) והמטרה היא
    # בירול בכל סרטון שיש לו קליפ מתאים. מה שנשאר לאכוף במקומו:
    #   1. קליפי Throwdown לא נכנסים לתוכן שאינו Throwdown (צילומי תחרות באמצע
    #      "טיפ אחד" = ההפך מהשתלבות).
    #   2. כל קליפ בתוכנית חייב להגיע מהקטלוג ולהיות קיים על הדיסק.
    #   3. בירול לא מכסה את ה-CTA (8ש אחרונות) — נאכף גם ב-broll_pick.
    broll_used = (W / "EXPORT+BROLL.mp4").exists()
    plan = read_json(W / "broll_plan.json", {}) or {}
    items = plan.get("plan") or []
    is_td = ("throwdown" in W.name.lower() or dept == "REL Throwdown"
             or (plan.get("content_type") == "throwdown_value"))
    td_leak = [it for it in items
               if "throwdown" in (it.get("file", "") + it.get("path", "")).lower()]
    add("broll_throwdown_scope", "HARD_FAIL",
        is_td or not td_leak,
        (f"{len(td_leak)} קליפי Throwdown בתוכן שאינו Throwdown: "
         + ", ".join(x.get("file", "")[:40] for x in td_leak[:3])) if td_leak
        else f"broll={'כן' if broll_used else 'לא'} · {len(items)} קליפים · content_type={ct}")

    missing = [it for it in items if it.get("path") and not Path(it["path"]).exists()]
    add("broll_files_exist", "HARD_FAIL", not missing,
        f"{len(missing)} קבצי בירול חסרים" if missing else f"{len(items)} קליפים תקינים")

    # תוכנית שקיימת אך לא הוחלה — לא חוסם, אבל חייב להיות גלוי (23.7.26: זו הייתה
    # בדיוק הבעיה — broll_plan.json נוצר ומעולם לא הוחל, בלי שום סימן בדוח)
    if items:
        add("broll_plan_applied", "WARNING", broll_used,
            f"תוכנית עם {len(items)} קליפים · EXPORT+BROLL "
            f"{'קיים' if broll_used else 'חסר — לבדוק FINISH_REPORT.md'}")

    # --- מוזיקה: טראק מהספרייה (Pixabay בלבד, לא _disabled) ---
    rot = read_json(HERE / "music-rotation.json", {}) or {}
    last_track = rot.get("last", "")
    if last_track:
        in_lib = (MUSIC_DIR / last_track).exists()
        add("music_from_library", "HARD_FAIL", in_lib,
            f"{last_track} {'בספרייה' if in_lib else 'לא בספרייה הפעילה (אולי _disabled?)'}")
    else:
        add("music_from_library", "INFO", True, "אין רישום rotation")

    # --- Hook protection: אין cut פעיל שמוחק את כל חלון הפתיחה ---
    cuts = (edl.get("review") or {}).get("cuts", [])
    hook_win = 6.0
    # ⚠️ שקט שלפני המילה הראשונה אינו הוק (17.8.26).
    # `edl_build` כבר מתיר במפורש לקצץ שקט-הובלה, ו-`edit_plan` מדפיס על כך
    # "מותר, ההוק עצמו לא נגע" — אבל השורה כאן ספרה שניות ולא תוכן, ולכן
    # חסמה בדיוק את מה שהמדיניות השנייה אישרה. נמדד על "טיפ-אחד-בטן-בר":
    # 7.14ש בלי אף מילה לפני "טיפ אחד לטוז טו בר", הקיצור אושר בתכנון —
    # ו-canon_lint הפיל את התוצר אחרי שכל שאר השערים עברו.
    # שתי מדיניות שחלוקות על אותו חיתוך אינן שער, הן תקלה.
    # הכלל: ההוק מתחיל במילה הראשונה. מה שלפניה אינו נספר.
    first_word = None
    # ⚠️ רק קבצים על **ציר ה-INPUT**. `words_final.json` יושב על ציר החיתוך
    # (אחרי EXPORT) ולכן אינו מתאים להשוואה מול `review.cuts`, שהם על המקור.
    for key in ("words_corrected.json", "whisper_raw.json"):
        p = W / key
        if p.exists():
            try:
                ws = json.loads(p.read_text(encoding="utf-8"))
                ws = ws.get("words", ws) if isinstance(ws, dict) else ws
                if ws:
                    first_word = min(float(w["start"]) for w in ws)
                    break
            except Exception:
                pass
    lead = max(0.0, float(first_word)) if first_word is not None else 0.0
    hook_end = hook_win
    # v9.22 (L55): פתיחה שנאמרה פעמיים — הטייק הראשון הוא טעות, לא ההוק.
    # החלון זז לטייק החוזר ונשאר באותו אורך, כך שההוק האמיתי ממשיך להיות מוגן.
    retake_at = _hook_retake_start(W)
    if retake_at is not None:
        lead, hook_end = retake_at, retake_at + hook_win
    opening_cut = sum(min(c["end"], hook_end) - max(min(c["start"], hook_end), lead)
                      for c in cuts
                      if c.get("active") and c["start"] < hook_end and c["end"] > lead)
    opening_cut = max(0.0, opening_cut)
    # v9.23: חריגה מוצהרת מורידה ל-WARNING ומצרפת את הנימוק. לא PASS.
    _exc_all, _exc_rejected = _canon_exceptions(W)
    for _msg in _exc_rejected:
        add("canon_exception_rejected", "WARNING", False, _msg)
    _hook_exc = _exc_all.get("hook_protected")
    _hook_level = "WARNING" if _hook_exc else "HARD_FAIL"
    _hook_note = ("  ⚠️ חריגה מוצהרת (%s, %s): %s"
                  % (_hook_exc["approved_by"], _hook_exc["at"],
                     _hook_exc["reason"])) if _hook_exc else ""
    add("hook_protected", _hook_level, opening_cut < hook_win * 0.9,
        f"{opening_cut:.1f}ש נחתכו מתוך חלון הפתיחה ({hook_win:.0f}ש)"
        + (f" — טייק חוזר ב-{retake_at:.2f}ש: החלון {lead:.2f}-{hook_end:.2f}ש" if retake_at is not None
           else (f" — שקט הובלה עד {lead:.2f}ש אינו נספר" if lead > 0.05 else "")) + _hook_note)

    # --- CTA protection: ב-8ש האחרונות אין ריבוי חיתוכים ---
    total = float(edl.get("total_dur") or 0)
    if total:
        cta_cuts = [c for c in cuts if c.get("active") and c["end"] > total - 8.0]
        add("cta_zone", "WARNING", len(cta_cuts) <= 2,
            f"{len(cta_cuts)} חיתוכים באזור ה-CTA (8ש אחרונות)")

    # --- צפיפות: מקס 2 גבולות לכל חלון 5ש ---
    keeps = edl.get("keep_segments", [])
    if len(keeps) > 1:
        bounds, acc = [], 0.0
        for k in keeps[:-1]:
            acc += k["end"] - k["start"]
            bounds.append(acc)
        dense = 0
        for i, b in enumerate(bounds):
            win = [x for x in bounds if b <= x < b + 5.0]
            dense = max(dense, len(win))
        add("cut_density", "WARNING", dense <= 2, f"מקס {dense} חיתוכים בחלון 5ש")

    # --- פורמט התוצר ---
    if target.exists():
        info = ffprobe(target)
        vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        w, h = vs.get("width"), vs.get("height")
        dur = float((info.get("format") or {}).get("duration") or 0)
        add("format_1080x1920", "HARD_FAIL", (w, h) == (1080, 1920), f"{w}x{h}")
        try:
            x, y = (vs.get("avg_frame_rate") or "0/1").split("/")
            fps = float(x) / float(y) if float(y) else 0
        except Exception:
            fps = 0
        add("fps_30_brand", "WARNING", 29.5 <= fps <= 30.5, f"{fps:.2f}fps")
        import length_policy as LP
        _lp = LP.evaluate(dur, ct, LP.from_workdir(W)[1])
        add("duration_hard", "HARD_FAIL", _lp["hard_ok"],
            f"{dur:.1f}s (קשיח {LP.HARD_MIN:.0f}-{LP.HARD_MAX:.0f})")
        add("duration_target", "WARNING", _lp["in_target"] and _lp["reason_ok"], _lp["message"])
        # אין לוגו/גרפיקה — לא ניתן לבדוק אוטומטית: INFO
        # v9.37 — טקסט גרפי/לוגו מותרים רק דרך שכבת ה-MG, שנבדקת בשערי MG0-MG8 (MOTION_REPORT.json)
        add("no_graphics_logo", "INFO", True, "טקסט גרפי/לוגו רק דרך שכבת ה-MG (שערי MG ב-MOTION_REPORT.json); מחוץ לה — בדיקה ידנית ברוויו")
    else:
        add("final_exists", "INFO", False, "אין עדיין FINAL — בדיקות פורמט ידולגו")

    # --- כתוביות: פיסוק אסור. הצורב (captions_build.clean_token) מסיר [.,…] בזמן
    # צריבה — לכן בודקים את מה ש*שורד* את הניקוי, לא את words_final הגולמי.
    words = read_json(W / "words_final.json", []) or []
    if words:
        surviving = [re.sub(r"[.,…]+", "", str(w.get("word", ""))) for w in words]
        # v8.6: `bad` כפי שהיה מוגדר לא יכול היה להתמלא — מסירים [.,…] ואז מחפשים
        # [.,…] באותה מחרוזת. השער היה טאוטולוגיה. עכשיו שתי שכבות: tripwire על
        # סדק בניקוי, וחסימה על נקודה-פסיק ששורדת ונצרבת בפועל.
        bad = [t for t in surviving if re.search(r"[.,…]", t)]
        survives_bad = [t for t in surviving if ";" in t]
        raw_punct = sum(1 for w in words if re.search(r"[.,…]", str(w.get("word", ""))))
        add("captions_no_periods_commas", "HARD_FAIL", not (bad or survives_bad),
            f"נקי אחרי clean_token ({raw_punct} מילים עם פיסוק גולמי — ינוקו בצריבה)"
            if not (bad or survives_bad)
            else f"{len(bad + survives_bad)} מילים ישרדו עם פיסוק: {(bad + survives_bad)[:5]}")

    # --- שם פלט ותיוק ---
    add("naming", "INFO", True, f"תוצר: {target.name}")

    # --- אישורים ---
    add("approve_publish_gate", "HARD_FAIL",
        bool(appr.get("tag") == "[APPROVE-PUBLISH]") or not final.exists(),
        "FINAL קיים בלי APPROVAL" if final.exists() and not appr else "תקין")

    hard = [c for c in checks if c["level"] == "HARD_FAIL"]
    warn = [c for c in checks if c["level"] == "WARNING"]
    result = "FAIL" if hard else ("PASS_WITH_WARNINGS" if warn else "PASS")
    report = {"workdir": str(W), "content_type": ct, "brand": brand,
              "result": result, "hard_fails": len(hard), "warnings": len(warn),
              "checks": checks}
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    icons = {"PASS": "✅", "WARNING": "⚠️", "HARD_FAIL": "❌", "INFO": "ℹ️"}
    for c in checks:
        print(f"{icons[c['level']]} {c['rule']:<28} {c['detail']}")
    print(json.dumps({"result": result}, ensure_ascii=False))
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
