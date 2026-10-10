# ממסר ענן ל-1080p/4K — תכנון (Descript → ענן → Monday)

> **⚠️ נשלל (8.6.2026) — fallback בלבד.** הראל: "לא רוצה עוד תוכנה." התברר שלא צריך: ההעלאה הישירה ל-Monday עובדת (18MB ב-38ש) — הכשל הקודם היה ניטור תכוף שהתנגש עם תהליך הרקע, לא רוחב פס. **השיטה בפועל: PUT ברקע + בדיקה פעם אחת** (ראה `PIPELINE.md` שלב 10). המסמך הזה נשמר רק כתוכנית גיבוי אם אי-פעם ה-egress ייכשל בעקביות.

**נכון ל-8.6.2026 | סטטוס: נשלל — fallback בלבד**

## הבעיה

צריבת הכתוביות (RTL עברית) חייבת לקרות מקומית/ב-ffmpeg — Descript לא תומך RTL. אבל ה-**egress (העלאה) מסביבת ההרצה שלי איטי מאוד (~35KB/s) ולא אמין** לקבצים גדולים. תוצאה: 1080p (~18MB) נתקע, 4K (~80MB) בלתי אפשרי. זה חוסם מסירה אוטומטית של 1080p/4K לבורד.

## התובנה המרכזית

**הווידאו כבר בענן.** `publish_project` של Descript מחזיר `download_url` ל-1080p/4K (ענן Descript, מהיר). הדבר היחיד שהסביבה שלי מייצרת וייחודי לה הוא **קובץ הכתוביות ASS** (כמה KB) + **ערך גיין ה-loudnorm** (מספר). אם שירות ענן יצרוב את ה-ASS על ה-URL — **שום קובץ גדול לא צריך לצאת ממני.**

## הארכיטקטורה

```
[הסביבה שלי]                          [ענן — Make]                    [ענן — Transloadit]         [Monday]
עריכה ב-Descript ✏️
publish 1080p/4K  ──► download_url ─┐
QA gate (silence) ✅                 │
מייצר ASS (כמה KB) ─────────────────┼─► Webhook:                ──►  ffmpeg (libass):        ──►  "Add a file to
gain (מספר) ────────────────────────┘   { video_url, ass_text,      • subtitles=ASS:fontsdir      file column"
                                          gain, item_id }             • volume=gain + alimiter      (file_mm402fp7)
                                                                      • פלט 1080p/4K
```

1. **הסביבה שלי** (כמו היום): עריכה ב-Descript → publish → `download_url`. גימור מקומי מפיק **רק** את ה-ASS (כתוביות מילה-אחת, בלי נקודות, Assistant ExtraBold + מתאר #871d1f) + ערך הגיין. QA gate אפס-שקט רץ מקומית.
2. **Make (webhook)** מקבל: `{ descript_video_url, ass_text, gain_db, item_id }`.
3. **Transloadit** (FFmpeg v7 בענן, רוחב פס ענן): מייבא את ה-URL → צורב את ה-ASS (`subtitles` filter + הפונט) → `volume={gain}dB,alimiter` ליעד ‎-14 LUFS/TP-1 → פלט 1080p/4K. **אותו ffmpeg+libass כמו אצלי = אותה איכות בדיוק, כולל RTL.**
4. **Make → Monday**: מודול "Adds a file to a file column value" מעלה את פלט Transloadit לעמודת "סרטון מוכן" — **בענן, מיידי, ב-1080p/4K מלא.**

## למה זה הפתרון הנכון

- **אפס egress גדול ממני** — רק KB של ASS + URL. החסם נעלם.
- **4K זמין מיידית** — Transloadit מעבד בענן, גודל הקובץ לא משנה.
- **אותה איכות כתוביות** — ffmpeg+libass אמיתי (לא מנוע ענן קנייני) → RTL מושלם, סטייל המותג זהה.
- **אוטומטי לחלוטין** — אפס התערבות שלך, בדיוק היעד.

## מה צריך כדי לבנות

| רכיב | אחראי | הערה |
|---|---|---|
| חשבון **Transloadit** + API key (template_id) | **הראל** | יש free tier (לאמת מכסה נוכחית). חלופות: Cloudinary / Shotstack / ffmpeg self-hosted. |
| העלאת **Assistant-ExtraBold.ttf** ל-Transloadit (לפונט בצריבה) | אני (פעם אחת) | מ-`descript-brand-assets/`. |
| **Template Transloadit** (assembly: import URL → /video/subtitle או /video/encode עם subtitles filter → encode) | אני | משכפל את פקודת ה-ffmpeg המקומית. |
| **סנריו Make 💙** (Webhook → Transloadit → Monday add-file) | אני | חדש, יסתיים ב-💙 לפי כלל הבטיחות. |
| עדכון `finish_local.py` / הצנרת לשלוח webhook במקום העלאה מקומית | אני | מפיק ASS+gain ושולח ל-Make. |

## עלות (לאמת)

Transloadit: תמחור לפי דקות-עיבוד/GB. ריל 27ש @1080p = עיבוד קצר. free tier בד"כ מספיק לנפחים שלנו. **לאמת מחיר עדכני לפני התחייבות.**

## הצעד הבא

הראל פותח חשבון Transloadit (או מאשר שירות חלופי) ומוסר API key → אני בונה את ה-Template, סנריו ה-Make 💙, ומחבר את הצנרת. עד אז — 1080p נשאר בתיקייה וניתן לגרור ידנית לבורד כפתרון ביניים.
