# Artifact Store — היסטוריית גרסאות הווידאו (v9.4)

> מקור אמת לתחום הזה. משלים את `ARCHITECTURE.md` (מבנה) ו-`DATA-SCHEMA.md` (סכמות).
> נכתב 31.7.26.

## הבעיה שנמדדה

סריקה של `~/rel-video-work` ב-31.7.26 החזירה:

| מדד | ערך |
|---|---|
| פרויקטים | 21 |
| רשומות ריצה | 103 |
| ריצות **מוצלחות** | 71 |
| קובצי וידאו סופיים ששרדו | 51 (21 FINAL + 30 FINAL_prev) |
| ריצות כושלות שנשאו `output_hash` של FINAL ישן | 21 |

בפרויקט `יום-בחיים-של-הראל`: 16 ריצות מוצלחות → 3 קבצים על הדיסק.

שלוש סיבות שורש, כולן אותו דפוס — **הזהות של גרסה הייתה שם קובץ**:

1. `FINAL.mp4` נדרס בכל ריצה. הגיבוי `FINAL_prev_<ts>.mp4` היה מוסכמה, לא חוזה.
2. `cleanup_work.py` גזם `FINAL_prev` ל-2 אחרונים — כלומר **ברירת המחדל של כלי
   הניקוי מחקה גרסאות וידאו מוצלחות**.
3. `run_finish.py` חתם `rec["output_hash"] = sha256_file(FINAL.mp4)` ללא תנאי —
   גם כשהריצה נכשלה. רשומה כושלת קיבלה את החתימה של FINAL תקין וישן.

בנוסף: הערות על FINAL נשמרו עם `on_final: true` בלבד, בלי זהות גרסה — ולכן
אחרי ריצה נוספת, הערה על 00:14 הצביעה לנקודה בסרטון אחר.

## הפתרון

`artifacts/` בתוך כל תיקיית פרויקט. מזהה קבוע (`art_<hex>`), תיקייה משלו,
`checksum` sha256 **מלא**, ולעולם לא נדרס.

```
artifacts/
  pointers.json          latest_candidate / approved_final / published_final
  index.json             cache; reindex() בונה מחדש מהתיקיות
  unmatched.json         ריצות מוצלחות שהווידאו שלהן אבד — תקלה, לא גרסה
  art_<hex>/
    FINAL.mp4            hardlink לתוכן, 0444
    artifact.json
    provenance.json      עותק FINAL_PROVENANCE.json של אותה ריצה
    qa_report.json
    broll_plan.json
```

### ארבעה עקרונות

**התיקיות הן מקור האמת.** `index.json` הוא cache. `pointers.json` ניתן לשחזור
(`repair_pointers`) כי כל artifact נושא בעצמו `approved_at` / `published_at`.

**יצירה אטומית.** נבנה ב-`.staging_<id>/`, ורק כשהכל שלם — `os.rename` לשם
הסופי. קריסה באמצע משאירה `.staging_*` שאינו נספר כגרסה ומנוקה ב-`sweep_staging()`.
ה-checksum נבדק *אחרי* ההעתקה; אי-התאמה מבטלת את היצירה.

**hardlink + 0444.** אפס עלות דיסק (נמדד: 50 גרסאות, 0.0MB תוספת). המצב 0444
חוסם `O_TRUNC` על אותו inode, ו-`rename` — כל מה שהצנרת עושה ל-FINAL.mp4 —
ממשיך לעבוד כי rename דורש הרשאה על התיקייה ולא על הקובץ.

**שלושה מצביעים, לא אחד.** ריצה מוצלחת מזיזה **רק** את `latest_candidate`.
`approved_final` ו-`published_final` זזים אך ורק בפעולה מפורשת של הראל.

### ברירת המחדל להצגה

`display_target()` מחזיר את **המאושרת**. אין מאושרת ⇒ המועמד האחרון, מסומן
מפורשות כלא-מאושר. אם קיימת גרסה חדשה יותר — `newer_count` מדווח, והאפליקציה
כותבת זאת בבאנר. **גרסה חדשה אף פעם לא מסתירה גרסה מאושרת בשקט.**

## API עיקרי — `tools/relvid/artifacts.py`

| פונקציה | מה עושה |
|---|---|
| `create_artifact(workdir, src, run_id=…)` | יוצר גרסה אטומית. תוכן זהה ⇒ מחזיר קיימת (idempotent) |
| `list_artifacts(workdir, verify_integrity=)` | כל הגרסאות, מהישנה לחדשה, נקרא מהתיקיות |
| `verify(workdir, aid)` | קובץ קיים + גודל + checksum. תשובה: `{ok,state,detail}` |
| `display_target(workdir)` | מה להציג, האם מאושר, כמה חדשות ממתינות |
| `approve / publish / set_pointer` | הזזת מצביעים + חותמת בתוך ה-artifact |
| `activate(workdir, aid)` | הופך גרסה ל-FINAL.mp4 הפעיל — **קודם לוכד את הנוכחי** |
| `protected_ids / sweep_staging / reindex / repair_pointers` | תחזוקה |

## נקודות חיבור

* `tools/run_finish.py` — ריצה מוצלחת יוצרת artifact; ריצה כושלת מקבלת
  `output_hash=None` ו-`artifact_id=None`.
* `tools/relvid/tasks.py` — כל הערה על וידאו נושאת `artifact_id` + `artifact_hash`;
  `comment_artifact()` פותר גם הערות ישנות (לפי זמן כתיבה) ומחזיר תקלה מפורשת
  כשהגרסה חסרה, במקום ליפול בשקט ל-FINAL הנוכחי.
* `tools/relvid/registry.py` — `set_schedule_approval("approve")` נועל
  `artifact_id` + `artifact_path`; `derive_state` בודק את שלמות **הגרסה**
  ולא את mtime של `FINAL.mp4`, ולכן ריצה חדשה לא מבטלת אישור קיים.
* `tools/cleanup_work.py` — `artifacts/` מחוץ לתחום; `FINAL_prev` שלא ארוכב
  לא נמחק בברירת מחדל (`--prune-unarchived` כדי לכפות); דיווח המקום מבחין בין
  מקום שמשתחרר בפועל לבין כפילויות hardlink.
* `review-app/server.py` — `/api/artifacts/<name>` · `/artifact-media/<name>/<aid>`
  · `/api/artifacts/<name>/<aid>/{approve,publish,activate,verify}` ·
  `/api/artifacts/<name>/compare`.

## מיגרציה — `tools/migrate_artifacts.py`

dry-run כברירת מחדל; לא מזיז, לא משנה, לא מוחק דבר. מתאים קובץ לריצה לפי
checksum, ואם אין — לפי חלון זמן הריצה **רק כשיש התאמה יחידה**. שתי מועמדות ⇒
לא מתאימים. קובץ שלא הותאם עדיין נשמר כגרסה (הווידאו הוא הנכס) ומסומן
`matched=false`. ריצה מוצלחת בלי קובץ נרשמת ב-`unmatched.json` כתקלה.

הרצה חוזרת אידמפוטנטית: התאמה ב-checksum מלא + `used` מאותחל מ-run_id של
גרסאות קיימות (בלי זה, ההרצה השנייה הייתה מסמנת את כל הריצות כ"אבודות").

**תוצאת ההרצה בפועל (31.7.26):** 50 גרסאות נשמרו ב-20 פרויקטים, 0MB תוספת
דיסק, 50/50 מאומתות. 42 ריצות מוצלחות נרשמו כתקלה — הווידאו שלהן אבד לפני
שהמערכת נכנסה לתוקף ואין מה לשחזר.

## בדיקות

`tests/test_artifacts.py` (21) — הזרקת כשל אמיתית לכל אחד מעשרת התרחישים.
`tests/test_artifacts_api.py` (7) — דרך `server.py` עצמו מול `REL_WORK_ROOT` זמני.
