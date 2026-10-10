# שדרוג Opus 5.5 — תוכנית גלים לשערי ראייה מדודים
> נכתב 22.9.26 בסוף גל 1; **עודכן 23.9.26 — גלים 1-6 בוצעו (v9.29 · v9.30 · v9.32 · v9.34)**. הסקיל v9.30 נשמר בחשבון (claude.ai → Customize → Skills, `skill_01UrJzW9bkQp48JBftssUv5A`, v2). לפני כל גל: לקרוא את הקבצים מחדש מהדיסק (צ'אטים מקבילים), להריץ `unittest` + `gate_registry --audit` + `lesson_registry --audit` + `system_doctor` כ-baseline.

## דירוג ICE (שלב 0, מצב חי 22.9.26)

| # | הזדמנות | I | C | E | ICE | מצב בכניסה | גל |
|---|---|---|---|---|---|---|---|
| 1 | V7 כתוביות על פריימים מ-FINAL | 9 | 8 | 7 | **8.0** | `manual` לנצח; אף שער לא הסתכל על מה שנצרב | ✅ גל 1 |
| 2 | ראיית הקאבר המרונדר | 8 | 8 | 8 | **8.0** | G-COVER1..3 בודקים קלט בלבד | ✅ גל 1 |
| 4 | V3/V4 סף מדוד | 5 | 9 | 9 | **7.7** | **no_data תמיד** — אף bundle מאושר לא הכיל תמליל | ✅ גל 1 |
| 5 | canon לקחים אחד | 7 | 6 | 4 | 5.7 | ~130 קבצי feedback בזיכרון הפרויקט; 76 לקחים ברשומה | ✅ גל 3 |
| 3 | בירול↔משפט בראייה | 8 | 4 | 3 | 5.0 | `broll_vision_model` מתייג people/crowding; אין בדיקה פר-משפט על ה-FINAL | ✅ גל 2 |

## גל 1 — בוצע (v9.29) · ראיות

| שיפור | הרצה אמיתית | ראיה |
|---|---|---|
| `tools/caption_vision.py` (V7, שלב 9c2b) | כיול 1,225 cues מ-16 המאושרים + 7 סוגי הזרקה · סריקה חיה של 40 FINAL | `tools/caption-vision-calibration.json` · `_opus55_wave1/sweep_caption_vision.json` · גיליונות `_opus55_wave1/sw_*.jpg` |
| `tools/thumbnail/cover_vision.py` (G-COVER5) | 36 קאברי cover_make + 13 ישנים · 34 הזרקות לכל כשל · cover_make אמיתי על EXPORT של איגור + שחזור תקלת 24.7 | `tools/thumbnail/cover-vision-calibration.json` · `_opus55_wave1/inject_cover_double_reversal.png` (נחסם) · `real_cover_make_ok.png` (עבר) |
| V3/V4 מציר הכתוביות | `vision_check --measure-words` על 16 המאושרים | `tools/vision_reference.json` (`promote:false` + `why_not_blocking`) |

**מה המדידה הפילה בדרך (ולכן לא נכנס כחוסם):**
- `garbled` בכתוביות: נקי בכיול (0/1,225), אבל 5 cues תקינים סומנו ב"דרג-לי-את-הפודיום" (רקע אירוע עמוס) — נבדק בעין ⇒ מדווח.
- `reversed` בודד: היחיד שנמצא בסריקה ("ההבנה-האנטומית-סוגי-קרעים" 39.25ש) היה מילה אחרת על המסך, לא היפוך ⇒ חוסם רק מ-≥3 cues וגם ≥20%.
- `garbled` בקאבר (סדר אותיות בתוך שורה, Studentit): תופס 50% ⇒ מדווח.
- `direction="ltr"` ב-raqm אינו משחזר את ההיפוך הכפול — הייחוס הוא מחרוזת הפוכה.

**ממצאים אמיתיים שהכלים מצאו (לא תוקנו — סרטונים שכבר פורסמו):**
- `טיפ-אחד-HSPU` נצרב מ-`words_final3.json`; `words_final.json` בתיקייה לא תואם ל-FINAL.
- `מאסל-מן-רוטטור-קאף` — פתיח 10.1ש לא רשום ב-FINAL_PROVENANCE (נאמד מהפיקסלים).
- `קניות-v2` — פונט כתוביות ישן (לפני 24.8.26) + מתאר כחול על מניפסט `rel`; היה נחסם היום (missing ×6).
- `הלקח-הכי-חשוב-במכירות`, `יום-בחיים-של-הראל` — מניפסט `rel`, כתוביות במתאר כחול (אישי).
- `thumbnail_build.build(sub_ratio=…)` התעלם מהפרמטר — **תוקן**.

## גלים 2-4 — בוצעו (v9.30) · ראיות

**מצב מערכת בסוף:** unittest **777 OK** · `gate_registry --audit` **181 שערים · 0 כשלים** · `lesson_registry --audit` **99 לקחים · 274 אוכפים** · `lessons_canon.py --audit` **133 feedback ממופים · 0 בעיות** · doctor 44 PASS / 1 FAIL (קיים מקודם) / 2 WARN.

| גל | שיפור | הרצה אמיתית | ראיה |
|---|---|---|---|
| 2 | `tools/broll_vision_qa.py` (שלב 9c2c, P21): B1 נחת (דמיון פריים FINAL↔קליפ, 8 דגימות) · B3 זהות הראל↔מועדון מתוויות מאומתות · B2 טקסט צרוב · B4 עוגן-משפט כשיפוט מודלי שמור כדאטה עם sha של ה-FINAL | 140 בירולים מ-26 FINAL + הזרקות | `tools/broll-vision-calibration.json` · `_opus55_wave1/sweep_broll.json` · `b1_bad.jpg` · `anchor_*.jpg` |
| 2 | `items_applied` במניפסט = אמת התוצר (לא broll_plan) | סטיות plan↔applied נמצאו בקמפיינים | L74-L93 |
| 2 | 9 קליפי מיכאל לוי קיבלו people/identity | חוב 2 הבדיקות נסגר | `catalog.json` · `vision-cache-model.json` · `broll-tags-override.json` |
| 3 | `tools/lessons_canon_data.py` + `lessons_canon.py` → `docs/LESSONS-CANON.md` נגזר | 133 slugs: 64 → L · 16 SUPERSEDED עם מחליף · 53 כללי תפעול (טבלה בסקיל) · 3 חובות | שער doctor "lessons canon audit" + בדיקות הזרקה |
| 4 | `intro_offset_sec` נרשם ב-FINAL_PROVENANCE בכל גימור (גם 0) | אמידה = חריג | `local_finish_pipeline.py` `_extra` |
| 4 | `audio_mix.run` עם `stdin=DEVNULL` (ffmpeg נתקע בקריאת stdin) · `music_intro_dip` מדווח | 47/105 טראקים עם שקע בפתיח | `tools/music-intro-dip.json` |
| 4 | `edl_cut`: ספירת packets + נסיגה אוטומטית ל-concat filter כשה-demuxer קוטע | בדיקה סינתטית | `tests/test_vision_gates_v930.py` |

**מה נשאר מדווח ולמה (מדידה, לא ויתור):**
- **B1 לא חוסם:** 6.4% FP על 140 — כולם קמפיינים שגומרו ידנית מחדש (הרשומה לא תואמת לתוצר). חוסם רק אחרי שכל גימור כותב `items_applied` אמיתי.
- **B2 טקסט צרוב:** הגלאי נכשל בהפרדה על הבריכה (טקסט סטטי ↔ רקע סטטי) — נשאר מדווח; `scan-pool` מייצר מטמון לעין.
- **B4 עוגן-משפט:** שיפוט מודלי, לא מספר — `anchor-request`/`anchor-apply` שומרים פסק עם sha; לעולם לא חוסם בלי קוהורט מאושר.
- V7 `garbled`/`extra_ink`, קאבר `garbled` (Studentit), `face` בכתוביות — כמו בגל 1.

**ממצאים אמיתיים שנמצאו בגל 2 (סרטונים שפורסמו — לא נגעתי):** `יום-בחיים-של-הראל` — 4 בירולי מועדון עם הראל? סומנו · `מי-אמר-שמאוחר-מידיי` — בירול "פגישת יעדים" עם הראל בתוכן מועדון · רשומות מודעות הקמפיין לא תואמות לתוצר.

**לא נגעתי במכוון:** `מי-יותר-ממי` (צ'אט Throwdown מקביל — סנכרון נדחה, round-trip + auto_cuts).

## גל 5 — בוצע (v9.32, 23.9.26) · ראיות

| שיפור | הרצה אמיתית | ראיה |
|---|---|---|
| **B1 חוסם** — דגימת קליפ כל 0.25ש + חציון 5 רגעים בחלון; רשומה כפולה נספרת פעם אחת | כיול על 22 FINAL: 120 חיוביים, חיובי נמוך 0.803 מול שלילי גבוה 0.622 ⇒ סף 0.713 · 0% שגוי · 100% נתפס | `tools/broll-vision-calibration.json` · `_opus55_wave1/calib_b1_v932.json` · `diag_b1_notlanded.py` |
| שורש ה-6.4% של v9.30 | **לא** רשומה ישנה: הקליפ היה על המסך (ncc 0.9999 בהיסט 0.8ש) — 8 דגימות לקליפ החמיצו אותו | L94 |
| **B2 OCR נמדד ונפל** | Vision בלי עברית; אזורי טקסט: 58% תפיסה ב-4.7% FP על 150+60; שני הפסולים האמיתיים לא נתפסים ⇒ לא נכנס לקוד | `_opus55_wave1/b2_ocr_samples.jsonl` · `analyze_b2_ocr.py` · `vision_ocr.swift` · L95 |
| **B4 קוהורט** — `tools/anchor_cohort.py` + פסיקת Claude + דף פסיקה להראל | 25 חלונות מ-10 סרטונים; Claude: 11 "לא מעוגן" (Read על 10 גיליונות) | `tools/bench/anchor_cohort.json` · Artifact "פסיקת עוגני בירול" (claude.ai/artifact/Q8sVki9b9JeT4V1TdeEw5M) · L96 |

**הסקיל v9.32 מותקן בממשק** (23.9.26 11:08 — rel-social-video-editor v5, שורת הגרסה v9.32).
**סטטוס מערכת:** unittest 798/0 · gates 183/0 · lessons 102 · 283 אוכפים · doctor 1 FAIL = `sync ציר↔חיתוך` על `דרג-לי-את-הפודיום` (צ'אט rerun-v931 #5 באמצע עבודה — לא נגעתי).

## גל 6 — בוצע (v9.34, 23.9.26) · ראיות ב-`_opus55_wave6/`
> מספור: v9.33 נתפס באותו יום ע"י צ'אט מקביל (scheduled-state) ⇒ הגל הזה v9.34.

| סעיף | מה נמדד | החלטה | ראיה |
|---|---|---|---|
| א. פסיקות הראל | `ArtifactData list/query labels` = **0 מסמכים** | <20 ⇒ לא יובא; `not_anchored` נשאר מדווח | — |
| ב1. V7 garbled על אירוע | כל ה-cues של 50 FINAL חיים (13 Throwdown) + 13,763 הזרקות. f_ok1 לבד לא מפריד (0.512 בתקין). g1=f_ok1×recall<0.30: מקס' 2 cues בתקין (חולצה לבנה, בעין) · scrambled 99.7% · wrong_word 100% | **`garbled_cue` חוסם ב-≥3** (L98). אחרי: 51 FINAL — רק קניות-v2 נחסם. E2E עותק דרג-לי + 3 מילים ⇒ rc=1 | `v7_full.*.jsonl` · `v7_analysis3.json` · `e2e_garbled_cue.txt` · `e2e_garbled_cue_sheet.jpg` |
| ב2. extra_ink ברכיבים | בסף FP=0: 78-82% כפילות רחוקה, 21-28% חופפת; החיוביים = לוגו R.E.L על החולצה | **נפל — לא בקוד** (L101) | `v7_analysis.json` · `extra_far_pos_sheet.jpg` |
| ב3. קאבר ייחוס מילה | כותרת: ≥0.991 מול ≤0.909; `--calibrate` 58 thumbnail: 0/33 FP, 96.8% | **`garbled_word` חוסם** (L100). Studentit: מאושרים עד 0.375 ⇒ **נפל** | `cover_rows.json` · `cover_analysis.json` · `cover_calib_new.json` · `cover_verify.json` |
| ב4. face / marginv | Haar: 35/3,656, 4 אמיתיות בעין · ≥2 עיניים: 4/4, 0/31 · marginv 330 מנקה 4/4 (סרטון אחד) | אימות עיניים נכנס (דיווח); **marginv דינמי לא מומש** (L99) | `face_rows.json` · `face_eyes.json` · `face_sheet_0/1.jpg` |
| ג. B1 בגימור חי | rerun-v931 #7/#8/#9: 3 בירולים, BROLL_VISION רץ עם items_applied — כולם עברו; בעין 3/3 נכון | תקין. **מרווח דק:** טרה-ראן own_run 0.73 מול 0.713 (מצלמה נעה) | `b1_live_sheet.jpg` |

**הזרקת כשל:** כיבוי כל אחד משלושת התיקונים ⇒ הבדיקות נכשלות (3/1/1 FAIL); שחזור ⇒ sha זהה (`fault_inject.txt`).
**רשומות:** gates 185/0 · lessons 107 · 302 אוכפים · `tests/test_vision_wave6_v934.py` 14.
**הסקיל v9.34 מותקן בממשק** (23.9.26 — rel-social-video-editor v7, שורת הגרסה v9.34 נקראה בדף הסקיל).
**baseline סופי:** unittest 820/0 (+14) · gates 185/0 · lessons 107/302 · skill pack v9.34 תואם · doctor 1 FAIL = `sync ציר↔חיתוך` על `אחרי-הריצה-איך-היה` (בתביעת rerun-v931 #8 — לא נגעתי).

## הבא בתור
1. **כשהראל פוסק בדף** (≥20 פסיקות — נכון ל-23.9.26: 0): `ArtifactData list labels` על https://claude.ai/artifact/Q8sVki9b9JeT4V1TdeEw5M → JSON → `anchor_cohort.py import FILE` → `agree`. ≥90% על "לא מעוגן" ⇒ `broll_vision:not_anchored` ל-MEASURED + לקח; פחות ⇒ לתקן את פרומפט הפסיקה ב-anchor_request, לא את הסף.
2. **B1 מרווח דק בקליפים עם מצלמה נעה** (0.73 מול 0.713 בגימור חי): למדוד על 120 החיוביים כמה בתוך 0.05 מהסף, ואם יש — חיפוש היסט זמן ±0.3ש בדמיון (מדידה לפני תיקון; היום אין חיובי-שגוי).
3. **garbled_cue — מעקב:** כל FINAL אירוע חדש עם 3 cues על רקע לבן ייעצר (המחיר: Read על הגיליון). אם זה קורה — לאסוף את ה-cues ולבחון מדד recall על המתאר ולא רק על המילוי.
4. **extra_ink:** מסלול שנשאר — הזרקת הכשל האמיתי (טקסט צרוב בגלם ממקור חיצוני, בלי מתאר מותג) ומדידה מחדש; המתאר האדום-לבן לא מבדיל כתובית מלוגו המועדון.
5. **B2:** פסיקת burned_text בקוהורט; OCR עברי אם יהיה.

## איך מריצים
```bash
P=~/.rel-whisper/bin/python
$P tools/caption_vision.py --workdir W [--strict]          # V7 על FINAL
$P tools/thumbnail/cover_vision.py --workdir W              # G-COVER5 על thumbnail.png
$P tools/vision_check.py --video W/FINAL.mp4 --from-bundle  # V1-V7
$P tools/caption_vision.py --calibrate DIR[::words.json] ... --per-video 80
$P tools/thumbnail/cover_vision.py --calibrate DIR ...
$P tools/vision_check.py --measure-words W1/FINAL.mp4 ...
$P tools/broll_vision_qa.py check --workdir W              # B1-B3 על FINAL
$P tools/broll_vision_qa.py anchor-request --workdir W     # גיליון עוגנים לשיפוט
$P tools/lessons_canon.py --audit --render                 # קנון לקחים
```
