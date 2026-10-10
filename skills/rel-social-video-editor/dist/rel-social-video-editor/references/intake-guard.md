# rel-social-video-editor · intake-guard
> נגזר מהמאסטר (v10.0 — 2026-10-10) ע"י tools/skill_pack.py — לא לערוך כאן.

## שומרי הגלם — intake_guard (v9.26, 19.9.26)

שלוש תקלות מארכיון REL Throwdown 2026 (47 ריליז), אותה משפחה: **הקלט השתנה או שגוי, והמערכת המשיכה כאילו הכל תקין.** הלוגיקה בכלי קנוני אחד, `tools/intake_guard.py`; `_td26/build_proj.py` רק קורא לו.

| לקח | התקלה | השומר | אכיפה |
|---|---|---|---|
| **L68** | קליפ תוקן במקור (סיבוב/נביחה במקום קללה) והבנייה החוזרת יצאה זהה — `clip_NN` ישן + INPUT/whisper במטמון | `sync_clip_copy`: גודל שונה **או** mtime חדש יותר ⇒ העתקה מחדש **ומחיקת כל הנגזרות** (INPUT · whisper_raw · orig · words_final · ROUGH) | `I2_stale_clip_copy` (מרפא, מדווח) |
| **L69** | גלם שצולם לאורך ונשמר landscape+rotation ⇒ הדמות הפוכה/על הצד | **הפריים מכריע**, לא המטא-דאטה: haar ב-0°/90°/180°/270° על 5 פריימים (minNeighbors 8). כיוון חלופי ≥3 פריימים וגם ≥ישר+3 ⇒ **חשד** עם `-vf` לתיקון ועין על הפריים. אין גלאי ⇒ `measured:false` | `I1_orientation` **מדווח** (נמדד על 257 קליפים: תופס את ההפוך, אבל 7 תקינים = 2.7% חיובי-שגוי — haar לא מפריד) · `P19_orientation` MED בפרה-פלייט |
| **L70** | turbo+VAD על INPUT זורק דיבור רועש (קהל, מוזיקה) ⇒ חור בכתוביות | צפיפות <0.6 מילים/ש בקטע שנשמר ≥2.5ש = חשד (תמלול ריק = החור הגרוע, לא "לא נמדד"). מונטאז׳ מוזיקלי מוחרג. תיקון: `intake_guard relisten` (large-v3, בלי VAD) והזרקת המילים | `P18_caption_density` מדווח (MED) — הסף **UNMEASURED**, אסור שיחסום |

```bash
python3 tools/intake_guard.py orient CLIP.mp4 [...]        # exit 1 = חשד → לפתוח פריים
python3 tools/intake_guard.py density --workdir W          # edl.json + whisper_raw.json
~/.rel-whisper/bin/python tools/intake_guard.py relisten CLIP.mp4 OUT.json
```

**אפליקציית הרוויו (v9.26):** השרת רץ **רק** על `~/.rel-whisper/bin/python` (ל-python3 המערכתי אין flask) ו-launchd הוא הבעלים שלו. שרת שהורם ידנית ב-nohup תופס את 5112 ו-launchd נכנס ללולאת קריסה ("Address already in use" — נמדדו 1,243 הפעלות ב-19.9.26). `system_doctor` בודק `review-app python` (פייתון ב-LaunchAgent · flask · המאזין על 5112 מ-.rel-whisper · pid של launchd = pid של המאזין). קובץ ה-`.command` כבר לא מרים שרת שני — הוא מעיר את launchd. **אחרי עדכון קוד: `launchctl kickstart -k gui/$(id -u)/com.rel.review-app`, לא `nohup python server.py`.**
