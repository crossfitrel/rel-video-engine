# אינטגרציה נותרת — Artifact Store v9.4

> להחלה **אחרי** שהקלאוד הראשי מסיים את עבודת מנוע ההחלטה וה-B-roll.
> כל מה שמתואר כאן נוגע בקבצים שהיו מוגנים בזמן הכתיבה ולכן **לא בוצע**.
> שום דבר כאן אינו חוסם: המערכת עובדת מלאה בלעדיו.

---

## 1. `~/rel-video-work/V3-לולאה` — מיגרציה שלא הורצה

הפרויקט הוחרג מהמיגרציה כי קובצי התוצר שלו היו בעבודה פעילה.
יש בו **10 ריצות מוצלחות** ו-FINAL אחד.

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System"
python3 tools/migrate_artifacts.py --project "V3-לולאה"           # דוח בלבד
python3 tools/migrate_artifacts.py --project "V3-לולאה" --apply   # אחרי קריאת הדוח
```

הפעולה **מוסיפה** תיקיית `artifacts/` עם hardlinks. היא לא מזיזה, לא משנה
ולא מוחקת אף קובץ קיים. עלות דיסק: 0.

---

## 2. `tools/local_finish_pipeline.py` — patch אופציונלי (שיפור, לא תיקון)

**המצב כרגע תקין:** `run_finish.py` יוצר את ה-artifact אחרי שהצנרת מסיימת
בהצלחה, ולכן כל ריצה דרך `run_finish.py` (כלומר כל ריצה מהאפליקציה) כבר
משמרת גרסה. ה-patch נועד לכסות מסלול אחד בלבד: הרצה **ידנית** של
`local_finish_pipeline.py` בלי העוטף.

מיקום: מיד אחרי הבלוק שכותב את `FINAL_PROVENANCE.json` (שלב 11), לפני
`report.append("")`:

```python
    # v9.4 — שימור הגרסה גם בהרצה ידנית בלי run_finish.py (שם זה כבר קורה).
    try:
        from relvid import artifacts as _art
        _a = _art.create_artifact(W, run_id=os.environ.get("REL_RUN_ID"),
                                  summary="גימור מקומי")
        report.append(f"- גרסה נשמרה לצמיתות: {_a['artifact_id']} (v{_a['version']})")
    except Exception as e:
        report.append(f"- ⚠️ שמירת הגרסה הקבועה נכשלה (לא חוסם): {e}")
```

`create_artifact` הוא idempotent לפי checksum, ולכן הרצה דרך `run_finish.py`
**לא** תיצור כפילות גם אחרי ה-patch הזה.

---

## 3. `skills/rel-social-video-editor/SKILL.md` — עדכון נוסח

שלושה מקומות שצריכים לשקף את המעבר מ"FINAL.mp4" ל"גרסה":

**(א) שער אישור 2 — קאבר+קפשן.** כרגע כתוב "נועל checksum של FINAL".
לעדכן ל: *נועל `artifact_id`. התזמון חייב לקחת את הקובץ מ-`schedule_approval.artifact_path`
ולוודא `artifact_checksum` מול הקובץ בפועל — לא מנתיב `FINAL.mp4` הכללי.*

**(ב) Metricool.** להחליף את
"אסור לתזמן בלי `state==ready_to_schedule` ו-checksum תואם ל-FINAL בפועל"
ב: *…ו-`artifacts.verify(workdir, schedule_approval.artifact_id).ok == True`.
המדיה נלקחת מ-`artifact_path`. אי-התאמה ⇒ `[STALE-FINAL]`.*

**(ג) פסקה חדשה — גרסאות:**
> **גרסאות וידאו (v9.4).** כל ריצת גימור מוצלחת יוצרת artifact קבוע שאינו
> נדרס ואינו נמחק בניקוי. ריצה חדשה יוצרת **מועמד** ואינה מבטלת גרסה מאושרת.
> האפליקציה נפתחת על המאושרת ומודיעה כשקיימת חדשה יותר. הערות על וידאו
> נקשרות ל-`artifact_id`. פירוט: `ARTIFACTS.md`.

---

## 4. `CHANGELOG.md` — רשומה להוספה

```markdown
## v9.4 (31.7.26) — Artifact Store: גרסאות וידאו קבועות

**שורש:** הזהות של גרסה הייתה שם קובץ. נמדד על `~/rel-video-work`: 71 ריצות
מוצלחות, 51 קבצים ששרדו, 21 ריצות כושלות שנשאו `output_hash` של FINAL ישן.
`יום-בחיים-של-הראל`: 16 הצלחות → 3 קבצים.

**נוסף:** `tools/relvid/artifacts.py` · `tools/migrate_artifacts.py` ·
`tests/test_artifacts.py` (21) · `tests/test_artifacts_api.py` (7) · `ARTIFACTS.md`.

**שונה:** `run_finish.py` (חתימת פלט מותנית בהצלחה + יצירת artifact) ·
`relvid/tasks.py` (הערות נושאות `artifact_id`) · `relvid/registry.py`
(אישור תזמון ננעל לגרסה; `derive_state` לא נסוג בגלל ריצה חדשה) ·
`cleanup_work.py` (`artifacts/` מחוץ לתחום; `FINAL_prev` לא-מארוכב מוגן;
דיווח מקום מבחין בין שחרור אמיתי לכפילות hardlink) · `review-app/*`
(לשונית "🎬 גרסאות ותוצרים"; "גרסאות" → "גרסאות עריכה"; באנר גרסה מוצגת;
הנגן מכוון ל-`artifact_id`).

**מיגרציה שבוצעה:** 50 גרסאות ב-20 פרויקטים, 0MB תוספת דיסק (hardlink),
50/50 מאומתות. 42 ריצות שהווידאו שלהן אבד נרשמו כתקלה ב-`unmatched.json`.
`V3-לולאה` הוחרג — ראה סעיף 1 לעיל.

**בדיקות:** 282 עוברות.
```

---

## נקודת חיכוך אפשרית אחת

הקובץ בתוך `art_*/` מקבל `chmod 0444` והוא **hardlink** לאותו inode של
`FINAL.mp4`. לכן `FINAL.mp4` עצמו נעשה קריאה-בלבד. זה מכוון — זו ההגנה מפני
`O_TRUNC` — ותואם לכל מה שהצנרת עושה בפועל (`PENDING.replace(FINAL)` הוא
rename, שדורש הרשאה על התיקייה ולא על הקובץ).

אם קוד חדש ינסה לפתוח `FINAL.mp4` לכתיבה ישירה, הוא ייכשל ב-`PermissionError`.
הפתרון הנכון הוא לכתוב לקובץ זמני ולעשות `os.replace` — לא להסיר את ההגנה.
