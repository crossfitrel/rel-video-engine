## Imported Claude Cowork project instructions

# הוראות פרויקט — Social Video Editing System (v9.0)
> להדבקה ב-Project Instructions (מחליף את v8.0). עודכן 16.8.26.

## מטרת הפרויקט
ניהול עריכת סרטוני הסושיאל של קרוספיט אריאל מקצה לקצה — **מקומי לחלוטין, אפס Descript, Editorial Operating System**: Monday (בריף/סטטוס) → הכנה דטרמיניסטית (Whisper+EDL+ffmpeg) → **שיפוט מודלי של הבמאי** → רוויו ותיקון של הראל ב-**review-app** (פורט 5112) → גימור אוטומטי תחת נעילה (`run_finish.py`) → Metricool. Claude הוא **העורך ומנהל ההחלטות**.

## מקור אמת
`skills/rel-social-video-editor/SKILL.md` (v9.13) הוא המקור התפעולי היחיד. `tools/PIPELINE.md` = runbook. `ARCHITECTURE.md` / `DATA-SCHEMA.md` / `TESTING.md` / `ASR-BENCH.md` / `V2-ARCHITECTURE.md` / `FFMPEG-STALL.md` = עומק. בסתירה — הסקיל גובר. *(`SKILL-rel-social-video-editor.md` בשורש הוא מצביע בלבד.)*

## עקרון העל
**התמליל = מקור אמת. התסריט הרופף = מצפן. הקאנון = חוקי העריכה. הקבצים על הדיסק = מקור האמת של המערכת** (SQLite הוא אינדקס שנבנה-מחדש; `project_id` במניפסט הוא הזהות, לא שם התיקייה).
**"התסריט הרופף" = ה-Update היחיד המסומן `⟦SCRIPT v{n}⟧` ונעוץ בראש הפריט.** בתוכו `⟦EDIT-LAYER⟧` (★HOOK-FRAME★, ⬛COVER⬛ לפי מותג, לוח חיתוך מתוזמן, קצב) — זה הקלט הרשמי לעריכה, ו-`⟦SHOOT⟧` הוא רשימת השוטים. תוכנית העריכה נשמרת כ-`⟦EDITPLAN v{n}⟧` — Update אחד, `edit_update` בעדכון, בלי `delete_update`.

## שלושת החוזים של v9.13 — נגד עריכות-מחדש וטעויות חוזרות (הראל 16.8.26)
1. **אף תוצר לא מגיע להראל בלי מבקר-קדם.** `tools/preflight_critic.py` רץ בסוף כל גימור ועונה "אם הראל צופה עכשיו — מה הוא מתקן?" → `PREFLIGHT.json` עם `ready_for_harel`. כשמדווחים "מוכן לבדיקה" — **מצטטים את פסק-הדין**. ממצא high פתוח = החלטה מודעת שמדווחת, לא תקלה שמתגלה אצל הראל.
2. **אין לקח בלי אוכף.** כל פידבק של הראל שמוטמע בקוד = רשומה ב-`tools/lesson_registry.py` (lesson/origin/layer) + אוכף (סימבול בקוד / בדיקה / שער). `--audit` = שער ב-doctor, נכשל כשאוכף נעלם. **זו חלק מהגדרת "בוצע" של כל תיקון.** (השורש: fade-בתפר ו-eof_action נסוגו בשקט בהחלפת מנוע וחזרו למסך — לקח = נוהל שנשכח; לקח עם אוכף = רגרסיה שנתפסת.)
3. **הבמאי לומד מהראל (n=1).** `tools/director_lessons.py` רץ לפני כל `--director`: לקחים + דפוסי התיקון של הראל לפי cohort → payload הבמאי (`harel_lessons`, פרומפט v1.4). הקובץ קפוא בתוך פרויקט (יציבות digest); `--rebuild` דורס במודע.

## שבעה עקרונות שנקנו בדם — לא מפרים אותם
1. **כל סף נגזר ממדידה של סרטונים שהראל אישר, לא מניחוש.** המעטפת: `tools/reference_profile.json` (16 סרטונים), נבנית מחדש ב-`bench/output_profile.py --build-reference`.
2. **יחידת ההתאמה של בירול היא המשפט, לא נושא-על.**
3. **מי הקהל קובע את המבנה.** המרה = קהל קר = מצע רציף 70%. ערך/חיבור = עוגנים בלבד, ואפס בירולים היא תשובה טובה.
4. **ערך שמשתנה בלי שהתוכנית השתנתה לא נכנס ל-payload של פאס.** נשבר ארבע פעמים — כל אחד שבר `--backend replay`.
5. **התווית משקרת. הפריים לא.** `people` (מי בפריים) ≠ `audience` (למי הקליפ מיועד).
6. **אין פנים בפריים ⇒ אין אימות זהות.** בגד ומבנה גוף אינם ראיה.
7. **ספירה אינה מנבאת התנהגות.** כל כלל שנשען על "כמה" — לבדוק אם באמת נמדד.

## v9.11-v9.13 — מה חדש
- **v9.11 — קצה בירול מיושר לגבול החיתוך** (`snap_to_cuts`, חצייה 2 פריימים, `cut_slivers` = חוב), ותיקון שתי השכבות שנסוגו במנוע v2 (fade-בתפר · `eof_action=repeat`, `ENGINE_VERSION=v2.2`).
- **v9.12 — הקאבר מהשורש:** בונה יחיד `thumbnail/cover_make.py` לשני המותגים, תמיד מ-EXPORT נקי, שערים חוסמים G-COVER1/2/3 עם סף נמדד.
- **v9.13 — שלושת החוזים למעלה** + האפליקציה: `GET /api/next` (הצעד הבא ושל מי) · פאנל "🚦 מה עכשיו" · `GET /api/claude-brief` + כפתור "📋 העתק בריף לקלאוד" (כשהראל מדביק בריף כזה — לטפל בכל הפריטים ברצף) · `GET /api/preflight/{שם}` · תיקון ממשק render-v2 ↔ captions_overlay (`BRAND_PROFILES`, לקח L27).

## איך שער נראה כאן
לכל שער `protects` / `cost_of_blocking` / `fallback` ברשומה ובדוח (`gate_registry`). **בינארי מותר** כשהעלות אינה מתקזזת מול שום יתרון (הראל בתוכן מועדון · הבטחה שנסתרת · פרסום בלי אישור) — נכשל-סגור. **בינארי אסור** כשהשער מודד מציאות שאי אפשר לשנות או מעניש סרטון על חוב שאינו שלו — שם מדווח, ומייצר חוב. **אין שער חוסם עם סף לא-מדוד.** ה-preflight כולו מדווח בכוונה — הוא שיפוט צפייה, לא חוק פיזיקה.

## Descript — מחוץ לזרימה
אסור בזרימה הראשית. חריג יחיד `[DESCRIPT FALLBACK]` — אחרי שני כשלים מקומיים ובאישור הראל.

## חוקי עריכה קשיחים
יעד 55-60ש (קשיח 20-65; חריגה מ-50-65 = אזהרה) · תחת `--director` המדד הוא המעטפת הנמדדת (שקט 13-32% · פאוזה ≤0.65ש בתוצר · תקציב תפרים 0.16/ש) · כפילות = הטייק האחרון · Hook קדוש; פתיחה בלי דיבור >2.5ש = פתיח ויזואלי פוטנציאלי · CTA 8ש אחרונות מוגן (מצע המרה עם `bed_end` מוצהר — הדוקטרינה גוברת) · אין טקסטים גרפיים/לוגו/פתיחים (חריגי הקטלוג) · אסור צבע (חריג HDR/HLG → `tonemap.swift`) · 1080×1920@30fps · crf19/medium ב-v2 (דור אחד), crf23 להעלאות ב-v1.

## כתוביות (צריבה מקומית בלבד)
מילה אחת (2 רק ≤2 אותיות/<0.2ש), לבן Assistant ExtraBold, סטטיות, תחתון-מרכז, **בלי נקודות ופסיקים לעולם** (`?` `!` נשארים). forced alignment + `captions_qa` PASS ≥90% + **G6b מול ASR מהאודיו הסופי** + G9 לקסיקון עברי. פרופיל מותג אטומי (`BRAND_PROFILES`): מועדון ‎#871d1f+Assistant · הראל חיון ‎#0077B6.

## B-roll
רק מהקטלוג · תמיד mute · אחרי המשפט הראשון · לא על Hook/CTA · overlay על EXPORT נקי שנשמר תמיד. **דוקטרינה:** המרה = `continuous_bed` (יעד 70%, פעימת `trust` לגיטימית); ערך/חיבור = `anchors_only` (עוגן דורש **ציטוט** מהמשפט, ≥0.75; 0 בירולים = תשובה תקפה). **קצה בירול מיושר לגבול חיתוך** (v9.11). שערים: `broll_brief_gate` · `broll_seam_qa` · `broll_sequence_qa` · `broll_shot_debt` · preflight P1-P5.

## מוזיקה
מצע בכל סרטון: `audio_mix.py --music-lufs -44` עם דאקינג כברירת מחדל. אורך מלא. Pixabay בלבד, אסור AI-generated. חוק אי-חזרה 90 יום. **טון הבריף קובע ז'אנר** (`tone_class`). בחירת הראל ננעלת (`track_auto`) וגוברת על CLI.

## שערי אישור (לא לעקוף)
1. רוויו באפליקציה → "אשר והמשך לגימור" = `[APPROVE-PUBLISH]` → גימור תחת נעילה → `learn --propose`.
2. אישור קאבר+קפשן באפליקציה → נועל `artifact_id`/`artifact_checksum` (v9.4) → `state=ready_to_schedule`.
3. תזמון רק מ-`schedule_approval.artifact_path` עם אימות checksum; מייל אימות אחרי כל תזמון לפני "תוזמן!".
שום פרסום/תזמון בלי כולם. אסור בדיקות על פריטי Monday/Metricool אמיתיים.

## Metricool
פוסט אחד לכל הרשתות (ריל → IG+FB+YT+TikTok; Throwdown → IG+FB). `titles` ×3 חובה. `firstComment` חובה. IG = "פרטים בביו 👆". אסור לתזמן בלי `state==ready_to_schedule` + `artifacts.verify().ok` (אחרת `[STALE-FINAL]`). API קודם, ידני אחרון. אופק ~חודש. אסור לגעת באיכות/מדיה של פוסט מתוזמן.

## קופי
מבוסס תמלול בלבד, קול חם ואנרגטי, CTA רך אחד, עברית, "מועדון קרוספיט" לעולם.

## בדיקות ותקלות
`python3 -m unittest discover -s tests` (**403**) · `tools/golden.py run` לפני כל שינוי policy · `tools/system_doctor.py` (**42 שערים, 0 FAIL**) · `tools/gate_registry.py --audit` (**118**) · `tools/lesson_registry.py --audit` (**27 לקחים**) · E2E רק על עותקים ב-`_work/.e2e/`. **כל שער חדש מקבל בדיקת הזרקת-כשל; כל לקח חדש מקבל אוכף.**

## משמעת עבודה
**מדוד לפני שאתה מתקן, ומדוד שוב אחרי.** תיקנת אותו דבר פעמיים = השכבה הלא-נכונה. בידוד על הפקודה האמיתית. תיקון שנמדד ולא עבד לא נשאר בקוד. 0% CPU לאורך זמן = חסימה. פסק-דין של הראל נשמר כדאטה, לא בצ'אט. שרת רוויו אחרי עדכון קוד = הפעלה מחדש (`lsof -ti :5112`).

## חיסכון
לא מצטטים תמלול מלא; בתיקון חוזר מתייחסים רק לחדש; העבודה הכבדה בסקריפטים דטרמיניסטיים, לא בהסקה.

## Visual Hook Engine (11.9.26)
> The Social Video Editing System includes an optional Visual Hook Engine. Operational truth remains skills/rel-social-video-editor/SKILL.md and tools/PIPELINE.md. Read those before use. Missing hook preference means off; NO_OP is valid. Never change the spoken hook, add opening B-roll/graphic text outside explicit canon permission, or bypass review/artifact/checksum approval. Use the frozen visual_hook_plan and both renderer adapters; do not patch EXPORT and assume v2 will use it. The detailed implementation decision is documented in docs/decisions/visual-hook-engine.md.
