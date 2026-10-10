#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_vision_law — האוכף של L31/L32 (חוק הראייה, 17.8.26).

הלקח מ-1.8.26: לקח לא שורד החלפת מנוע. חוק הראייה חי היום בשלוש שכבות
(סקריפט, כלי מדידה, מבקר-קדם) — הבדיקה הזאת נכשלת ברגע שאחת מהן נעלמת,
ולא ברגע שהראל מקבל סרטון שאף אחד לא פתח.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import vision_check as VC          # noqa: E402
import gate_registry as GR         # noqa: E402
import lesson_registry as LR       # noqa: E402


def t(name, cond, detail=""):
    print(f"{'✅' if cond else '❌'} {name}{(' — ' + detail) if detail else ''}")
    return bool(cond)


def main() -> int:
    ok = True

    # 1. הכלי שנותן את העיניים נמצא בתוך הפרויקט, לא רק בסקיל המסונכרן.
    ok &= t("scripts/video_eyes.py קיים בפרויקט", VC.VIDEO_EYES.exists(),
            str(VC.VIDEO_EYES))

    # 2. טריות ה-bundle היא הדבר היחיד שנאכף אוטומטית — היא חייבת להתקיים.
    src = (ROOT / "tools" / "vision_check.py").read_text(encoding="utf-8")
    ok &= t("vision_check בודק טריות bundle", "bundle_is_fresh" in src)
    pf = (ROOT / "tools" / "preflight_critic.py").read_text(encoding="utf-8")
    ok &= t("preflight מריץ P13", "P13_vision_bundle" in pf)
    ok &= t("P13 מחווט ל-rollup", "check_vision(findings, W)" in pf)

    # 3. L32 — אף שער ראייה עם סף לא-מדוד אינו חוסם.
    unmeasured_blocking = [
        k for k, g in GR.GATES.items()
        if k.startswith("vision:")
        and g["enforcement"] == GR.BLOCKING
        and g["threshold_source"] == GR.UNMEASURED]
    ok &= t("אין שער ראייה חוסם עם סף לא-מדוד",
            not unmeasured_blocking, str(unmeasured_blocking))
    # v9.29: V7 חוסם — אבל רק כי נמדד (caption-vision-calibration). הכלל נשאר:
    # שער ראייה חוסם ⇒ סף נמדד.
    ok &= t("שער ראייה חוסם רק כשנמדד",
            all(GR.GATES[k]["enforcement"] == GR.REPORTING
                or GR.GATES[k]["threshold_source"] == GR.MEASURED
                for k in GR.GATES if k.startswith("vision:")))

    # 4. אותה הבטחה בקוד עצמו: blocking רק כשהמעטפת נמדדה.
    ok &= t("vision_check מקדם ל-blocking רק לפי מעטפת נמדדת",
            'blocking" if source == MEASURED else "reporting' in src)
    ok &= t("קיים מסלול הפיכת סף עגול למדוד", "def build_reference" in src)

    # 5. כל שער בטבלת CHECKS רשום ב-gate_registry, ולהיפך.
    in_code = {c[0] for c in VC.CHECKS} | {VC.MANUAL["id"]}
    in_reg = {k.split(":", 1)[1] for k in GR.GATES if k.startswith("vision:")}
    ok &= t("שערי הראייה בקוד וברשומה זהים", in_code == in_reg,
            f"קוד-בלבד {sorted(in_code - in_reg)} · רשומה-בלבד {sorted(in_reg - in_code)}")

    # 6. v9.29 — V7 כבר לא "ידני לנצח": נמדד בפיקסלים (caption_vision), והגיליון
    # עדיין נקרא ב-Read כשיש ממצא.
    ok &= t("V7 נמדד בפיקסלים", "def v7_captions" in src and "caption_vision" in src)

    # 7. הלקחים רשומים ואכיפים.
    for lid in ("L37_no_visual_claim_without_eyes", "L38_a_round_threshold_is_not_a_gate"):
        ok &= t(f"{lid} ברשומת הלקחים", lid in LR.LESSONS)
    audit_ok, problems = LR.audit()
    ok &= t("אודיט לקחים עובר", audit_ok, " | ".join(problems)[:200])

    # 8. הערכה על data.json מינימלי — הפונקציות לא קורסות ולא ממציאות.
    d = {"meta": {"duration_sec": 30.0},
         "scenes": [1.4, 9.0],
         "motion_series": [{"t": round(i / 4, 2), "motion": 0.2 if i < 20 else 3.0}
                           for i in range(120)],
         "audio_levels": [{"t": 0.0, "db": -22.0}],
         "silences": [{"start": 3.0, "end": 4.9}],
         "transcript": {"segments": [{"start": 0.8, "text": "שלום"}],
                        "words_per_minute": 140.0}}
    checks = {c["id"]: c for c in VC.evaluate(d)}
    ok &= t("V2 תופס את הקאט ב-1.4ש", checks["V2_change_before_2s"]["value"] == 1.4,
            str(checks["V2_change_before_2s"]["value"]))
    ok &= t("V3 מזהה מילה ראשונה מאוחרת",
            checks["V3_first_word"]["status"] == "fail")
    ok &= t("V5 מודד שתיקה 1.9ש", checks["V5_dead_silence"]["value"] == 1.9)
    # bundle בלי אודיו אינו "אין שתיקה" — הוא "לא נמדד".
    no_audio = dict(d); no_audio.pop("audio_levels"); no_audio["silences"] = []
    v5 = {c["id"]: c for c in VC.evaluate(no_audio)}["V5_dead_silence"]
    ok &= t("V5 לא עובר PASS על bundle בלי אודיו",
            v5["status"] == "no_data", v5["detail"])
    ok &= t("V6 מודד חלון סטטי 5.0ש", checks["V6_static_window"]["value"] == 5.0,
            str(checks["V6_static_window"]["value"]))
    # כושל חוסם רק כשהסף שלו נמדד ומקודם (vision_reference) — לא מספר עגול.
    ok &= t("שער כושל חוסם רק מסף נמדד",
            all(c["enforcement"] == "reporting" or c["threshold_source"] == VC.MEASURED
                for c in checks.values()))

    print(f"\n{'✅ עבר' if ok else '❌ נכשל'} — test_vision_law")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
