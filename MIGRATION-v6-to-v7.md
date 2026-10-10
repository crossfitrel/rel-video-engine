# MIGRATION v6.1 → v7.0
בוצע 23.7.2026 ע"י Claude. אין צעדי מיגרציה ידניים — הכל אוטומטי והדרגתי.

## מה קורה מעצמו
* **מניפסטים**: `project_manifest.json` נוצר לכל פרויקט בפעם הראשונה שהוא נסרק (registry/doctor/UI). פרויקטים ישנים מקבלים project_id בסריקה.
* **revisions**: פרויקט ישן בלי revisions — הגרסה הראשונה נוצרת אוטומטית כ-baseline בשמירה/אישור הראשונים. ההיסטוריה הישנה (edl.machine.json, edl.*.bak) נשארת במקומה.
* **learn-state**: מיגרציה אוטומטית v1→v2 בריצת הלמידה הראשונה. offsets עוברים לפי project_id; תיקייה ששוננה (offset יתום) מתחילה מסוף הקובץ הנוכחי — **לא סופרים היסטוריה כפול** (המקרה של shina). counts הישנים נשמרים תחת `_legacy_v1`.
* **music-rotation**: פורמט v1 (`{"last":...}`) נקלט כהיסטוריה בת רשומה אחת.
* **rounds v6**: review_rounds.json ממשיך לעבוד ומוצג בלשונית הערות תחת "היסטוריית סבבים". הערת טקסט חופשי חדשה נכנסת גם כהערה מובנית בתור קלאוד.

## שינויי שמות (עם רשת ביטחון)
* `descript-brand-assets/` → `brand-assets/` + symlink בשם הישן (צרכן שלא עודכן ממשיך לעבוד).
* `descript_instructions.md` → `review_suggestions.md` (פלט edl_build; אין צרכן קוד לשם הישן).
* `align_reconcile.py`: `load_descript_words`→`load_corrected_words`, ארגומנט `descript`→`corrected` (פוזיציונלי — קוראים לא מושפעים).
* מסמכי עידן-Descript הועברו ל-`archive/עידן-דיסקריפט/`.

## שינויי התנהגות שחשוב להכיר
1. הגימור כותב `FINAL_PENDING.mp4` ומקדם ל-`FINAL.mp4` **רק אחרי QA PASS**; FINAL קודם מגובה `FINAL_prev_<ts>.mp4`.
2. אישור באפליקציה רץ דרך `run_finish.py` — נעילה, run record, resume. לחיצה כפולה לא מכפילה ריצה.
3. `learn_from_edits --apply` לא מכייל ישירות יותר — יוצר הצעה ב-shadow (ראה SKILL שלב 5.5).
4. QA v2: נוספו אזהרות רכות G1b (יעד 50-65ש) ו-G5b (30fps). שום סף קשיח לא השתנה.
5. loudness: מעבר שני עם תקרת limiter ‎-1.6dB כשה-TP נשאר חם (תוקן כשל אמיתי שנצפה ב-E2E).
6. מוזיקה: חוק אי-חזרה 90 יום; הספרייה הורחבה ל-23 טראקים (Pixabay, לא-AI).

## Rollback
* policy: `python3 tools/learn_from_edits.py --rollback` (snapshots ב-tools/policy-history/).
* revision: באפליקציה (לשונית גרסאות → שחזר) או `review_cli.py restore`.
* קוד: אין git — הקבצים ששונו מגובים ב-iCloud versioning של מערכת ההפעלה; רשימת הקבצים המלאה ב-CHANGELOG.md.
