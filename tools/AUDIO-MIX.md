# מיקס אודיו — Social Video Editing System
עודכן **30.7.2026 (v8.6)** · כלי: `tools/audio_mix.py` · תלות: ffmpeg + ffprobe

> **המסמך נכתב מחדש ב-30.7.26.** הגרסה הקודמת (3.6.26) הצהירה ש"המיקס נשאר
> ב-Descript ופקודת `mix` לא בשימוש", תיארה `sidechaincompress` ו-`loudnorm`
> לדיבור ל-‎-16, ופרסמה חמישה דגלים (`--voice-lufs`, `--duck-ratio`,
> `--duck-threshold`, `--duck-attack`, `--duck-release`) — **אף אחד לא קיים
> בקוד**, והפקודה `mix` היא בדיוק ליבת הגימור מאז v6. מסמך שסותר את הקוד גרוע
> ממסמך שלא קיים: הוא שולח את מי שקורא אותו לדבג פרמטרים דמיוניים.
> מכאן והלאה `system_doctor` בודק את ההתאמה בין ה-LUFS בקוד למסמך הזה.

## הבעיה שנפתרה
גיין באחוזים אף פעם לא עקבי — לכל מנגינה loudness אינהרנטי אחר, ואותו "50%"
נשמע חזק בטראק אחד וחלש באחר. הפתרון: מודדים LUFS ומנרמלים ליעד קבוע.

## מה הקוד עושה בפועל (`audio_mix.py mix`)
1. **נרמול הטראק** — `loudnorm` **two-pass ליניארי** (מדידה, ואז החלה עם
   `measured_*`) ליעד `--music-lufs`. הליניאריות קריטית: single-pass דינמי
   *מנפח* קטעים שקטים בטראק — זה היה השורש של "המוזיקה רועשת מדי".
2. **דאקינג — מדרגת גיין מתוזמנת, לא sidechain.** `volume=enable='gte(t,ss)'`
   על חלונות הדיבור מ-`words_final`. עומק ברירת מחדל 8dB.
   *למה לא `sidechaincompress`:* המצע נדחק לפי **התמליל** — מה שאנחנו יודעים
   בוודאות — ולא לפי מפתח אודיו שמגיב גם לנשימות ולרעש רקע.
3. **premix** — הטראק המנורמל+מדוקק מרונדר ל-WAV ונמדד; המדידה מוזנת ל-loudnorm
   הסופי (שוב ליניארי).
4. **amix + תקרת True Peak** → החלפת רצועת האודיו ב-`-c:v copy`.

## המספרים בפועל (מה שהצנרת שולחת)
| אלמנט | ערך | מקור |
|---|---|---|
| מצע מוזיקה | **‎-46 LUFS** (דיבור ‎-54) | `local_finish_pipeline.py --music-lufs` default |
| עומק דאקינג | **8 dB** ⇒ דיבור ‎-52 | `--duck-depth` default |
| loudness סופי | **‎-14 LUFS** | `loudness_align(PENDING, -14.0)` |
| True Peak | יעד ‎-1.0 · סף שער ‎-0.8 | `alimiter` + `qa_gates` G4 |
| מכירה אמיתית | עד ‎-32 מותר | חוק קאנון 7 |

היסטוריית כיול המצע: ‎-30 → ‎-38 → ‎-46 → ‎-44 → **‎-46** (10.9.26, דאקינג 8 ⇒ דיבור ‎-54). ההנמכות נבעו מ-12 הערות
"חזק מדי" מול 0 "חלש מדי"; ה-‎-44 הוא חזרה מעלה אחרי ש-‎-46 היה נמוך מדי.
טווח הסליידר באפליקציה: עד ‎-52 — בחירה מודעת של הראל, לא תקלה.

## שימוש
```bash
python3 tools/audio_mix.py measure FILE.(mp4|wav|mp3)
python3 tools/audio_mix.py mix --video EXPORT.mp4 --music TRACK.mp3 --out MIXED.mp4 \
        --music-lufs -46 --duck-depth 8 --words words_final.json
python3 tools/audio_mix.py mix ... --no-duck        # מבטל דאקינג
```
הדגלים הקיימים בפועל: `--music-lufs` `--duck-depth` `--no-duck` `--words`
`--tp-limit` `--fade-in`.
**אין**: `--voice-lufs` / `--duck-ratio` / `--duck-threshold` / `--duck-attack` /
`--duck-release`.

## שלושה חובות פתוחים (מתועדים, לא מתוקנים ב-v8.6)
1. **`--tp-limit`** — ברירת המחדל של הכלי 0.75, וה-docstring שלו מתעד ש-0.84
   נמדד כמייצר `TP +0.23 dBTP` (קליפינג). **הצנרת שולחת 0.84.** לתקן עם מדידה
   לפני/אחרי על 3 סרטונים.
2. **הדאקינג הוא מדרגה בפריים אחד** (8dB בלי ramp) ⇒ inter-sample peaks שחומקים
   מה-limiter. הפתרון הנכון: `afade` 40-60ms בכל קצה חלון דיבור.
3. **fallback שקט** — אם מדידת ה-premix נכשלת, הקוד נופל ל-`loudnorm` single-pass
   **דינמי**, כלומר מחזיר את הבאג שהתיקון נועד למנוע, ומדווח ל-stderr בלבד
   (שהצנרת לא בודקת). צריך להפוך לכשל מפורש.

## מקום בתהליך
המוזיקה נכנסת בשלב `music` של `local_finish_pipeline.py`, על `base`
(EXPORT_TIGHT / EXPORT+BROLL / EXPORT+FX), **לפני** צריבת הכתוביות.
Descript מחוץ לזרימה לגמרי.
מקור הטראקים: `brand-assets/music/` — Pixabay בלבד; מוזיקה מג'ונרטת אסורה.
רוטציה עם חוק אי-חזרה 90 יום (`music-rotation.json`).
מוזיקה נכנסת ל**כל** סוגי התוכן — ההגבלה ל-conversion בוטלה ב-v7.8.
