# ריצת ענן — v11 (29.10.26)

> העבודה הכבדה כבר לא רצה בסשן Claude. היא רצה ב-GitHub Actions (`cloud/worker.py`) שמופעל מאירוע.
> הסשן המתוזמן "עריכת סושיאל בענן" הוא רק ערוץ ההסלמה והגיבוי. כל חוקי הברזל, שלושת החוזים ושערי האישור בתוקף.

## 0. סריקה זולה (שאילתה אחת, בלי bootstrap)
```sql
select id, kind, project_id, runner, status, dispatch, created_at from video.jobs
 where status='queued' and (runner='claude' or coalesce((dispatch->>'ok')::boolean,false)=false) order by created_at;
```
אין שורות ⇒ מסיימים מיד, בשקט. (Monday כבר לא נסרק: ה-webhook 660374019 יוצר ג'וב `prep` לבד.)

## 1. ג'וב runner=actions שלא נשלח (חסר github_dispatch_token, או GitHub נכשל)
הסשן מריץ את אותו worker בעצמו — אותה פקודה, אותם שערים:
```
add_repo crossfitrel/rel-video-cloud → clone → bash cloud/bootstrap.sh
export VIDEO_ADMIN_KEY=<vault: video_admin_key>   # Supabase execute_sql, לא נכתב לקובץ בריפו
$REL_PY cloud/worker.py run --job-id <id>
```
אם `github_dispatch_token` קיים: עדיף `python3 cloud/video_api.py redispatch '{"job_id":"<id>"}'` ולסיים — Actions עושה את העבודה.

## 2. ג'וב `judge` (הסלמה מה-worker)
`payload.why` אומר למה: `preflight_not_ready` · `note_unmapped` / `notes_to_editor` (עם מפת ההערות של Sonnet) · `gate_failed_twice` · `cover_change`.
טוענים את הסקיל `rel-social-video-editor` ואת ה-reference של השלב בלבד, מטפלים בפרויקט אחד, ובסוף:
`push-project` (חובה) → `review_bridge.py proxy` → `video_api.upload` → `project_upsert` (state=review רק עם PREFLIGHT תקין) → `job_done`.

## 3. ג'וב `schedule` (הראל לחץ "אשר קאבר, קפשן ותזמון")
- פרויקט `test: true` (`p-e2etest`) לעולם לא מתוזמן ולא נוגע במאנדיי.
- הקובץ רק מ-`schedule_approval.artifact_path` + `artifacts.verify().ok` + sha256 מול `artifact_checksum`.
- העלאה ל-"סרטון מוכן" `file_mm402fp7` → public_url. הקאבר → `videoThumbnailUrl`.
- `createScheduledPost` — התאריך **רק** מ-`date_mkrpvw3n` (UTC), מותג לפי מחלקה. קפשן = `payload.caption` (מה שהראל אישר).
- אימות `getScheduledPosts`: מועד, רשתות, קפשן מדויק, קאבר. לא תואם ⇒ `[SCHEDULE VERIFY FAILED]`, לא מסמנים.
- רק אחרי אימות: Monday "תוזמן!" + `[SCHEDULED-METRICOOL]` · `project_upsert state=scheduled` · `job_done` עם consume_action.

## 4. סגירה
`push-project` לכל workdir שנגעו בו · `job_done` · `health_set ok` לכל מפתח שתוקן. אין מייל. תקלה שדורשת את הראל ⇒ `health_set` (באנר בעמוד).

## שעונים
ראו `cloud/BENCH-v11.md` (Actions מול סשן מול מק).
