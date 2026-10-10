# rel-social-video-editor · workflow
> נגזר מהמאסטר (v10.0 — 2026-10-10) ע"י tools/skill_pack.py — לא לערוך כאן.

## תוכן
- Workflow v6
  - שלב 0 — Pre-flight (Monday)
  - שלב 0.5 — שיוך גלם מקומי
  - שלב 1 — Validation גמישה
  - שלב 1.5 — קריאת שכבת העריכה (v9.21, חדש — חובה לפני EDL)
  - שלב 2 — הכנה מקומית (המק, Desktop Commander)
  - שלב 2.5 — בניית הוק (v9.44, חובה לפני הצגה להראל)
  - שלב 3 — INTENT CARD (ללא שינוי)
  - שלב 4 — רוויו של הראל באפליקציה (מחליף את Descript)
  - שלב 5 — גימור מקומי אוטומטי (`local_finish_pipeline.py`)
  - שלב 5.5 — לולאת הלמידה v2 (אחרי כל אישור)
  - שלב 4.5 — Claude Bridge (טיפול בהערות הראל)
  - שלב 4.6 — סנכרון ציר: עריכה בצ'אט ↔ אפליקציה (v7.7, חדש — הראל 25.7)
  - שלב 6 — QA, תיוק והעלאה
  - שלב 6.5 — אישור קאבר+קפשן באפליקציה (v7.2, חדש — בקשת הראל 23.7)
  - שלב 7 — תזמון Metricool (v3.2 גרעין + v7.2 שער checksum, נועל artifact_id מ-v9.4, אימות בקריאה חוזרת מ-v9.31)
  - QA לפני יציאה (תמצית)

## Workflow v6

### שלב 0 — Pre-flight (Monday)
`get_board_items_page` על 18395578529, filter סטטוס index 11, `includeColumns` מלא. לכל פריט `get_updates(limit:5)` — `[AUTO-EDIT` קיים → דלג. עד BATCH_LIMIT.

### שלב 0.5 — שיוך גלם מקומי
`python3 tools/match_intake.py --items items.json --pretty` → רק `matched` ממשיך. דו-משמעי → הראל. חסר → `[INTAKE MISSING]`.
**ראייה (v9.14):** לפני שמאשרים שיוך — `python3 scripts/video_eyes.py analyze RAW.mp4 --no-audio --max-frames 24` וקריאת הגיליון. שם קובץ אינו ראיה לתוכן.

### שלב 1 — Validation גמישה
תסריט רופף מספיק; אין תסריט → `[INFERRED-INTENT]`. חובה: גלם matched + מחלקה. סוג תוכן חסר → value.

### שלב 1.5 — קריאת שכבת העריכה (v9.21, חדש — חובה לפני EDL)
`get_updates(item_id, limit:20)` → מאתרים `⟦SCRIPT` → קוראים `⟦EDIT-LAYER⟧` ו-`⟦SHOOT⟧` → `video_eyes.py analyze RAW.mp4 --max-frames 72` + `Read` על כל הגיליונות → **בונים את טבלת הפער מתוכנן-מול-מצולם** → משם נגזרת טיוטת ה-EDL, ⬛COVER⬛ ותקרת הקצב. אין `⟦SCRIPT` → `[INFERRED-INTENT]` מסומן בדוח ובכותרת ה-`⟦EDITPLAN⟧`. הפירוט המלא: הסעיף "שכבת העריכה מהתסריט" למעלה.

**מחלקה "הראל חיון" + תוכן AI/אפליקציה (v9.23):** באותו שלב נכתב גם `ai_app_brief.json` — מילת המפתח, ה-CTA, קטע "הוספה למסך הבית", סטטוס בירול הצ'אט, ושני ערוצי המסירה (Flow + SmartLink). הפירוט: הסעיף "סרטוני הראל חיון" למעלה. בלעדיו `P17_ai_app` מחזיר ממצא high.

### שלב 2 — הכנה מקומית (המק, Desktop Commander)
בתוך `_work/{שם}/` — כמו v5: דחיסה crf23 (HLG? tonemap.swift קודם) → concat → INPUT.mp4 → Whisper (`align_words`) → `edl_build` → `edl_cut` → ROUGH.mp4 + edl.json + sentences.json + intent_card.md. סטטוס Monday → "לאחר צילום, בעריכה".
הערה: `descript_instructions.md` עדיין נוצר — אבל צרכניתו היא **אפליקציית הרוויו** (הצעות כתומות), לא agent.
**ראייה (v9.14):** `analyze RAW.mp4 --max-frames 72` לפני `edl_build` — מפת השוטים והשתיקות מהגיליון היא הבסיס ל-EDL. חותכים לפי מה שנראה, לא לפי ניחוש.
**שכבת העריכה (v9.21):** לוח החיתוך מ-`⟦EDIT-LAYER⟧` (שלב 1.5) הוא טיוטת ה-EDL — `edl_build` מתקן אותו מול הגלם, לא מתחיל מאפס. בסוף השלב נכתב `⟦EDITPLAN v{n}⟧` על הפריט (`edit_update` אם קיים).

### שלב 2.5 — בניית הוק (v9.44, חובה לפני הצגה להראל)
`hook_plan.py init` → בחירת טכניקה מ-`tools/hook_toolbox.json` לפי כלל הבחירה → `HOOK_PLAN.json` → `sheet` + Read על `HOOK_SHEET.jpg` → `stamp`. שורת "הוק:" ב-`⟦EDITPLAN⟧`. **v9.46:** + בלוק `edit` (מתכון עריכה: תנועה/מעבר/צליל) → `hook_fx.py` בגימור → Read על `HOOK_FX_SHEET.jpg` (הסעיף "ארגז העריכה של ההוק"). P22 הופך ריל בלי עוגן מוצהר ל-"לא מוכן". הפירוט: הסעיף "בניית הוק" למעלה.

### שלב 3 — INTENT CARD (ללא שינוי)
בדיקת שפיות על intent_card.md; הוק אמיתי באמצע → לסמן hook_move באפליקציה או ב-edl.

### שלב 4 — רוויו של הראל באפליקציה (מחליף את Descript)
1. ודא שהשרת רץ (בריאות: `curl 127.0.0.1:5112/health`; לא רץ → הראל מפעיל "▶ הפעל רוויו R.E.L.command").
2. Update על הפריט: `[AUTO-EDIT v2 DRAFT]` + לינק `http://127.0.0.1:5112` + משך + INTENT CARD בקצרה + מספר ההצעות הפתוחות.
3. הראל באפליקציה (v9.16 — מצב פשוט): צופה, זורק הערות בשורת ההערה שמתחת לנגן (נצמדות לזמן ולגרסה), ואז **"📤 שלח הכל לקלאוד"** — או **"✔ אשר והתחל גימור"** מכרטיס "מה עכשיו" (כותב APPROVAL.json עם `[APPROVE-PUBLISH]` ומריץ גימור אוטומטית). עריכת ציר/חיתוכים/טקסט — במצב מתקדם, כמו קודם.
4. כל תיקון שלו נרשם ל-`corrections.jsonl` אוטומטית.
5. **חלוקת העבודה הקבועה (הראל 18.8.26): הראל מעיר — קלאוד מסדר.** ברירת המחדל היא שהערות עוברות לקלאוד לתיקון; האפליקציה לא דורשת מהראל לערוך בעצמו אף שלב.

### שלב 5 — גימור מקומי אוטומטי (`local_finish_pipeline.py`)
רץ מהאפליקציה עם האישור (או ידנית):
```
~/.rel-whisper/bin/python tools/local_finish_pipeline.py --workdir "_work/{שם}" \
    --content-type {value|conversion} [--title "כותרת קאבר"] [--broll-plan broll_plan.json]
```
recut (EXPORT.mp4 crf18, נקי) → Whisper על הקאט (turbo-he+VAD) → **notefix** (v7.8: תיקוני הכתיב מההערות) → reconcile עם הטקסט המתוקן (words_final.json) → **tighten אקוסטי מודע-דיבור** (silencedetect ‎-40dB + הגנת תחילות-מילים ±0.15ש → EXPORT_TIGHT; תזמוני המילים ממופים-מחדש, בלי whisper שני; **מגבלת צפיפות: מקס 2 חיתוכים לכל חלון 5ש; באזור ה-CTA — 8ש אחרונות — נחתך רק שקט ≥0.8ש** — נגד "מקלעת קפיצות", הראל 19.7) → gate אפס-שקט (words חוסם; אודיו חוסם חור ≥0.6ש — כויל 1.5→0.9→0.6 ב-20.7; פאוזות מכוונות → הרפיה זמנית 0.8-1.5 עדיפה על חיתוך לתוך מילה; נכשל → חזרה לאפליקציה) → בירול (v7.8: כל סוגי התוכן, בכפוף לסף רלוונטיות; על EXPORT נקי) → מוזיקה ‎-46 עם דאקינג (rotation, חוק 90 יום) → כתוביות PIL (רצועה בלבד, veryfast/crf16) → loudness ‎-14 (‏`-c:v copy`) → `qa_gates` (חובה PASS) → thumbnail (אם יש כותרת). סטטוס חי: `finish_status.json`; דוח: `FINISH_REPORT.md`.
⚠️ לקח נעול: אסור להשתמש בתזמוני whisper (start/end) כמפת-דיבור לחיתוך אקוסטי — הם מרופדים. ההפרדה = סף אנרגיה ‎-40dB + הגנת word-start בלבד.

### שלב 5.5 — לולאת הלמידה v2 (אחרי כל אישור)
`python3 tools/learn_from_edits.py --propose` → סריקת תיקונים (reason_codes יציבים, offsets לפי project_id, cohorts לפי סוג-תוכן/מותג). **שום כיול לא מוחל ישירות:** הצעה נוצרת ב-shadow (`tools/policy-proposals/`), מוערכת על ה-Golden Set (`--evaluate`), ומוחלת רק עם regression PASS + אישור הראל (`--approve`). Rollback: `--rollback`. ספים: ≥6 ראיות מ-≥3 פרויקטים. את "מה נלמד" מדווחים להראל בשורה-שתיים.

### שלב 4.5 — Claude Bridge (טיפול בהערות הראל)
הראל כותב הערות באפליקציה (קטגוריה+עדיפות+טיימקוד) ולוחץ "שלח לקלאוד". Claude:
```
python3 tools/review_cli.py tasks --json          # התור
python3 tools/review_cli.py claim TASK_ID          # (exit 4 = stale — ה-EDL השתנה מאז; לבדוק רלוונטיות, --force במודע)
# מבצעים את התיקון (API /api/save יוצר revision, או עריכה ידנית + new-revision)
python3 tools/review_cli.py resolve TASK_ID --revision REV_ID --summary "..."
```
resolve בלי revision קיים — נדחה. באפליקציה זה מוצג "תוקן — ממתין לבדיקה שלך". אחרי כל תיקון ממשיכים לקרוא גם ל-`POST /api/round/{name}/correct` (תאימות v6).

**v9.18 — סבב תיקונים נסגר באימות, לא בדיווח (חובת קלאוד, L45).** אחרי שכל
המשימות של הסבב נפתרו ורץ גימור (נוצרה גרסה חדשה עם `fixes`):
```
python3 tools/review_cli.py verify-fixes PROJECT --reel     # מדידות + גיליון-מגע פר-תיקון + CHECK_REEL
# → Read על כל fix_verify/<artifact>/sheet_*.jpg — זו הצפייה (חוק הראייה)
python3 tools/review_cli.py fix-verdict PROJECT cmt_XXX verified --evidence "מה נראה בגיליון, בחותמת זמן"
python3 tools/review_cli.py fix-verdict PROJECT cmt_YYY not_fixed --note "..."   # מחזיר לתור אוטומטית
```
- **מדידה ≠ פסיקה**: `machine.status` הוא ראיה; הפסיקה נרשמת רק אחרי קריאת
  הגיליון. `not_found` במכונה + גיליון שמראה שהתיקון כן נכנס ⇒ verified עם
  הסבר. אין דרך לאמת (הערת טעם בלי טיימקוד) ⇒ `needs_eye`, לא ניחוש.
- **not_fixed לפני הראל**: פסיקה כזו מחזירה את ההערה לתור באותה פעולה —
  מתקנים ומריצים גימור נוסף לפני שמדווחים "מוכן לבדיקה". לא מוסרים סבב
  שידוע שנכשל (P14 יעלה את זה כ-high).
- **הדיווח להראל מצטט את האימות**: "תוקנו ואומתו N/M (ראיות באפליקציה),
  נשאר לך לבדוק ~Xש" — לצד פסק-הדין של preflight. באפליקציה הראל רואה
  🤖 פר-תיקון, כפתור "בדוק רק מה שלא אומת", ו-CHECK_REEL.mp4 לצפייה מהירה.

**v7.8 — הערת כתיב לא דורשת סבב קלאוד.** תיקוני `"מילה*"` / `"X* ולא Y"` / `"X במקום Y"`
מוחלים אוטומטית בשלב `notefix` בכל גימור (כולל גימור מהיר). כשקלאוד כן מטפל בהערת
כתוביות — קודם `python3 tools/note_corrections.py --workdir "_work/{שם}"` (בלי `--apply`)
כדי לראות מה כבר טופל אוטומטית ומה נשאר ב-`needs_manual`; לטפל **רק** בעמומים.
שיבוש שחוזר על פני 2+ פרויקטים: `--promote` מקדם אותו למילון הגלובלי, וממילא לא יחזור.

### שלב 4.6 — סנכרון ציר: עריכה בצ'אט ↔ אפליקציה (v7.7, חדש — הראל 25.7)
**שורש:** ל-`edl.json` שתי שכבות — `review.cuts` (מה שהאפליקציה מציירת) ו-`keep_segments`
(מה ש-`edl_cut` חותך בפועל → EXPORT → FINAL). האפליקציה כותבת את שתיהן יחד (`/api/save`
→ `derive_keep`), אבל **עריכה בצ'אט נגעה רק ב-`keep_segments`** — ולכן ה-FINAL היה נכון
בזמן שהאפליקציה הציגה את הגרסה הקודמת (נמדד: 13.2ש ו-31.5ש פער בשני פרויקטים).

**חוק עבודה לקלאוד — אין עריכת EDL בלי סנכרון:**
```
# אחרי כל שינוי ידני ב-edl.json (בצ'אט, בסקריפט, בכל דרך):
python3 tools/review_cli.py sync PROJECT --summary "מה תיקנתי"    # מיישר review.cuts ל-keep_segments + revision
python3 tools/review_cli.py sync-status PROJECT --json            # in_sync / drift / edl_ahead / final_ahead
python3 tools/review_cli.py sync-all --json                       # סריקה+תיקון בכל הפרויקטים
```
`new-revision` כבר עושה sync בעצמו — זו הדרך המועדפת לסיים תיקון בצ'אט.
הכיוון תמיד אחד: **`keep_segments` מנצח** (זה מה שנחתך בפועל), ו-`review.cuts` נבנה
מחדש ממנו (`sync.cuts_from_keeps`, עם אימות round-trip לפני כתיבה — לא נכתב אם לא מאמת).

**שלוש שכבות ההגנה:**
1. `GET /api/project/{שם}` מריץ `reconcile_edl` אוטומטית בפתיחה — הראל לא יכול לערוך מעל ציר ישן.
2. כל גימור מוצלח כותב `FINAL_PROVENANCE.json` — revision, `edl_hash`, `keep_segments`,
   `tight_keeps`, speed ו-stat של FINAL. משם האפליקציה יודעת אם מה שמוצג = מה שנבנה.
3. באנר במסך הסרטון: `in_sync` (ירוק) · `drift` (כתום + "🔗 סנכרן ציר") · `edl_ahead`
   (כחול — הציר חדש מה-FINAL, צריך גימור מחדש) · `final_ahead` (אדום — FINAL הוחלף מחוץ לגימור).
`system_doctor.py` נכשל אם קיים דריפט בכל פרויקט.

**פער מבני מוסבר:** `tighten` מקצץ שקט *אחרי* החיתוך (`tight_keeps.json`, בציר EXPORT) ולכן
FINAL תמיד קצר מהציר. זה לא באג — הבאנר מציג "ציר: Xש → FINAL בפועל ~Yש", והמיפוי לציר
המקור נשמר ב-`sync.tighten_trims_in_source`. אסור לקפל את ההידוק ל-`review.cuts` (זה יגרום
לחיתוך-כפול בגימור הבא).

### שלב 6 — QA, תיוק והעלאה
**ראייה לפני הכל (v9.14):** `python3 tools/vision_check.py --video FINAL.mp4 --workdir "_work/{שם}"` ואז `Read` על כל `contact_*.jpg` שה-VISION.json מונה. בלי זה אין אמירה על התוצר, ו-`P13_vision_bundle` יסמן זאת ב-preflight.
qa_gates כבר רץ בפייפליין; מוודאים `qa_report.json` PASS. תיוק: `resolve_output_path` → DC move → `{מחלקה}/{חודש}/{סרטון}/{שם} - סופי.mp4` (EXPORT נקי נשמר ב-_work). העלאה לבורד: clear_all על file_mm402fp7 → get_asset_upload_url → nohup curl על המק (בדיקה אחת אחרי ~40ש) → finalize. בלי מייל "מוכן לתזמון" (הסטטוס בבורד ובאפליקציה הוא ההודעה — הראל 30.8/3.9/13.9.26). סטטוס → "מוכן לבדיקה"/"מוכן לתזמון!".

### שלב 6.5 — אישור קאבר+קפשן באפליקציה (v7.2, חדש — בקשת הראל 23.7)
**שורש:** קודם היה רק מייל אחד לפני תזמון עם קאבר מוטמע; אין מסך שבו הראל רואה קאבר+קפשן יחד ומתקן לפני שזה "מוכן". זה יוצר סיכון שדבר לא-מדויק יתוזמן. עכשיו זה שער נפרד, באפליקציה:
1. קלאוד כותב טיוטת קפשן לפי **מנוע הקפשן v4** (`docs/CAPTION-ENGINE.md`, v9.48, הראל 10.10.26: "הקפשן תמיד חוזר על מה שנאמר בתסריט"): `python3 tools/caption_gate.py --sources <workdir>` → מפת מה-שכבר-נאמר (הוק, נקודה, CTA) → **מהלך הוספה אחד** ממקור אמיתי (חומר שנחתך, בריף, קאנון, המחשבה של הצופה, היישום, למי לשלוח) → אלמנט StoryBrand אחד מוביל → שורה 1 = הוק שני. **קודם טוענים `rel-cta-psychology` ורק אז כותבים** (קבוע, הראל 17.8.26) — הוא קובע את מבנה ה-CTA; הקול לפי `rel-reel-caption-generator` v4. לא מסכמים את התסריט ולא ממציאים. ומוודא ש-`thumbnail.png` קיים (נוצר בשלב 5 אם היה `--title`; אם אין — `tools/thumbnail/frame_select.py`+`thumbnail_build.py` ידנית).
2. `POST /api/schedule-review/{שם} {"action":"set_draft","cover_path":"thumbnail.png","caption_draft":"...","caption_type":"ערך|המרה|קהילה|עדות","caption_meta":{"move":"…","sb7":"…","persona":"…"}}` — **השרת מריץ את `caption_gate` (v9.48, L132)**: קאנון + "משלים, לא משכפל" מול `words_final`. `CAPTION-GATE FAIL` (400) = כותבים מחדש, לא עוקפים. אחרי מעבר — הפרויקט עובר למצב **"ממתין לאישור קאבר+קפשן"** באפליקציה (לשונית ריצות → פאנל "🖼 אישור קאבר וקפשן").
3. Update ל-Monday: "קאבר+קפשן מוכנים לאישורך באפליקציה" (בלי מייל נפרד — האפליקציה כבר פתוחה על השולחן).
4. הראל: מאשר (עורך את הקפשן בטקסטריה אם רוצה → "✔ אשר קאבר וקפשן") **או** מבקש שינוי ("✏️ בקש שינוי" → נכנס לתור קלאוד כהערה בקטגוריית `cover`/`captions`, בדיוק כמו הערות עריכה — Claude Bridge רגיל, `review_cli.py tasks`).
5. אישור **נועל `artifact_id`** (v9.4) — `registry.set_schedule_approval` יוצר/מאתר artifact קבוע מ-FINAL.mp4 הנוכחי ורושם `schedule_approval.artifact_id`/`artifact_checksum`/`artifact_path` (בנוסף ל-`caption_approved`) **ברגע האישור**. מצב הפרויקט הופך ל-**"מוכן לתזמון!"**. התזמון חייב לקחת את הקובץ מ-`schedule_approval.artifact_path` ולוודא `artifact_checksum` מול הקובץ בפועל — לא מנתיב `FINAL.mp4` הכללי, שעלול להיכתב מחדש בריצה חדשה. כל שינוי מאוחר יותר (הערה חדשה שנפתרה, gate שנכשל ותוקן) יוצר artifact **מועמד** חדש ואינו מבטל את הגרסה המאושרת — `derive_state` בודק `artifacts.verify()` מול ה-artifact הנעול, לא `stat()` חי על FINAL.mp4.
"תרוץ על כל מה שמוכן באפליקציה" (שלב 7) = לסרוק `review_cli.py projects --json`, לסנן `state == "ready_to_schedule"` בלבד (`scheduled`/`published` = כבר תוזמן — לעולם לא נאספים; v9.33).

### שלב 7 — תזמון Metricool (v3.2 גרעין + v7.2 שער checksum, נועל artifact_id מ-v9.4, אימות בקריאה חוזרת מ-v9.31)
זהה ל-v5 בבסיס: מותג לפי מחלקה (Throwdown→6436350), ריל→IG+FB+YT+TikTok בפוסט אחד; בדיקת אופק ~חודש; קופי מאומת מול התמליל, CTA לפי רשת. **v7.2 — לפני כל `createScheduledPost` חובה:**
1. לוודא `state == "ready_to_schedule"` (לא "final"/"awaiting_schedule_approval" — ראה חוק ברזל 15) **וכי `artifacts.verify(workdir, schedule_approval.artifact_id).ok == True`**. אם לא — לעצור, לא לתזמן, `[STALE-FINAL]`.
2. להשתמש **רק** ב-`schedule_approval.artifact_path` (הקובץ, המדיה נלקחת ממנו), `artifact_checksum` (לאימות סופי מול `sha256` על הקובץ בפועל רגע לפני ההעלאה), `caption_approved` (הקפשן) ו-`cover_path` (הקאבר) — לא לגזור אף אחד מהם מחדש ממקור אחר ולא מנתיב `FINAL.mp4` הכללי.
3. `createScheduledPost` (titles×3: youtube+tiktok+facebook, firstComment, providers בקריאה אחת) — **כולל `videoThumbnailUrl` = ה-public_url של `cover_path` שהועלה ל-Monday (חוק ברזל 18).** הקאבר כבר לא ידני. ידני בקומפוזר נשאר רק: CTA-ביו ל-IG, מיקום, תיוג משתתפים.
4. **אימות בקריאה חוזרת מיד אחרי הצלחה** (חוק ברזל 16): `getScheduledPosts` → הפוסט קיים עם מועד, רשתות, הקפשן המדויק ו-`videoThumbnailUrl` ב-`static.metricool.com` — **לפני** עדכון "תוזמן!" ב-Monday. לא תואם → `[SCHEDULE VERIFY FAILED]`, לא מסמנים "תוזמן!"; מייל להראל רק אם התיקון דורש אותו (`rel-email-design`). הדיווח (נתיב+checksum, קאבר, מועד+רשתות) — בצ'אט.
5. Update `[SCHEDULED-METRICOOL]` + "קפשן סופי:" HTML + סטטוס "תוזמן!" + **חובה** `state_override:"scheduled"` באפליקציה (`POST /api/meta/{שם}` — "📅 תוזמן — ממתין לפרסום") — רק אחרי שהאימות בסעיף 4 עבר. זה מה שמוציא את הפרויקט מתור "מוכן לתזמון" (`registry.SCHEDULE_CLOSED_STATES`; לקח 23.8.26: 12 פרויקטים שתוזמנו נשארו ב-ready_to_schedule ⇒ סכנת תזמון כפול). **לא** `published` (v9.33, L97; הראל 24.7.26: "הושלם באפליקציה זה לא פורסם בפועל אלא תוזמן"). `published` ("🚀 הושלם — פורסם בפועל") רק ידנית ע"י הראל, או כש-`getScheduledPosts` מראה `providers[].status=PUBLISHED` לכל הרשתות.

### QA לפני יציאה (תמצית)
```
[עריכה]  Hook נפתח ✓ · אפס דד-אייר (נמדד) ✓ · טייק אחרון ✓ · אורך ביעד הסוג (length_policy) / נימוק מעליו ✓
[גימור]  כתוביות PASS≥90 ✓ · מוזיקה -46+דאקינג מלוא האורך ✓ · בירול עם fade 0.12 ✓
         · קאבר מ-EXPORT נקי, band 0.725 ✓ · -14 LUFS / TP יעד -1.0 (סף קשיח -0.8) ✓ · 1080×1920 30fps ≤60MB ✓ · תויק + EXPORT נשמר ✓
[ראייה]  VISION.json נוצר ✓ · bundle טרי מה-FINAL ✓ · כל contact_*.jpg נקראו ✓
         · V1-V6 מדווחים עם מספר ✓ · V7 כתוביות נקראו בעין ✓ · כל הערה בחותמת זמן ✓
[הוק]    HOOK_PLAN.json (טכניקה מהארגז, עוגן ב-0ש) ✓ · HOOK_SHEET.jpg נקרא ✓ · stamp על ה-FINAL ✓ · P22 בלי high ✓ · עמודת "טכניקת הוק" בבורד ✓
[תסריט] ⟦EDIT-LAYER⟧ נקרא ✓ · טבלת פער נבנתה ✓ · ⟦EDITPLAN v{n}⟧ נכתב (edit_update) ✓
         · קצב: ≤2 קפיצות/5ש ✓ · 4-6 שינויים/10ש (או פער מדווח) ✓ · בדיקה מושתקת ✓
         · ⬛COVER⬛ מהתסריט, מותג נכון, נקרא ב-236px ✓
[למידה]  corrections נאספו ✓ · learn_from_edits רץ ✓ · לקח דווח ✓
[קאבר+קפשן] טיוטה נכתבה ✓ · הראל אישר באפליקציה ✓ · artifact_id ננעל ✓
[תזמון]  state==ready_to_schedule ✓ · artifacts.verify(artifact_id).ok ✓ · מותג/רשתות/מועד ✓ · titles×3 ✓ · firstComment ✓ · videoThumbnailUrl נשלח ואומת ✓ · API→ידני ✓ · קפשן סופי ✓ · getScheduledPosts אומת ✓ · Monday+אפליקציה (`scheduled`, לא published) עודכנו ✓
```

---
