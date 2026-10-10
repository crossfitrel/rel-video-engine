# TD26 — שתיקות, פילרים ומוזיקה (28-29.9.26)

## מה נעשה
- 52 פרויקטי Throwdown: keep_segments נבנו מחדש לפי תזמוני מילים (`~/rel-video-work/_td26_fix_0928.py`).
  פער 0.4-2.5ש נחתך ל-~0.2ש · פילרים מתומללים יוצאים · פער >2.5ש נחתך רק אם שקט ביחס לדיבור (‎-9dB) ·
  משחקי תגובה (מי-יותר-ממי) — פערים עד 0.8ש נשמרים · ויזואליים/מונטאז' — בלי שינוי חיתוך.
  גיבויים: `edl.json.bak-td26-0928`, `project_manifest.json.bak-td26-0928`. גימור עם `--tighten off`.
- מוזיקה: מפלס פתיח = I_dialog-10, בדיבור = I_dialog-18 (27.9 היה I-1/I-9 = "חזק מדי").
- טראקים: בריכה קלילה (funk/afrobeat/hiphop-groove) — `_td26_music_light.py`. מונטאז'/אפטר-מובי נשארו אקשן.
- רמזי מקצה (2) — לא שייכים לסבב (אין APPROVAL, canon_lint חוסם); ה-FINAL הקודם שלהם לא נגע.

## שינויי קוד
- `captions_qa.py`: `median_signed` בסיכום.
- `qa_gates.py` G6b: בענף matched<72 שופטים לפי חציון (mean זוהם מהתאמות-שווא; אביגיל mean ‎-0.42 / median ‎-0.10 / onset +0.14).
- `local_finish_pipeline.py`:
  - `finish_prefs.captions.offset` — היסט כתוביות פר-פרויקט (+=מאחר) + אמת G6 מוזזת (`whisper_export_offset.json`).
  - v9.37 `pick_music(light=True)` — פרופיל קליל אוטומטי לפרויקטי Throwdown (לא מונטאז'/אפטר-מובי), או `finish_prefs.music.profile="light"`; `"full"` מבטל.

## חוב פתוח (שורש)
- כתוביות מקדימות ‎0.1-0.3ש גם בסרטונים שלא נגעו בהם (נמדד בקורלציית אנבלופ `_td26_lag.py`): תזמוני Whisper מרופדים.
  התיקון הנכון = הצמדת תחילת מילה ל-onset אקוסטי ב-reconcile (כמו `candidates.snap_words_to_audio` של הבמאי), ואז למחוק את ה-offsets הידניים.
- להוסיף אוכף ב-lesson_registry לפרופיל המוזיקה הקליל.

## סגירה 30.9.26
- 50/50 FINAL עודכנו (בלי 2 רמזי מקצה). מאסטרס-פיין נכשל 3 פעמים על loudness (TP חם, חומר קטום, AAC לא דטרמיניסטי).
- v9.38 ב-loudness_align: מעבר 3 ‎-4.4dB/attack 1ms, מעבר 4 גיין פיצוי ‎-3dB, וגיבוי loudnorm דינמי TP ‎-3/‎-3.5/‎-4 עם בדיקה בכל ניסיון.
- work_claim: אין תביעות פעילות.
