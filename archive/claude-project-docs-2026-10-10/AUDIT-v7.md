# AUDIT-v7 — מצב המערכת לפני שדרוג v6.1 → v7
תאריך: 23.7.2026 · בוצע ע"י Claude (Fable Mode) · כל הממצאים VERIFIED מקריאת קוד/קבצים בפועל אלא אם צוין אחרת.

## שורה תחתונה
המערכת v6.1 עובדת מקצה-לקצה (הוכחה: `_work/שינה-והתאוששות` → FINAL.mp4 + qa_report PASS + APPROVAL.json מ-19.7), אבל היא בנויה על "קיום קבצים בתיקייה" כמודל מצב יחיד: אין git, אין requirements, אין טסטים, אין מזהה פרויקט יציב, אין revisions, אין נעילות ריצה, ולולאת הלמידה כמעט מנוטרלת (classifier לא מזהה את רוב סוגי האירועים שנרשמים בפועל, ואף כיול לא הוחל מעולם).

## 1. מה עובד בפועל (VERIFIED)
- הכנה דטרמיניסטית: `edl_build.py` → edl.json (keep_segments/auto_cuts/manual_review_cuts + confidence/source/active) → `edl_cut.py` frame-accurate.
- review-app (פורט 5112): רשימת פרויקטים, עריכת cuts/hook_move, תיקון תמליל (edited.txt), PREVIEW, סבבי הערה↔תיקון (review_rounds.json), אישור שמריץ את הגימור.
- גימור `local_finish_pipeline.py`: recut→whisper→reconcile→tighten→gate→broll→music→captions(PIL)→loudness→qa_gates→thumbnail, עם finish_status.json חי.
- corrections.jsonl נכתב מכל פעולה באפליקציה.
- captions-app עצמאית (5111) עם resume per-job (uuid).

## 2. מה רק מוגדר / חצי-עובד
- למידה: `learn_from_edits.py` — `classify()` מזהה רק restore_cut/add_cut/adjust_cut/hook_move/transcript_fix, וקורא reason רק מ-`act["cut"]["reason"]`. בפועל נרשמים גם: cut_disable, cut_widen, cut_shift, cuts_merge, activate_cut, note_sent, round_correct, gate_override, music_redo, video_patch_* — כולם נזרקים. counts בפועל: silence_restore:2, manual_add:13, transcript_fix:1 → אף כיול לא הוחל (edit-lessons.md: 3 ריצות, כולן "אין כיול").
- offsets של הלמידה לפי **שם תיקייה** — התיקייה shina שונתה ל"שינה-והתאוששות" → בריצה הבאה 22 השורות ייספרו כפול.
- resume: קיים רק ב-captions-app. לפייפליין אין — `אופן-גים-חיזוק` תקוע state=failed אחרי tighten (gate שקט, gate_fail.json מ-4 spans של 0.79-0.93ש).

## 3. מה שבור / מסוכן
- **אין נעילה על approve**: `server.py:283` מריץ Popen ללא lock — לחיצה כפולה = שתי ריצות מקבילות על אותם קבצים.
- **FINAL חלקי**: captions כותב FINAL.mp4 לפני loudness+QA — כשל QA משאיר FINAL.mp4 "שקרי" על הדיסק.
- **זהות פרויקט = שם תיקייה** — רינון שובר learn-state, לוגים, נתיבים ב-finish_status (נצפה ב-shina).
- **אין שום snapshot של EDL מעבר ל-edl.machine.json חד-פעמי** — תיקוני הראל דורסים, אין undo.

## 4. סתירות קאנון ↔ קוד (+הכרעות v7)
| # | סתירה | מקורות | הכרעת v7 (מנומקת) |
|---|---|---|---|
| 1 | דד-אייר: SKILL/PIPELINE "חוסם ≥1.5ש" מול קוד 0.6 | SKILL.md:131, finish_local.py:217, qa_gates.py:71 | **0.6 הוא האמת** (כויל 1.5→0.9→0.6 ב-20.7 ע"פ פידבק הראל). התיעוד יתוקן. |
| 2 | True-Peak: SKILL "TP≤-1" מול gate ≤-0.8 | SKILL.md:147, qa_gates.py:88 | יעד -1.0 (loudnorm), **סף קשיח -0.8** (טולרנס מדידה). מתועד כך. |
| 3 | משך: יעד 55-60 מול G1 קשיח 20-65 | edl-policy:39, qa_gates:38 | G1 קשיח נשאר 20-65 (לא מפילים סרטון שהראל אישר); **נוסף WARN רך מחוץ ל-50-65** ב-QA v2 + canon linter. |
| 4 | fps: מותג בפועל 30 מול G5 מקבל 24-60 | qa_gates:101 | קשיח נשאר 24-60; **WARN אם fps∉[29.5,30.5]**. |
| 5 | EXPORT.mp4 מתועד כ"ייצוא Descript" | rel-thumbnail-creator/SKILL.md:32, _work/README.md:7 | תיעוד stale — יתוקן ל"recut מקומי". |

## 5. שרידי Descript בזרימה הפעילה (לניקוי)
- `align_reconcile.py` — arg בשם `descript`, פונקציה `load_descript_words` (הקלט בפועל: edited.txt מהאפליקציה).
- `edl_build.py` — כותב `descript_instructions.md` (הצרכן: אפליקציית הרוויו; אין קורא בקוד → שינוי שם בטוח ל-review_suggestions.md).
- `descript-brand-assets/` — שם ספרייה legacy; צרכנים: local_finish_pipeline.py:34, captions-app/server.py, captions_overlay.py, captions_build.py, finish_local.py:174.
- הודעת כשל ב-finish_local.py:158 ("הרץ refinement ב-Descript") + הערות stale ב-captions_build.py.
- שאר ה-hits ב-grep הם false-positives (`argparse(description=...)`).
- מחוץ לזרימת הסושיאל (לא נוגעים): rel-podcast-descript-editor, rel-animation-compositor — זרימות נפרדות עם Descript מותר.

## 6. פערי תשתית (VERIFIED — חיפוש מקיף)
אין: git repo · requirements/lockfile · tests · SQLite · locks/run_id · resume לפייפליין · revisions · manifests/UUID · schema להערות (רק rounds טקסטואליים).

## 7. Baseline
- `שינה-והתאוששות` (עותק ישמש Golden): E2E מלא, qa_report.json pass:true (G7 soft-fail), 22 שורות corrections, APPROVAL תקין.
- `אופן-גים-חיזוק` (עותק ישמש Golden-failure): state=failed ב-tighten/gate, gate_fail.json, 17 corrections כולל video_patch.

## 8. החלטות ארכיטקטורה v7
1. **אין git** בתיקיית iCloud (מדיה כבדה + סנכרון = קונפליקטים). versioning = Revision Engine ייעודי.
2. Python+Flask נשארים. אפס תלויות חדשות כבדות — stdlib+sqlite3+ffmpeg+PIL הקיימים.
3. זהות: `project_manifest.json` עם UUID פר-פרויקט; SQLite אינדקס נבנה-מחדש ב-`_work/.index/registry.db`.
4. Revisions: `_work/{שם}/revisions/` — snapshot מלא של edl+transcript לכל שינוי, index עם undo/redo, אין מחיקת revision מאושר.
5. ריצות: `run_finish.py` עוטף את הפייפליין — lock אטומי, run_id, רשומת ריצה, resume, FINAL רק אחרי QA PASS.
6. Claude Bridge: `tools/review_cli.py` מעל tasks.json פר-פרויקט; stale-task נבדק מול edl hash.
7. למידה v2: reason_code יציב, offsets לפי project_id, proposals ב-shadow mode + אישור הראל בלבד.
