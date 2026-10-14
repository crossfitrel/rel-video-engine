# rel-social-video-editor · constants
> נגזר מהמאסטר (v9.40 — 2026-10-04) ע"י tools/skill_pack.py — לא לערוך כאן.

## תוכן
- MONDAY_BOARD_ID · STATUS_COLUMN_ID · LABEL_READY_TO_EDIT · LABEL_IN_EDIT · LABEL_READY_TO_REVIEW · DEPT_COLUMN_ID · CONTENT_TYPE_COLUMN_ID · FORMAT_COLUMN_ID · PARTICIPANTS_COL · EMAIL_TO · AUTO_EDIT_DRAFT_TAG · APPROVAL_TRIGGER_TAG · BATCH_LIMIT · BRAND_RED · PROJECT_FOLDER · CONTENT_ROOT · WORK_ROOT · RENDER_V2 · DIRECTOR · CANDIDATES · AI_PROVIDER · SEGMENT_SOURCES · BASELINE · GATE_TESTS · REVIEW_APP · FINISH_PIPELINE · LEARN · ROUTING_CONFIG · RESOLVER · MATCHER · EDL_POLICY · BROLL_CATALOG · BROLL_PICK · QA_GATES · GATE_REGISTRY · LESSON_REGISTRY · PREFLIGHT · DIRECTOR_LESSONS · SHOT_DEBT · WHISPER · NOTEFIX · FIXED_INTRO · WORDS_MAP · CAPTIONS_MAC · CAPTIONS_SANDBOX · MUSIC_MIX · MUSIC_LIB · REGISTRY · MANIFEST · REVISIONS · RUNNER · CLAUDE_BRIDGE · SYNC · DOCTOR · CUT_QA · CANON_LINT · CAPTION_SAFETY · GOLDEN · LEARNING_V2 · OPS_DASH · THUMBNAIL · METRICOOL_BRAND_REL · METRICOOL_BRAND_THROWDOWN · METRICOOL_TZ · LABEL_READY_TO_SCHEDULE · LABEL_READY_TO_SCHEDULE_DRAFT · LABEL_SCHEDULED · SCHEDULE_DATE_COLUMN_ID · FINAL_VIDEO_COLUMN_ID · SCHEDULE_APPROVAL_TAG · SCHEDULED_TAG · METRICOOL_LOCATION · SCHEDULE_REVIEW_API · SCHEDULE_APPROVAL_FIELD · STATE_READY_TO_SCHEDULE · STATE_AWAITING_SCHED_APPR · STATE_SCHEDULED · STATE_PUBLISHED

## קונסטנטות מערכת

```
MONDAY_BOARD_ID        = 18395578529
STATUS_COLUMN_ID       = color_mkrp4sgm           # "סטטוס | הפקה"
LABEL_READY_TO_EDIT    = "מוכן לעריכה"             # index 11
LABEL_IN_EDIT          = "לאחר צילום, בעריכה"      # נקבע מיד עם תחילת הכנה מקומית
LABEL_READY_TO_REVIEW  = "מוכן לבדיקה"             # index 12
DEPT_COLUMN_ID         = color_mkzks1yg            # מחלקה / קהל יעד
CONTENT_TYPE_COLUMN_ID = color_mm09wp6b            # סוג תוכן
FORMAT_COLUMN_ID       = color_mkrpg05d            # פורמט (ריל/קרוסלה/...)
HOOK_COL / MSG_COL / CTA_COL = long_text_mkzk9556 / long_text_mkzkwwgk / long_text_mkzkwys7
PARTICIPANTS_COL       = long_text_mkzkx9am
EMAIL_TO               = harel@crossfitrel.com
AUTO_EDIT_DRAFT_TAG    = [AUTO-EDIT v2 DRAFT]
APPROVAL_TRIGGER_TAG   = [APPROVE-PUBLISH]         # נכתב ע"י review-app ל-APPROVAL.json
BATCH_LIMIT            = 3
BRAND_RED              = #871d1f
PROJECT_FOLDER         = /Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System
CONTENT_ROOT           = /Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי
WORK_ROOT              = ~/rel-video-work        # v8.6 — יצא מ-iCloud (eviction באמצע גימור)
                         מקור אמת: tools/relvid/paths.py (env REL_WORK_ROOT →
                         tools/paths.json → ברירת מחדל היסטורית {PROJECT_FOLDER}/_work).
                         **אסור לקבע את הנתיב בקוד חדש** — לקרוא work_root().
                         מיגרציה/חזרה: tools/migrate_work_root.py [--apply|--rollback]
                         תוצרים סופיים ממשיכים להיתייק ל-iCloud כרגיל.
RENDER_V2              = tools/relvid/render.py + tools/render_v2.py (V2 שלב 2) ·
                         --render-engine v2 בצנרת · דור וידאו אחד במקום 4-7 ·
                         מטמון תוכן: שינוי מוזיקה = אפס רינדור וידאו ·
                         שער: tools/bench/render_ab.py (5/5, חציון +8.7 SSIM) ·
                         **ברירת המחדל עדיין v1** · תוצר השוואה: FINAL_engine2.mp4
                         (**אסור** FINAL_v2.mp4 — שם שהראל משתמש בו לגרסאות שלו)
DIRECTOR               = tools/edit_director.py (V2 שלב 1) — חמישה פאסים:
                         מפיק → הבנה → במאי → ביצוע → מבקר → ציון.
                         הפעלה: local_finish_pipeline.py --director
                                [--director-backend api|chat|replay] [--director-threshold 7.5]
                         דורש whisper_raw.json קיים (רץ אחרי התמלול, לא לפניו).
CANDIDATES             = tools/candidates.py → candidates.json (מרחב ההחלטות הסופי) ·
                         tools/edit_plan.py (validator + קומפילציה ל-edl.json)
AI_PROVIDER            = tools/relvid/provider.py · פרומפטים: tools/relvid/prompts/*.md
                         cache: <proj>/ai_cache/<role>.<digest>.json — content addressed.
                         backend=chat כותב כרטיס ל-ai_requests/ וקורא מ-ai_responses/.
SEGMENT_SOURCES        = <proj>/segment_sources.json (v8.8) — מקור פר-סגמנט לפרויקטים
                         עם ביניים שהורכב ביד. נכשל קשה על אי-התאמת אורך/צבע.
BASELINE               = tools/bench/baseline_v7.py → baseline_v7.FROZEN.json (13 KPIs)
GATE_TESTS             = tests/test_gates_block.py (31 בדיקות הזרקת-כשל)
REVIEW_APP             = review-app/  (פורט 5112, "▶ הפעל רוויו R.E.L.command" / LaunchAgent)
                         v9.16: **מצב פשוט הוא ברירת המחדל** — צפייה → הערות → שלח
                         לקלאוד/אשר, בפעולה ראשית אחת ("מה עכשיו"). כלי העריכה
                         המלאים ב"מצב מתקדם" (כפתור בכותרת). פאנל האישור הסופי
                         והתקדמות הגימור = כרטיסים מתחת לנגן, לא לשוניות.
                         v9.17: **מצב לילה** (🖥️/☀️/🌙, דפוס rel.fit/tasks, ברירת
                         מחדל לפי המק) · הקלדת הערה עוצרת את הנגן ותופסת את הזמן
                         (דפוס Frame.io) · פס סמני הערות מתחת לנגן · שורות "מה
                         עכשיו" לחיצות · "⏭ הבא בתור" · רענון אוטומטי בפוקוס.
FINISH_PIPELINE        = tools/local_finish_pipeline.py   # v6 — הגימור בקריאה אחת
LEARN                  = tools/learn_from_edits.py        # לולאת הלמידה
ROUTING_CONFIG         = tools/folder-routing.json
RESOLVER               = tools/resolve_output_path.py
MATCHER                = tools/match_intake.py
EDL_BUILD / EDL_CUT    = tools/edl_build.py / tools/edl_cut.py
EDL_POLICY             = tools/edl-policy.json            # ספים — מכויל ע"י learn_from_edits
BROLL_CATALOG          = tools/broll_catalog.py + catalog_path מ-tools/broll-catalog-config.json (כיום PROJECT/בירולים/catalog.json; CONTENT_ROOT/בירולים לא קיים)
BROLL_PICK             = tools/broll_pick.py
QA_GATES               = tools/qa_gates.py
GATE_REGISTRY          = tools/gate_registry.py (v9.13) · **118 השערים במקום אחד.**
                         לכל שער protects / cost_of_blocking / fallback — נכנסים
                         לדוח עצמו (`why`), לא נשארים כהערה בקוד.
                         `--audit` (שער ב-doctor) · `--suspects` · `--workdir W`
                         כלל נאכף: **אין שער חוסם עם סף לא-מדוד.**
LESSON_REGISTRY        = tools/lesson_registry.py (v9.13) · **כל הלקחים במקום אחד,
                         כל לקח עם אוכף** (סימבול בקוד / בדיקה / שער). `--audit`
                         נכשל כשאוכף נעלם — כך לקח שורד החלפת מנוע (שער ב-doctor).
                         `--director` מדפיס את הלקחים שמוזרמים לבמאי.
PREFLIGHT              = tools/preflight_critic.py (v9.13) · **הצפייה של הראל לפני
                         הראל**: מרכז את כל הדוחות + בדיקות-הכאב (קפיצה כפולה
                         בגבול · הבהוב · בירול בלי הקשר · Hook/CTA) לפסק-דין
                         ready_for_harel ב-PREFLIGHT.json. רץ בצנרת אחרי qa_gates;
                         מדווח, לא חוסם. ממצא high פתוח = החלטה מודעת שמדווחת.
DIRECTOR_LESSONS       = tools/director_lessons.py (v9.13) · למידה מ-n=1: לקחי
                         lesson_registry (director_relevant) + דפוסי התיקון של
                         הראל מ-corrections.jsonl (לפי cohort) → payload הבמאי
                         (harel_lessons, פרומפט director.plan_v1.4). הקובץ נכתב
                         פעם אחת לפרויקט — יציבות digest (חוק ברזל 4).
SHOT_DEBT              = tools/broll_shot_debt.py (v9.9) · מה מציעים במקום לחסום —
                         משפט בלי שוט + רצף חוזר + חוסר בבריכה → פריטי צילום
                         לבורד הסושיאל. רץ בצנרת אחרי broll_sequence_qa.
WHISPER                = tools/align_words.py  (המק: /Users/hayon/.rel-whisper/bin/python)
                         v7.8: מודל ברירת מחדל ivrit-ai/whisper-large-v3-turbo-ct2 + VAD
                         (עברית מכווננת; פי ~2 מהר וכמחצית השגיאות מול medium — ASR-BENCH.md)
NOTEFIX                = tools/note_corrections.py (v7.8) · תיקוני 'מילה*' מההערות → תמליל
                         + asr-glossary pending; עמום ⇒ needs_manual, לא ניחוש
FIXED_INTRO            = tools/fixed_intro.py (v7.9) · זיהוי משפט-טריגר בתמליל →
                         הרכבת אפקט הפורמט הקבוע (ניפוץ זכוכית + צליל) על הרגע המדויק
WORDS_MAP              = relvid.edl_utils.map_words_to_keeps (v7.9) · **לא מתמללים
                         פעמיים** — התמלול המקורי ממופה לציר החתוך; שער כיסוי
                         (speech_coverage_gate) מוודא שאין דיבור בלי כתוביות
CAPTIONS_MAC           = captions-app/captions_overlay.py  # צריבה PIL על המק (בלי libass)
CAPTIONS_SANDBOX       = tools/captions_build.py           # ASS+libass (בסנדבוקס בלבד)
MUSIC_MIX              = tools/audio_mix.py mix — יחסי לדיבור: gap 26 / רצפה 25 / רצפה מקומית 20 לחלון 3ש (L138, 14.10.26; tools/music-level-policy.json) ·
                         דאקינג ברירת-מחדל בעומק 8 (דיבור ‎-54) · אורך מלא · --no-duck מבטל
MUSIC_LIB              = brand-assets/music/  ("calm" בשם = רגוע; rotation אוטומטי;
                         חוק 90 יום: אותה מנגינה לא חוזרת בחלון 3 חודשים — music-rotation.json v2)
# v7 — Editorial OS:
REGISTRY               = tools/project_registry.py (rebuild/list/show) · אינדקס SQLite נבנה-מחדש ב-_work/.index/
MANIFEST               = project_manifest.json פר-פרויקט (project_id יציב — שם תיקייה אינו מזהה)
REVISIONS              = tools/relvid/revisions.py · כל שמירה=גרסה · undo/redo/restore באפליקציה
RUNNER                 = tools/run_finish.py (נעילה, run_id, resume, FINAL רק אחרי QA PASS)
CLAUDE_BRIDGE          = tools/review_cli.py (projects/tasks/task/claim/resolve/fail/revisions/qa/sync/sync-status/sync-all)
SYNC                   = tools/relvid/sync.py (v7.7) · FINAL_PROVENANCE.json פר-פרויקט ·
                         GET/POST /api/sync/{שם} · ריפוי-עצמי בפתיחת פרויקט באפליקציה
DOCTOR                 = tools/system_doctor.py [--json]
CUT_QA                 = tools/cut_qa.py (בדיקה ויזואלית של כל גבולות החיתוך — דיווח)
CANON_LINT             = tools/canon_lint.py (policy-as-code: HARD/WARN/INFO)
CAPTION_SAFETY         = tools/caption_safety.py · STORY = tools/story_structure.py (המלצות)
GOLDEN                 = tools/golden.py (build/run) — regression לכל שינוי policy
LEARNING_V2            = tools/learn_from_edits.py (shadow proposals; --approve רק אחרי regression PASS)
OPS_DASH               = tools/ops_dashboard.py
THUMBNAIL              = tools/thumbnail/ (band-center 0.725 נעול)

# Metricool (v3.2 — נשמר):
METRICOOL_BRAND_REL        = 6323702   # IG+FB+TikTok+YouTube
METRICOOL_BRAND_THROWDOWN  = 6436350   # IG+FB בלבד
METRICOOL_TZ               = Asia/Jerusalem
LABEL_READY_TO_SCHEDULE    = "מוכן לתזמון!"        # id 8  → autoPublish
LABEL_READY_TO_SCHEDULE_DRAFT = "מוכן לתזמון בDraft" # id 10 → draft
LABEL_SCHEDULED            = "תוזמן!"               # id 6
SCHEDULE_DATE_COLUMN_ID    = date_mkrpvw3n
FINAL_VIDEO_COLUMN_ID      = file_mm402fp7
SCHEDULE_APPROVAL_TAG      = [APPROVE-SCHEDULE]
SCHEDULED_TAG              = [SCHEDULED-METRICOOL]
METRICOOL_LOCATION         = "קרוספיט אריאל - CrossFit R.E.L"   # ידני בקומפוזר, תמיד

# v7.2 — אישור קאבר+קפשן (שער בין FINAL לתזמון), נועל artifact_id (v9.4):
SCHEDULE_REVIEW_API        = POST/GET /api/schedule-review/{שם}   # action: set_draft|approve|request_changes
SCHEDULE_APPROVAL_FIELD    = project_manifest.json → schedule_approval {status,cover_path,caption_draft,
                             caption_approved,artifact_id,artifact_checksum,artifact_path,
                             approved_final_live_sig,approved_final_checksum,
                             approved_final_path,approved_at}
STATE_READY_TO_SCHEDULE    = "ready_to_schedule"    # status=approved + artifacts.verify(workdir, artifact_id).ok == True
STATE_AWAITING_SCHED_APPR  = "awaiting_schedule_approval"
STATE_SCHEDULED            = "scheduled"            # v9.33 — "📅 תוזמן — ממתין לפרסום": state_override אחרי תזמון מאומת
STATE_PUBLISHED            = "published"            # "🚀 הושלם — פורסם בפועל": ידני / Metricool מראה PUBLISHED בלבד
# סדר: … ready_to_schedule → scheduled → published. registry.SCHEDULE_CLOSED_STATES = שניהם — מחוץ לתור התזמון.
```

---
