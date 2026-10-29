#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lesson_registry — המקום האחד שרואה את כל הלקחים שנקנו בדם, ובודק שהם עדיין אכופים.

למה זה נולד
-----------
הראל, 16.8.26: *"טעויות שחוזרות על עצמן כמה פעמים במקום ללמוד ולהשתפר
מהפידבקים."* והלקח המתועד מ-1.8.26: **לקח לא שורד החלפת מנוע** — v2 נבנה
בלי כיבוי fade-בתפר (v8.3) ובלי eof_action=repeat (v8.4), ושניהם חזרו למסך
של הראל בדיוק באותה צורה שבה תוקנו חודש קודם.

הסיבה המבנית: לקח שחי בזיכרון, בסקיל או בהערת-קוד הוא **נוהל** — ונוהל
אפשר לשכוח, במיוחד כשכותבים מנוע חדש. לקח ששרד הוא לקח שיש לו **אוכף**:
סימבול בקוד, בדיקה, או שער ברשומת השערים. הרשומה הזאת קושרת כל לקח לאוכף
שלו, ו---audit נכשל ברגע שהאוכף נעלם — *לפני* שהטעות חוזרת למסך, לא אחרי.

זה המקביל המדויק של gate_registry: שם — "אין שער שלא רשום"; כאן — "אין לקח
בלי אכיפה". שניהם רצים כשער ב-system_doctor.

מבנה רשומה
----------
  lesson      — הכלל, במשפט אחד, במונחי הצופה/התוצר
  origin      — מתי ומאיפה (תאריך + ציטוט/אירוע)
  layer       — plan / render / pipeline / broll / captions / covers / music / app / process
  enforced_by — רשימת אוכפים. סוגים:
      {"kind":"code", "file":"tools/x.py",  "pattern":"regex"}   הסימבול קיים בקוד
      {"kind":"test", "file":"tests/t.py",  "pattern":"regex?"}  הבדיקה קיימת (ואופציונלית מכילה)
      {"kind":"gate", "gate":"tool:name",   "enforcement":"?"}   השער קיים ברשומה (ואופציונלית באכיפה הנכונה)
      {"kind":"doc",  "file":"FFMPEG-STALL.md"}                  מסמך שורש קיים

שימוש
-----
  python3 lesson_registry.py            # טבלה אנושית
  python3 lesson_registry.py --json
  python3 lesson_registry.py --audit    # לקח שהאוכף שלו נעלם = כשל (exit 1)
  python3 lesson_registry.py --director # רק הלקחים שמוזרמים לבמאי (director_relevant)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # tools/
SYSDIR = HERE.parent                        # שורש הפרויקט


def L(lesson, origin, layer, enforced_by, director_relevant=False):
    return {"lesson": lesson, "origin": origin, "layer": layer,
            "enforced_by": enforced_by, "director_relevant": director_relevant}


LESSONS: dict[str, dict] = {

 # ── רינדור ותפרים ──────────────────────────────────────────────────────
 "L01_seam_fade_exposes_speaker": L(
    "fade על אלפא בתפר פנימי של בירול מוריד את שקיפות הבירול וחושף את הדובר "
    "בדיוק בקאט (נמדד: 3 פריימים = 0.1ש). בתפר פנימי אין fade, ו-eof_action=repeat.",
    "v8.3+v8.4 → נסוג בשקט בהחלפת המנוע ל-v2 → חזר למסך של הראל ותוקן שוב ב-v9.11 (1.8.26)",
    "render",
    [{"kind": "code", "file": "tools/relvid/render.py", "pattern": r"def mark_seam_fades"},
     {"kind": "code", "file": "tools/relvid/render.py", "pattern": r"eof_action=repeat"},
     {"kind": "gate", "gate": "render:segment_stall_budget"}]),

 "L02_broll_edge_snaps_to_cut_boundary": L(
    "קצה בירול מיושר לגבול החיתוך ולא לעצמו: חצייה של 2 פריימים (0.067ש) מעבר "
    "לגבול, אחרת פריים-הגבול נשאר חשוף. אין הארכה חלקית ואין הזזה — מה שלא "
    "נחצה יוצא cut_slivers (חוב), לא מוסתר.",
    "הראל 1.8.26: \"אם קטע נגמר ב-1.5ש הבירול חייב להיגמר ב-1.55 ולא ב-1.4\" (v9.11)",
    "broll",
    [{"kind": "code", "file": "tools/broll_director.py", "pattern": r"def snap_to_cuts"},
     {"kind": "code", "file": "tools/broll_director.py", "pattern": r"CUT_OVERHANG = round\(2 / 30\.0"},
     {"kind": "test", "file": "tests/test_broll_cut_snap.py"}]),

 "L03_flash_gap_is_a_blink": L(
    "חזרה של 0.3-1.2ש לפנים בין שני אירועים ויזואליים היא הבהוב, לא נשימה. "
    "חור ≤FLASH_GAP נסגר בהחלקה קדימה של הקליפ המוקדם; הקליפ הבא לא זז לעולם.",
    "הראל 25.7.26, נמדד (v8.2)",
    "broll",
    [{"kind": "code", "file": "tools/broll_director.py", "pattern": r"FLASH_GAP = 1\.2"}],
    director_relevant=True),

 "L04_director_is_last_word_on_pacing": L(
    "שיפוט שרץ לפני מנוע-כללים לא שינה כלום — השכבה האחרונה שנוגעת בציר קובעת. "
    "תחת --director ההידוק (tighten) כבוי; הבמאי קובע כל פער.",
    "הראל 30.7.26 על תוצר V2 הראשון: \"עדיין יותר שקט ממה שצריך, אין Flow\" — "
    "הבמאי שמר 12 פאוזות בנימוק ו-tighten גזם אותן (v9.2)",
    "pipeline",
    [{"kind": "code", "file": "tools/local_finish_pipeline.py",
      "pattern": r'a\.tighten == "auto" and not a\.director'}]),

 "L05_no_volatile_metadata_in_pass_payload": L(
    "ערך שמשתנה בלי שהתוכנית השתנתה (גודל קובץ · רשימת שערים · last_used_days · "
    "זמן-ריצה) לא נכנס ל-payload של פאס — כל אחד מהם שבר --backend replay.",
    "נשבר ארבע פעמים; האחרונה 31.7.26 דרך qa_report (v9.2→v9.10)",
    "plan",
    [{"kind": "code", "file": "tools/edit_director.py", "pattern": r"_qa_report_snapshot"},
     {"kind": "test", "file": "tests/test_scorer_payload_stability.py"}]),

 # ── בירולים: הקשר ───────────────────────────────────────────────────────
 "L06_anchor_reason_must_quote_sentence": L(
    "בירול-עוגן נכנס רק אם הנימוק מצטט את המשפט (צירוף שתי מילים רצופות או "
    "מילת תוכן ≥5 אותיות). תיאור של הקליפ אינו נימוק. נושא-על אינו יחידת התאמה.",
    "30.7.26 — שתי התקלות ההפוכות: נושא ריק ⇒ 0 בירולים; נושא מלא ⇒ "
    "\"ראיון עם מתאמנת\" על משפט מחיר (v9.4)",
    "broll",
    [{"kind": "code", "file": "tools/broll_director.py", "pattern": r"def quoted_span"}],
    director_relevant=True),

 "L07_no_broll_better_than_wrong_broll": L(
    "confidence<0.75 ⇒ אין בירול. אין מכסה; 0 בירולים היא תשובה תקפה. סרטון בלי "
    "בירול טוב מסרטון עם בירול לא-קשור — העדפה, לא פשרה.",
    "הראל 25.7-31.7.26 (v8.x-v9.4)",
    "broll",
    [{"kind": "code", "file": "tools/broll_director.py", "pattern": r"MIN_CONF = 0\.75"},
     {"kind": "code", "file": "tools/broll_director.py", "pattern": r"MIN_CONF_BED = 0\.60"}],
    director_relevant=True),

 "L08_min_clip_len_readability": L(
    "בירול קצר מ-1.8ש אינו מפוענח — הבהוב. לא ממלאים כדי שיהיה.",
    "הראל 25.7.26 (v8.2)",
    "broll",
    [{"kind": "code", "file": "tools/broll_director.py", "pattern": r"MIN_CLIP_LEN = 1\.8"}],
    director_relevant=True),

 "L09_audience_determines_structure": L(
    "המרה = קהל קר = מצע רציף (יעד 70%, בלי חזרה לפנים באמצע חוץ מפעימת trust); "
    "ערך/חיבור = עוגנים בלבד. חורי-פנים במצע נסגרים בקוד; מה שנשאר מדווח "
    "bed_face_holes, לא מוסתר.",
    "הראל 31.7.26 (v9.5, v9.10 trust)",
    "broll",
    [{"kind": "code", "file": "tools/broll_director.py", "pattern": r"def close_small_holes"},
     {"kind": "code", "file": "tools/broll_director.py", "pattern": r"def face_holes"},
     {"kind": "code", "file": "tools/broll_director.py", "pattern": r"def doctrine"}],
    director_relevant=True),

 "L10_hook_and_cta_are_sacred": L(
    "לא בירול על ה-Hook (4ש ראשונות) ולא על ה-CTA (8ש אחרונות); ב-tighten אזור "
    "ה-CTA נחתך רק על שקט ≥0.8ש. Hook מאוחר מועבר לפתיחה, לא נחתך.",
    "קאנון מהיום הראשון; מגבלת הצפיפות — הראל 19.7.26",
    "plan",
    [{"kind": "code", "file": "tools/broll_director.py", "pattern": r"HOOK_GUARD"},
     {"kind": "code", "file": "tools/edl_build.py", "pattern": r"hook_protect_sec"}],
    director_relevant=True),

 # ── ציר, מילים, סנכרון ─────────────────────────────────────────────────
 "L11_keep_segments_wins_sync": L(
    "ל-edl.json שתי שכבות; עריכה שנוגעת רק ב-keep_segments משאירה את האפליקציה "
    "על ציר ישן. הכיוון תמיד אחד: keep_segments מנצח ו-review.cuts נבנה ממנו מחדש.",
    "הראל 25.7.26 — נמדד פער 13.2ש ו-31.5ש בשני פרויקטים (v7.7)",
    "pipeline",
    [{"kind": "code", "file": "tools/relvid/sync.py", "pattern": r"def cuts_from_keeps"}]),

 "L12_map_words_dont_retranscribe": L(
    "לא מתמללים פעמיים — התמלול המקורי ממופה לציר החתוך (map_words_to_keeps), "
    "ושער כיסוי מוודא שאין דיבור בלי כתוביות.",
    "v7.9 (25.7.26)",
    "captions",
    [{"kind": "code", "file": "tools/relvid/edl_utils.py", "pattern": r"def map_words_to_keeps"}]),

 # ── מוזיקה ──────────────────────────────────────────────────────────────
 "L13_tone_class_filters_genre": L(
    "טון הבריף קובע ז'אנר, לא רק סוג התוכן: המרה בטון רגוע מסוננת מ-phonk/trap/"
    "rock_sport/edm. תיקון של אותה בעיה בשתי שכבות = השכבה הנכונה לא זוהתה.",
    "31.7.26 — האופן-ג'ים קיבל phonk ותוקן פעמיים (v9.10)",
    "music",
    [{"kind": "code", "file": "tools/local_finish_pipeline.py", "pattern": r"def tone_class"},
     {"kind": "test", "file": "tests/test_v99_tone_trust_envelope.py"}]),

 "L14_music_pref_overrides_cli": L(
    "בחירת מוזיקה של הראל ננעלת במניפסט (track_auto) וגוברת על --music בגימורים "
    "הבאים — אחרת גימור מהיר מחליף לו את הטראק שבחר.",
    "v7.4 (24.7.26)",
    "music",
    [{"kind": "code", "file": "tools/local_finish_pipeline.py", "pattern": r"track_auto"}]),

 # ── קאברים ─────────────────────────────────────────────────────────────
 "L15_cover_single_entry_with_gates": L(
    "כל קאבר עובר דרך בונה יחיד (cover_make), תמיד מ-EXPORT נקי, תמיד 2 שורות, "
    "תמיד Studentit — כשערים חוסמים בקוד, לא כנוהל בסקיל. נוהל אפשר לשכוח; שער לא.",
    "הראל 2.8.26: \"למה אתה כל הזמן נופל בקאברים? תטפל בזה מהשורש\" (v9.12)",
    "covers",
    [{"kind": "code", "file": "tools/thumbnail/cover_make.py", "pattern": r"G-COVER1"},
     {"kind": "gate", "gate": "cover_make:G-COVER1_clean_source", "enforcement": "blocking"},
     {"kind": "gate", "gate": "cover_make:G-COVER2_two_lines", "enforcement": "blocking"},
     {"kind": "test", "file": "tests/test_cover_gates.py"}]),

 # ── כתוביות ────────────────────────────────────────────────────────────
 "L16_rtl_no_double_reversal": L(
    "עם Pillow שנבנה מול libraqm, הפעלת get_display נוספת יוצרת היפוך כפול — "
    "טקסט לוגי גולמי עם direction=rtl בלבד.",
    "24.7.26 — הכתוביות יצאו הפוכות אחרי בניית Pillow מחדש לקאברים",
    "captions",
    [{"kind": "code", "file": "captions-app/captions_overlay.py", "pattern": r"raqm"}]),

 # ── שערים והחלטות ──────────────────────────────────────────────────────
 "L17_review_approval_is_final": L(
    "אחרי שהראל סקר ואישר ברוויו — שער שקט חוסם היה דורס את הפסק שלו; G2 נשאר "
    "מדווח, לא חוסם. אישור הראל = המילה האחרונה.",
    "20.7.26 (כיול 1.5→0.9→0.6) + v8.6",
    "pipeline",
    [{"kind": "gate", "gate": "qa_gates:G2_silence", "enforcement": "advisory"}]),

 "L18_no_blocking_gate_on_unmeasured_threshold": L(
    "אין שער חוסם עם סף לא-מדוד. 60MB היה מספר עגול בשער חוסם ותוקן ידנית בכל "
    "ריצה — הופרד לדיווח.",
    "v9.9 (31.7.26)",
    "process",
    [{"kind": "gate", "gate": "qa_gates:G5c_size", "enforcement": "advisory"},
     {"kind": "code", "file": "tools/gate_registry.py", "pattern": r"UNMEASURED"}]),

 "L19_people_is_not_audience": L(
    "התווית משקרת, הפריים לא: people (מי בפריים, מאימות ויזואלי) ≠ audience "
    "(פילטר בחירה). אין פנים בפריים ⇒ אין אימות זהות — בגד ומבנה גוף אינם ראיה.",
    "v9.6-v9.7 (31.7.26) — 4 קליפים של הראל בבריכת המתאמנים, כולם חסרי-פנים",
    "broll",
    [{"kind": "code", "file": "tools/system_doctor.py", "pattern": r"def clip_gender"},
     {"kind": "test", "file": "tests/test_gender_balance.py"}]),

 "L20_stall_fallback_measured_not_counted": L(
    "ספירה אינה מנבאת התנהגות: התקיעה ב-v2 היא per-segment (seek מדויק+overlay), "
    "לא per-count. -noaccurate_seek נמדד ונכשל על הפקודה האמיתית ולכן לא בקוד; "
    "הנפילה ל-v1 היא ה-fallback הפעיל, וההחלטה נמדדת.",
    "v9.7-v9.10 (31.7.26), FFMPEG-STALL.md",
    "render",
    [{"kind": "doc", "file": "FFMPEG-STALL.md"},
     {"kind": "code", "file": "tools/local_finish_pipeline.py", "pattern": r'rs\.get\("stalled"\)'},
     {"kind": "code", "file": "tools/relvid/render.py", "pattern": r"ENGINE_VERSION"}]),

 "L21_thresholds_from_approved_videos": L(
    "כל סף קצב/שקט/תפרים נגזר ממדידה של סרטונים שהראל אישר (reference_profile, "
    "16 סרטונים) — לא מניחוש. envelope_score הוא ציון נמדד, לא ציון עצמי.",
    "v9.2-v9.10 (30-31.7.26)",
    "plan",
    [{"kind": "code", "file": "tools/reference_profile.json", "pattern": r"."},
     {"kind": "gate", "gate": "output_profile:envelope_score"}],
    director_relevant=True),

 "L22_seams_cost_more_than_silence": L(
    "אחוז השקט אינו המטרה — קיצוץ פער חוסך 0.2ש ועולה תפר נראה. חיתוך רק אם "
    "החיסכון ≥0.50ש; עדיף 20% שקט עם 10 תפרים מ-16% עם 24.",
    "v9.2 (30.7.26) — נמדד מול 19 סרטונים מאושרים",
    "plan",
    [{"kind": "code", "file": "tools/relvid/prompts/director.plan_v1.3.md",
      "pattern": r"0\.50"}],
    director_relevant=True),

 "L23_schedule_locks_artifact": L(
    "אישור קאבר+קפשן נועל artifact_id+checksum; התזמון לוקח אך ורק את הקובץ "
    "הנעול ומאמת checksum — נגד תזמון גרסה שגויה שאי אפשר לתקן אחרי פרסום.",
    "v7.2 (23.7.26) + v9.4 Artifact Store",
    "app",
    [{"kind": "code", "file": "tools/relvid/registry.py", "pattern": r"def set_schedule_approval"},
     {"kind": "code", "file": "tools/relvid/registry.py", "pattern": r"artifact_checksum"}]),

 # ── הלקחים של השדרוג הזה (16.8.26) ─────────────────────────────────────
 "L24_preflight_before_harel": L(
    "אף תוצר לא מוצג להראל בלי צפיית-מבקר מסכמת: PREFLIGHT.json עם פסק-דין "
    "ready_for_harel וממצאים ממוינים. עריכות-מחדש הן כשל של המערכת, לא של הראל.",
    "הראל 16.8.26: \"מספר רב של עריכות מחדש במקום מוצר מוגמר כבר מהתחלה\" (v9.13)",
    "pipeline",
    [{"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"ready_for_harel"},
     {"kind": "code", "file": "tools/local_finish_pipeline.py", "pattern": r"preflight_critic"},
     {"kind": "test", "file": "tests/test_preflight_critic.py"}]),

 "L25_harel_corrections_reach_director": L(
    "התיקונים של הראל (corrections.jsonl מכל הפרויקטים, לפי cohort) נכנסים "
    "לפיילוד של הבמאי כ-harel_lessons — למידה מ-n=1, לא רק כיול ספים ב-n≥6. "
    "הקובץ דטרמיניסטי (בלי חותמות-זמן) כדי לא לשבור replay.",
    "הראל 16.8.26: \"מערכת שתדע לשפר את דפוסי החשיבה שלה\" (v9.13)",
    "plan",
    [{"kind": "code", "file": "tools/director_lessons.py", "pattern": r"harel_patterns"},
     {"kind": "code", "file": "tools/edit_director.py", "pattern": r"harel_lessons"},
     {"kind": "test", "file": "tests/test_director_lessons.py"}]),

 "L27_render_captions_interface_is_a_contract": L(
    "מנוע הרינדור v2 צורך את captions_overlay דרך פרופיל המותג "
    "(BRAND_PROFILES/BRAND_ALIASES) — לא דרך קבועים גלובליים. שינוי ממשק "
    "בכלי אחד בלי לבדוק את הצרכן השני = שבירה שקטה שרק בדיקת אינטגרציה תופסת.",
    "16.8.26 — כתיבת captions-app מחדש (3.8) מחקה את FONT_TTF/BRAND_COLORS; "
    "v2 קרס בכל סרטון עם כתוביות ו-v1 (ברירת המחדל) הסתיר את זה שבועיים",
    "render",
    [{"kind": "code", "file": "tools/relvid/render.py", "pattern": r"co\.BRAND_PROFILES"},
     {"kind": "code", "file": "captions-app/captions_overlay.py", "pattern": r"BRAND_PROFILES"},
     {"kind": "test", "file": "tests/test_render_v2.py"}]),

 "L28_prompt_promises_must_reach_the_payload": L(
    "פרומפט שמורה למודל לשפוט לפי מדד — והמסננת של ה-payload לא מעבירה את "
    "המדד — מייצר החלטה שנראית מנומקת ומבוססת על None. כל שדה שהפרומפט מזכיר "
    "בשמו חייב להופיע ב-_slim_candidate.keep.",
    "17.8.26 — director.plan_v1.4 מקדיש סעיף שלם ל-motion_around_norm / "
    "pose_delta_at_024 / pose_range_in_gap / face_low_*, אבל _slim_candidate "
    "זרק את חמשתם בשקט. נמדד על בריאות-לקום-מכיסא: gap_0001 motion_around_norm"
    "=0.57 (תקיעה) ו-gap_0003 pose_delta_at_024=0.315 — הגיעו לבמאי כ-None",
    "plan",
    [{"kind": "code", "file": "tools/edit_director.py",
      "pattern": r"motion_around_norm"},
     {"kind": "test", "file": "tests/test_director_payload_visual_fields.py",
      "pattern": r"pose_delta_at_024"}],
    director_relevant=True),

 "L29_code_that_edits_a_value_owns_its_legality": L(
    "קוד שרשאי לשנות ערך שהמודל ביקש (best_split/KEEP_NUDGE) אחראי לכך שהערך "
    "יישאר חוקי מול כל שער חוסם. אחרת נוצר מצב שאין ממנו יציאה: אף ערך שהבמאי "
    "יבקש לא יעבור, כי מה שנכשל נוצר **אחרי** הבקשה שלו.",
    "17.8.26 — בריאות-לקום-מכיסא gap_0003: בקשה ≤0.74 ⇒ קפיצת תנוחה 0.146 "
    "(מעל 0.130), בקשה ≥0.76 ⇒ ה-nudge האריך ל-0.82 (מעל MAX_KEPT_GAP 0.78). "
    "שני שערים חוסמים, אפס ערכים חוקיים, שלושה סבבי במאי ריקים",
    "plan",
    [{"kind": "code", "file": "tools/edit_plan.py", "pattern": r"k_hi = min\(k_hi, cap\)"},
     {"kind": "test", "file": "tests/test_moving_gap_ceiling.py",
      "pattern": r"nudge"}],
    director_relevant=True),

 "L30_a_gap_the_body_moves_through_is_a_shot": L(
    "פער שהדובר עובר בו מסלול גוף רציף אינו שתיקה אלא שוט, ותקרת הפאוזה "
    "(שנגזרה מפאוזות-שקט על תמונה סטטית) אינה חלה עליו כפי שהיא. ההקלה מותנית "
    "בתנועה מוכחת (pose_range ≥0.25, פי-10 מהחציון), חסומה ל-0.84ש, ומדווחת — "
    "ושער התנוחה ממשיך לחול במלואו.",
    "17.8.26 — בריאות-לקום-מכיסא: הדובר קם מהכיסא בתוך gap_0003 והראש עולה "
    "בפריים ברצף מונוטוני. ככל שהאוויר קטן הקפיצה גדלה (0.268 ב-0.55ש · "
    "0.146 ב-0.60-0.78 · 0.087 ב-0.82) — כלומר שני השערים דחפו הפוך",
    "plan",
    [{"kind": "code", "file": "tools/edit_plan.py",
      "pattern": r"MOVING_GAP_POSE_RANGE"},
     {"kind": "test", "file": "tests/test_moving_gap_ceiling.py",
      "pattern": r"MAX_KEPT_GAP_MOVING"}],
    director_relevant=True),

 "L37_no_visual_claim_without_eyes": L(
    "אמירה על מה שיש בסרטון — הוק, שוט, כתובית, קאבר, QA — נשענת על פתיחת "
    "גיליונות המגע בפועל, לא על report.md, שם הקובץ או התסריט המתוכנן. כל "
    "הערה נושאת חותמת זמן, אחרת אינה ניתנת לתיקון. bundle ראייה ישן מהקובץ "
    "שהוא מתאר נפסל — הוא מתאר וידאו אחר.",
    "הראל 17.8.26: \"להפסיק לעבוד על וידאו בעיוורון\" — הנחיות פרויקט "
    "rel-video-vision, סעיפים 1-3",
    "process",
    [{"kind": "code", "file": "tools/vision_check.py", "pattern": r"bundle_is_fresh"},
     {"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"P13_vision_bundle"},
     {"kind": "doc", "file": "scripts/video_eyes.py"},
     {"kind": "test", "file": "tests/test_vision_law.py"}]),

 "L38_a_round_threshold_is_not_a_gate": L(
    "סף שהגיע כמספר עגול בהנחיה (0.3ש למילה ראשונה · 2.0ש לשינוי · 1.2ש "
    "לשתיקה · 3.5ש לחלון סטטי) נכנס כמדווח, לא כחוסם, עד שנמדד מול סרטונים "
    "שהראל אישר. נמדד בפועל: reference_profile מראה longest_pause חציון 0.81ש "
    "ומקסימום 5.83ש ב-16 המאושרים — סף חוסם של 1.2ש היה פוסל את הראל לעצמו.",
    "17.8.26 — הטמעת שערי הראייה; עקרון 1 של הפרויקט גובר על נוסח ההנחיה",
    "process",
    [{"kind": "code", "file": "tools/vision_check.py",
      "pattern": r"blocking\" if source == MEASURED else \"reporting"},
     {"kind": "code", "file": "tools/vision_check.py", "pattern": r"def build_reference"},
     {"kind": "test", "file": "tests/test_vision_law.py", "pattern": r"reporting"}]),

 "L40_word_map_must_use_the_measured_cut": L(
    "מיפוי המילים לציר הקאט חייב להיכייל לאורך ה-EXPORT **שנמדד**, לא לסכום "
    "משכי ה-keep המתוכננים. edl_cut מעגל כל מקטע כלפי מעלה לגבול פריים — כחצי "
    "פריים לתפר — וההפרש מצטבר, ולכן הכתוביות מקדימות ביחס ישר למספר התפרים.",
    "18.8.26 — G6c דיווח הסחה שיטתית בכל ארבעת הסרטונים באותו יחס: 6 תפרים "
    "→ ‎-0.13ש · 7 תפרים → ‎-0.13ש · 11 תפרים → ‎-0.25ש. השער דיווח נכון במשך "
    "חודש ואיש לא חיבר בין המספרים לשורש. בדקה-להורים זה גם הפיל את G6b "
    "(ציון 70.7 מול סף 85) וחסם את הקידום ל-FINAL",
    "render",
    [{"kind": "code", "file": "tools/local_finish_pipeline.py",
      "pattern": r"כיול ציר המילים לאורך הקאט בפועל"},
     {"kind": "gate", "gate": "qa_gates:G6c_caption_drift_bias"},
     {"kind": "test", "file": "tests/test_word_map_calibration.py",
      "pattern": r"calibrat"}]),

 "L39_speed_must_not_cost_a_re_tighten": L(
    "האצה (--speed) ותכנון פערים הן שתי החלטות נפרדות, ואסור שהאחת תגרור את "
    "השנייה. עד v9.15 --speed נאכף רק בתוך שלב ההידוק, ולכן כל תוכנית שהפערים "
    "בה כבר הוכרעו — ע\"י הבמאי או ע\"י הראל באפליקציה — שילמה על ההאצה "
    "בחיתוך שתיקות נוסף. ההאצה מתבצעת מעכשיו במסלול speed-only (--min-sil 99): "
    "אותו שלב, אפס שתיקות נחתכות.",
    "הראל 17.8.26, על-הלוח-כוח-וגיל: \"מגבירים את קצב הסרטון ל-1.15\" יחד עם "
    "\"רוב הסרטון רץ בלי צורך בחיתוכים\". נמדד: --tighten on --speed 1.15 הוסיף "
    "8 תפרים על תוכנית של 7 — 0.118/ש → 0.259/ש, מעל התקרה הקשיחה 0.24",
    "render",
    [{"kind": "code", "file": "tools/local_finish_pipeline.py",
      "pattern": r"--min-sil\", str\(a\.min_sil\)"},
     {"kind": "code", "file": "tools/local_finish_pipeline.py",
      "pattern": r"speed-only"},
     {"kind": "test", "file": "tests/test_speed_without_retighten.py",
      "pattern": r"min_sil"}]),

 "L31_sentence_text_must_keep_its_first_word": L(
    "שיוך מילה→משפט חייב להיות לפי קרבה ולא לפי הכלה בחלון זמן: גבולות "
    "המשפטים נבנים מזמנים **מוצמדים** (snap_words_to_audio) והמילים נקראות "
    "מ-whisper_raw הלא-מוצמד. ההפרש שיטתי ותמיד באותו כיוון — המילה הראשונה "
    "של כל משפט נופלת החוצה.",
    "17.8.26 — טיפ-אחד-בטן-בר: sent_000 'טיפ אחד לטוז טו בר' הפך ל'אחד לטוז "
    "טו בר'. שני הצרכנים של s['text'] הם ה-edited_transcript של המבקר וההתאמה "
    "המילולית של הבירול (חוק ברזל 6) — שניהם קיבלו משפטים קטומים. הכתוביות "
    "נבנות מהמילים ולכן לא נפגעו, וזה מה שהסתיר את זה מכל שער קיים",
    "plan",
    [{"kind": "code", "file": "tools/edit_director.py",
      "pattern": r"_nearest_sentence"},
     {"kind": "test", "file": "tests/test_sentence_text_keeps_first_word.py",
      "pattern": r"first_word"}],
    director_relevant=True),

 "L32_asr_can_truncate_silently": L(
    "תמלול יכול להיקטע באמצע קובץ בלי שגיאה. כל שערי הכתוביות שואלים 'האם "
    "המילים שיש מסונכרנות' ואף אחד לא שאל 'האם יש מילים לכל הדיבור' — ולכן "
    "כשל כזה עובר בציון מלא. מודדים דיבור-אחרון מול מילה-אחרונה, ומדווחים.",
    "17.8.26 — דקה-להורים: 134 מילים שנגמרו ב-155.57ש על קובץ 181.39ש. "
    "24 השניות החסרות כללו את ה-CTA (דברו איתנו). הבמאי לא יכול לשמור משפט "
    "שאינו יודע שקיים, ולכן התוצר היה יוצא בלי קריאה לפעולה",
    "pipeline",
    [{"kind": "code", "file": "tools/candidates.py", "pattern": r"def asr_coverage"},
     {"kind": "code", "file": "tools/candidates.py",
      "pattern": r"trailing_untranscribed_sec"},
     {"kind": "test", "file": "tests/test_asr_coverage.py",
      "pattern": r"truncated_transcript"}]),

 "L33_two_policies_on_one_cut_is_a_bug": L(
    "שני שערים שחלוקים על אותו חיתוך אינם שער — הם תקלה. ההוק מתחיל במילה "
    "הראשונה; שקט שלפניה אינו הוק ואינו נספר ב-hook_protected.",
    "17.8.26 — טיפ-אחד-בטן-בר: 7.14ש בלי אף מילה בפתיחה. edl_build מתיר "
    "קיצוץ שקט-הובלה ו-edit_plan מדפיס 'מותר, ההוק עצמו לא נגע', בעוד "
    "canon_lint ספר שניות ולא תוכן והפיל את התוצר ב-HARD_FAIL — אחרי ש-qa "
    "ו-preflight כבר עברו",
    "plan",
    [{"kind": "code", "file": "tools/canon_lint.py", "pattern": r"שקט הובלה"},
     {"kind": "test", "file": "tests/test_hook_lead_silence.py",
      "pattern": r"lead_silence_is_allowed"}]),

 "L34_anchor_sits_on_the_words_it_quotes": L(
    "הציטוט אינו רק תנאי קבלה לעוגן — הוא גם קובע את **הזמן** שלו. עוגן "
    "שמושם תמיד בתחילת החלון מאייר בחלון ארוך מילים אחרות לגמרי מאלה "
    "שהצדיקו אותו.",
    "17.8.26 — בריאות-לקום-מכיסא: חלון broll_003 באורך 17.74ש, הציטוט "
    "'לחזק את... תבניות התנועה' בסופו, והקליפ נצרב על 5.07-8.57ש מעל 'הרבה "
    "אנשים לא שמים לב... להיעזר בידיים'. שוט בק-סקוואט על משפט שמדבר על "
    "להישען על הידיים. נתפס רק בצפייה בגיליון המגע, לא באף שער",
    "broll",
    [{"kind": "code", "file": "tools/broll_director.py", "pattern": r"def anchor_start"},
     {"kind": "test", "file": "tests/test_anchor_lands_on_the_quote.py",
      "pattern": r"late_quote_moves_the_clip_late"}],
    director_relevant=True),

 "L35_a_seam_is_a_boundary_not_a_decision": L(
    "תקציב התפרים נמדד בגבולות בין קטעים שנשמרו, לא במספר החלטות החיתוך. "
    "החלטות צמודות (פער שקוצץ + המשפט שהוסר אחריו) יוצאות כגוש אחד ומייצרות "
    "קפיצה אחת על המסך.",
    "17.8.26 — דקה-להורים: 48 החלטות חיתוך שהתמזגו ל-12 קטעים. השער דיווח "
    "1.099/ש במקום 0.252/ש — פי ארבעה, וחסם תוכנית תקינה. הטווח שאליו משווים "
    "(0.038-0.191) נמדד בספירת תפרים בווידאו, לא בספירת החלטות בתוכנית",
    "plan",
    [{"kind": "code", "file": "tools/edit_plan.py", "pattern": r"n_seams = max\(0, len\(keeps\) - 1\)"},
     {"kind": "test", "file": "tests/test_seam_count_is_visible_seams.py",
      "pattern": r"adjacent_cuts_are_one_seam"}],
    director_relevant=True),

 "L36_open_visual_must_not_end_after_speech_starts": L(
    "חלון 'לפני הדיבור' נבנה מהמילה הראשונה **אחרי** ההצמדה לאנרגיה, וההצמדה "
    "רשאית להזיז מילה מאוחר יותר — ואז החלון בולע את תחילת הדיבור. הבנייה "
    "חייבת לקחת את המוקדם מבין ההתחלה המוצמדת לגולמית.",
    "17.8.26 — טיפ-אחד-בטן-בר: ההצמדה הזיזה את 'טיפ' מ-6.80 ל-7.14, "
    "open_visual נבנה 0→7.14 ונחתך כשקט-פתיחה, ו-85% מהמילה יצאו איתו. "
    "map_words_to_keeps מפיל מילה ששרד ממנה פחות מחצי, ולכן הכתובית הראשונה "
    "בסרטון ששמו 'טיפ אחד' הפכה ל'אחד'. שער הכיסוי עבר, כי הוא משווה מול "
    "words_final שממנו המילה כבר נעלמה",
    "plan",
    [{"kind": "code", "file": "tools/candidates.py", "pattern": r"raw_first_start"},
     {"kind": "test", "file": "tests/test_open_visual_never_eats_speech.py",
      "pattern": r"never_eats_speech|clamp_is_present"}]),

 "L40_a_fix_belongs_to_a_version": L(
    "תיקון שייך לגרסה, ולכן הוא נחתם ברשומת הגרסה **ברגע היצירה** (fixes). "
    "בדיקה של תיקון = ניגון הנקודה שלו בציר של הגרסה הזו (טיימקוד ממופה דרך "
    "keep_segments+speed), לא צפייה חוזרת בסרטון המלא. שיוך שהוסק בדיעבד "
    "מסומן 'משוער', ונקודה שנחתכה מסומנת cut_out — לעולם לא מוצג טיימקוד "
    "שנראה ודאי ומצביע למקום אחר.",
    "הראל 17.8.26: \"הערות לכל גרסה שנערכת שאוכל לבדוק בדיוק את ההערות שתוקנו "
    "במקום לעבור על הסרטון המלא כל פעם שיש תיקונים\" (v9.15). השורש: אחרי "
    "מיגרציית v9.4 כל הגרסאות הישנות נושאות created_at זהה — שיוך בדיעבד הוא "
    "ניחוש, ולכן החתימה חייבת להיעשות בזמן היצירה",
    "app",
    [{"kind": "code", "file": "tools/relvid/changelog.py", "pattern": r"def stamp_fixes"},
     {"kind": "code", "file": "tools/relvid/changelog.py", "pattern": r"def map_time"},
     {"kind": "code", "file": "tools/relvid/artifacts.py", "pattern": r"cl_mod\.stamp_fixes"},
     {"kind": "code", "file": "review-app/server.py", "pattern": r"/api/changelog/<name>"},
     {"kind": "test", "file": "tests/test_changelog.py", "pattern": r"cut_out"}]),

 "L44_full_intro_must_be_automatic": L(
    "נכס שמתועד בקטלוג אבל אף שלב בצנרת לא מרכיב אותו — לא קיים. פורמט עם "
    "`פתיח מלא` מזוהה **מהכותרת/הבריף** (לא מהתמליל — הדובר לא אומר 'מאסל מן' "
    "בגוף הסרטון) ומודבק אוטומטית אחרי `deliver` ולפני השערים. שלושה כללי "
    "הרכבה שנמדדו: (1) concat demuxer עם -c copy משאיר duration ישן בזרם "
    "ו-avg_frame_rate יוצא מדומה — המסלול הוא mp4→mpegts→concat→mp4; "
    "(2) אורך אודיו ≠ אורך וידאו בפתיח שובר את החיבור — חותכים לאורך הווידאו; "
    "(3) הפתיח מנורמל **למפלס הגוף הנמדד**, לא לערך קבוע.",
    "הראל 18.8.26: \"האמת שגם שכחנו, צריך לצרף את הפתיח של מאסל מן בתחילת "
    "הסרטון\" — אחרי שהסרטון כבר תוזמן. הנכס והכללים ישבו ב-catalog.json "
    "מ-21.7.26, ו-fixed_intro.py תיעד במפורש ש-full_intro 'לא ממומש כאן — הוא "
    "concat פשוט שנעשה בשלב ההכנה', כלומר נשען על זיכרון אנושי. נמדד בהרכבה "
    "הידנית: concat -c copy נתן 37.44fps מדומה (G5b נכשל), והפתיח היה "
    "-22.0 LUFS מול -14.4 של הגוף — קפיצה של 7.6 יחידות",
    "render",
    [{"kind": "code", "file": "tools/fixed_intro.py", "pattern": r"def prepend_full_intro"},
     {"kind": "code", "file": "tools/fixed_intro.py", "pattern": r"def detect_full_intro"},
     {"kind": "code", "file": "tools/fixed_intro.py", "pattern": r"mpegts"},
     {"kind": "code", "file": "tools/local_finish_pipeline.py", "pattern": r"st\.step\(\"full_intro\"\)"},
     {"kind": "test", "file": "tests/test_full_intro.py"}],
    director_relevant=False,
),

 "L42_overlay_input_must_be_trimmed": L(
    "כל קלט בירול נפתח עם `-t` באורך החלון שלו. בלי זה הקלט המשני ארוך "
    "מהחלון, ו-`eof_action=repeat` (L: v8.4) מחזיק את הפריים האחרון של "
    "**הבסיס** עד שכל הקלטים נגמרים — כלומר הסרטון מתארך מעבר לווידאו "
    "ומסתיים בתמונה קפואה. הבדיקה: אורך EXPORT+BROLL חייב להיות שווה "
    "לאורך EXPORT_TIGHT.",
    "הראל 18.8.26: \"בסוף הסרטון יש 2 שניות של תמונה קפואה\" (ממומן ת2, "
    "שני הקהלים). נמדד: EXPORT_TIGHT 35.58ש → EXPORT+BROLL 37.20ש, "
    "freezedetect freeze_start=35.53 — 1.70ש קפואות. הבירול האחרון היה "
    "קליפ של 16.3ש שנפתח ב-off=3.0 לחלון של 7.5ש, ו-13.3ש הנותרות גררו "
    "את הפלט. שני לקחים קודמים הצטלבו כאן: repeat נועד למנוע חשיפת-פנים "
    "בתפר, והוא זה שיצר את הזנב",
    "render",
    [{"kind": "code", "file": "tools/animation_overlay.py",
      "pattern": r'"-t", f"\{\(float\(e\) - float\(s\)\)'},
     {"kind": "test", "file": "tests/test_overlay_no_tail_freeze.py",
      "pattern": r"broll_does_not_extend_video"}]),

 "L43_bed_covered_seam_is_not_a_visible_seam": L(
    "תפר שנופל בתוך מיטת הבירול אינו קפיצה נראית: הוא מוסתר מאחורי הקליפ. "
    "לכן הוא לא נספר בתקציב `CUTS_PER_SEC`, וסף החיסכון שלו יורד ל-"
    "`MIN_SAVING_PER_CUT_COVERED` במקום `MIN_SAVING_PER_CUT`. תפר חשוף על "
    "פני הדובר ממשיך בדיוק כמו קודם — שם הקליברציה של הראל תקפה. בלי "
    "ההבחנה הזאת המערכת משלמת מחיר של תפר-נראה על חיתוכים שאין בהם מה "
    "לראות, ולכן מוותרת עליהם ומשאירה אוויר מת.",
    "אלי (פרטנר ממומן) 21.8.26 על 8 סרטוני הקמפיין ספט-נוב: \"כל שנייה "
    "שאתם לא מדברים ועושים תנועה סתם בלי דיבור. יש שתיקות יותר מדי של "
    "מילי שנייה כזה, לא צריך.\" נמדד על אותם 8: אפס פערים מעל 0.6ש — "
    "כלומר שערי הפאוזה הארוכה עבדו — אבל 29 פערים בטווח 0.25-0.48ש "
    "שמצטברים ל-10.1ש אוויר מת. פילוח מול broll_plan: 17 מהם (6.1ש) "
    "מתחת למיטת הבירול, 12 (4.1ש) חשופים. השורש: CUTS_PER_SEC ו-"
    "MIN_SAVING_PER_CUT כוילו על סרטוני **ערך** — שוט דיבור סטטי שבו כל "
    "חיתוך נראה — והוחלו כמות שהם על תוכן המרה שרץ בדוקטרינת "
    "continuous_bed",
    "edit",
    [{"kind": "code", "file": "tools/edit_plan.py",
      "pattern": r"MIN_SAVING_PER_CUT_COVERED"},
     {"kind": "code", "file": "tools/edit_plan.py",
      "pattern": r"def _cut_seam_covered"},
     {"kind": "test", "file": "tests/test_bed_covered_seams.py",
      "pattern": r"test_seam_inside_bed_is_covered"}]),

 "L41_caption_always_via_cta_psychology": L(
    "קפשן הוא ה-CTA בפועל, ולכן הוא לא נכתב מקול בלבד. כל טיוטת קפשן "
    "מגובשת דרך `rel-cta-psychology` — הסקיל נטען **לפני** הכתיבה, לא "
    "כתיקון אחרי. סקילי הקול (rel-content-creator / "
    "rel-reel-caption-generator / harel-whatsapp-voice) קובעים איך זה "
    "נשמע; rel-cta-psychology קובע את מבנה הצעד הבא.",
    "הראל 17.8.26: \"תמיד תגבש את הקפשן עם הסקיל הזה. קבוע\". השורש: "
    "B = MAP — כשאדם לא פועל הבעיה כמעט תמיד ב-Ability או ב-Prompt "
    "(ניסוח הצעד הבא), לא במוטיבציה. קפשן חם שאין בו צעד קונקרטי אחד "
    "לא ממיר, וזה בדיוק מה שלא נבדק עד היום",
    "copy",
    [{"kind": "code", "file": "skills/rel-social-video-editor/SKILL.md",
      "pattern": r"rel-cta-psychology"},
     {"kind": "code", "file": "skills/rel-social-video-editor/SKILL.md",
      "pattern": r"\u05e7\u05d5\u05d3\u05dd \u05d8\u05d5\u05e2\u05e0\u05d9\u05dd"}]),

 "L42_review_app_simple_mode_is_default": L(
    "מסך הרוויו של הראל = צפייה → הערות → שלח לקלאוד/אשר, בפעולה ראשית אחת. "
    "'מצב פשוט' הוא ברירת המחדל: שורת הערה מתחת לנגן (נצמדת לזמן ולגרסה), "
    "'שלח הכל לקלאוד' אחד, וכרטיס 'מה עכשיו' עם כפתור אחד שנגזר מהמצב. כלי "
    "העריכה חיים ב'מצב מתקדם' — קליק אחד, שום יכולת לא נמחקת. פאנל האישור "
    "הסופי והתקדמות הגימור הם כרטיסים מתחת לנגן — לעולם לא קבורים בלשונית.",
    "הראל 18.8.26: \"יותר מדיי שלבים... הכפתורים לא ברורים. אני מעדיף לבקש "
    "מקלאוד שיסדר את ההערות וזהו\" (v9.16). השורש: המסך הציג את כל 9 "
    "הלשוניות ו-3 סרגלי הכלים לכולם, כשה-Job של הראל הוא 3 אינטראקציות",
    "app",
    [{"kind": "code", "file": "review-app/index.html",
      "pattern": r'localStorage\.getItem\("relReviewMode"\)\|\|"simple"'},
     {"kind": "code", "file": "review-app/index.html", "pattern": r"function renderNowBar"},
     {"kind": "code", "file": "review-app/index.html", "pattern": r'id="snSendAll"'},
     {"kind": "code", "file": "review-app/index.html",
      "pattern": r'card" id="scheduleApprovalPanel"'}]),

 "L43_one_theme_system_across_apps": L(
    "מצב לילה נבנה פעם אחת לכל האפליקציות: data-theme על html + מפתח "
    "localStorage + מחזור אוטומטי→יום→לילה, באותה פלטה כמו rel.fit/tasks. "
    "צבע נושא לא נכתב כהקס קשיח בגוף האפליקציה — רק טוקן var(); קנבס, "
    "שלא מבין var(), קורא את הטוקנים מ-getComputedStyle (tlPal) ומתרענן "
    "בהחלפת ערכה.",
    "הראל 18.8.26: \"תייצר גם מצב לילה כמו באפליקציה של המשימות\" (v9.17). "
    "השורש: בבניית v9.16 הוטמעו טינטים כהקסים בתוך תבניות JS, ומצב לילה "
    "היה דורס אותם — התיקון היה מעבר גורף לטוקנים, וזה הכלל שנשאר",
    "app",
    [{"kind": "code", "file": "review-app/index.html", "pattern": r"relReviewTheme"},
     {"kind": "code", "file": "review-app/index.html", "pattern": r"function tlPal"},
     {"kind": "code", "file": "review-app/index.html", "pattern": r'html\[data-theme="dark"\]'}]),

 "L45_claude_verifies_fixes_before_harel": L(
    "סבב תיקונים לא נמסר להראל לפני שקלאוד אימת **כל תיקון** בראיות: "
    "fix_verify מודד (מילים בכתוביות · גבול EDL · LUFS · חפיפת בירול) ומפיק "
    "גיליון-מגע פר-פריט; קלאוד קורא את הגיליונות ב-Read ופוסק fix-verdict "
    "(verified / not_fixed / needs_eye). not_fixed מחזיר את ההערה לתור לפני "
    "שהראל בכלל פתח את הסרטון, והסבב של הראל (review_plan focus) מנגן רק "
    "את מה שלא אומת. אין דיווח 'תוקן ואומת' בלי פסיקה רשומה.",
    "הראל 18.8.26: \"מה שלוקח לי כרגע הכי הרבה זמן זה לעבור כל סרטון כל פעם "
    "שיש תיקונים ולוודא שהכל פיקס. יש לך דרך לייעל את זה ולקחת בזה חלק?\" "
    "(v9.18). השורש: v9.15 קיצר את הצפייה לנקודות, אבל את האימות עצמו עדיין "
    "עשה הראל — לכל נקודה, בכל סבב. האימות הוא עבודת קלאוד; להראל נשאר הטעם",
    "app",
    [{"kind": "code", "file": "tools/fix_verify.py",
      "pattern": r"def machine_checks"},
     {"kind": "code", "file": "tools/relvid/changelog.py",
      "pattern": r"def set_claude_verdict"},
     {"kind": "code", "file": "tools/relvid/changelog.py",
      "pattern": r"focus=False"},
     {"kind": "code", "file": "tools/review_cli.py",
      "pattern": r"fix-verdict"},
     {"kind": "code", "file": "tools/preflight_critic.py",
      "pattern": r"P14_fixes_unverified"},
     {"kind": "test", "file": "tests/test_fix_verify.py",
      "pattern": r"claude_verdict|focus"}]),

 # ── המחשה ויזואלית (v9.20, 21.8.26) ───────────────────────────────────
 "L46_illustration_region_must_be_verified": L(
    "בהמחשה אנטומית, האזור שנדלק על המילה נגזר מהאיור — לא מהתמליל — ולכן "
    "אינו יודע מה שמו. כל מיפוי ישות→אזור עובר אימות מפורש מול האיור "
    "(illustration_regions.json עם verified לכל ישות + תמונת בדיקה שמראה כל "
    "אזור צבוע על האיור). בלי אימות ההמחשה **אינה מוחלת**. אימות שלא נעשה "
    "אינו 'כנראה בסדר'.",
    "הראל 21.8.26: \"רק שהסימונים על השרירים עכשיו לא היו מדויקים כשהוא ציין "
    "אותם כמו מקודם.\" השורש: קו התפר בין אינפרספינטוס לטרס מינור סומן ידנית "
    "מקריאת גריד, אחרי ששתי שיטות אוטומטיות (ארוזיה מורפולוגית · חיתוך לפי "
    "בהירות הפאשיה) נכשלו — והסימון לא אומת מול האיור לפני ההרכבה",
    "broll",
    [{"kind": "code", "file": "tools/illustration_gate.py",
      "pattern": r"def region_verified"},
     {"kind": "gate", "gate": "illustration_gate:IL5_region_verified",
      "enforcement": "blocking"},
     {"kind": "test", "file": "tests/test_illustration_gate.py",
      "pattern": r"region_verified"}]),

 "L50_placement_is_solved_from_the_frame_not_hardcoded": L(
    "מיקום ההמחשה בפריים **נפתר מהפריים עצמו** ולא מוזן כמספר קבוע: קופסאות "
    "פנים (אזור אסור מוחלט) + רצועת הכתוביות (מהקאנון) + מפת עומס (תנועה "
    "וקצוות). **הרצועה המועדפת היא מתחת לראש ומעל הכתוביות** — רצועת הגוף: "
    "בקו המבט, גבוהה פי שניים מהמקום שמעל הראש (ולכן הקלף גדול וקריא יותר), "
    "ובלי התקרה והדגלונים שהופכים המחשה לבאנר מודבק. העדפה ולא חוק: רצועה "
    "נמוכה מ-0.16 ⇒ נסיגה למקום הטוב הבא, עם דיווח למה. שובר-שוויון: מרכוז "
    "אופקי, ואז שטח. אין מיקום חוקי ⇒ ההמחשה יורדת — כיסוי פנים אינו פשרה. "
    "ובנוסף: **אין רקע שחור** — האיור צף מעל הווידאו, עם הילה כהה ש**עוצמתה "
    "נגזרת מ-`busy_cost` שכבר נמדד**: רחבה ריקה כמעט לא צריכה הילה, חליפת "
    "שרירים מודפסת בולעת את האיור בלעדיה.",
    "הראל 21.8.26: \"שווה לוודא שזה לא מסתיר את הראש של מי שמדבר. אולי לשים "
    "את זה במרכז. ולהוריד את הרקע השחור.\" המספר הקבוע (500x524 ב-x=290,y=0) "
    "נמדד על סרטון אחד והיה נכון בדיוק לו — בפריים ההוא הוא ישב על הראש",
    "render",
    [{"kind": "code", "file": "tools/illustration_place.py",
      "pattern": r"def solve_placement"},
     {"kind": "code", "file": "tools/illustration_place.py",
      "pattern": r"def alpha_from_backdrop"},
     {"kind": "code", "file": "tools/illustration_build.py",
      "pattern": r"transparent: bool = True"},
     {"kind": "gate", "gate": "illustration_place:IL8_face_occlusion",
      "enforcement": "blocking"},
     {"kind": "test", "file": "tests/test_illustration_place.py",
      "pattern": r"face|centre"}]),

 "L53_cut_boundaries_come_from_energy_not_from_whisper": L(
    "תזמוני whisper מרופדים בשני הקצוות ואינם מפת דיבור. חיתוך EDL לפיהם "
    "נכשל בשני הכיוונים באותו סרטון: whisper טען שהמילה האחרונה בבלוק "
    "נגמרת ב-44.41 בעוד הדיבור נגמר אקוסטית ב-43.51 (0.90ש ריפוד) ⇒ הקטע "
    "השאיר כמעט שנייה של הדובר יושב בשקט ומוריד מבט; ובאותו סרטון whisper "
    "טען שהמילה הבאה מתחילה ב-71.07 בעוד האונסט האמיתי 70.69 (0.38ש) ⇒ "
    "תחילת המילה נבלעה. **גבול חיתוך נגזר מאנרגיה (silencedetect); whisper "
    "קובע מה נאמר, לא מתי.** נגזרת שנייה: --skip-whisper/מיפוי-מילים מזרים "
    "את אותו ריפוד לכתוביות — בסבב תיקון על טיימינג מריצים --no-map-words.",
    "27.8.26 — גאה-בצוות. שני סבבי תיקון נכשלו על אותו שורש כי נעשה שימוש "
    "בתזמוני whisper כגבולות חיתוך; נפתר עם tools/edl_acoustic.py",
    "pipeline",
    [{"kind": "code", "file": "tools/edl_acoustic.py",
      "pattern": r"def detect_silences"},
     {"kind": "code", "file": "tools/edl_acoustic.py",
      "pattern": r"def build_segments"},
     {"kind": "test", "file": "tests/test_edl_acoustic.py",
      "pattern": r"head_pad_never_eats_into_speech"},
     {"kind": "test", "file": "tests/test_edl_acoustic.py",
      "pattern": r"tail_pad_is_short"}]),

 "L52_a_false_positive_erases_the_area_it_lands_on": L(
    "חיובי-שגוי של גלאי אינו רק רעש — הוא **מוחק את האזור שעליו נחת**. Haar "
    "זיהה \"פנים\" על חליפת השרירים המודפסת של מאסל מן (4 קופסאות על החזה, "
    "בגודל דומה לפנים האמיתיות), וזה הפך את כל רצועת הגוף לאזור אסור ודחף "
    "את ההמחשה בחזרה מעל הראש. שטח לבדו אינו מבדיל — שניהם באותו סדר גודל. "
    "מה שמבדיל הוא **התמדה**: מאשכלים לפי מרכז ומדרגים (שיעור הפריימים "
    "שנראה) × (שטח ממוצע); מתחת ל-60% מהמוביל — לא פנים. היחס שנשמר/נמצא "
    "מדווח, כי יחס נמוך אומר שהמיקום נשען על גלאי רועש.",
    "21.8.26 — הרצועה המועדפת יצאה 0.073 גובה (בלתי-שמישה) ונראתה כמו החלטה "
    "נכונה; רק פירוק הקופסאות חשף שארבע מהן על החולצה",
    "pipeline",
    [{"kind": "code", "file": "tools/illustration_place.py",
      "pattern": r"def _persistent_faces"},
     {"kind": "code", "file": "tools/illustration_place.py",
      "pattern": r"keep_ratio"},
     {"kind": "test", "file": "tests/test_illustration_place.py",
      "pattern": r"persistent|false_positive"}]),

 "L51_a_detector_that_quietly_stops_detecting": L(
    "גלאי שמפסיק לעבוד בשקט גרוע מגלאי שאין. OpenCV 5 הפסיק לארוז את קבצי "
    "ה-Haar, ושלושה כלים (`candidates` · `broll_vision` · `illustration_place`) "
    "עוטפים את הטעינה ב-try/except ונופלים בשקט ל'אין פנים'. לכן: (א) שער "
    "ב-doctor שמדווח כשהקסקייד חסר; (ב) שער שנשען על מדידה **מסמן** כשלא "
    "נמדד ואינו חוסם על סמך חוסר — `measured: false` הוא דאטה, לא PASS.",
    "21.8.26 — הפותר בחר מיקום שיושב על הראש, ובדיוק אז התגלה ש-cv2 5.0 "
    "מותקן בלי קסקיידים. הוחזר ל-4.10 והכושר חזר לשלושת הכלים",
    "pipeline",
    [{"kind": "code", "file": "tools/illustration_place.py",
      "pattern": r"unavailable:no-cascade"},
     {"kind": "code", "file": "tools/illustration_place.py",
      "pattern": r'"measured": False'},
     {"kind": "code", "file": "tools/system_doctor.py",
      "pattern": r"haarcascade"},
     {"kind": "test", "file": "tests/test_illustration_place.py",
      "pattern": r"unavailable|measured"}]),

 "L49_separate_at_the_source_not_with_an_algorithm": L(
    "שני שרירים סמוכים שנוגעים בצבע באיור **אינם ניתנים להפרדה** ממנו: שלוש "
    "שיטות נוסו ונכשלו (ארוזיה מורפולוגית · חיתוך לפי בהירות · חיתוך לפי "
    "רצועת הגיד החיוורת) כי לא קיים באיור חתך שאפשר למצוא. הפתרון אינו "
    "אלגוריתם טוב יותר אלא **קלט שניתן להפריד**: מבקשים מהמאייר רינדור שני "
    "של אותה קומפוזיציה עם צבע-מפתח רווי לכל שריר (`atlas`), גוזרים ממנו את "
    "המסכות לפי גוון, ומודדים את הרישום מול האיור היפה (IoU). האטלס משמש "
    "למסכות בלבד — מה שהצופה רואה נשאר האיור.",
    "הראל 21.8.26: \"ה-Teres Minor לא מדויק בגיליון.\" קו התפר נקרא ידנית "
    "מגריד, ולכן היה מדויק בדיוק כמו העין שקראה אותו",
    "broll",
    [{"kind": "code", "file": "tools/illustration_build.py",
      "pattern": r"def masks_from_atlas"},
     {"kind": "code", "file": "tools/illustration_gate.py",
      "pattern": r"def atlas_registration"},
     {"kind": "gate", "gate": "illustration_gate:IL7_atlas_registration"},
     {"kind": "test", "file": "tests/test_illustration_gate.py",
      "pattern": r"atlas"}]),

 "L47_illustration_is_rationed_not_available": L(
    "המחשה ויזואלית היא אירוע, לא פיצ'ר. ברירת המחדל היא אפס; אחת לסרטון; "
    "שתיים רק דרך חריגה מנומקת שחוצה סף גבוה בהרבה ומדווחת. בנוסף — קצב על "
    "פני הקטלוג: אם המחשות הופיעו ביותר מסרטון אחד מתוך חמשת האחרונים, הסף "
    "עולה. תוכן המרה מוחרג לגמרי (מצע בירולים רציף).",
    "הראל 21.8.26: \"זה אחלה וצריכים להשתמש בזה בחוכמה ובמינון נכון. בגג פעם "
    "אחת או שניים במקרים חריגים בסרטון ולא בכל סרטון.\" הסיכון אינו איכות "
    "אלא שכיחות — כלי שנראה טוב הופך למניירה תוך שבועיים",
    "plan",
    [{"kind": "code", "file": "tools/illustration_gate.py",
      "pattern": r"MAX_PER_VIDEO\s*=\s*1"},
     {"kind": "code", "file": "tools/illustration_gate.py",
      "pattern": r"def recent_rate"},
     {"kind": "gate", "gate": "illustration_gate:IL3_dosage_budget",
      "enforcement": "blocking"},
     {"kind": "gate", "gate": "illustration_gate:IL1_content_type_eligible",
      "enforcement": "blocking"},
     {"kind": "test", "file": "tests/test_illustration_gate.py",
      "pattern": r"dosage|MAX_PER_VIDEO"}],
    director_relevant=True),

 "L48_css_mask_from_file_url_is_blocked": L(
    "CSS mask-image מקובץ מקומי (file://) נחסם ב-Chrome ומחזיר ERR_FAILED — "
    "והשכבה הממוסכת נעלמת **בשקט**, בלי שגיאה בקונסולה ובלי שינוי ב-computed "
    "style. כל מסכה ותמונה בקומפוזיציה מוטמעות base64 inline. וברינדור מקומי "
    "מסירים את סקריפט הרנטיים של HyperFrames — הוא מרוקן את הקומפוזיציה.",
    "21.8.26 — שני פרקי דיבוג ארוכים באותה שעה: פעם אחת הרנטיים ריקן את ה-SVG, "
    "ופעם שנייה המסכות נחסמו. בשני המקרים הפריים היה שחור וה-DOM נראה תקין",
    "render",
    [{"kind": "code", "file": "tools/illustration_build.py",
      "pattern": r"data:image/(?:png|jpeg);base64"},
     {"kind": "code", "file": "tools/illustration_build.py",
      "pattern": r"hyperframe\.runtime"},
     {"kind": "test", "file": "tests/test_illustration_gate.py",
      "pattern": r"inline|base64"}]),

 "L50b_finish_run_from_server_inherits_path": L(
    "גם הגימור שהשרת מפעיל יורש את ה-PATH הקטוע: edl_cut נפל על ffmpeg חסר אחרי 0.4ש, "
    "ו-python3 היה 3.9 של המערכת. הריצה מקבלת סביבה עם נתיבי Homebrew (runner._tool_env), "
    "והצינור עצמו מקדים אותם בעלייה (ensure_tool_path) — שתי שכבות, כי גם הרצה ידנית "
    "מסביבה חלקית חייבת לעבוד.",
    "הראל 10.9.26 אישר את 'איך הכרנו' באפליקציה — הגימור נכשל מיד ונפתחה משימה "
    "'הגימור נכשל'. אותו שורש כמו L50 (22.8), שכבה אחרת",
    "app",
    [{"kind": "code", "file": "tools/relvid/runner.py", "pattern": r"env=_tool_env\(\)"},
     {"kind": "code", "file": "tools/local_finish_pipeline.py", "pattern": r"\nensure_tool_path\(\)\n"},
     {"kind": "code", "file": "tools/vision_check.py", "pattern": r"L50b"}]),

 "L54_music_bed_calibrated_down_again": L(
    "מצע המוזיקה כויל -44→-46 LUFS (דיבור -52→-54 בדאקינג 8). הכיוון נגזר מההערות: "
    "מאז 23.7 — 14 'חזק מדי/להנמיך' מול 0 'חלש מדי'; -55 נמדד כ'מעט נמוך' ו--52 כ'טיפה חזק'. "
    "שינוי נוסף רק עם ראיה כפולה (הערה + מפלס ידני באפליקציה), לא לפי תחושה.",
    "הראל 10.9.26 על-הלוח + טיפ-אחד-דאבל-אנדרס: 'טיפה להנמיך את הווליום של המוזיקה. "
    "זה משהו שקצת חוזר על עצמו ושווה לדייק במנגנון'",
    "audio",
    [{"kind": "code", "file": "tools/local_finish_pipeline.py",
      "pattern": r"--music-lufs\", type=float, default=-46\.0"},
     {"kind": "doc", "file": "tools/AUDIO-MIX.md", "pattern": r"-46"}]),

 "L55_retake_in_opening_is_not_the_hook": L(
    "טייק פתיחה שגוי שנאמר שוב מיד אחריו אינו ההוק — ההוק הוא הטייק החוזר. canon_lint "
    "מזהה חזרה של 3 המילים הראשונות בתוך 30ש ומזיז את חלון ההגנה (6ש) לטייק החוזר. "
    "בלי זה, הסרת הטייק השגוי (חוק 'טייק אחרון') נחסמה כ'מחיקת ההוק'.",
    "10.9.26 טיפ-אחד-דאבל-אנדרס: 'טיפ אחד לדאבל אנדרס… מה שאמרתי' ואז שוב 'טיפ אחד לדאבל "
    "אנדרס' ב-6.24ש. אחרי שהאפליקציה בנתה review.cuts, canon חסם: 5.5ש נחתכו מחלון הפתיחה",
    "gates",
    [{"kind": "code", "file": "tools/canon_lint.py", "pattern": r"def _hook_retake_start"},
     {"kind": "test", "file": "tests/test_canon_hook_retake.py", "pattern": r"retake"}]),

 "L60_canon_exception_is_data_not_a_workaround": L(
    "שער קאנון שצודק במקרה שאין לו דרך לדעת עליו מקבל **חריגה מוצהרת כנתון** — "
    "לא עקיפה בקוד, לא הנמכת סף, ולא כיבוי. החריגה נרשמת ב-project_manifest.json "
    "תחת canon_exceptions עם נימוק (20+ תווים), מאשר ותאריך, ומורידה HARD_FAIL "
    "ל-WARNING בלבד — לעולם לא ל-PASS — כשהנימוק נכנס לדוח. רשימת ההיתר "
    "(CANON_EXCEPTABLE) צרה בכוונה: חריגה גורפת היא ביטול השער. חריגה שנפסלה "
    "מדווחת ולא נבלעת. **נגזרת:** שער שרמתו נקבעת במשתנה עדיין שער — דפוס הסריקה "
    "ב-gate_registry חייב לתפוס גם את הצורה הזו, אחרת השער נראה לאודיט כמי שנעלם.",
    "21.9.26 אחרי-הריצה-עקפתי-את-פיין: 9.38ש הראשונות צילמו מתאמנים שאינם המרואיין "
    "באזור החלפה, חלקם ללא חולצה — חומר שאינו ניתן לפרסום ואין עריכה שמצילה אותו. "
    "הסרתו הפילה את hook_protected (6.0ש מתוך חלון 6ש), והתוצר נתקע ב-FINAL_PENDING "
    "למרות qa PASS ו-preflight נקי. _hook_retake_start מטפל בטייק חוזר בלבד ולא במקרה הזה",
    "gates",
    [{"kind": "code", "file": "tools/canon_lint.py", "pattern": r"CANON_EXCEPTABLE"},
     {"kind": "code", "file": "tools/canon_lint.py", "pattern": r"def _canon_exceptions"},
     {"kind": "code", "file": "tools/gate_registry.py", "pattern": r"CANON_EXC_REGISTRY_V1"},
     {"kind": "test", "file": "tests/test_canon_exception.py", "pattern": r"never_becomes_pass"}]),

 "L59_player_speed_only_on_input": L(
    "קצב הנגינה באפליקציה חל רק על INPUT (סימולציית העריכה). FINAL/PREVIEW כבר מכילים "
    "את ה-speed בקובץ; ניגון שלהם ב-playbackRate=speed מאיץ פעמיים, והמוזיקה — שבקובץ "
    "בקצב המקורי — נשמעת מואצת. גם defaultPlaybackRate נקבע, כי טעינת src מאפסת את הקצב.",
    "הראל 11.9.26 על 'איך הכרנו' (speed 1.175): 'המוזיקה לא צריכה להיות בקצב גבוה. זה נשמע "
    "מוזר.' בקובץ המוזיקה מעורבבת אחרי ההאצה — הבאג היה בנגן (setSpeed מ-reloadProject)",
    "app",
    [{"kind": "code", "file": "review-app/index.html", "pattern": r'curSrc==="input"\)\?speed:1'}]),

 "L50_server_must_not_depend_on_path": L(
    "שרת ארוך-חיים לא מאתר בינארים חיצוניים דרך PATH. השרת מופעל לעיתים "
    "בלי סביבת login, ואז `/opt/homebrew/bin` חסר: `subprocess.run([\"ffmpeg\"…])` "
    "זורק FileNotFoundError, המטפל הגלובלי מחזיר 404 \"פרויקט לא נמצא\", "
    "והתמונות נשברות **בשקט** — עם שגיאה שמצביעה על הבעיה הלא-נכונה. "
    "כל בינארי נפתר בנתיב מוחלט (`_ffmpeg_bin`), וכשל בינארי מקבל קוד שגיאה "
    "משלו (FFMPEG_MISSING) ולא מתחזה לכשל תוכן.",
    "הראל 22.8.26: \"הפריימים של החיתוך לא עובדים באפליקציה, לא רואים את "
    "התמונות.\" ה-404 טען שהפרויקט חסר — הפרויקט היה שם, ffmpeg לא",
    "app",
    [{"kind": "code", "file": "review-app/server.py",
      "pattern": r"def _ffmpeg_bin"},
     {"kind": "code", "file": "review-app/server.py",
      "pattern": r"FFMPEG_MISSING"},
     {"kind": "test", "file": "tests/test_review_app_binaries.py",
      "pattern": r"broken_path"}]),

 "L26_lessons_need_enforcers": L(
    "לקח בלי אוכף (קוד/בדיקה/שער) הוא נוהל שיישכח בהחלפת המנוע הבאה. הרשומה "
    "הזאת נבדקת ב---audit כשער ב-system_doctor.",
    "הראל 16.8.26 + הלקח מ-1.8.26 (fade/eof שנסוגו בשקט) (v9.13)",
    "process",
    [{"kind": "code", "file": "tools/system_doctor.py", "pattern": r"lesson_registry"},
     {"kind": "test", "file": "tests/test_lesson_registry.py"}]),
 # ── Visual Hook Engine (v9.23, 11.9.26) ────────────────────────────────
 "L56_visual_hook_off_by_default_no_unseen_treatment": L(
    "פתיחה חזותית: ברירת מחדל off; auto בלי קוהורט מאושר = NO_OP; טיפול מוחל רק מתוכנית "
    "שנצפתה ואושרה (digest), ואישור בלי תצוגה טרייה = אין טיפול (לא כשל). NO_OP היא החלטה תקינה.",
    "הראל 11.9.26 באישור יישום ה-MVP: \"שמור על ברירת מחדל off ועל הזרימה הקיימת. "
    "אל תפעיל אוטומטית בפרויקטים אמיתיים\"",
    "pipeline",
    [{"kind": "code", "file": "tools/visual_hook_policy.json", "pattern": r'"default_mode": "off"'},
     {"kind": "code", "file": "tools/local_finish_pipeline.py",
      "pattern": r'or a\.visual_hook or "off"'},
     {"kind": "code", "file": "tools/relvid/visual_hook.py", "pattern": r"auto_cohort_not_approved"},
     {"kind": "test", "file": "tests/test_visual_hook.py",
      "pattern": r"test_auto_without_approved_cohort_is_noop"},
     {"kind": "test", "file": "tests/test_visual_hook_review.py",
      "pattern": r"test_approve_without_fresh_preview_binds_nothing"}]),

 "L57_declared_transition_never_hides_a_flash": L(
    "מעבר מוצהר בתוכנית אינו פוטר פריים שחור/לבן בודד, A→B→A או תמונה ממקור לא נכון — "
    "הבדיקות רצות גם בנקודת המעבר, מול המקור הנקי (חשכה מהצילום אינה נענשת). G8 הישן לא הוחלש.",
    "הרחבת לקח הראל 19.7 (פלאש בשנייה הראשונה → G8) ולקחי ההבהוב 25.7 למנוע הפתיחה החזותית (11.9.26)",
    "gates",
    [{"kind": "code", "file": "tools/visual_hook_qa.py", "pattern": r'gate\("VH5_introduced_flash"'},
     {"kind": "gate", "gate": "visual_hook_qa:VH5_introduced_flash", "enforcement": "blocking"},
     {"kind": "gate", "gate": "qa_gates:G8_opening_flash", "enforcement": "advisory"},
     {"kind": "test", "file": "tests/test_visual_hook_qa.py",
      "pattern": r"test_wrong_source_at_declared_transition_is_not_exempt"}]),

 "L58_hook_engine_changes_picture_only_in_both_engines": L(
    "המנוע משנה תמונה בלבד: audio_mode=preserve, אותו מספר פריימים, EXPORT הנקי לא נדרס "
    "(cut_qa/קאבר צורכים אותו), ואותה תוכנית קפואה ב-v1, ב-v2 וב-fallback — אף ענף בירול "
    "ב-v1 לא מקבל ‎--base EXPORT כשיש טיפול.",
    "Hook קדוש (קאנון) + הראל 11.9.26 \"שמור על הזרימה הקיימת\"; ממצא האפיון: base יחיד "
    "נדרס ע\"י ‎--base EXPORT, ו-v2 מרנדר מ-INPUT ומתעלם מ-EXPORT מתוקן",
    "render",
    [{"kind": "code", "file": "tools/relvid/hook_render.py", "pattern": r"HOOK_AUDIO_CHANGED"},
     {"kind": "code", "file": "tools/local_finish_pipeline.py", "pattern": r'"--base", VISUAL_BASE'},
     {"kind": "code", "file": "tools/relvid/render.py", "pattern": r"hook_plan=None"},
     {"kind": "test", "file": "tests/test_visual_hook_render.py",
      "pattern": r"test_every_broll_overlay_uses_visual_base"},
     {"kind": "test", "file": "tests/test_visual_hook_render.py",
      "pattern": r"test_v2_frames_audio_and_pixels_speed_1"}]),

 # ── סרטוני "הראל חיון" — בניית אפליקציות ופרומפטים עם AI (v9.23) ──────
 "L60_cta_keyword_must_match_the_flow": L(
    "מילת המפתח שה-Flow האוטומטי מאזין לה, המילה שנאמרת בקול ב-CTA והטקסט על המסך "
    "הם דבר אחד. אי-התאמה הורגת את כל שרשרת המסירה **בשקט** — הסרטון נראה מצוין "
    "ואף אחד לא מקבל כלום. מילת מפתח שלא נאמרת בתמליל = חוב צילום, לא נושא לעריכה.",
    "הראל 12.9.26, אחרי שריל \"אפליקציית קניות\" (11.9.26) שבר שיא והופעלה אוטומציית "
    "Comment→DM ב-Metricool Flows: \"ודא שה-CTA בסוף הסרטון תואם למילת המפתח שנבחרה לפוסט\"",
    "preflight",
    [{"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"P17_ai_app"},
     {"kind": "gate", "gate": "preflight:P17_ai_app", "enforcement": "reporting"},
     {"kind": "test", "file": "tests/test_preflight_ai_app.py",
      "pattern": r"test_cta_text_not_containing_keyword_is_high"},
     {"kind": "test", "file": "tests/test_preflight_ai_app.py",
      "pattern": r"test_keyword_never_spoken_is_high"}]),

 "L61_problem_first_never_tool_first": L(
    "סרטון AI-אפליקציה נפתח בבעיה קונקרטית בגוף ראשון, לא בשם הכלי ולא ב-AI. "
    "המבנה: בעיה → מה בניתי → מה זה פתר. שם הכלי ב-4 השניות הראשונות = ממצא.",
    "הראל 12.9.26: \"שמור על מבנה כלל הפתיחה בבעיה — לא לפתוח בשם הכלי או ב-AI\"; "
    "מגובה במדידת יוצרים ישראלים (12.9.26): כל ההוקים החריגים פותחים בבעיה/בתוצאה, "
    "אף אחד לא פותח בשם הכלי",
    "preflight",
    [{"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"AI_TOOL_WORDS"},
     {"kind": "test", "file": "tests/test_preflight_ai_app.py",
      "pattern": r"test_opening_with_tool_name_is_flagged"},
     {"kind": "doc", "file": "skills/rel-social-video-editor/SKILL.md",
      "pattern": r"כלל הפתיחה בבעיה"}]),

 "L62_home_screen_moment_belongs_next_to_the_cta": L(
    "הצופה מקבל לינק ולא יודע שזה הופך לאפליקציה על הטלפון שלו. קטע \"הוספה למסך "
    "הבית\" באורך 5-10ש צמוד לרגע ה-CTA סוגר את הפער. חומר חסר = shot_debt מוצהר, "
    "לא ויתור שקט.",
    "הראל 12.9.26: \"הוסף קטע קצר (5-10 שנ') שמדגים הוספה למסך הבית — למקם ליד רגע ה-CTA\"",
    "preflight",
    [{"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"home_screen"},
     {"kind": "test", "file": "tests/test_preflight_ai_app.py",
      "pattern": r"test_missing_home_screen_segment"}]),

 "L63_value_goes_out_on_two_channels": L(
    "הערך נמסר בשני ערוצים ולא באחד: DM אוטומטי למי שהגיב, ודף הקישורים בביו "
    "(Metricool SmartLink) למי שלא. ערוץ אחד בלבד מאבד את כל מי שצפה ולא הגיב, "
    "ואת כל מי שמגיע לפרופיל חודש אחרי.",
    "הראל 12.9.26: \"תוכל גם להכניס את שליחת הערך בנוסף לאוטומציה גם בלינק בביו שלי. "
    "יש לנו במטריקול ריכוז של כל הקישורים\"",
    "preflight",
    [{"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"smartlink"},
     {"kind": "test", "file": "tests/test_preflight_ai_app.py",
      "pattern": r"test_missing_smartlink_is_reported"},
     {"kind": "doc", "file": "skills/rel-social-video-editor/SKILL.md",
      "pattern": r"SmartLink"}]),

 "L64_public_artifact_is_pinned_never_latest": L(
    "דף אפליקציה מתארח כ-Artifact של קלוד. לינק ציבורי (General access = Anyone with the link) "
    "**תמיד נעוץ לגרסה מספרית** — האפשרות Latest חסומה כל עוד הגישה ציבורית. לכן כל פרסום מחדש "
    "לא מגיע לקהל עד שמזיזים ידנית את Shared version, ואין על זה שום שגיאה. אימות: כפתור ה-Share "
    "עצמו אומר sharing pinned version {n}.",
    "הראל 12.9.26 (\"אני לא רוצה שזה יעלה דרך Netlify. האמת ש-Artifact זה רעיון מעולה. רק צריך "
    "לוודא באמת שהוא פתוח לשיתוף תמיד\") + ההודעה שנמדדה ב-UI: \"Can't switch to Latest while "
    "people outside your organization can open this artifact\"",
    "publishing",
    [{"kind": "doc", "file": "skills/rel-social-video-editor/SKILL.md",
      "pattern": r"sharing pinned version"},
     {"kind": "doc", "file": "handoff/link-in-bio/README.md",
      "pattern": r"Shared version"}]),

 "L65_activated_flow_must_prove_zero_backfill": L(
    "אוטומציית תגובה→DM מופעלת רק אחרי שנמדד שהיא לא נגעה בתגובות הקיימות: מיד אחרי "
    "Activate בודקים ברשימת ה-Flows ש-Sends=0 ו-Last execution ריק. הראל שולח ידנית לפני "
    "שהאוטומציה קיימת, ולכן backfill = הודעה שנייה לאותם אנשים, נזק בלתי הפיך.",
    "הראל 12.9.26: \"הכי חשוב אבל שזה לא ישלח לתגובות קיימות אלא רק לתגובות שיעלו מעכשיו. "
    "כי כבר שלחתי ידנית לכולם. שזה לא ישלח פעמיים\" — נמדד על ריל עם 111 תגובות",
    "publishing",
    [{"kind": "doc", "file": "handoff/link-in-bio/פלייבוק-Flow-תגובה-ל-DM.md",
      "pattern": r"Sends = 0"},
     {"kind": "doc", "file": "skills/rel-social-video-editor/SKILL.md",
      "pattern": r"Last execution"}]),

 "L66_pixabay_license_not_immune_to_content_id": L(
    "רישיון Pixabay מתיר שימוש אבל לא מחסן מפני Content ID: אותה הקלטה יכולה "
    "להיות רשומה במקביל אצל מנהל-זכויות צד-שלישי (למשל HAAWK), ויוטיוב חוסם "
    "את הסרטון גלובלית למרות רישיון תקין. טראק שנתבע/נחסם עובר מיד ל-"
    "brand-assets/music/_disabled/ (ה-glob הלא-רקורסיבי ב-pick_music מוציא אותו "
    "מהרוטציה אוטומטית) ומסומן banned+banned_reason בקטלוג — לעולם לא רק מוסר "
    "בשקט בלי תיעוד של הסיבה.",
    "הראל 13.9.26, על מייל חסימת יוטיוב מ-11.9.26 (Content ID של HAAWK על הטראק "
    "Starostin, שנבחר ידנית ב-29.7.26 לפרק 'מאסל-מן-רוטטור-קאף', studio "
    "4t6zfzCc-pk): \"תלמד מזה לפעמים הבאות שלא יחסמו לנו ביוטיוב את הסרטון\"",
    "music",
    [{"kind": "code", "file": "tools/local_finish_pipeline.py",
      "pattern": r'MUSIC_DIR\.glob\("\*\.mp3"\)'},
     {"kind": "doc", "file": "tools/music-catalog.json",
      "pattern": r'"banned": true'}]),

 # ── אורך הריל ─────────────────────────────────────────────────────────
 "L67_length_follows_content_not_60s": L(
    "אורך הריל נקבע ע\"י סוג התוכן — הכי קצר שמנחית את הרעיון במלואו — ולא ע\"י תקרת "
    "60ש. המרה/הוק לקהל קר: 20-45ש; ערך/הסבר/סיפור/חיבור: 45-90ש; נימוק אמיתי מעל "
    "90 לכל סוג (הראל 19.9 ערב, v9.26); פודקאסט: 45-90ש (נימוק מעל 120). חוסם רק 12-180ש. לעולם לא מאיצים "
    "סרטון רק כדי להיכנס מתחת ל-60 — ההוק (view-rate 3ש, rho=0.83 מול reach) הוא "
    "הלוחץ, לא האורך (rho=0.10 על 40 ריילס).",
    "הראל 19.9.26: \"לא כל סרטון חייב להיות מוגבל עד 60 שניות... אם עוברים 90 שנ׳, "
    "צריך שתהיה סיבה אמיתית שהצופה ירצה להמשיך\" — מחליף את תקרת ה-60ש מ-23.7.26 "
    "ואת ה-speed_fit האוטומטי מ-25.7.26. מחקר: docs/מחקר-אורך-ריל-19.9.26.md",
    "pipeline",
    [{"kind": "code", "file": "tools/length_policy.py", "pattern": r"HARD_MAX = 180\.0"},
     {"kind": "code", "file": "tools/local_finish_pipeline.py",
      "pattern": r"dur > LP\.HARD_MAX"},
     {"kind": "gate", "gate": "qa_gates:G1c_length_reason", "enforcement": "advisory"},
     {"kind": "test", "file": "tests/test_length_policy.py",
      "pattern": "test_no_60s_cap_anywhere"},
     {"kind": "test", "file": "tests/test_length_policy.py",
      "pattern": "class TestHarelNumbers"},
     {"kind": "doc", "file": "docs/מחקר-אורך-ריל-19.9.26.md"}],
    director_relevant=True),

 # ── שומרי הגלם (v9.26, ארכיון REL Throwdown 2026) ──────────────────────
 "L68_fixed_clip_must_invalidate_cache": L(
    "קליפ שתוקן במקור (סיבוב, צנזור בנביחה) חייב להחליף את העותק בתיקיית העבודה "
    "ולמחוק כל נגזרת שנבנתה מהעותק הישן (INPUT, תמלולים, ROUGH) — אחרת הבנייה "
    "החוזרת מרנדרת את הגלם הישן בלי שום שגיאה. השוואה בגודל וב-mtime, לא בקיום.",
    "ארכיון Throwdown 2026 (19.9.26): קליפים שסובבו/צונזרו נבנו מחדש ויצאו זהים — "
    "clip_NN ישן + INPUT.mp4 במטמון. תוקן קודם ב-_td26/build_proj.py והועבר לכלי קנוני.",
    "pipeline",
    [{"kind": "code", "file": "tools/intake_guard.py", "pattern": r"def sync_clip_copy"},
     {"kind": "code", "file": "tools/intake_guard.py", "pattern": r"DERIVED = \("},
     {"kind": "gate", "gate": "intake_guard:I2_stale_clip_copy", "enforcement": "reporting"},
     {"kind": "test", "file": "tests/test_intake_guard.py",
      "pattern": "test_injected_stale_copy_is_refreshed"}]),

 "L69_sideways_raw_is_judged_by_frame": L(
    "גלם שצולם לאורך ונשמר landscape עם rotation (180/0) יוצא עם הדמות על הצד. "
    "המטא-דאטה רק מעוררת חשד — הפריים מכריע (פנים ב-0°/90°/180°/270°). חשד ⇒ דיווח "
    "בכניסה ובפרה-פלייט עם הצעת תיקון, ואז עין על הפריים. לא חוסם: נמדד 2.7% "
    "חיובי-שגוי על 257 קליפים. אין גלאי ⇒ measured:false, לא PASS שקט.",
    "ארכיון Throwdown 2026 (19.9.26): קליפ שצולם הפוך (IMG_4997, vibe) נכנס ל-ROUGH; "
    "תוקן ידנית ב-_td26/fixrot.sh אחרי שנראה בגיליון.",
    "pipeline",
    [{"kind": "code", "file": "tools/intake_guard.py", "pattern": r"def judge_orientation"},
     {"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"P19_orientation"},
     {"kind": "code", "file": "tools/intake_guard.py", "pattern": r"ORIENT_EVIDENCE = "},
     {"kind": "gate", "gate": "intake_guard:I1_orientation", "enforcement": "advisory"},
     {"kind": "gate", "gate": "preflight:P19_orientation", "enforcement": "reporting"},
     {"kind": "test", "file": "tests/test_intake_guard.py",
      "pattern": "test_injected_sideways_is_flagged"}]),

 "L70_turbo_vad_drops_noisy_speech": L(
    "turbo עם VAD על INPUT מפספס דיבור רועש (קהל, מוזיקה ברחבה); קטע שנשמר עם "
    "פחות מ-0.6 מילים/ש הוא חשד לחור בכתוביות. מדווח (הסף לא נמדד מול מאושרים), "
    "והתיקון הוא האזנה חוזרת ב-large-v3 בלי VAD על הקליפ — לא ניחוש מילים.",
    "ארכיון Throwdown 2026 (19.9.26): ראיונות ברחבה יצאו עם חורים בכתוביות; "
    "_td26/gapcheck.py + relisten_words.py + fixgaps.py מילאו אותם.",
    "captions",
    [{"kind": "code", "file": "tools/intake_guard.py", "pattern": r"def word_density_gaps"},
     {"kind": "code", "file": "tools/intake_guard.py", "pattern": r"vad_filter=False"},
     {"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"def check_caption_density"},
     {"kind": "gate", "gate": "preflight:P18_caption_density", "enforcement": "reporting"},
     {"kind": "test", "file": "tests/test_intake_guard.py",
      "pattern": "test_injected_silent_keep_is_reported"}]),

 # ── v9.29 (22.9.26) — שדרוג Opus 5.5: מה שנבדק בעיוורון הופך לשער מדוד ──
 "L71_captions_are_judged_on_the_pixels": L(
    "הכתוביות נשפטות על הפריים של ה-FINAL, לא על המילים: כל cue מושווה לרינדור "
    "הצפוי (אותו קוד שצורב) ולרינדור ההפוך. היפוך RTL כפול משוחזר ע\"י מחרוזת "
    "הפוכה — direction=ltr ב-raqm זהה לנכון ולכן אינו ייחוס. חוסם רק דגל שנמדד "
    "נקי על המאושרים; ציר מילים שלא תואם ל-FINAL הוא ממצא, לא רעש.",
    "V7 היה 'ידני לנצח' (17.8.26); תקלת ההיפוך הכפול (24.7.26) עברה כל שער מילים. "
    "המדידה (22.9.26) מצאה גם FINAL שנצרב מקובץ מילים אחר (טיפ-אחד-HSPU) ופתיח "
    "לא רשום (מאסל-מן, 10.1ש).",
    "captions",
    [{"kind": "code", "file": "tools/caption_vision.py", "pattern": r"def score_cue"},
     {"kind": "code", "file": "tools/caption_vision.py", "pattern": r"text\[::-1\]"},
     {"kind": "code", "file": "tools/caption_vision.py", "pattern": r"def estimate_offset"},
     {"kind": "code", "file": "tools/local_finish_pipeline.py", "pattern": r"V7_captions"},
     {"kind": "code", "file": "tools/preflight_critic.py", "pattern": r"def check_caption_vision"},
     {"kind": "gate", "gate": "caption_vision:reversed", "enforcement": "blocking"},
     {"kind": "gate", "gate": "caption_vision:missing", "enforcement": "blocking"},
     {"kind": "test", "file": "tests/test_vision_gates_v929.py",
      "pattern": "test_injected_reversed_captions_block"},
     {"kind": "test", "file": "tests/test_vision_gates_v929.py",
      "pattern": "test_ltr_does_not_reproduce_double_reversal"}]),

 "L72_the_cover_is_judged_on_the_png": L(
    "קאבר נשפט על ה-PNG שיצא, לא על הקלט לבונה: שתי שורות בפיקסלים, כותרת גדולה "
    "מתת-כותרת בגודל-גופן שנאמד מהדיו, אין כתובית מחוץ לקופסה, וסדר הגליפים תואם "
    "פריסה ידנית תו-אחר-תו (ייחוס שלא עובר דרך shaping). הסבולת יחסית לגובה השורה "
    "— Studentit הוא קו דק ונענש על עובי ולא על צורה.",
    "תקלות הקאבר שהראל תפס (תת-כותרת הפוכה/מקוטעת, 126px מול 80px, 'אז מה' מבצבץ) "
    "היו בפלט בזמן שהקלט עבר את G-COVER1..3. נמדד 22.9.26 על 36 קאברי cover_make.",
    "cover",
    [{"kind": "code", "file": "tools/thumbnail/cover_vision.py", "pattern": r"def manual_layout"},
     {"kind": "code", "file": "tools/thumbnail/cover_make.py", "pattern": r"G-COVER5"},
     {"kind": "gate", "gate": "cover_make:G-COVER5_png_vision", "enforcement": "blocking"},
     {"kind": "test", "file": "tests/test_vision_gates_v929.py",
      "pattern": "test_injected_reversed_text_blocks"},
     {"kind": "test", "file": "tests/test_vision_gates_v929.py",
      "pattern": "test_injected_one_line_blocks"}]),

 "L73_measured_does_not_mean_promoted": L(
    "למדוד שער זה לא לקדם אותו לחוסם. ההחלטה נגזרת מהמדידה ונשמרת כדאטה "
    "(promote + why_not_blocking): סף קאנוני שהיה פוסל סרטון מאושר, או שער בלי "
    "מחלקה שלילית, נשאר מדווח — עם המעטפת בפירוט.",
    "V3/V4 החזירו no_data תמיד: אף bundle של המאושרים לא הכיל תמליל. מציר הכתוביות "
    "(22.9.26): V3 0–5.51ש — 0.30ש היה פוסל 4/16; V4 121–200 מילים/דקה בלי שלילי.",
    "vision",
    [{"kind": "code", "file": "tools/vision_check.py", "pattern": r"def promotion"},
     {"kind": "code", "file": "tools/vision_check.py", "pattern": r"def words_timeline"},
     {"kind": "code", "file": "tools/vision_check.py", "pattern": r"MEASURED_NOT_PROMOTED"},
     {"kind": "test", "file": "tests/test_vision_gates_v929.py",
      "pattern": "test_measured_but_not_promoted_stays_reporting"}]),

 # ── v9.30 (22.9.26) — קנון הלקחים: לקחים שחיו רק בזיכרון מקבלים אוכף ──
 'L74_ffmpeg_never_reads_stdin': L(
    'ffmpeg שרץ מתוך תהליך לעולם לא קורא stdin (-nostdin / stdin=DEVNULL). ffmpeg שיורש TTY מחכה ל-[q] ונכשל רק כשמריצים מטרמינל אינטראקטיבי — תקלה שנראית כמו באג בפרמטרים.',
    "audio_mix נכשל פעמיים ב-26.7.26 בשלב המוזיקה מתוך Desktop Commander; עקיפה ב-'< /dev/null' בלבד עד v9.30.",
    'pipeline',
    [{'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': 'stdin=subprocess\\.DEVNULL'}, {'kind': 'code', 'file': 'captions-app/captions_overlay.py', 'pattern': '"-nostdin"'}, {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_audio_mix_never_reads_stdin'}]),
 'L75_broll_brand_identity_is_checked': L(
    "בירול של הראל (ספריית 'הראל חיון' / personal_tags / identity מאימות ויזואלי) לא נכנס לתוכן מועדון — והבדיקה נעשית על מה שנצרב ב-FINAL, לא רק בבחירה.",
    "הראל 25.7.26: 'עדיף לא לשלב בירולים של הראל בסרטונים שנוגעים לקרוספיט'. v9.30: פגישת-יעדים של מיכאל לוי סומנה identity=harel? באימות הבריכה.",
    'broll',
    [{'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'def b3_identity'}, {'kind': 'code', 'file': 'tools/broll_pick.py', 'pattern': 'personal_tags'}, {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_harel_clip_in_club_is_flagged'}]),
 'L76_burned_text_is_judged_by_eyes': L(
    "טקסט גרפי צרוב בבירול נשפט בעין (פסק-דין מודלי burned_text בגיליון העיגון), לא בגלאי פיקסלים: גלאי 'טקסט סטטי על מצלמה שזזה' נמדד על 532 קליפים ונתן ציונים גבוהים לצילומי חצובה עם רקע סטטי — לא מפריד, ולכן מדווח בלבד.",
    'קציר 21.8.26: פריים פודקאסט עם טקסט צרוב עבר כל שער מדיד; מדידה 22.9.26 על כל הבריכה.',
    'broll',
    [{'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'def text_static_score'}, {'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'burned_text'}, {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_anchor_answer_requires_all_booleans'}]),
 'L77_broll_is_judged_where_it_landed': L(
    'בירול נשפט במקום שבו נחת ב-FINAL מול מה שנצרב בפועל (items_applied במניפסט), לא מול התוכנית: FINAL מושווה לרינדור הצפוי של הקליפ (אותו גרף overlay — מסך מלא, blur 0) ולבסיס של הדובר.',
    "22.9.26: בשני סרטונים מאושרים broll_plan.json לא הוחל בכלל, ובשלישי הקליפ הראשון הושמט ע״י מגן ה-Hook — מדידה מול התוכנית הייתה מדווחת 'לא נחת' על משהו שלא נועד לנחות.",
    'broll',
    [{'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'def b1_landed'}, {'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'items_applied'}, {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': '"\\-\\-width",\\ "1080",\\ "\\-\\-blur",\\ "0"'}, {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_landed_broll_matches_and_missing_is_caught'}]),
 'L78_anchor_verdict_is_bound_to_the_final': L(
    "'הבירול מאייר את המשפט' הוא שיפוט מודלי — נשמר כדאטה (BROLL_ANCHOR_VERDICT) עם sha של ה-FINAL; FINAL שהשתנה הופך את הפסיקה ל-stale; בלי פסיקה = 'לא נמדד', לא PASS.",
    "הראל 25.7.26: 'מה שנאמר קובע מה נראה — זה צריך להיות היסוד'. עד v9.30 רק הנימוק בתוכנית נבדק (L06), לא הפריים.",
    'broll',
    [{'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'def anchor_apply'}, {'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'final_sha'}, {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_stale_anchor_verdict_is_rejected'}]),
 'L79_e2e_on_copies_never_commits_usage': L(
    'ריצת גימור על עותקים/תצוגה מקדימה לא כותבת usage גלובלי של בירולים (REL_BROLL_USAGE_COMMIT=0) — אחרת בדיקות מזהמות את רוטציית הבחירה של סרטונים אמיתיים.',
    'feedback_e2e_copies_leak_broll_usage; הוראת הראל 22.9.26: אסור e2e על עותקים בלי לנטרל כתיבת usage.',
    'pipeline',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': 'REL_BROLL_USAGE_COMMIT'}, {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_usage_commit_can_be_neutralized'}]),
 'L80_hlg_is_tonemapped_not_graded': L(
    "גלם HLG/HDR מומר ל-SDR בשרשרת מכוילת בלבד — במק tonemap.swift, בענן tools/hdr_gate.py (zscale+hable npl=160, כויל מול tonemap.swift, SSIM 0.95/0.98) — לא בתיקון צבע ידני. 'צבעים דהויים' = לבדוק color_transfer קודם.",
    'גוון חום ב-Descript, דהייה אחרי ffmpeg — כולם HLG לא-מטופל (7.26).',
    'render',
    [{'kind': 'code', 'file': 'tools/relvid/render.py', 'pattern': 'tonemap.swift'}, {'kind': 'code', 'file': 'tools/relvid/registry.py', 'pattern': 'color_transfer'}, {'kind': 'code', 'file': 'tools/hdr_gate.py', 'pattern': 'CALIBRATION'}]),
 'L81_no_arabic_codepoints_in_hebrew': L(
    'אין תו ערבי בכתוביות/שמות קבצים עבריים — אותיות מתחלפות חזותית ועוברות כל בדיקת מילים.',
    'לקח 20.7.26.',
    'captions',
    [{'kind': 'code', 'file': 'tools/caption_safety.py', 'pattern': 'arabic_char'}, {'kind': 'gate', 'gate': 'caption_safety:arabic_char', 'enforcement': 'blocking'}]),
 'L82_same_timestamp_words_are_decollided': L(
    'מילים סמוכות עם אותו timestamp (אינטרפולציה) מפוזרות לחלונות נפרדים ומונוטוניים — אחרת אחת דורסת את השנייה ונעלמת מהמסך.',
    "'מילים נעלמות' 22.6/30.6.26.",
    'captions',
    [{'kind': 'code', 'file': 'tools/align_reconcile.py', 'pattern': 'de-collide'}]),
 'L83_rtl_punctuation_lands_left': L(
    'סימני ? ! בסוף cue עברי נוחתים משמאל: ב-libass כל cue עטוף RLE/PDF; ב-PIL raqm עם direction=rtl — והפיקסלים נבדקים ב-V7.',
    'הראל 30.6.26.',
    'captions',
    [{'kind': 'code', 'file': 'tools/captions_build.py', 'pattern': 'RIGHT-TO-LEFT EMBEDDING'}, {'kind': 'code', 'file': 'tools/caption_vision.py', 'pattern': 'def score_cue'}]),
 'L84_concat_truncation_is_measured_on_video': L(
    'concat demuxer עם -c copy יכול לקטוע את ערוץ הווידאו בשקט (exit 0, אודיו ממשיך). משך נבדק על ערוץ הווידאו עצמו, ובכשל ה-join נבנה מחדש ב-concat filter — לא רק נכשל אחרי שהקובץ השבור נכתב.',
    'ניפוץ מיתוסים 23.7.26: וידאו נעצר ב-24ש, אודיו עד 47ש.',
    'render',
    [{'kind': 'code', 'file': 'tools/edl_cut.py', 'pattern': 'def ffprobe_vdur'}, {'kind': 'code', 'file': 'tools/edl_cut.py', 'pattern': 'def concat_filter'}, {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_concat_filter_joins_full_length'}]),
 'L85_burned_words_are_real_hebrew': L(
    "כל מילה שנצרבת היא עברית מוכרת: גלוסרי ASR לשיבושים חוזרים + שער לקסיקון G9 חוסם. 'לא ממציאים' אינו מצדיק להשאיר מילה שלא קיימת.",
    "הראל 30.7.26: 'הכתוביות מלאות בשגיאות כתיב'; מנוע התיקון אושר על אופן ג'ים 40+.",
    'captions',
    [{'kind': 'code', 'file': 'tools/caption_lexicon_qa.py', 'pattern': 'def '}, {'kind': 'code', 'file': 'tools/align_words.py', 'pattern': 'asr-glossary'}]),
 'L86_music_bed_in_every_video_full_length': L(
    "מצע מוזיקה בכל סרטון, בכל סוג תוכן, לאורך מלא בלי אובדן זנב; אנרגטי ולא 'מעלית'. הכלל 'רק מכירה' בוטל 22.6.26.",
    'feedback_music_sales_only · music_upbeat_not_elevator · music_mix_no_ducking_full_length.',
    'music',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': '# 6. music'}, {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': 'energetic'}]),
 'L87_intro_gesture_is_not_silence': L(
    'שקט בתוך מחווה פיזית בפתיחה (מחיאת כף, תנועה לפני מילה) אינו שקט לחיתוך: --intro-keep ו---max-word-dur ביחד.',
    'קפיצה בפתיחה בין מחיאת כף לדיבור.',
    'edit',
    [{'kind': 'code', 'file': 'tools/tighten_finish.py', 'pattern': 'intro_keep'}, {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': '--max-word-dur'}]),
 'L88_one_generation_spends_the_bitrate': L(
    'ב-v2 יש דור קידוד אחד — שם מוציאים את התקציב (crf19/medium), לא crf23/veryfast שנבחר כשהיו 4-7 דורות.',
    'v2 crf23 מרכך את התמונה (30.7.26).',
    'render',
    [{'kind': 'code', 'file': 'tools/relvid/render.py', 'pattern': '"crf":\\ 19'}]),
 'L89_no_black_bars_blur_fill': L(
    'מקור שאינו 9:16 ממלא את הפריים ברקע מטושטש של אותו פריים — אף פעם פסים שחורים (קאבר ובירול).',
    'feedback_landscape_to_vertical_blur_background.',
    'render',
    [{'kind': 'code', 'file': 'tools/thumbnail/thumbnail_build.py', 'pattern': 'blur-fill'}, {'kind': 'code', 'file': 'tools/animation_overlay.py', 'pattern': 'force_original_aspect_ratio=increase'}]),
 'L90_filtergraph_hygiene': L(
    "filter_complex נבנה בלי ';' עודף בסוף — ffmpeg מחזיר 'No such filter: ' על גרף תקין.",
    'tighten_finish 24.7.26.',
    'render',
    [{'kind': 'code', 'file': 'tools/tighten_finish.py', 'pattern': 'fc\\.rstrip\\(";"\\)'}]),
 'L91_correction_bursts_count_once': L(
    'קליקים חוזרים של הראל על אותו חיתוך תוך שניות הם אירוע אחד בלולאת הלמידה (BURST_GAP_SEC) — אחרת הראיות מתנפחות.',
    'learn_from_edits 23.7.26.',
    'plan',
    [{'kind': 'code', 'file': 'tools/learn_from_edits.py', 'pattern': 'BURST_GAP_SEC'}]),
 'L92_scheduled_fetch_never_waits_for_confirm': L(
    'משיכה מתוזמנת לא יכולה לחכות לאישור אינטראקטיבי: osxphotos רץ עם --update, אחרת Abort שקט ו-0 הורדות.',
    'קציר הגלריה ייצר 0 בירולים שבועיים.',
    'pipeline',
    [{'kind': 'code', 'file': 'tools/gallery_cut.py', 'pattern': '"--update"'}]),
 'L93_music_intro_dip_is_measured': L(
    'טראק שצונח לקטע שקט ב-8ש הראשונות נמדד בכל מיקס ומדווח עם offset מוצע — loudnorm מנרמל ממוצע ולא פותר דיפ מקומי. לא מוחל אוטומטית: שינוי שמיעתי דורש את האוזן של הראל.',
    "הראל 20.7.26 על 513742: 'ההתחלה שקטה — תגיע לקטע הטוב'. נמדד 22.9.26: דיפ ב-4ש, קטע חזק מ-12ש — בדיוק התקלה.",
    'music',
    [{'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': 'def music_intro_dip'}, {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_music_intro_dip_finds_the_known_track'}]),

 # ── v9.32 (23.9.26) — גל 5: B1 חוסם, B2 נכשל במדידה, B4 מול פסיקת הראל ─────────
 'L94_gate_false_positive_is_measured_before_blamed': L(
    'כשגלאי מסמן "לא נחת" על סרטון מאושר — קודם מודדים את הגלאי (היסט זמן, צפיפות דגימה), '
    'ורק אחר כך מאשימים את הרשומה. B1 דוגם את הקליפ כל 0.25ש ולוקח חציון של 5 רגעים בחלון.',
    '22.9.26 ה-6.4% של B1 יוחסו ל"גימור ידני אחרי items_applied". 23.9.26 נמדד: הקליפ היה על '
    'המסך (ncc 0.9999 בהיסט 0.8ש) — 8 דגימות לקליפ החמיצו אותו. אחרי התיקון: 0% על 120, B1 חוסם.',
    'qa',
    [{'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'SAMPLE_STEP_SEC = 0.25'},
     {'kind': 'code', 'file': 'tools/broll_vision_qa.py', 'pattern': 'def window_sim'},
     {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_dense_sampling_finds_clip_between_old_samples'},
     {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_window_median_survives_one_bad_moment'},
     {'kind': 'gate', 'gate': 'broll_vision:not_landed', 'enforcement': 'blocking'}]),
 'L95_no_hebrew_ocr_burned_text_is_judged': L(
    'Vision של macOS לא קורא עברית (27: אין he ב-supportedRecognitionLanguages); גילוי אזורי טקסט '
    'בלי שפה תפס 58% מהכיתובים המוזרקים ב-4.7% FP ⇒ לא נכנס לקוד. טקסט צרוב בבירול נשפט '
    'בעין (burned_text בפסיקת B4) ובקוהורט של הראל — לא בגלאי.',
    'handoff opus55 "הבא בתור 2" (22.9.26); נמדד 23.9.26 על 150 קליפי בריכה + 60 הזרקות + 2 הפסולים מהקציר.',
    'qa',
    [{'kind': 'code', 'file': 'tools/broll-vision-calibration.json', 'pattern': 'b2_ocr_v932'},
     {'kind': 'gate', 'gate': 'broll_vision:burned_text'}]),
 'L96_model_judgment_needs_harel_cohort': L(
    'שיפוט מודלי (B4 עיגון בירול למשפט) עובר ל-MEASURED רק אחרי ≥20 פסיקות של הראל על אותם '
    'חלונות, עם sha של ה-FINAL, והסכמה ≥90% על מה שהשער היה חוסם. פסיקה על FINAL שהשתנה נפסלת.',
    'עקרון 1 (סף ממדידה של סרטונים שהראל אישר) + v9.22 (calibrated:false עד פסיקת הראל). '
    'קוהורט 23.9.26: 25 חלונות מ-10 סרטוני ערך/חיבור.',
    'qa',
    [{'kind': 'code', 'file': 'tools/anchor_cohort.py', 'pattern': 'MIN_LABELS = 20'},
     {'kind': 'test', 'file': 'tests/test_vision_gates_v930.py', 'pattern': 'test_anchor_cohort_rejects_stale_and_needs_twenty'}]),

 # ── v9.33 (23.9.26) — תוזמן ≠ פורסם ─────────────────────────────────────
 'L97_scheduled_is_not_published': L(
    'אחרי תזמון מאומת (getScheduledPosts) הפרויקט מסומן state_override="scheduled" — לא '
    '"published". published רק ידנית או כש-Metricool מראה PUBLISHED. שניהם '
    '(SCHEDULE_CLOSED_STATES) יוצאים מתור "מוכן לתזמון", מ-/api/next ומהבריף לקלאוד.',
    'הראל 24.7.26: "הושלם באפליקציה זה לא פורסם בפועל אלא תוזמן" (feedback_published_vs_scheduled_state_bug). '
    'לקח 23.8.26: 12 פרויקטים שתוזמנו נשארו ב-ready_to_schedule ⇒ סכנת תזמון כפול, ולכן הסקיל '
    'השתמש ב-published כעקיפה עד v9.33.',
    'app',
    [{'kind': 'code', 'file': 'tools/relvid/registry.py', 'pattern': r'SCHEDULE_CLOSED_STATES = \("scheduled", "published"\)'},
     {'kind': 'code', 'file': 'review-app/server.py', 'pattern': r'in reg\.SCHEDULE_CLOSED_STATES'},
     {'kind': 'test', 'file': 'tests/test_scheduled_state_v933.py', 'pattern': 'test_b_scheduled_with_queued_comment_stays_closed'},
     {'kind': 'doc', 'file': 'skills/rel-social-video-editor/SKILL.md', 'pattern': r'state_override:"scheduled"'}]),

 # ── v9.34 (23.9.26) — גל 6: הידוק מה שנשאר מדווח, לפי מדידה ────────────────
 'L98_caption_check_weights_recall_on_event_backgrounds': L(
    'שיבוש כתוביות נמדד ב-g1 = f_ok1 × recall: דיו זר ברקע אירוע מוריד precision ולא recall, '
    'גליף שגוי מוריד recall. חוסם ב-≥3 cues בלי תנאי אחוז — הסף נגזר מכל ה-cues של כל FINAL '
    'חי (המקסימום בתקין: 2, כתובית נכונה על חולצה לבנה), לא מ-16 המאושרים בלבד.',
    'handoff opus55 "גל 1": garbled סימן 5 cues תקינים בדרג-לי-את-הפודיום ולכן חסם רק ב-≥25%. '
    'נמדד 23.9.26 על 50 FINAL (13 Throwdown): E2E על עותק — 3 מילים מוזרקות ⇒ rc=1; הכלל הישן לא עוצר.',
    'qa',
    [{'kind': 'code', 'file': 'tools/caption_vision.py', 'pattern': r'flags\.append\("garbled_cue"\)'},
     {'kind': 'code', 'file': 'tools/caption-vision-calibration.json', 'pattern': 'garbled_cue_w6'},
     {'kind': 'test', 'file': 'tests/test_vision_wave6_v934.py', 'pattern': 'test_wrong_words_on_screen_block_by_count'},
     {'kind': 'test', 'file': 'tests/test_vision_wave6_v934.py', 'pattern': 'test_two_cues_report_but_do_not_block'},
     {'kind': 'gate', 'gate': 'caption_vision:garbled_cue', 'enforcement': 'blocking'}]),
 'L99_face_under_caption_needs_eyes': L(
    'Haar-פנים לבדו אינו "פנים": 35 פגיעות ב-3,656 cues, 4 אמיתיות בעין (ידיים, ברכיים, חולצה). '
    'face נספר רק עם ≥2 עיניים בתיבה (4/4, 0/31). marginv דינמי לא מומש: 4 cues מסרטון סלפי '
    'אחד מ-50 — ההמלצה לסרטון הזה היא marginv נמוך יותר (330 ניקה 4/4).',
    'handoff opus55 "גל 6 ב\'": למדוד אם marginv דינמי משפר בלי לפגוע בקריאות. face_sheet_*.jpg נקראו בעין 23.9.26.',
    'qa',
    [{'kind': 'code', 'file': 'tools/caption_vision.py', 'pattern': 'def eyes_in'},
     {'kind': 'test', 'file': 'tests/test_vision_wave6_v934.py', 'pattern': 'test_haar_hit_without_eyes_is_not_face'},
     {'kind': 'gate', 'gate': 'caption_vision:face'}]),
 'L100_word_attribution_only_where_font_matches_reference': L(
    'ייחוס ברמת מילה עובד רק כשהפונט מצויר כמו הייחוס הידני: כותרת Assistant — מאושרים ≥0.991 '
    'מול מילה מעורבבת ≤0.909 ⇒ garbled_word חוסם. תת-כותרת Studentit (כתב-יד עם shaping) — '
    'מאושרים עד 0.375 ⇒ נמדד ונפל, לא בקוד. רווח בסוף רצף LTR ("17 ") הוא גבול מילה.',
    'handoff opus55: "קאבר garbled — ייחוס ברמת מילה ל-Studentit" (תפיסה 50% ברמת שורה). '
    'cover_vision --calibrate 23.9.26: 0/33 חיובי-שגוי, 96.8% תפיסה.',
    'qa',
    [{'kind': 'code', 'file': 'tools/thumbnail/cover_vision.py', 'pattern': r'word_scores\(m1, title, "title"\)'},
     {'kind': 'test', 'file': 'tests/test_vision_wave6_v934.py', 'pattern': 'test_one_scrambled_title_word_blocks'},
     {'kind': 'test', 'file': 'tests/test_vision_wave6_v934.py', 'pattern': 'test_no_word_attribution_for_studentit_subtitle'},
     {'kind': 'gate', 'gate': 'cover_vision:garbled_word', 'enforcement': 'blocking'}]),
 'L101_extra_ink_components_measured_and_failed': L(
    'כתובית כפולה אינה מתגלה ברכיבים מחוברים: לוגו R.E.L על חולצת המועדון הוא לבן במתאר אדום — '
    'אותה חתימה כמו כתובית (נבדק בעין). בסף 0 חיובי-שגוי: 78-82% מכפילות רחוקה, 21-28% מחופפת. '
    'המדד יצא מהקוד; extra_ink נשאר מדווח.',
    'handoff opus55 "גל 6 ב\'": extra_ink — מדד חדש במקום סף הדיו. נמדד 23.9.26 על 51 FINAL + הזרקות.',
    'qa',
    [{'kind': 'test', 'file': 'tests/test_vision_wave6_v934.py', 'pattern': 'test_extra_ink_components_not_in_code'},
     {'kind': 'code', 'file': 'tools/caption-vision-calibration.json', 'pattern': 'extra_ink_components_w6'},
     {'kind': 'gate', 'gate': 'caption_vision:extra_ink'}]),
 'L102_preflight_high_only_on_real_block_or_unruled': L(
    'P20 עולה HIGH רק כש-caption_vision עצמו חצה את סף החסימה (blocking_hits), לא על כל דגל מסוג חוסם. '
    'פסיקה על ממצא (PREFLIGHT_WAIVERS.json) מורידה ל-LOW רק עם evidence + גיליון קיים + '
    'מדיה זהה (גודל+mtime) — FINAL חדש מבטל את הפסיקה.',
    'סבב דיוק 23.9.26: דרג-לי ומי-יסיים נעצרו NOT-READY על garbled_cue ×2 כשהסף ≥3 וה-false positive '
    'כבר נקרא בגיליון; מי-יותר-ממי נעצר על V5 "שתיקה" שהיא תשובה בהצבעה.',
    'qa',
    [{'kind': 'code', 'file': 'tools/preflight_critic.py', 'pattern': r'def apply_waivers'},
     {'kind': 'test', 'file': 'tests/test_preflight_critic.py', 'pattern': 'test_below_block_threshold_is_not_high'},
     {'kind': 'test', 'file': 'tests/test_preflight_critic.py', 'pattern': 'test_changed_media_voids_waiver'}]),
 'L103_preflight_judges_the_broll_that_was_burned': L(
    'broll_plan.json על הדיסק אינו מה שנצרב. גימור עם --no-broll משאיר את התוכנית, ו-P1 דיווח "קפיצה כפולה" '
    'מבירול שלא קיים ב-FINAL. מקור האמת = finish_prefs.broll.items_applied.',
    'ניפוץ-מיתוסים 23.9.26: 2 ממצאי P1 HIGH אחרי refinish בלי בירול.',
    'qa',
    [{'kind': 'code', 'file': 'tools/preflight_critic.py', 'pattern': r'items_applied'},
     {'kind': 'test', 'file': 'tests/test_preflight_critic.py', 'pattern': 'test_skipped_broll_means_no_plan'}]),
 'L104_clip_edges_are_stabilized_at_the_source': L(
    'קצה של קליפ אייפון = לחיצה על הקלטה/עצירה (מבט למטה, רכינה לטלפון). keep אוטומטי ומילה אחרונה '
    'ש-Whisper מותח עד סוף הקליפ מכניסים 1-5 פריימים מהתנועה לגבול החיתוך. התיקון במקור, לפני EDL: '
    'clip_edge_stabilize מזהה ויזואלית ראש/זנב לא-יציבים (זנב רק אחרי סוף הדיבור לפי אנרגיה) ומחליף '
    'רק את הווידאו ב"האטה רציפה" (הפריימים היציבים בחצי מהירות) — משך ואודיו זהים, כל הנגזרות תקפות. נפסלו במדידה: הקפאה/מראה (זוג פריימים זהה ליד הגבול ⇒ possible_freeze חוסם), לולאה קדימה (קפיצה שנייה אחרי החיתוך ⇒ flash_frame). '
    'האוכף: cut_qa flash_frame על EXPORT_TIGHT. ⚠️ 24.9.26: הראל דחה את ההאטה (נראית כ"פייד") — הכלי ידני '
    'בלבד; השורש האמיתי היה שבבי הידוק בגבול (L105), שמטופל בלי לגעת בווידאו.',
    'הראל 23.9.26 (חלבון 88.1, E-Myth 51.3 "זה חוזר על עצמו וצריך לסדר מהשורש", לידים 20.9): '
    'פריים של רכינה לטלפון בכל גבול קליפ.',
    'pipeline',
    [{'kind': 'code', 'file': 'tools/clip_edge_stabilize.py', 'pattern': r'def analyse'},
     {'kind': 'code', 'file': 'tools/clip_edge_stabilize.py', 'pattern': r'def _stretch'},
     {'kind': 'code', 'file': 'tools/cut_qa.py', 'pattern': r'def flash_probe'},
     {'kind': 'gate', 'gate': 'cut_qa:flash_frame', 'enforcement': 'reporting'},
     {'kind': 'test', 'file': 'tests/test_clip_edge_flash.py', 'pattern': 'test_injected_two_frame_flash_is_flagged'},
     {'kind': 'test', 'file': 'tests/test_clip_edge_flash.py', 'pattern': 'test_unsettled_head_is_detected'},
     {'kind': 'test', 'file': 'tests/test_clip_edge_flash.py', 'pattern': 'test_fill_keeps_length_and_has_no_frozen_pair'}]),
 'L105_tighten_never_leaves_a_clip_sliver': L(
    'שקט שחוצה גבול EXPORT (סוף קליפ → תחילת קליפ) נחתך בהידוק עם ריפוד keep_sil/2, ולכן ה-keep הבא '
    'מתחיל 1-2 פריימים לפני הגבול: אחרי חיתוך ההידוק רואים שבריר מהקליפ הקודם ואז קפיצה נוספת. '
    'קצה הידוק במרחק <0.15ש מגבול EDL נצמד לגבול; שארית <0.1ש נזרקת. הגבול נמדד בפריימים של EXPORT '
    '(הווידאו של edl_cut מאחר ~0.05-0.1ש מסכום ה-keeps) — לא מחושב. האוכף: cut_qa flash_frame.',
    'הראל 23.9.26, חלבון "קאטים מוזרים שקופצים... זה קרה בעוד שלב": tight keep 16.501 מול גבול 16.556.',
    'pipeline',
    [{'kind': 'code', 'file': 'tools/tighten_finish.py', 'pattern': r'def snap_keeps'},
     {'kind': 'code', 'file': 'tools/tighten_finish.py', 'pattern': r'def refine_boundaries'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'--boundaries-edl'},
     {'kind': 'gate', 'gate': 'cut_qa:flash_frame', 'enforcement': 'reporting'},
     {'kind': 'test', 'file': 'tests/test_clip_edge_flash.py', 'pattern': 'test_sliver_before_edl_boundary_is_snapped'}]),
 'L106_p1_judges_cuts_on_the_sped_timeline': L(
    'P1_cut_flash חישב גבולות מ-tight_keeps (ציר שלפני --speed) מול תוכנית בירול בציר ה-FINAL ⇒ HIGH מדומים '
    'על כל סרטון מואץ. הגבולות מחולקים בהאצה שהוחלה; מקור האמת להאצה = cut_qa_report.speed '
    '(FINAL_PROVENANCE רושם 1.0 גם כשהואץ).',
    'חלבון 23.9.26 (--speed 1.1 לבקשת הראל): 3 ממצאי P1 על 35.05/36.88/54.22 כשהחיתוכים האמיתיים ב-31.86/33.52.',
    'qa',
    [{'kind': 'code', 'file': 'tools/preflight_critic.py', 'pattern': r'bounds = \[b / sp for b in bounds\]'},
     {'kind': 'test', 'file': 'tests/test_clip_edge_flash.py', 'pattern': 'test_sped_cut_covered_by_broll_is_not_flagged'}]),
 # ── v9.36 (28.9.26) — ספריית מוזיקה מגוונת ─────────────────────────────
 'L107_music_variety_is_measured_not_labeled': L(
    'גיוון מוזיקה נמדד באודיו, לא בתווית ז\'אנר: כל טראק בקטלוג נושא sound_family (אשכול אקוסטי MFCC+contrast), '
    'energy_level 1-5, vocals ו-heavy. pick_music לא בוחר משפחת סאונד של 3 הבחירות האחרונות, מתאים אנרגיה לטון/סוג תוכן, '
    'ובתוכן ערך בלי vocal chops. מקורות מותרים: Pixabay + Mixkit (רישיון מסחרי בלי קרדיט), בלי AI, בלי Content ID מסומן, בלי קאברים.',
    "הראל 28.9.26: 'כרגע הכל נשמע די אותו דבר'. נמדד: 27% מהספרייה הישנה במשפחת סאונד אחת; "
    "סימולציה של 10 בחירות ערך — 5 משפחות/4 ז'אנרים/4 חזרות צמודות (ישן) מול 7/10/0 (v9.36).",
    'music',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': 'recent_fam'},
     {'kind': 'test', 'file': 'tests/test_music_variety_v936.py', 'pattern': 'test_every_track_is_tagged'},
     {'kind': 'doc', 'file': 'tools/music-catalog.json', 'pattern': '"sound_family"'}]),
 # ── v9.37 (4.10.26) — שכבת Motion Graphics ─────────────────────────────
 'L108_mg_faces_checked_at_the_same_time': L(
    'טקסט MG נבדק מול פנים **באותו זמן** (5 דגימות לאירוע), לא בזמן גיבור אחד; קופסה = איחוד צמתי הטקסט הגלויים '
    '(חתוכים למסכה), לא הקונטיינר. Haar מחזיר "פנים" על חולצה/מכנסיים — קופסה שכולה מתחת לקופסה אחרת היא גוף, '
    'והתמדה נספרת בפריימים ולא בשטח. בסרטוני הדיבור שלנו הפנים בשליש העליון ⇒ ברירת המחדל לשכבה היא body.',
    'דמו סוגי אחיזות 4.10.26: 5/7 אירועי top נחסמו; קופסה של 590px על המכנסיים ניצחה אשכול מדורג-שטח.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'def _clean_faces'},
     {'kind': 'code', 'file': 'tools/motion/render.js', 'pattern': r'mg-word-mask'},
     {'kind': 'gate', 'gate': 'motion_build:MG2_face_occlusion', 'enforcement': 'blocking'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_faces_compared_at_same_time'}]),
 'L109_fonts_load_explicitly': L(
    'Chrome טוען פונט רק כשמשתמשים בו — "unloaded" אינו "שבור". טוענים כל פנים במפורש, ורק status=error חוסם (MG5).',
    'דמו 4.10.26: Ploni 500 לא שימש ⇒ MG5 חסם בטעות.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/render.js', 'pattern': r'f\.load\(\)'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_missing_brand_font_blocks'}]),
 'L110_logo_white_is_a_silhouette': L(
    'tools/thumbnail/brand/logo_white.png הוא צללית לבנה מלאה (מסכה), לא לוגו לבן. הלוגו = logo_rel.png; הצללית רק למסכת ברק.',
    'דמו 4.10.26: חתימת המותג הציגה כתם לבן במקום הלוגו.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'LOGO = HERE / "thumbnail" / "brand" / "logo_rel.png"'}]),
 'L111_mg_never_double_text': L(
    'כשה-MG מציג את הדיבור עצמו (הוק, ציטוט, שאלה) הכתוביות יורדות בחלון (suppress_captions) — ו-V7 מודד מול מה שנצרב בפועל; '
    'בירול שמתחת לשכבת MG נמדד על הבסיס שלפני ה-MG. אחרת השערים חוסמים את ה-MG עצמו (missing 24 / not_landed).',
    'דמו 4.10.26: V7 missing×24 + broll_vision not_landed×1 — שניהם תוצאה של השכבה, לא תקלה.',
    'pipeline',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'CAPS_WORDS'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'mg_pre_base'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_finish_pipeline_runs_motion_before_music_and_filters_captions'}]),
 'L112_mask_padding_holds_the_shadow': L(
    'מסכת מילה (overflow:hidden) צרה חותכת את הצל של הטקסט לריבוע כהה סביב כל מילה. ריפוד רחב + שוליים שליליים זהים '
    '(הפריסה לא זזה), והמילה נכנסת מ-yPercent 160 כדי שלא תציץ מתחת למסכה.',
    'דמו 4.10.26 — ריבועים כהים סביב מילים בגיליון.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/lib/rel-motion.css', 'pattern': r'padding:\.36em \.3em \.36em'}]),
 'L113_freeze_frame_faces': L(
    'טלסטרייטור עם פריים קפוא: מה שנמצא מתחת לתוויות הוא הפריים הקפוא, לא הווידאו בזמן האירוע — MG2 בודק פנים ב-freeze_at.',
    'דמו HSPU 4.10.26 — "באותו קו" על פריים מ-30.8ש שמוצג מ-29.2ש.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'freeze\.get\(me\["id"\]'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_freeze_frame_text_is_checked_against_the_frozen_frame'}]),
 'L114_ltr_layout_leaks_into_hebrew': L(
    'direction:ltr שנקבע לפריסה (פודיום 2·1·3) עובר בירושה לטקסט העברי שבתוכו ⇒ "גברים העלית". כל טקסט בתוך קונטיינר ltr מקבל direction:rtl מפורש.',
    'דמו איתי 4.10.26 — הקטגוריה מעל הפודיום התהפכה בגיליון.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/templates/story.js', 'pattern': r"textAlign:'center',direction:'rtl'"}]),
 'L115_no_orphan_no_period_on_accent': L(
    'כותרת MG בלי מילה יתומה (text-wrap:balance) ובלי נקודה בסוף מילה מודגשת — הנקודה נכנסת לבלוק האדום ונראית כשגיאה.',
    'דמו 4.10.26 — "אף אחד." / "שווה את / זה" בגיליון הראשון.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/lib/rel-motion.css', 'pattern': r'text-wrap:balance'}]),
 'L116_mg_never_touches_color': L(
    'שכבת ה-MG לא נוגעת בצבע: השכבה מומרת ל-YUV במטריצה של הבסיס והפלט מתויג בדיוק כמו הבסיס (HLG/bt2020 נשאר HLG/bt2020). '
    'MG11 חוסם כל שינוי תגית — שוויון, בלי סף.',
    'הראל 4.10.26 על דמו HSPU: "משהו בצבע מוזר" — ההרכבה תייגה בסיס bt2020nc כ-bt709 ⇒ פענוח במטריצה הלא-נכונה.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'def gate_color'},
     {'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'out_color_matrix'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_color_tags_must_equal_base'}]),
 'L117_reveal_keeps_the_shadow': L(
    'חשיפה ב-clip-path עם inset(0) חותכת את הצל של משטח מעוגל למלבן שנראה סביבו. משתמשים ב-REL.CLIP (מרווח 60px מכל צד, '
    'מצב מוסתר מעבר לקצה). מילים נכנסות/יוצאות מ-yPercent ±200 כדי שקצה ל/ך לא יציץ מהמסכה.',
    'הראל 4.10.26: "רואים ברמה 1, רמה 2 את המלבן שעוטף את הצורה" + נקודה לבנה מתחת לכרטיס הציטוט.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/lib/rel-motion.js', 'pattern': r'REL\.CLIP'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_no_reveal_clips_the_shadow'}]),
 'L118_sfx_varied_and_sparse': L(
    'צלילים: וריאציות מתחלפות לכל סוג, מרווח ≥0.9ש, לכל היותר 2 בכל 4ש (hit > whoosh > pop > tick), אותו סוג שוב תוך 3ש ⇒ ‎-4dB, '
    'ובסיס ‎-2.5dB. MG9 מדווח צפיפות.',
    'הראל 4.10.26: "מרגיש קצת עמוס מידיי בצלילים — צריך או לגוון או למתן".',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'def plan_sfx'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_sfx_thinned_varied_and_capped'}]),
 'L119_full_mg_transitions_and_harel_20': L(
    'סרטון MG מלא: מעברים שתופסים את העין בין הסצנות (REL.transitions — panel/zoom/iris/shutter/push/flash במחזור), '
    'ו-~20% מהזמן הראל במצלמה (base_windows — בלי MG מעליו, רק כתוביות; MG10 מדווח את החלק).',
    'הראל 4.10.26 על "בעל מועדון": "הייתי מכניס מעברים ויזואלים שיותר תופסים את העין" + "העיקר אנימציות ו-20% זה אני".',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/lib/rel-motion.js', 'pattern': r'REL\.transitions'},
     {'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'def gate_base_share'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_full_mg_has_transitions_and_base_windows'}]),
 'L120_end_card_by_judgment': L(
    'חתימת המותג (end_card) אהובה — אבל לא בכל סרטון. משתמשים בה כשהסרטון נגמר בלי CTA חזק משלו ותוכן הערך/המותג מרוויח סגירה; '
    'לא אחרי CTA מעורבות, לא בסיפור מתאמן (outro), לא ברצף סרטונים מאותה סדרה בפרק זמן קצר.',
    'הראל 4.10.26: "הסיומת זה אחלה אבל לא הייתי משלב את זה בכל סרטון. לשיקולך".',
    'motion',
    [{'kind': 'doc', 'file': 'skills/rel-motion-graphics/SKILL.md', 'pattern': r'end_card.*לא בכל סרטון'}]),
 'L122_mg_style_chosen_in_script': L(
    'סגנון ה-MG נבחר כבר בתסריט (`◆MG STYLE`, `◆BASE`, דרישות צילום ב-`⟦SHOOT⟧` — rel-script-writer v3.2 §6.1) ולא בעריכה: '
    'הוא משנה את המשפטים ואת מה שמצלמים (תנוחה מוחזקת 2ש, קול נקי, חזה פנוי). במצב B הם הבסיס של motion_plan.json.',
    'הראל 4.10.26: "כל הסגנונות מדהימים, זה מאוד תלוי סרטון ... תיישם את זה בתסריטים".',
    'motion',
    [{'kind': 'doc', 'file': 'skills/rel-motion-graphics/SKILL.md', 'pattern': r'מהתסריט לתוכנית'},
     {'kind': 'doc', 'file': 'skills/rel-social-video-editor/SKILL.md', 'pattern': r'הסגנון נבחר בתסריט'}]),
 'L121_story_no_cutaway_at_confession': L(
    'בסיפור מתאמן לא חותכים מהפנים שלו לסצנה גרפית במסך מלא ברגע הווידוי הרגשי — הפנים הן הרגע. MG שם רק עדין או בכלל לא.',
    'הראל 4.10.26 על דמו איתי עוזרי: "רק השנתיים מאוד קשות הייתי מוותר. כל השאר מושלם."',
    'motion',
    [{'kind': 'doc', 'file': 'skills/rel-motion-graphics/SKILL.md', 'pattern': r'וידוי'}]),
 'L123_trainee_name_is_name_sparkle': L(
    'שם מתאמן על המסך = האפקט הקבוע `name_sparkle`: הפריים קופא ברגע החיוך (pick_smile_frame) והופך לתמונה עם זום קטנטן, נצנצים וצליל sparkle אוטומטי. בלי קשת (בוטלה 8.10.26), לא "שם על רקע בורדו". הפריים חייב להיות מחמיא (לא פה פתוח בדיבור). זה קטע נוסף שבו הסרטון והדיבור עוצרים (insert) — לא שכבה מעל דיבור רץ; הציר מתארך וכל מה שאחרי זז. רק בתוכן שמציג מתאמנים — לא לצוות. '
    'GSAP דורס את מאפיין transform של אלמנט SVG מונפש — גודל של נצנץ נאפה בקואורדינטות, אחרת הכוכב מתכווץ ל-2px בשקט.',
    'הראל 7.10.26 (Monday 13225968348): "אפקט יותר ייחודי מאשר שם עם רקע בורדו ... נצנצים וסאונד חמוד"; 8.10.26: "תוותר על הקשת ... להקפיא את הפריים ברגע שהוא מחייך ... זום קטנטן כדי להוסיף חיות".',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'"type": "name_sparkle"'},
     {'kind': 'code', 'file': 'tools/motion/templates/name_sparkle.js', 'pattern': r'STAR\.replace'},
     {'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'def pick_smile_frame'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_propose_skips_team'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_insert_remaps_timeline'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'words_after_mg'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_auto_sparkle_sfx_replaces_entry_whoosh'}]),

 # ── v9.44 — ארגז כלי ההוק (8.10.26) ─────────────────────────────────────
 'L124_hook_anchor_declared_and_measured': L(
    'כל ריל נפתח בעוגן מוחשי בשנייה 0 (סצנה/פעולה/חפץ/אדם/מספר/איבר) — לא בכרטיס כותרת, לא ב"פרק N", לא בפתיח קבוע, '
    'לא בעיקרון מופשט ולא בפנייה גאוגרפית בריל אורגני. הבמאי מצהיר ב-HOOK_PLAN.json (טכניקה מ-tools/hook_toolbox.json + '
    'מה רואים ושומעים ב-0/1/2ש), בודק על HOOK_SHEET.jpg וקושר לקובץ; P22 הופך הצהרה חסרה/עוגן חסר/כרטיס לפני העוגן ל-high. '
    'מגבר (MG/punch-in/צליל) לכל היותר אחד ב-0-2ש ורק מעל עוגן. then_now: פנים נבדקות בפריים של כל פאנל, ממופות לציר הפאנל.',
    'רטרו 8.10.26: VR (נשארים אחרי 3ש) מנבא חשיפה r=0.83/0.94; גיליונות 48 ריילס באותו יום: פעולה/סצנה בפריים 0 = VR חציוני '
    '42.6% מול 30.3% למדבר-למצלמה (p=0.00006); מאסל מן עם פתיח 30.8-36.8% מול 53.3% בלי; "פרק X" 17.3% פעמיים.',
    'director',
    [{'kind': 'code', 'file': 'tools/hook_plan.py', 'pattern': r'def evaluate'},
     {'kind': 'code', 'file': 'tools/preflight_critic.py', 'pattern': r'check_hook_anchor\(findings, W\)'},
     {'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': r'THEN_NOW_PANELS'},
     {'kind': 'test', 'file': 'tests/test_hook_plan.py', 'pattern': 'test_no_plan_is_high_for_new_project'},
     {'kind': 'test', 'file': 'tests/test_hook_plan.py', 'pattern': 'test_then_now_face_gate_reads_panel_frames'}],
    director_relevant=True),
 'L125_mg_event_at_zero_visible_on_frame_zero': L(
    'אירוע MG שמתחיל ב-0 גלוי מהבנייה (style.visibility) — set באפס-משך בזמן 0 מתבטל כשהרנדרר מבקש time(0) אחרי זמן אחר, '
    'והפריים הראשון יצא בלי השכבה. בתבנית הוק פריים 0 הוא כל העניין.',
    'גיליון then_now 8.10.26: ב-0.00 נראה הבסיס, לא הפיצול; אחרי התיקון — הפיצול בפריים 0.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/lib/rel-motion.js', 'pattern': r"ev\.start <= 1e-4"},
     # והפריים הריק המשותף מצולם עם display:none — visibility:hidden על ה-stage לא מסתיר ילד עם visibility:visible
     # (נמדד: הפיצול הופיע שוב מ-2.7ש בכל פריים "ריק" של הדמו)
     {'kind': 'code', 'file': 'tools/motion/render.js', 'pattern': r"style\.display = 'none'"}]),
 'L126_hook_toolbox_is_edit_level': L(
    'ארגז ההוק הוא שכבת עריכה, לא תסריט: תנועת מצלמה, מעבר, צליל ואנימציה שנבנים בגימור על הרגע שצולם '
    '(HOOK_PLAN.json[edit] → hook_fx.py → HOOK_FX_SHEET.jpg). התסריט רק מצלם לו חומר.',
    'הראל 8.10.26: "הרעיון של ארגז הכלים הוא לא ברמת התסריט אלא ברמת העריכה שלנו. אפקטים, אנימציה שמשתלבת בהוק, מעברים, צלילים".',
    'edit',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'st\.step\("hook_fx"\)'},
     {'kind': 'code', 'file': 'tools/hook_plan.py', 'pattern': r'def evaluate_edit'},
     {'kind': 'test', 'file': 'tests/test_hook_fx.py', 'pattern': r'test_declared_not_applied_is_high'}],
    director_relevant=True),
 'L127_rawvideo_pipe_needs_passthrough': L(
    'קריאת פריימים ב-rawvideo pipe בלי -fps_mode passthrough משכפלת את הפריים הראשון; וקונקט של חלון+שארית בלי '
    'setpts=N/fps מזיז את כל מה שאחרי התפר 1-3 פריימים. ציר פריימים קשיח + שער יישור.',
    'hook_fx 8.10.26: HSPU +1 פריים, פודיום +3→+2 אחרי החלון — נמדד בגיליון ותוקן.',
    'render',
    [{'kind': 'code', 'file': 'tools/hook_fx.py', 'pattern': r'"-fps_mode", "passthrough"'},
     {'kind': 'code', 'file': 'tools/hook_fx.py', 'pattern': r'HFX8b_frame_align'},
     {'kind': 'test', 'file': 'tests/test_hook_fx.py', 'pattern': r'HFX8b_frame_align'}]),
 'L128_light_music_is_pop_and_starts_on_beat': L(
    'מצע לתוכן אירוע/קהילה (פרופיל light) = פופ/דאנס-פופ/אינדי/סינת\'-פופ/טרופיקל/נו-דיסקו/האוס, בלי מצב רוח '
    'אגרסיבי/אפל/אפי; funk/afrobeat/hiphop יצאו. והמצע נכנס בקצב מ-0: offset אוטומטי מדלג על הפתיח הרך של הטראק. '
    'מפלס Throwdown: פתיח I-12, בדיבור I-20 (היה I-10/I-18).',
    'הראל 9.10.26 על 24 ריליז Throwdown: "מוזיקה על הפנים, המוזיקה לאחרונה לא מתאימה לסגנון הסרטון בכל התכנים", '
    '"צריך משהו יותר קצבי וקליל", "המוזיקה מתחילה מאוחר מידיי", "טיפה להנמיך" ×4. נמדד: 26/31 טראקים קלילים פותחים '
    'בפתיח רך 6-45ש (חציון 15ש).',
    'music',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'LIGHT_BAD_MOODS = \{"aggressive", "dark", "epic"\}'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'_music_offset = "auto"'},
     {'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': r'def music_start_offset'},
     {'kind': 'test', 'file': 'tests/test_music_light_v2.py', 'pattern': 'test_light_pool_excludes_funk_afro_hiphop'},
     {'kind': 'test', 'file': 'tests/test_music_light_v2.py', 'pattern': 'test_start_offset_skips_soft_intro'}]),
 'L129_caption_curse_half_word': L(
    'קללה בכתוביות מוצגת כחצי מילה + #$% (שרמ#$%) — מבינים מה נאמר בלי לכתוב אותה. לקסיקון חד-משמעי ב-tools/caption-censor.json, '
    'מילה דו-משמעית פר-פרויקט ב-finish_prefs.captions.censor. רק העותק שנצרב משתנה.',
    'הראל 9.10.26 (תחרות-ראשונה-שלי): "כשיש קללות, תכניס בכתוביות כל מיני סימנים של *#$% ... עם חצי מהמילה".',
    'captions',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'def censor_caption_words'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'censor_caption_words\(_caps_words, W, manifest\)'},
     {'kind': 'test', 'file': 'tests/test_music_light_v2.py', 'pattern': 'test_censor_mask_half_word'}]),
 'L130_name_insert_shifts_g6_truth': L(
    'קטע שם (name_sparkle insert) מאריך את הציר: גם האמת של G6 (whisper_export) זזה באותו hold, אחרת G6 נכשל בהיסט של אורך העצירה '
    'בזמן שהכתוביות מדויקות (G6b מול האודיו עובר).',
    'TD26 9.10.26 (נכנס-בדקה-התשעים): G6 נכשל ב-mean_signed 2.11ש = אורך העצירה, G6b 96.5.',
    'captions',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'whisper_export_after_mg\.json'}]),
 'L131_refinish_needs_fresh_tight_axis': L(
    'גימור בלי הידוק (--tighten off / --director) כותב גם EXPORT_TIGHT.mp4 = הציר הנוכחי (hardlink), ו---refinish נכשל במפורש '
    'כש-EXPORT_TIGHT ישן מ-EXPORT — אחרת הוא ממחזר ציר מריצה קודמת והכתוביות זזות (קלט שהשתנה מבטל נגזרות).',
    'TD26 9.10.26 (קליפ-מקצה-טרה-ראן-מונטאז): EXPORT_TIGHT מ-25.9 (40.8ש) מול EXPORT 47.9ש, G6b ‏mean_signed 7.2ש.',
    'finish',
    [{'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'EXPORT_TIGHT\.mp4 ישן מ-EXPORT\.mp4'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'os\.link\(EXPORT, _tf\)'}]),

 'L132_caption_completes_the_video': L(
    'הקפשן משלים את הסרטון ולא משכפל אותו: כל קפשן נבנה סביב "מהלך הוספה" אחד ממקור אמיתי '
    '(חומר שנחתך, בריף, עובדת קאנון, המחשבה של הצופה, היישום מחר בבוקר) ואלמנט StoryBrand אחד מוביל. '
    'טיוטה שאין בגופה אף משפט שלא נשמע בסרטון, או שרובה כבר נשמע, נדחית ב-set_draft.',
    'הראל 10.10.26: "הקפשן תמיד חוזר על מה שנאמר בתסריט עצמו. זה צריך להיות יותר מתוחכם מזה". '
    'מדידה: 88 קפשנים מאושרים, חציון 56% מהגוף כבר נשמע בסרטון, שורה 1 = הד ב-42/88, 28/88 היו נכשלים.',
    'copy',
    [{'kind': 'code', 'file': 'tools/caption_gate.py', 'pattern': r'def novelty'},
     {'kind': 'code', 'file': 'tools/relvid/registry.py', 'pattern': r'CAPTION-GATE FAIL'},
     {'kind': 'test', 'file': 'tests/test_caption_gate.py', 'pattern': r'test_set_draft_rejects_echo_caption'},
     {'kind': 'gate', 'gate': 'caption_gate:no_novel_sentence', 'enforcement': 'blocking'},
     {'kind': 'doc', 'file': 'docs/CAPTION-ENGINE.md'}]),
 'L133_v7_reads_mg_axis': L(
    'כשה-MG מכניס פריים קפוא, הכתוביות ב-FINAL יושבות על ציר words_after_mg.json. V7 העצמאי (vision_check) '
    'חייב למדוד על הציר הזה, אחרת הוא מדווח "garbled" על כתוביות תקינות.',
    'ריל הבדיקה בענן 10.10.26 (אביגיל): words_final ⇒ 41/54 garbled · words_after_mg ⇒ 0/54. בגימור עצמו נמדד נכון.',
    'qa',
    [{'kind': 'code', 'file': 'tools/caption_vision.py', 'pattern': 'words_after_mg.json'},
     {'kind': 'test', 'file': 'tests/test_caption_vision_mg_axis.py', 'pattern': 'test_prefers_words_after_mg_when_newer'}]),
 'L134_knowledge_folder_no_media': L(
    'הפרויקט ב-claude.ai והתיקייה המסונכרנת מחזיקים ידע בלבד. מדיה, תוצרי עבודה, לוגים, .bak וסקריפטים חד-פעמיים '
    'הולכים ל-Drive של hayonhq (REL Video Cloud/) או לריפו, לעולם לא לתיקייה המסונכרנת.',
    'v10 ענן 10.10.26: 853 קבצים (5.6GB) מילאו את הפרויקט ונגמר המקום; הועברו לארכיון עם מניפסט ו-md5.',
    'ops',
    [{'kind': 'code', 'file': 'tools/project_hygiene.py', 'pattern': 'MEDIA_EXT'},
     {'kind': 'test', 'file': 'tests/test_project_hygiene.py', 'pattern': 'test_self_test_flags_media_and_junk'}]),
 'L135_music_level_relative_to_dialog': L(
    'מפלס המוזיקה נקבע יחסית לדיבור הנמדד של הסרטון (dialog_I - gap), לא כ-LUFS מוחלט; רצפה 21 LU שאף ריל עם דיבור '
    'לא עובר (גם בחירה ידנית נחתכת), ושער מדוד מרנדר את המצע לבד ומודד אותו בחלון הדיבור. ערכים: tools/music-level-policy.json.',
    'הראל 11.10.26 "כל פעם אנחנו נופלים עם המוזיקה. הווליום חזק מידיי". ביקורת 60 ריליז: עם LUFS מוחלט ה-gap נע 1.7-27.7 LU '
    'כי הדיבור בקלט נע ‎-10.8 עד ‎-37; כל ה"חזק מדי" ב-16.6-20.0; העוגן המאושר (E-Myth 24.9) 20.9.',
    'music',
    [{'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': r'def apply_dialog_relative_levels'},
     {'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': r'def measure_bed_gap'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'music-level-policy.json'},
     {'kind': 'test', 'file': 'tests/test_music_gap_l135.py', 'pattern': 'test_absolute_manual_pref_is_clamped_by_floor'},
     {'kind': 'test', 'file': 'tests/test_music_gap_l135.py', 'pattern': 'test_gate_catches_loud_bed'}]), 'L136_clip_cache_key_survives_copy': L(
    'מטמון ראיות הבירול ממופתח file|mtime|size; העתקה (git/rclone/tar) משנה mtime בלי שהקליפ השתנה. '
    'כשאין התאמה מדויקת — שם+גודל בלי mtime הם אותו קליפ.',
    'v10 ענן 11.10.26: אחרי מעבר הספריות לענף libs, 64 קליפים בבריכה "איבדו" ראיה ויזואלית והשער נכשל-סגור על כולם.',
    'broll',
    [{'kind': 'code', 'file': 'tools/broll_vision_model.py', 'pattern': 'def resolve_key'},
     {'kind': 'code', 'file': 'tools/broll_vision.py', 'pattern': 'L136'},
     {'kind': 'test', 'file': 'tests/test_clip_key_copy_l136.py', 'pattern': 'test_lookup_survives_mtime_change'}]), 'L137_music_gap_closed_loop': L(
    'שער G_music_gap לא נכשל על חוסר שנמדד אחרי שהמפלס תוכנן נכון: מזיזים את המצע בגודל החוסר הנמדד (+0.3) '
    'ומרנדרים פעם אחת. רק כשל אחרי התיקון חוסם.',
    'אימות E2E בענן 11.10.26: ריל אביגיל נחתך לרצפה 21.0, נמדד 20.37 (0.66 LU קרוב מהמבוקש) והגימור כולו נפל ב-0.03 LU אחרי 10 דקות רינדור.',
    'music',
    [{'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': '_gap_nudge'},
     {'kind': 'test', 'file': 'tests/test_music_gap_l135.py', 'pattern': 'test_closed_loop_retry_lands_above_floor'}]),
 'L138_music_local_floor_and_recalibration': L(
    'מוזיקה מתחת לדיבור נמדדת גם פר-חלון: בכל חלון 3ש עם דיבור המצע לפחות 20 LU מתחת לקול של אותו חלון '
    '(מעטפת שמנמיכה בלבד, slew 6dB/ש). המפלס האינטגרלי: gap 26 / רצפה 25. עוגן "מאושר" שנשמע אחרי פרסום כחזק — נפסל, '
    'ותיקון מפלס כולל סריקת התור ב-Metricool כי קובץ שגומר קודם לא מתעדכן לבד.',
    'הראל 14.10.26 על E-Myth שעלה: "שוב המוזיקה גבוהה מידיי... למרות שאמרת שטיפלת". הקובץ גומר 25.9 (לפני L135) והיה העוגן של L135 '
    '(gap 20.9); נמדד אחרי פרסום בהפרדת קול/מוזיקה: gap 20.3, ובחלון ה-CTA האחרון ~9.6 dB בלבד. ה"דאקינג" בקוד הוא מדרגה אחת בכניסת הדיבור.',
    'music',
    [{'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': r'def local_envelope'},
     {'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': r'def bed_filter'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'--local-gap'},
     {'kind': 'test', 'file': 'tests/test_music_local_l138.py', 'pattern': 'test_quiet_tail_is_caught_and_fixed'},
     {'kind': 'test', 'file': 'tests/test_music_gap_l135.py', 'pattern': 'test_policy_floor_well_below_rejected_anchor'}]),
 'L139_mg_no_negative_transition': L(
    'שום אנימציה בטיימליין הראשי של ה-MG לא מתחילה בזמן שלילי: חלון בסיס שמתחיל ב-0 לא מקבל מעבר כניסה, '
    'וזמן התחלה של שכבת מעבר נחתך ל-0. מעבר שלילי גורם ל-GSAP להזיז את כל הילדים קדימה — כל ה-MG מאחר אחרי הדיבור.',
    'דמו "על הלוח" 17.10.26: base_windows [[0,1.85]] + backdrop ⇒ shutter ב-‎-0.24ש ⇒ כל 11 האירועים זזו +1.27ש '
    '("בריאות" הופיעה 1.4ש אחרי שנאמרה). נמדד ב-getChildren().startTime מול ev.start. באג קיים מ-v9.39.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/lib/rel-motion.js', 'pattern': r's0 > 0\.3\) evs\.push'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'class NoNegativeTransitionL139'}]),
 'L140_word_anchor_exact_first': L(
    'זמני MG הם עוגני מילה מהציר הסופי ולא מספרים שחושבו בראש (MG12 חוסם עוגן יתום); '
    'התאמה מדויקת קודם, התאמת שורש רק אם אין אף מופע מדויק.',
    'הראל 17.10.26: "ברמה גבוהה יותר בדיוק של התוכן". בדמו "השאלה" נקצץ לשורש "אלה" ונתפס על "האלה" 7.6ש מוקדם — '
    'סצנת המדרגות נעלמה. תוקן לסריקה מדויקת-קודם.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': 'def gate_anchors'},
     {'kind': 'code', 'file': 'tools/motion_build.py', 'pattern': 'exact=True'},
     {'kind': 'test', 'file': 'tests/test_motion_build.py', 'pattern': 'test_exact_before_stem'}]),
 'L142_music_bed_macro_level': L(
    'המצע מיושר לאורך הזמן לפני כל מדידה: S(3ש) של הקטע שמתנגן מיושר לחציון שלו (הנמכה עד 12dB, הגבהה עד 3dB), '
    'ורק אז loudnorm, G_music_gap, המעטפת המקומית (L138) וה-nudge (L137) — כך טראק שנבנה לא מסיים ב-CTA הכי רועש. '
    'הסף המקומי אחד: min_local_gap_lu בחלון 3ש. רצפת momentary נבדקה ונפסלה — היא תופסת הפסקות בין מילים ומייצרת שאיבה.',
    'הראל 23.10.26 על פינה-אנטומית-פרק2 (53.5ש): "המוזיקה רועשת מידיי. זה חוזר על עצמו כל הזמן". נמדד על המק: gap אינטגרלי 24.2 עבר, '
    'אבל המצע עלה ‎-60→‎-49 LUFS-M לאורך הסרטון. התיקון נכתב במק כ-L137 (level_bed) ומוזג לריפו כשלב לפני L138 (ה-L137 של הריפו = nudge).',
    'music',
    [{'kind': 'code', 'file': 'tools/audio_mix.py', 'pattern': r'def macro_level_bed'},
     {'kind': 'code', 'file': 'tools/local_finish_pipeline.py', 'pattern': r'--bed-level'},
     {'kind': 'test', 'file': 'tests/test_music_bed_level_l142.py', 'pattern': 'test_build_is_flattened_before_measurement'},
     {'kind': 'test', 'file': 'tests/test_music_bed_level_l142.py', 'pattern': 'test_leveling_failure_is_not_silent'},
     {'kind': 'doc', 'file': 'tools/AUDIO-MIX.md', 'pattern': 'L142'}]),
 'L141_board_caption_floor': L(
    'סצנת MG מסך-מלא על משטח בהיר/אדום מחזיקה רצפה כהה ברצועת הכתוביות (מ-1262) — הכתובית הממותגת '
    '(לבן + מתאר אדום) לא נקראת על נייר ונעלמת על אדום.',
    'דמו "על הלוח" 17.10.26: V7 מדד garbled 27/90 cues על משטחי נייר/אדום; אחרי הרצפה — 0 ממצאים, f_ok 0.871.',
    'motion',
    [{'kind': 'code', 'file': 'tools/motion/templates/board.js', 'pattern': 'רצפת כתוביות'},
     {'kind': 'doc', 'file': 'tools/motion/MOTION.md', 'pattern': 'רצפת כתוביות'}]),
 'L143_workdir_saved_or_not_done': L(
    'אין "בוצע" בלי שמירת workdir מאומתת: worker.save_state דוחף לענף libs, מושך חזרה לתיקייה זמנית ומשווה טביעה; '
    'טביעה שונה = RuntimeError והג\'וב נכשל. ג\'וב שנכשל לא צורך את הפעולה של הראל ומעלה באנר.',
    'הראל 29.10.26: תיקיות עבודה של סשן ענן מ-23.10 אבדו כי push-project לא רץ, וכל סבב תיקונים ב-29.10 התחיל בשחזור.',
    'state',
    [{'kind': 'code', 'file': 'cloud/worker.py', 'pattern': 'def save_state'},
     {'kind': 'test', 'file': 'tests/test_v11_worker.py', 'pattern': 'test_save_state_mismatch_is_not_done'},
     {'kind': 'test', 'file': 'tests/test_v11_worker.py', 'pattern': 'test_failed_job_sets_health_and_does_not_consume_action'}]),
 'L144_opus_only_on_escalation': L(
    'קריאת מודל עוברת רק ב-tools/llm.py: Haiku לסיווג ובדיקות מהירות, Sonnet לבמאי/הוק/קפשן/ראייה, Opus רק עם סיבת הסלמה '
    '(שער שנכשל פעמיים או הערה שלא ממופה). תקרת עלות לריל וליום נאכפת בצד השרת (פונקציית video).',
    'הראל 25.10 ו-29.10.26: המכסה השבועית נגמרה; כל סוכן עריכה צרך כ-500k טוקנים.',
    'cost',
    [{'kind': 'code', 'file': 'tools/llm.py', 'pattern': 'ESCALATION_REASONS'},
     {'kind': 'test', 'file': 'tests/test_v11_worker.py', 'pattern': 'test_opus_requires_escalation_reason'}]),
 'L145_paths_portable_between_runners': L(
    'נתיב מוחלט שנכתב במכונה אחרת (מק, סשן ענן, runner של Actions) לא מפיל שער: canon_lint ממפה לפי המקטע שאחרי שורש הריפו '
    '(בירולים/brand-assets/…), וטראק המוזיקה נבדק מהמניפסט של הפרויקט ולא מהרוטציה הגלובלית. ה-worker שם את ה-venv ראשון ב-PATH.',
    'מדידה ב-GitHub Actions 29.10.26: ריל הבדיקה עבר את כל השערים ו-PREFLIGHT "מוכן להראל", ואז canon נפל על broll_plan עם נתיבי /Users/hayon; '
    'לפני כן audio_mix נפל בשקט כי python3 של המערכת רץ בלי numpy.',
    'portability',
    [{'kind': 'code', 'file': 'tools/canon_lint.py', 'pattern': 'def _resolve'},
     {'kind': 'code', 'file': 'tools/canon_lint.py', 'pattern': 'track_auto'},
     {'kind': 'code', 'file': 'cloud/worker.py', 'pattern': 'os.environ["PATH"] = str(Path(PY).parent)'}]),
}


# ═══════════════════════════════════════════════════════════════════════
# אודיט — כל אוכף חייב להתקיים בפועל.
# ═══════════════════════════════════════════════════════════════════════
def _check_enforcer(e: dict) -> str | None:
    """None אם האוכף קיים; אחרת תיאור הכשל."""
    kind = e.get("kind")
    if kind in ("code", "test", "doc"):
        p = SYSDIR / e["file"]
        if not p.exists():
            return f"קובץ חסר: {e['file']}"
        if kind == "test" and not e.get("pattern"):
            return None
        pat = e.get("pattern")
        if pat:
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except Exception as ex:                       # pragma: no cover
                return f"קריאת {e['file']} נכשלה: {ex}"
            if not re.search(pat, src):
                return f"הדפוס '{pat}' לא נמצא ב-{e['file']} — האוכף נעלם"
        return None
    if kind == "gate":
        try:
            import gate_registry as GR
        except Exception as ex:                           # pragma: no cover
            return f"gate_registry לא נטען: {ex}"
        g = GR.GATES.get(e["gate"])
        if not g:
            return f"השער {e['gate']} אינו ברשומת השערים"
        want = e.get("enforcement")
        if want and g["enforcement"] != want:
            return (f"השער {e['gate']} באכיפה '{g['enforcement']}' "
                    f"במקום '{want}' — הלקח אומר שזה בכוונה כך")
        return None
    return f"סוג אוכף לא מוכר: {kind}"


def audit() -> tuple[bool, list[str]]:
    problems: list[str] = []
    for lid, rec in LESSONS.items():
        if not rec.get("enforced_by"):
            problems.append(f"❌ {lid} — לקח בלי אף אוכף")
            continue
        for e in rec["enforced_by"]:
            err = _check_enforcer(e)
            if err:
                problems.append(f"❌ {lid} — {err}")
        for f in ("lesson", "origin", "layer"):
            if not rec.get(f):
                problems.append(f"❌ {lid} — חסר שדה {f}")
    return (not problems), problems


def director_lessons() -> list[str]:
    """הלקחים שמוזרמים לבמאי — משפט הכלל בלבד, בסדר יציב (למען replay)."""
    return [LESSONS[k]["lesson"] for k in sorted(LESSONS)
            if LESSONS[k]["director_relevant"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--director", action="store_true")
    a = ap.parse_args()

    if a.audit:
        ok, problems = audit()
        for p in problems:
            print(p)
        n_enf = sum(len(r["enforced_by"]) for r in LESSONS.values())
        print(f"\n{'✅' if ok else '❌'} אודיט לקחים: {len(LESSONS)} לקחים · "
              f"{n_enf} אוכפים · {len(problems)} בעיות")
        return 0 if ok else 1

    if a.director:
        for s in director_lessons():
            print(f"- {s}")
        return 0

    if a.json:
        print(json.dumps(LESSONS, ensure_ascii=False, indent=1))
        return 0

    for lid in sorted(LESSONS):
        r = LESSONS[lid]
        enf = " · ".join(
            e.get("gate") or e.get("file", "?") for e in r["enforced_by"])
        print(f"{lid}  [{r['layer']}]")
        print(f"  {r['lesson']}")
        print(f"  מקור: {r['origin']}")
        print(f"  אוכפים: {enf}\n")
    print(f"סה\"כ {len(LESSONS)} לקחים · "
          f"{sum(1 for r in LESSONS.values() if r['director_relevant'])} מוזרמים לבמאי")
    return 0


if __name__ == "__main__":
    sys.exit(main())
