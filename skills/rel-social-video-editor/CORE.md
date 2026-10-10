# rel-social-video-editor — ליבה

> **קובץ זה נבנה אוטומטית** (`tools/skill_pack.py build`) מתוך `CORE.md` + המאסטר `skills/rel-social-video-editor/SKILL.md` בפרויקט. לא עורכים את הגרסה המותקנת — עורכים את המאסטר/CORE ובונים מחדש.
> **היררכיה:** `00_META/VIDEO-CANON.md` (עותק: `references/video-canon.md`) › הליבה הזו › ה-references. פורמט התסריט ו-`⟦EDIT-LAYER⟧` בבעלות `rel-script-writer`. כל קפשן דרך `rel-cta-psychology`.

## איך לעבוד עם הסקיל הזה (חיסכון טוקנים)
1. **קוראים רק את ה-reference של השלב שבו עובדים** (מפה בסוף הקובץ). לא קוראים את כל המאסטר, לא את CHANGELOG ולא את כל ה-handoffs.
2. **פתיחת סשן = פקודה אחת** על המק (Desktop Commander):
   `~/.rel-whisper/bin/python tools/claude_start.py` → מצב המערכת, תור "מה עכשיו", גרסה נוכחית, תביעות קבצים של צ'אטים מקבילים — בכ-30 שורות.
3. **baseline/אימות = פקודה אחת:** `~/.rel-whisper/bin/python tools/baseline.py` (unittest + doctor + שני ה-audits, סיכום קצר ודיף מול הריצה הקודמת). לא מריצים את ארבעתם בנפרד ולא מדביקים פלט מלא.
4. **צ'אט מקביל:** לפני עריכת קובץ משותף — `tools/work_claim.py claim <קבצים> --by "<נושא הצ'אט>"`; בסוף — `release`. תביעה פעילה של צ'אט אחר = לתאם, לא לדרוס.
5. העבודה הכבדה בסקריפטים דטרמיניסטיים; לא מצטטים תמלול מלא; בתיקון חוזר מתייחסים רק לחדש.

## התפיסה בשורה אחת
Monday (בריף/סטטוס) → הכנה דטרמיניסטית מקומית (Whisper+EDL+ffmpeg) → שיפוט הבמאי (`--director`) → רוויו של הראל ב-**review-app** (פורט 5112) → גימור מקומי תחת נעילה (`run_finish.py` / `local_finish_pipeline.py`) → אישור קאבר+קפשן באפליקציה → Metricool. **Descript מחוץ לזרימה** (חריג יחיד `[DESCRIPT FALLBACK]` — אחרי שני כשלים מקומיים ובאישור הראל).
**עקרון העל:** תמליל = מקור אמת · תסריט רופף (`⟦SCRIPT v{n}⟧` הנעוץ) = מצפן · הקאנון = חוקי העריכה · הקבצים על הדיסק = מקור האמת (SQLite = אינדקס; `project_id` במניפסט = הזהות).

## קבועים שצריך כמעט בכל סשן
```
PROJECT   = ~/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System
WORK_ROOT = ~/rel-video-work   (לקרוא work_root() מ-tools/relvid/paths.py — לא לקבע נתיב)
PYTHON    = ~/.rel-whisper/bin/python   (ל-python3 המערכתי אין flask/raqm — פלט בדיקות שגוי)
REVIEW    = http://127.0.0.1:5112 · launchd com.rel.review-app · אחרי עדכון קוד: launchctl kickstart -k gui/$(id -u)/com.rel.review-app (לעולם לא nohup)
MONDAY    = בורד סושיאל 18395578529 · סטטוס color_mkrp4sgm · "מוכן לעריכה"(11) → "לאחר צילום, בעריכה" → "מוכן לבדיקה"(12) → "מוכן לתזמון!"(8) → "תוזמן!"(6) · תאריך date_mkrpvw3n (UTC!) · קובץ file_mm402fp7
METRICOOL = מועדון 6323702 (IG+FB+TikTok+YT) · Throwdown 6436350 (IG+FB) · "הראל חיון" 6519658 (SmartLink t.mtrbio.com/HarelHayon)
ASR       = ivrit-ai turbo + VAD + language=he · רץ ב-MLX על ה-GPU (~/.rel-mlx, פי ~3), נסיגה ל-ct2 בכשל · REL_ASR_BACKEND=ct2 לכפות (ASR-BENCH.md §MLX)
BRAND     = מועדון #871d1f · הראל חיון #0077B6 · 1080×1920@30 · אסור לגעת בצבע (HDR/HLG → tonemap.swift)
EMAIL_TO  = harel@crossfitrel.com — רק כשנדרשת פעולה מהראל (כשל שדורש אותו, לפי rel-email-design); אין מייל אימות/סטטוס שגרתי (הראל 30.8/3.9/13.9.26)
```
קבועים מלאים (עמודות, נתיבי כלים, API): `references/constants.md`.

## שערי אישור — לא עוקפים
1. **רוויו באפליקציה** → "אשר והמשך לגימור" = `[APPROVE-PUBLISH]` → גימור תחת נעילה → `learn_from_edits.py --propose`.
2. **אישור קאבר+קפשן באפליקציה** → נועל `artifact_id`/`artifact_checksum` → `state=ready_to_schedule`.
3. **תזמון** רק מ-`schedule_approval.artifact_path` אחרי `artifacts.verify().ok` + sha256; **אימות אחרי כל תזמון = קריאה חוזרת ב-Metricool (`getScheduledPosts`), ורק אז "תוזמן!" במאנדיי + עדכון האפליקציה + דיווח בצ'אט; מייל רק בכשל שדורש את הראל.** חוסר התאמה = `[STALE-FINAL]`, לא מתזמנים.
   עדכון האפליקציה = `state_override:"scheduled"` ("📅 תוזמן — ממתין לפרסום"), **לא** `published` — published רק ידני / Metricool מראה `PUBLISHED` (v9.33, L97). שניהם מחוץ לתור התזמון.

## שלושת החוזים
1. **אין תוצר להראל בלי מבקר-קדם** — `PREFLIGHT.json` (`ready_for_harel`); "מוכן לבדיקה" מצטט את פסק-הדין.
2. **אין לקח בלי אוכף** — פידבק שהוטמע = רשומה ב-`lesson_registry.py` + אוכף; `--audit` הוא שער ב-doctor.
3. **הבמאי לומד מהראל (n=1)** — `director_lessons.py` לפני כל `--director`.

## חמישה-עשר עקרונות שנקנו בדם
1. כל סף נגזר ממדידה של סרטונים שהראל אישר (`tools/reference_profile.json`), לא מניחוש.
2. יחידת ההתאמה של בירול היא המשפט, לא נושא-על.
3. מי הקהל קובע את המבנה: המרה = קהל קר = מצע רציף 70%; ערך/חיבור = עוגנים בלבד, ואפס בירולים היא תשובה טובה.
4. ערך שמשתנה בלי שהתוכנית השתנתה לא נכנס ל-payload של פאס.
5. התווית משקרת, הפריים לא — `people` (מי בפריים) ≠ `audience` (למי הקליפ).
6. אין פנים בפריים ⇒ אין אימות זהות.
7. ספירה אינה מנבאת התנהגות — כלל שנשען על "כמה" נבדק במדידה.
8. המחשה ויזואלית היא אירוע, לא פיצ'ר — ברירת מחדל אפס.
9. מסכה שנגזרת מתמונה אינה יודעת מה שמה — מיפוי ישות→אזור מאומת בעין.
10. מיקום נפתר מהפריים, לא מוזן כמספר.
11. גלאי שמפסיק לעבוד בשקט גרוע מגלאי שאין — 'לא נמדד' הוא דאטה, לא PASS.
12. כששני דברים אינם ניתנים להפרדה בקלט — מתקנים את הקלט, לא את האלגוריתם.
13. חוליית מסירה נכשלת בשקט — התאמה בין שתי מערכות (CTA↔Flow) נמדדת, לא מונחת.
14. האורך נקבע ע"י התוכן, לא ע"י תקרה; ההוק מזיז חשיפה, האורך לא.
15. קלט שהשתנה מבטל כל מה שנגזר ממנו (גודל **ו-**mtime, ומוחקים נגזרות).
**אין שער חוסם עם סף לא-מדוד** · בינארי מותר רק כשעלות החסימה אפסית; שער שמודד מציאות שאי אפשר לשנות — מדווח ומייצר חוב.

## חוקי ברזל — תמצית (הנוסח המלא והנימוקים: `references/iron-rules.md`)
1. **Hook קדוש** — לא נחתך; Hook מאוחר מועבר לפתיחה. פתיח ויזואלי >2.5ש בלי דיבור = הצעה, לא חיתוך.
2. **האורך נקבע ע"י התוכן** (`tools/length_policy.py` — מקור יחיד): המרה 20-45 · ערך/סיפור 45-90 · פודקאסט 45-90 · קשיח 12-180 · מעל 90 (פודקאסט 120) = `length_reason`. **אסור להאיץ כדי לעמוד במספר.**
3. **אפס דד-אייר, פאוזות מכוונות נשמרות.** תחת `--director` המדד הוא המעטפת הנמדדת (שקט 13-32% · פאוזה ≤0.65ש · תפרים 0.16/ש) — `references/v3-decision-engine.md`.
4. **כתוביות מקומיות**: מילה אחת, בלי `.` `,` לעולם, Assistant ExtraBold, forced alignment, `captions_qa` ≥90%, מתאר לפי מותג.
5. **טקסט גרפי/לוגו/חתימה — רק דרך שכבת ה-Motion Graphics** (v9.37, סקיל `rel-motion-graphics`, שערי MG0-MG8: כל מילה נאמרה/מתועדת, לא על פנים, מעל הכתוביות). מחוץ לשכבה — בלי (חריגי הקטלוג בלבד). המחשה מאיור — תחת שערי v9.20.
6. **B-roll**: קטלוג בלבד · mute · לא על Hook/CTA (8ש אחרונות) · המרה = מצע רציף 70% · ערך/חיבור = עוגנים עם **ציטוט** ≥0.75 · אפס בירולים = תשובה טובה · הפרדת מחלקות קשיחה.
7. **מוזיקה**: מצע בכל סרטון, ‎-46 LUFS + דאקינג (דיבור ‎-54; ברירת המחדל של `local_finish_pipeline.py` מאז v9.22), אורך מלא, Pixabay/Mixkit בלבד (v9.36 — רישיון מסחרי, בלי AI/Content ID/קאברים/שירה), אי-חזרה 90 יום + לא אותה משפחת סאונד כמו 3 הבחירות האחרונות.
8. **1080×1920** · crf19/medium ב-v2, crf23 להעלאות ב-v1 · אסור ultrafast · **לעולם לא לדחוס FINAL.**
9. **אסור לגעת בצבע** (HDR/HLG → `tonemap.swift`).
10. **אסור לגעת במדיה של פוסט מתוזמן.**
11. **ראיות לפני "בוצע"** — FINAL בלי `qa_gates` PASS לא יוצא.
12. **קובץ סופי יחיד** → `{מחלקה}/{חודש}/{סרטון}/`; ביניים רק ב-`_work`.
13. **אסור Descript בזרימה הראשית.**
14. **קאבר+קפשן = אישור נפרד**, קפשן תמיד דרך `rel-cta-psychology` + **מנוע הקפשן v4** (`docs/CAPTION-ENGINE.md`): משלים את הסרטון ולא משכפל אותו, מהלך הוספה אחד ממקור אמיתי, אפס האשטגים. `set_draft` מריץ את `caption_gate` וחוסם הד (L132).
15-16. **checksum לפני תזמון + אימות בקריאה חוזרת אחריו** (`getScheduledPosts`; לא מייל שגרתי).
17. **חוק הראייה** — אין אמירה על סרטון בלי גיליון שנפתח ב-`Read` **בסשן הזה**; כל הערה בחותמת זמן (`references/vision-law.md`).
18. **הקאבר עולה ב-API** (`videoThumbnailUrl` מ-public_url של Monday) ונבדק שחזר `static.metricool.com`.
19-20. **התסריט הוא הקלט** (`⟦EDIT-LAYER⟧`/`⟦SHOOT⟧`); Update אחד לכל סוג — `edit_update`, לא `create_update` שני, לא `delete_update`.
21. **קצב = שער נמדד**: ≤2 קפיצות-חיתוך/5ש; חסר חומר = `shot_debt`, לא עוד חיתוכים.
22. **בדיקה מושתקת** לפני "מוכן לבדיקה".
23-25. **"הראל חיון" + אפליקציה/פרומפט**: פותחים בבעיה · CTA = מילת המפתח = ה-Flow · הערך ב-DM **וגם** בביו (`references/harel-ai-apps.md`).

## מה עושים לפי בקשה
| הבקשה | מה עושים | לקרוא |
|---|---|---|
| "תרוץ על מה שמוכן" / "ערוך את X" | שלבים 0-2: Monday → `match_intake` → `⟦SCRIPT⟧` → הכנה מקומית → Update `[AUTO-EDIT v2 DRAFT]` | `workflow.md` §0-2 · `edit-layer.md` |
| הראל שלח הערות מהאפליקציה | `review_cli.py tasks/claim/resolve` → גימור → `verify-fixes` + `fix-verdict` | `workflow.md` §4.5 · `fix-verify.md` |
| עריכת EDL בצ'אט | אחרי כל שינוי: `review_cli.py sync PROJECT` | `workflow.md` §4.6 |
| גימור | רק `local_finish_pipeline.py` / `run_finish.py` — לעולם לא שלבים ידניים; גימור חוזר = הפקודה המדויקת מרשומת הריצה | `workflow.md` §5 |
| הוק / "מה פותח את הריל" / פריים ראשון | שלב 2.5: `hook_plan.py init` → טכניקה מ-`tools/hook_toolbox.json` → `HOOK_PLAN.json` → `sheet` + Read → `stamp`; P22 חוסם ריל בלי עוגן מוחשי ב-0ש | `hook-build.md` (חסר בהתקנה → `tools/hook_toolbox.json` + `docs/ארגז-כלי-הוק-v9.44.md` בפרויקט) |
| אפקט/זום/וויפ/צליל בהוק · "עריכת הוק" | בלוק `edit` ב-`HOOK_PLAN.json` (מתכון מ-`edit_recipes`) → `hook_fx.py check` → גימור `--hook-fx auto` → Read על `HOOK_FX_SHEET.jpg`; מתכון אחד, ≤2 תנועות, ≤3 צלילים, רק על העוגן | `hook-edit.md` (חסר בהתקנה → `docs/ארגז-עריכת-הוק-v9.46.md` + `tools/hook_toolbox.json` edit_recipes) |
| Motion Graphics / שם על המסך / אנטומיה / סרטון MG | סקיל `rel-motion-graphics`: `motion_build.py propose` → `motion_plan.json` → `check` → `snap` + ביקורת ≥8 → גימור `--motion auto` → Read על `MG_SHEET.jpg` | `motion-graphics.md` |
| QA / "מוכן לבדיקה" | `vision_check` + Read על הגיליונות + PREFLIGHT | `vision-law.md` · `workflow.md` §6 |
| קאבר+קפשן | `caption_gate.py --sources` → `docs/CAPTION-ENGINE.md` + `rel-cta-psychology` → `POST /api/schedule-review/{שם} set_draft` (שער L132) | `workflow.md` §6.5 |
| תזמון | `state==ready_to_schedule` + verify → Metricool → `getScheduledPosts` חוזר → Monday+אפליקציה → דיווח בצ'אט | `workflow.md` §7 · `constants.md` |
| תקלה | טבלת כשלים | `failures.md` |

## כללי עבודה שנוטים להישכח
- **פריים 0 = עוגן מוחשי** (סצנה/פעולה/חפץ/אדם/מספר) — לא כרטיס, לא פתיח, לא מדבר-למצלמה מופשט. `HOOK_PLAN.json` + Read על `HOOK_SHEET.jpg` לפני כל הצגה להראל (P22). מגבר אחד לכל היותר ב-0-2ש.
- אחרי כל תזמון: Metricool **+** Monday **+** אפליקציה (גם קרוסלות). תאריך רק מעמודת הבורד. אופק ~חודש.
- גימור ארוך רץ ב-Desktop Commander על המק, לא ב-bash של הסנדבוקס (מגבלת זמן).
- קליטת גלם מקומית; קבצים גדולים ל-Monday — מהמק.
- "לעולם לא 'חדר כושר'" — מועדון קרוספיט. לב: הראל 🩵 · מועדון 🖤❤️.
- תיקנת אותו דבר פעמיים = השכבה הלא-נכונה. מדוד לפני התיקון ואחריו. תיקון שנמדד ולא עבד לא נשאר בקוד.
- כל שער חדש מקבל בדיקת הזרקת-כשל ורשומה ב-`gate_registry` (protects/cost_of_blocking/fallback); כל לקח חדש מקבל אוכף. `tools/golden.py run` לפני כל שינוי policy. E2E רק על עותקים.
- 0% CPU לאורך זמן = חסימה (ffmpeg stall), לא "עוד רגע".
- הטבלה המלאה של כללי התפעול (53 שורות, נבדקת ב-`lessons_canon.py --audit`): `references/ops-rules.md`.
