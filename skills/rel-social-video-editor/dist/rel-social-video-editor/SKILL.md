---
name: rel-social-video-editor
description: "מערכת עריכת סרטוני הסושיאל המקומית של קרוספיט אריאל: Monday → הכנה (Whisper+EDL) → review-app (5112) → גימור → אישור קאבר+קפשן → Metricool. TRIGGERS: ערוך סרטון, תרוץ על הסרטונים, הערות מהאפליקציה, גימור, מוכן לתזמון, תזמן ב-Metricool, EDITPLAN, סרטון אפליקציה. NEGATIVE: תסריט → rel-script-writer · קפשן → rel-cta-psychology · פודקאסט מלא → rel-podcast-descript-editor."
---

# rel-social-video-editor — ליבה

> **קובץ זה נבנה אוטומטית** (`tools/skill_pack.py build`) מתוך `CORE.md` + המאסטר `skills/rel-social-video-editor/SKILL.md` בפרויקט. לא עורכים את הגרסה המותקנת — עורכים את המאסטר/CORE ובונים מחדש.
> **היררכיה:** `00_META/VIDEO-CANON.md` (עותק: `references/video-canon.md`) › הליבה הזו › ה-references. פורמט התסריט ו-`⟦EDIT-LAYER⟧` בבעלות `rel-script-writer`. כל קפשן דרך `rel-cta-psychology`.

## איך לעבוד עם הסקיל הזה (חיסכון טוקנים)
1. **קוראים רק את ה-reference של השלב שבו עובדים** (מפה בסוף הקובץ). לא קוראים את כל המאסטר, לא את CHANGELOG ולא את כל ה-handoffs.
2. **פתיחת סשן (v10 ענן)** = `add_repo crossfitrel/rel-video-cloud` → clone → `bash cloud/bootstrap.sh` (~3 דק'; venv, ivrit-ai ct2, ffmpeg, puppeteer, ספריות+מצב מ-Drive של hayonhq) → `source cloud/env.sh` → `$REL_PY tools/claude_start.py`. ארכיטקטורה: `CLOUD.md` · מה ריצה מתוזמנת עושה: `cloud/RUN.md`.
3. **baseline/אימות = פקודה אחת:** `$REL_PY tools/baseline.py` (unittest + doctor + שני ה-audits, סיכום קצר ודיף מול הריצה הקודמת). לא מריצים את ארבעתם בנפרד ולא מדביקים פלט מלא.
4. **צ'אט מקביל:** לפני עריכת קובץ משותף — `tools/work_claim.py claim <קבצים> --by "<נושא הצ'אט>"`; בסוף — `release`. תביעה פעילה של צ'אט אחר = לתאם, לא לדרוס.
5. העבודה הכבדה בסקריפטים דטרמיניסטיים; לא מצטטים תמלול מלא; בתיקון חוזר מתייחסים רק לחדש.

## התפיסה בשורה אחת
גלם מהטלפון ל-Monday ("קבצים" `file_mkrpfxkz`, סטטוס "מוכן לעריכה") → ריצת ענן מתוזמנת כל שעה (`cloud/prep.py`: שער HDR + Whisper + EDL + ffmpeg) → שיפוט הבמאי (`--director`) → גימור מלא + PREFLIGHT → **עמוד הרוויו** (Artifact עם db, בטלפון; `cloud/review_bridge.py` מחבר אותו למנוע ה-review-app) → גימור תחת נעילה (`local_finish_pipeline.py`) → אישור קאבר+קפשן+תזמון בעמוד → Metricool. **אפס תלות במק בריל** (המק נשאר לפודקאסט ולמסלול גיבוי עד סגירת האימותים). **Descript מחוץ לזרימה** (חריג יחיד `[DESCRIPT FALLBACK]` — אחרי שני כשלים מקומיים ובאישור הראל).
**עקרון העל:** תמליל = מקור אמת · תסריט רופף (`⟦SCRIPT v{n}⟧` הנעוץ) = מצפן · הקאנון = חוקי העריכה · הקבצים על הדיסק = מקור האמת (SQLite = אינדקס; `project_id` במניפסט = הזהות).

## קבועים שצריך כמעט בכל סשן
```
REPO      = github.com/crossfitrel/rel-video-cloud (פרטי) · REL_HOME = שורש הריפו · נתיבים רק מ-cloud/env.sh (לא לקבע /Users/...)
WORK_ROOT = $REL_WORK_ROOT = ~/rel-video-work   (לקרוא work_root() מ-tools/relvid/paths.py — לא לקבע נתיב)
PYTHON    = $REL_PY = ~/.rel-whisper/bin/python (venv של bootstrap; ל-python3 המערכתי אין cv2/flask)
REVIEW    = עמוד הרוויו https://claude.ai/artifact/B799jvngoLRUMYzoz1XqZn (db: projects · comments · actions · system/health; doc id = p-<monday_item_id>)
DRIVE     = Drive של hayonhq@gmail.com → "REL Video Cloud/" (ספריות · מצב · מסירות · ארכיון · מניפסט) דרך rclone remote hayonhq (טוקן רק מ-env). לעולם לא ה-Drive של crossfitrel
TRIGGER   = משימה מתוזמנת "עריכת סושיאל בענן" trig_018rae8HZ3XwT7tsdZEdAwSA (כל שעה, ענן בלבד) · מנעול: "לאחר צילום, בעריכה" + [CLOUD-LOCK]
MAC       = מסלול גיבוי בלבד עד שהאימותים בטלפון נסגרים: review-app 5112 (launchd com.rel.review-app) + Desktop Commander
MONDAY    = בורד סושיאל 18395578529 · סטטוס color_mkrp4sgm · "מוכן לעריכה"(11) → "לאחר צילום, בעריכה" → "מוכן לבדיקה"(12) → "מוכן לתזמון!"(8) → "תוזמן!"(6) · תאריך date_mkrpvw3n (UTC!) · קובץ file_mm402fp7
METRICOOL = מועדון 6323702 (IG+FB+TikTok+YT) · Throwdown 6436350 (IG+FB) · "הראל חיון" 6519658 (SmartLink t.mtrbio.com/HarelHayon)
ASR       = ivrit-ai turbo (ct2) + VAD + language=he · בענן REL_ASR_BACKEND=ct2 (MLX רק במק)
BRAND     = מועדון #871d1f · הראל חיון #0077B6 · 1080×1920@30 · אסור לגעת בצבע (HDR כבוי באייפון מ-10.10.26; גלם HLG ישן → tools/hdr_gate.py המכויל, SDR עובר כמו שהוא)
EMAIL_TO  = harel@crossfitrel.com — רק כשנדרשת פעולה מהראל (כשל שדורש אותו, לפי rel-email-design); אין מייל אימות/סטטוס שגרתי (הראל 30.8/3.9/13.9.26)
```
קבועים מלאים (עמודות, נתיבי כלים, API): `references/constants.md`.

## שערי אישור — לא עוקפים
1. **רוויו בעמוד הרוויו** (במצב מעבר גם review-app) → "אשר והתחל גימור" = `[APPROVE-PUBLISH]` → גימור תחת נעילה → `learn_from_edits.py --propose`.
2. **אישור קאבר+קפשן+תזמון לתאריך שבבורד — כפתור אחד בעמוד** → נועל `artifact_id`/`artifact_checksum` → `state=ready_to_schedule`.
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
9. **אסור לגעת בצבע** (HLG → `tools/hdr_gate.py` המכויל npl=160 hable, מסומן ב-`HDR_GATE.json`; לעולם לא חוסם בשקט).
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
- גימור רץ בסשן הענן (2 ליבות: ~13 דק' עם MG). בסוף כל ריצה: `cloud/state_sync.sh push` + `archive-final` ל-Drive של hayonhq.
- הגלם נכנס מהטלפון ל-Monday; התוצר הסופי עולה ל-`file_mm402fp7` ו-Metricool מושך מ-public_url.
- **הפרויקט ב-claude.ai = ידע בלבד.** מדיה/תוצרים/לוגים/.bak — ל-Drive או לריפו, לעולם לא לתיקייה המסונכרנת (L134, `tools/project_hygiene.py scan`).
- "לעולם לא 'חדר כושר'" — מועדון קרוספיט. לב: הראל 🩵 · מועדון 🖤❤️.
- תיקנת אותו דבר פעמיים = השכבה הלא-נכונה. מדוד לפני התיקון ואחריו. תיקון שנמדד ולא עבד לא נשאר בקוד.
- כל שער חדש מקבל בדיקת הזרקת-כשל ורשומה ב-`gate_registry` (protects/cost_of_blocking/fallback); כל לקח חדש מקבל אוכף. `tools/golden.py run` לפני כל שינוי policy. E2E רק על עותקים.
- 0% CPU לאורך זמן = חסימה (ffmpeg stall), לא "עוד רגע".
- הטבלה המלאה של כללי התפעול (53 שורות, נבדקת ב-`lessons_canon.py --audit`): `references/ops-rules.md`.

## מפת references (נטענים לפי צורך — אפס טוקנים עד שקוראים)
| קובץ | לקרוא כש… | סעיפי המאסטר | גודל |
|---|---|---|---|
| `references/hook-edit.md` | עריכת הוק: תנועות/מעברים/צלילים (hook_fx), 12 מתכונים, שערי HFX, --hook-fx | (פתיח) · ארגז העריכה של ההוק (v9.46, 8.10.26) | 3K |
| `references/concept.md` | רקע: למה מקומי, גרסאות וידאו (artifacts) | תפיסת העל (מה השתנה ב-v6) | 2K |
| `references/constants.md` | צריך ID/עמודה/נתיב כלי/API שלא בליבה | קונסטנטות מערכת | 10K |
| `references/v3-decision-engine.md` | --director, מעטפת נמדדת, תקציב שקט/תפרים, best_split | V3 — מנוע ההחלטה, וארבעת המדדים שנגזרו ממדידה (v9.2, 30.7.26) | 2K |
| `references/iron-rules.md` | הנוסח המלא והנימוק של חוק ברזל (בירול, המחשה, תזמון…) | חוקי ברזל (קאנון — אין לעבור) | 20K |
| `references/vision-law.md` | QA ויזואלי, vision_check, גיליונות מגע | חוק הראייה (v9.14, 17.8.26) | 3K |
| `references/edit-layer.md` | שלב 1.5: קריאת ⟦SCRIPT⟧/⟦EDIT-LAYER⟧, טבלת פער, ⟦EDITPLAN⟧ | שכבת העריכה מהתסריט — ⟦EDIT-LAYER⟧ (v9.21, 22.8.26) | 3K |
| `references/ai-enhancement.md` | שכבת AI לסרטון ממומן (higgsfield-ai-enhancement) | שכבת AI לממומן — higgsfield-ai-enhancement (v9.35, 25.9.26) | 0K |
| `references/visual-hook.md` | Visual Hook Engine (NO_OP / SMART_PUNCH_IN) | פתיחה חזותית — Visual Hook Engine (v9.22, 11.9.26) | 2K |
| `references/harel-ai-apps.md` | מחלקת הראל חיון + סרטון אפליקציה/פרומפט (Flow, SmartLink, P17) | סרטוני "הראל חיון" — בניית אפליקציות ופרומפטים עם AI (v9.23, 12.9.26) | 14K |
| `references/intake-guard.md` | קליטת גלם: סיבוב, מטמון ישן, חורי כתוביות | שומרי הגלם — intake_guard (v9.26, 19.9.26) | 2K |
| `references/ops-rules.md` | טבלת כללי התפעול המלאה (lessons_canon) | כללי תפעול מהזיכרון (קנון v9.30) | 8K |
| `references/workflow.md` | ביצוע שלב בפועל (0-7): פקודות, סדר, QA | Workflow v6 | 15K |
| `references/failures.md` | משהו נכשל / בקשה ידנית חריגה | טיפול בכשלים · ערוץ ידני | 1K |
| `references/fix-verify.md` | סבב תיקונים: changelog פר-גרסה, verify-fixes, fix-verdict | שלושת החוזים של v9.13 (16.8.26) — נגד עריכות-מחדש וטעויות חוזרות · "מה תוקן בגרסה הזו" — בדיקת תיקונים במקום צפייה מחדש  | 4K |
| `references/hook-build.md` | שלב 2.5: ארגז כלי ההוק, HOOK_PLAN, P22, מגברי spotlight/then_now | בניית הוק — ארגז כלי ההוק (v9.44, 8.10.26) | 3K |
| `references/motion-graphics.md` | שכבת MG: תבניות, motion_plan, שערי MG0-MG8, --motion בגימור, אזורים ומינון | שכבת Motion Graphics (v9.37, 4.10.26) | 3K |
| `references/version-history.md` | היסטוריה בלבד — כמעט אף פעם | גרסה | 19K |
| `references/video-canon.md` | מחלוקת על חוק עריכה — הקאנון גובר | VIDEO-CANON (עותק מ-00_META) | 20K |

---
*גרסת מערכת v10.0 — 2026-10-10 · נבנה 2026-10-10 23:25 · master sha a1ff1bdc8db1 · core sha b4d321bc8202*
