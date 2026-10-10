> ⛔ **SUPERSEDED — 22.8.2026.** ארכיון היסטורי. הגרסה החיה: `skills/rel-social-video-editor/SKILL.md` (v9.21). "התסריט הרופף = מצפן" **בוטל** — מ-22.8.2026 התסריט הוא קלט רשמי דרך `⟦EDIT-LAYER⟧` בבעלות `rel-script-writer`. אין לפעול לפי הקובץ הזה.

---
name: rel-social-video-editor
description: **Social Video Editor — CrossFit R.E.L (v5)**: מערכת עריכת סרטוני סושיאל היברידית — עריכה דטרמיניסטית מקומית (Whisper+EDL+ffmpeg) לפני Descript, Descript ככלי כירורגי ורוויו בלבד, גימור מקומי מלא (כתוביות/מוזיקה/קאבר), ותזמון Metricool. מנהלת את כל ה-workflow מהזיהוי ב-Monday ועד "תוזמן!". TRIGGERS — "ערוך סרטון", "עריכת סושיאל", "סרוק בורד סושיאל", "סרטון מוכן לעריכה", "Descript edit", "social video edit", "ready to edit", "תרוץ על הסרטונים", "תייצר edit plan", "תפעיל את מערכת העריכה", "פרסם סרטון", "אשר עריכת סרטון", "תזמן ב-Metricool", "מוכן לתזמון", "schedule post". מופעל אוטומטית מ-scan-social-board-ready-to-edit וידנית.
project: Social Video Editing System
version: v5.0
updated: 2026-07-16
---

# rel-social-video-editor v5 — מקומי-קודם, Descript כירורגי

## תפיסת העל (מה השתנה ב-v5)

**הבעיה שנפתרה:** ה-agent של Descript קיבל פרומפט ענק ("ערוך לפי התסריט") וקיבל החלטות עריכה בעצמו — חיתוכי יתר, פספוסים, פערי שקט, תלות בתסריט מדויק. מ-v5 **ההחלטות עוברות אלינו, מקומית ודטרמיניסטית**:

1. **תמליל = מקור אמת. תסריט רופף = מצפן. הקאנון = חוקי העריכה.** משפט טוב שנאמר ולא היה בתסריט — נשאר. לא מסננים תוכן כי "לא בתסריט".
2. **עריכה מקומית לפני Descript:** Whisper (זמן אמיתי לכל מילה) → `edl_build.py` (שקטים, כפילויות-טייקים, התחלות כושלות, מילות מילוי, פקודות בימוי) → `edl_cut.py` → **ROUGH.mp4** נקי-שקטים, ~90% ערוך.
3. **Descript = כירורגי בלבד:** מקבל רשימת פעולות ממוספרת עם טיימסטמפים (מה שנשאר להחלטה) — או **כלום** (מסלול אפס-קרדיט). והוא ה-UI שבו הראל בודק ומתקן.
4. **בירולים = קטלוג דטרמיניסטי:** `broll_catalog.py` + `broll_pick.py` בוחרים לפי תגים/קהל/rotation, והשילוב הוא overlay מקומי (ffmpeg) על האקספורט הנקי — לא דרך ה-agent.
5. **QA מאוחד:** `qa_gates.py` — ריצה אחת, כל השערים, על המדיה עצמה. "מוגדר ≠ עובד".

שערי האישור של הראל נשארים בדיוק כמו היום: `[APPROVE-PUBLISH]` על הטיוטה, ומייל אישור מרוכז לפני כל תזמון.

---

## קונסטנטות מערכת

```
MONDAY_BOARD_ID        = 18395578529
STATUS_COLUMN_ID       = color_mkrp4sgm           # "סטטוס | הפקה"
LABEL_READY_TO_EDIT    = "מוכן לעריכה"             # index 11
LABEL_IN_EDIT          = "לאחר צילום, בעריכה"      # נקבע מיד אחרי import מוצלח (מניעת עיבוד כפול)
LABEL_READY_TO_REVIEW  = "מוכן לבדיקה"             # index 12
DEPT_COLUMN_ID         = color_mkzks1yg            # מחלקה / קהל יעד
CONTENT_TYPE_COLUMN_ID = color_mm09wp6b            # סוג תוכן
FORMAT_COLUMN_ID       = color_mkrpg05d            # פורמט (ריל/קרוסלה/...)
HOOK_COL / MSG_COL / CTA_COL = long_text_mkzk9556 / long_text_mkzkwwgk / long_text_mkzkwys7
PARTICIPANTS_COL       = long_text_mkzkx9am
EMAIL_TO               = harel@crossfitrel.com
AUTO_EDIT_DRAFT_TAG    = [AUTO-EDIT v2 DRAFT]
AUTO_EDIT_TAG          = [AUTO-EDIT v2]
APPROVAL_TRIGGER_TAG   = [APPROVE-PUBLISH]
BATCH_LIMIT            = 3
BRAND_RED              = #871d1f
PROJECT_FOLDER         = /Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System
CONTENT_ROOT           = /Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי
WORK_ROOT              = {PROJECT_FOLDER}/_work
ROUTING_CONFIG         = tools/folder-routing.json      # מחלקה→תיקייה (מקור אמת, לא לשכפל)
RESOLVER               = tools/resolve_output_path.py
MATCHER                = tools/match_intake.py
DESCRIPT_PUT           = tools/descript_put.sh
EDL_BUILD / EDL_CUT    = tools/edl_build.py / tools/edl_cut.py       # v5
EDL_POLICY             = tools/edl-policy.json                        # ספי שקט/טייקים — מקור אמת
BROLL_CATALOG          = tools/broll_catalog.py + CONTENT_ROOT/בירולים/catalog.json
BROLL_PICK             = tools/broll_pick.py
QA_GATES               = tools/qa_gates.py
WHISPER                = tools/align_words.py  (רץ על המק: /Users/hayon/.rel-whisper/bin/python)
CAPTIONS               = tools/captions_build.py (צריבה בסנדבוקס — libass; מילה אחת; בלי . , …)
MUSIC_MIX              = tools/audio_mix.py mix --music-lufs -38 (קבוע; בלי ducking; אורך מלא)
MUSIC_LIB              = descript-brand-assets/music/  (ראה MUSIC-LIBRARY.md; rotation בין סרטונים)
THUMBNAIL              = tools/thumbnail/ (frame_select + thumbnail_build; band-center 0.725 נעול)

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
```

**Descript Business:** 1,500 credits/חודש. עובדים נקי: המסלול הרגיל ב-v5 צורך **0-1 קריאות agent** לסרטון (לרוב 0). Brand Kit קיים (Assistant, ‎#871D1F, glossary לטיני). Underlord: Sonnet לפרומפט כירורגי. Eye Contact / Studio Sound — **אסור להפעיל**.

---

## חוקי ברזל (קאנון — אין לעבור)

1. **Hook קדוש.** לא מסירים קליפ פתיחה/בלוק ראשון; מילות מילוי בפתיחה מוסרות ידנית-נקודתית בלבד; Hook מאוחר מועבר לתחילה — לא נחתך. בחלון 6ש הראשונות `edl_build` חותך רק שקט-הובלה ופקודות בימוי.
2. **אנטי חיתוך-יתר.** שאלות רטוריות, הסבר טכני, מחקרים = תוכן. יעד 55-60ש; מוכן לחרוג מעט; לא יורדים משמעותית מתחת בלי צורך.
3. **אפס דד-אייר, פאוזות מכוונות נשמרות.** נמדד על המדיה (`qa_gates` G2), לא בפרומפט. beat אחרי punch / לפני CTA = תוכן.
4. **כתוביות: מקומי בלבד** (Descript לא תומך RTL). מילה אחת (2 רק ל≤2 אותיות/<0.2ש), בלי `.` `,` `…` לעולם (`?` `!` נשארים), Assistant ExtraBold + מתאר ‎#871d1f, סטטיות, de-collide לתזמונים זהים, עטיפת RTL לסימני שאלה/קריאה. תזמון = forced alignment אמיתי + `captions_qa` PASS ≥90%.
5. **בלי טקסטים גרפיים, בלי לוגו, בלי פתיח/סיום** (חריג: פתיח מאסל-מן). רק כתוביות דיבור.
6. **B-roll רק ב-conversion** (חריג: Throwdown גם בערך — התאמת-הקשר). תמיד mute. מתחיל אחרי המשפט הראשון (או 5-10ש), לא מכסה Hook ולא CTA. דוספיט → בירולי דוספיט בלבד. מקור: הקטלוג בלבד.
7. **מוזיקה: מצע מקומי תמיד** — `audio_mix.py --music-lufs -38`, בלי ducking, אורך מלא (QA אודיו=וידאו). טראק royalty-free מ-MUSIC_LIB ב-rotation; תוכן רגוע → טראק רגוע; מכירה אמיתית → מותר ‎-32 מעט בולט. אסור שיר מסחרי. אם הראל אומר "אין מוזיקה" על סרטון — מעלים לאותו סרטון ל-‎-32 (מסקינג), לא משנים גלובלית.
8. **1080×1920 תמיד** (סושיאל; פודקאסט = 4K, סקיל נפרד). דחיסה crf23 לפני כל העלאה. **אסור ultrafast** (מנפח פי 2) — veryfast/medium.
9. **אסור לגעת בצבע** ב-99% מהמקרים. בלי tonemap/grade אלא אם HDR/HLG בקלט (בדוק `color_transfer`; arib-std-b67/bt2020 → zscale+tonemap=hable→bt709 לפני הכל) או שהראל ביקש.
10. **אסור לגעת באיכות/מדיה של פוסט מתוזמן.** שינוי פוסט קיים = רק ה-URL המקורי מ-static.metricool. עדכון API מוחק geotag/תיוג — כל עדכוני API קודם, ידני בקומפוזר אחרון.
11. **ראיות לפני "בוצע".** כל שלב מסתיים בפלט/מדידה. הסוכן של Descript נבדק לפני ואחרי (silencedetect + השוואת משך + transcript).
12. **קובץ סופי יחיד**, מתויק ל-`{מחלקה}/{חודש}/{סרטון}/` (resolve_output_path + Desktop Commander). ביניים ב-`_work/{שם}/` בלבד. תמיד לשמור `EXPORT.mp4` נקי (טרום-כתוביות, טרום-בירול).

---

## Workflow

### שלב 0 — Pre-flight (Monday)
כמו תמיד: `get_board_items_page` על 18395578529 עם filter סטטוס index 11, `includeColumns` על כל העמודות למעלה. לכל פריט `get_updates(limit:5)` — אם יש `[AUTO-EDIT` → דלג. עד BATCH_LIMIT פריטים.

### שלב 0.5 — שיוך גלם מקומי
`python3 tools/match_intake.py --items items.json --pretty` → matched / needs_review / missing / orphans. רק `matched` ממשיך. דו-משמעי → שואלים את הראל, לא מנחשים. חסר → Update `[INTAKE MISSING]`.

### שלב 1 — Validation גמישה (v5)
- **תסריט רופף מספיק.** Update כלשהו עם כיוון ("ריל על עקביות למתחילים") = תקף.
- **אין תסריט בכלל → לא נכשלים.** מצב הסקה: ה-INTENT CARD ייבנה מהתמליל בלבד, וה-Update יסומן `[INFERRED-INTENT]` כדי שהראל יתקן בבדיקה.
- חובה עדיין: גלם matched + מחלקה. סוג תוכן חסר → "לא סווג" → מטופל כ-value (בלי בירול, מצע מוזיקה רגוע).

### שלב 2 — הכנה מקומית (המק, Desktop Commander) — לב v5
לכל פריט, בתוך `_work/{שם}/`:
```
a. דחיסה:   ffmpeg -y -i {raw} -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
             -c:a aac -b:a 128k -ar 48000 -ac 2 -movflags +faststart {name}_1080.mp4   (לכל קובץ גלם)
   (HDR/HLG? בדוק ffprobe color_transfer קודם — חוק ברזל 9.)
b. איחוד:   כמה קבצי דיבור → concat demuxer -c copy (אותם פרמטרים אחרי הדחיסה) → INPUT.mp4
c. תמלול:   /Users/hayon/.rel-whisper/bin/python tools/align_words.py INPUT.mp4 whisper_raw.json small he
d. EDL:     python3 tools/edl_build.py --words whisper_raw.json --out-dir _work/{שם}/ \
             --video INPUT.mp4 [--loose-script script.txt] --end {dur}
             → edl.json · sentences.json · intent_card.md · descript_instructions.md
e. חיתוך:   python3 tools/edl_cut.py --video INPUT.mp4 --edl edl.json --out ROUGH.mp4
f. אימות:   ffmpeg silencedetect על ROUGH — חייב נקי; משך בטווח היעד.
```
`edl_build` חותך אוטומטית רק חיתוכי **high-confidence** (שקטים, טייק-כפול מובהק, פקודות בימוי, פילרים מבודדים מחוץ לחלון ההוק). כל ספק → `descript_instructions.md` להחלטה בשלב 5. הספים ב-`tools/edl-policy.json` — לשנות שם, לא בקוד.

### שלב 3 — INTENT CARD (אפס credit)
קרא את `intent_card.md` (Hook/CTA/קו סיפור שנאמרו בפועל + התסריט הרופף כמצפן). אם `[INFERRED-INTENT]` — צרף אותו ל-Update הטיוטה. בדיקת שפיות: ההוק הוא באמת ההתחלה? ה-CTA הגיוני? אם ההוק האמיתי באמצע — רשום הוראת "העבר לפתיחה" להוראות הכירורגיות.

### שלב 4 — Descript: import של ROUGH בלבד
1. re-use פרויקט קיים אם יש (regex על Updates: `descript.com/project/UUID`).
2. `import_media` DIRECT FILE UPLOAD — **קובץ אחד: ROUGH.mp4** (media בלבד, ≤3 לקריאה; composition בקריאה נפרדת — לקח batches). PUT דרך `descript_put.sh` על המק.
3. `add_compositions`: "Edit v1", 1080×1920, fps 30, clips=[ROUGH], language he, team_access edit. שם פרויקט `[REL] {item.name} | {item.id}`.
4. מיד אחרי import מוצלח: סטטוס → "לאחר צילום, בעריכה".

### שלב 5 — Agent כירורגי (0-1 קריאות)
- אם `descript_instructions.md` אומר "אין החלטות פתוחות" **ואין** צורך בהעברת Hook → **דלג. אפס קרדיט.** Descript הוא רק רוויו.
- אחרת, קריאה אחת עם פרומפט קצר:
```
בצע אך ורק את הפעולות הממוספרות הבאות על הקומפוזיציה, לפי טיימקודים. אל תבצע שום עריכה אחרת.
{תוכן descript_instructions.md — סעיפים שהוחלט לבצע}
איסורים מוחלטים: אל תוסיף captions/subtitles/pop-text; אל תוסיף מוזיקה או SFX; אל תוסיף B-roll;
אל תשנה צבע; אל תפעיל Studio Sound או Eye Contact; אל תיצור קומפוזיציה חדשה; אל תיגע בקטעים שלא צוינו.
```
- **אימות אחרי agent (חובה):** `export_transcript` + השוואת משך לפני/אחרי מול הצפוי + silencedetect על export ביניים אם בוצעו חיתוכים. סטייה לא מוסברת → Update `[AGENT VERIFY FAILED]` + עצירה לפריט.
- refinement: מקסימום 1. כישלון שני → ידני.

### שלב 5.5 — Draft Checkpoint (ללא שינוי)
Update `[AUTO-EDIT v2 DRAFT]`: לינק Descript, משך, סוג/מחלקה, ה-INTENT CARD בקצרה, ורשימת ההחלטות שבוצעו. בלי publish, בלי מייל. ממתינים ל-`[APPROVE-PUBLISH]` של הראל.

### שלב 5.7 — זיהוי אישור (בריצה הבאה)
פריט עם DRAFT tag + Update חדש `[APPROVE-PUBLISH]` → המשך לשלב 6. **חובה קודם:** `export_transcript` והשוואה לגרסת טרום-אישור — אם הראל תיקן ידנית, לתעד את הלקח (process_diff_harel_edits) ב-Update קצר + ביומן הלקחים.

### שלב 6 — ייצוא
`publish_project` (= מנגנון הייצוא, 1080p, מחזיר download_url חתום 24ש; **זה לא פרסום לרשת**) → הורדה ל-`_work/{שם}/EXPORT.mp4`. לשמור את EXPORT הנקי תמיד (קאבר + בירול-רטרו תלויים בו).

### שלב 7 — גימור מקומי (הסדר מחייב)
```
1. GATE שקט:   python3 tools/finish_local.py gate --words words.json --video EXPORT.mp4
                (words: align_words על EXPORT + align_reconcile עם תמליל Descript)
                נכשל (exit 3) → refinement אחד ב-Descript עם הטיימקודים → ייצוא מחדש → gate שוב.
2. B-roll:      [conversion בלבד] python3 tools/broll_pick.py --topic "{נושא}" --content-type conversion \
                  --audience "{קהל}" --dept "{מחלקה}" --sentences sentences.json --video-dur {dur} \
                  --json broll_plan.json --commit
                → python3 tools/animation_overlay.py --base EXPORT.mp4 --out EXPORT+BROLL.mp4 {overlay_args מהתוכנית}
                (overlay מושתק, בסיס-הדיבור נשמר; EXPORT הנקי לא נמחק!)
3. מוזיקה:      python3 tools/audio_mix.py mix --video {EXPORT|EXPORT+BROLL}.mp4 --music {טראק} --out MIXED.mp4
                (-38 קבוע; rotation; רגוע לתוכן רגוע. QA מובנה אודיו=וידאו.)
4. קאבר:        tools/thumbnail/frame_select.py על EXPORT הנקי (לעולם לא מהסופי עם כתוביות; אין נקי? cover_inpaint)
                → thumbnail_build.py --band-center 0.725 (נעול!) → thumbnail.png ביחס הסרטון (9:16, ריבועי→1080×1080)
5. כתוביות:     align_words על MIXED (או remap) → align_reconcile → de-collide → captions_qa (PASS≥90%)
                → צריבה בסנדבוקס: captions_build.py burn (מילה אחת, סטטי, בלי נקודות/פסיקים) → FINAL.mp4
6. QA מאוחד:    python3 tools/qa_gates.py --video FINAL.mp4 --words words.json --truth whisper_export.json
                חייב PASS. נכשל → מתקנים, לא ממשיכים.
7. תיוק:        resolve_output_path → DC list/create/move → {מחלקה}/{חודש}/{סרטון}/{שם} - סופי.mp4
8. העלאה לבורד: clear_all על file_mm402fp7 → get_asset_upload_url → nohup curl על המק (בדיקה אחת אחרי ~40ש,
                בלי ניטור תכוף!) → finalize. מייל "מוכן לתזמון" קצר להראל. סטטוס → "מוכן לבדיקה" (או ישר
                "מוכן לתזמון!" אם הראל הגדיר מראש).
```

### שלב 8 — תזמון Metricool (v3.2 — נשמר במלואו, עם ההקשחות)
טריגר: סטטוס "מוכן לתזמון!" / "מוכן לתזמון בDraft" + קובץ ב"סרטון מוכן" + אין `[SCHEDULED-METRICOOL]`.
1. **מותג:** Throwdown→6436350 (IG+FB), אחרת→6323702. **רשתות:** ריל→IG+FB+YT Short+TikTok **בפוסט אחד, אותו מועד**; קרוסלה/סטורי/תמונה/לייב→IG בלבד. שבת → מזיזים ליום חול.
2. **תאריך:** `date_mkrpvw3n`; **בדיקת אופק ~חודש** — תאריך רחוק מחודש קדימה → לעצור ולאשר מול הראל; בעבר → דגל. שעה: מפורשת אם יש, אחרת `getBestTimeToPostByNetwork`.
3. **קופי:** Update קיים של קפשן ("🤖 נכתב ע״י Claude") אחרי אימות מול `export_transcript` — בלי הטבות שלא נאמרו, עברית (עוריות≠straps), דיפלומטי מול מתחרים. אין קופי → rel-reel-caption-generator (קול חם ואנרגטי). **CTA לפי רשת:** טקסט הבסיס נושא קישור (rel.fit/sign-up-form או Rebrandly ייעודי) ל-FB/TikTok/YT; אינסטגרם → "פרטים בביו 👆" בהתאמה ידנית בקומפוזר.
4. **Gate מייל (חובה, בלי יוצא מן הכלל):** מייל מרוכז אחד — לכל פריט: שם, מותג, רשתות, מועד, הקופי המלא, firstComment, **הקאבר מוטמע בגוף המייל**, לינק Monday, דגלים. תזמון רק אחרי `[APPROVE-SCHEDULE]`/תשובה.
5. **createScheduledPost:** media=[public_url מ-get_assets — לא protected_static], providers כולם בקריאה אחת, autoPublish/draft לפי הסטטוס, `instagramData:{type:REEL}`, **titles חובה לשלושתם: youtubeData.title ✓ tiktokData.title ✓ facebookData.title ✓** (הוק/כותרת), firstCommentText חובה, publicationDate עם Asia/Jerusalem. רוחב ≤1920px.
6. **סדר קשיח:** כל עדכוני ה-API קודם → פעולות קומפוזר ידניות אחרונות (קאבר "Upload video thumbnail", מיקום קבוע, תיוג משתתפים מ-long_text_mkzkx9am, התאמת CTA-ביו ל-IG). עדכון API אחרי-ידני מוחק אותן. קאבר = ידני בלבד (אין API, אין דפדפן — native picker). **אימות ויזואלי** אחרי שמירה בקומפוזר — Vuetify מדווח הצלחה בלי להישמר.
7. **סגירה:** Update `[SCHEDULED-METRICOOL]` + **Update "קפשן סופי:" בפורמט HTML עם הקפשן שעלה בפועל** + סטטוס "תוזמן!" — לפני שמדווחים להראל.

### QA לפני יציאה (תמצית — המדידות ב-qa_gates.py)
```
[עריכה]  Hook נפתח ✓ · אפס דד-אייר (נמדד) ✓ · טייק אחרון בכפילויות ✓ · 50-65ש ✓ · בלי כתוביות/מוזיקה/טקסט-גרפי ב-Descript ✓
[גימור]  כתוביות מסונכרנות PASS≥90 ✓ · מוזיקה -38 מלוא האורך ✓ · בירול conversion-בלבד, mute, לא על Hook/CTA ✓
         · קאבר מ-EXPORT נקי, band 0.725 ✓ · -14 LUFS / TP≤-1 ✓ · 1080×1920 ≤60MB ✓ · תויק נכון + EXPORT נשמר ✓
[תזמון]  מותג/רשתות/מועד ✓ · titles×3 ✓ · firstComment ✓ · מייל+אישור ✓ · API→ידני בסדר הנכון ✓ · קפשן סופי תועד ✓
```

---

## טיפול בכשלים
| כשל | פעולה |
|---|---|
| אין גלם matched | `[INTAKE MISSING]` + דלג |
| whisper נכשל על המק | נסה model=base; נכשל שוב → `transcript_to_words.py` כ-fallback מסומן + דגל "תזמון כתוביות מוערך" |
| edl_cut נכשל | fallback legacy: העלה INPUT.mp4 המקומפרס + פרומפט agent מלא בסגנון v3.2 + הקשחות. Update `[EDL FALLBACK]` |
| import/PUT נכשל | retry (URL תקף דקות) או `--bg`; ואז `[IMPORT FAILED]` |
| agent נכשל / אימות נכשל | `[AGENT FAILED]`/`[AGENT VERIFY FAILED]` + המשך לפריט הבא |
| gate שקט נכשל פעמיים | עצירה + דיווח טיימקודים להראל |
| מייל נכשל | `[EMAIL FAILED]`, לא מעדכנים Monday עד שמייל יוצא |
| credit exhausted | `[CREDIT EXHAUSTED]` + עצירת batch (המסלול הרגיל בקושי צורך קרדיטים) |
| Metricool נכשל | `[SCHEDULE FAILED] {error}`, בלי עדכון סטטוס, בלי כפילות |

## ערוץ ידני
"ערוך את הסרטון של X" → פריט בודד מלא · "תרוץ על מה שמוכן" → batch≤3 · "dry run על X" → שלבים 0-3 בלבד (אפס Descript) והחזרת edl+intent כ-Update · "תזמן את X" → שלב 8 בלבד.

## גרסה
v5.0 — 16.7.2026. ארכיטקטורה היברידית מקומי-קודם (אושרה ע"י הראל 16.7). היסטוריה מלאה: `SKILL-v3.2-archive.md`.
כלים חדשים: edl_build, edl_cut, broll_catalog, broll_pick, qa_gates + edl-policy.json + broll-catalog-config.json.
Runbook: `tools/PIPELINE.md` (v5). נוהל Notion: 3627c0039aed81bba1bcce23661e2044 (לעדכן בפרסום הבא).
