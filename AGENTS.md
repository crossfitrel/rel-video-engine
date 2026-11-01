# AGENTS.md — מערכת עריכת הסושיאל של קרוספיט אריאל (v11, 29.10.26)

> לכל סוכן שאינו Claude (Codex, ChatGPT, כל מודל אחר) שעובד על הריפו הזה או מפעיל אותו.
> אותם כללים ואותם שערים כמו ל-Claude. בסתירה: הסקיל `skills/rel-social-video-editor` (CORE.md + references) גובר על הקובץ הזה.

## מה המערכת
גלם מהטלפון ל-Monday (גאנט 18395578529, עמודה "קבצים" `file_mkrpfxkz`, סטטוס "מוכן לעריכה")
→ worker דטרמיניסטי ב-GitHub Actions (`cloud/worker.py`, `.github/workflows/video-worker.yml`)
→ שיפוט במודלים זולים דרך `tools/llm.py` (Haiku/Sonnet, Opus רק להסלמה)
→ PREFLIGHT → עמוד הרוויו **rel.fit/review** (Netlify `rel-video-review`, מצב ב-Supabase סכמה `video`)
→ הראל מאשר בטלפון → גימור → אישור קאבר+קפשן+תזמון → Metricool.

## מה מותר לך לעשות מבחוץ
כל הפעולות עוברות דרך פונקציית ה-edge `video` (Supabase `xfsvbpqbfmqlwgyusrww`), עם `cloud/video_api.py`:
```
export VIDEO_ADMIN_KEY=…        # מהכספת של Supabase (video_admin_key). לעולם לא בקוד, לא בקומיט, לא בלוג.
python3 cloud/video_api.py jobs '{}'                                   # מה בתור
python3 cloud/video_api.py costs '{}'                                  # עלות לריל וליום
python3 cloud/video_api.py enqueue '{"kind":"prep","project_id":"p-<item>","payload":{"item_id":"<item>"}}'
python3 cloud/video_api.py redispatch '{"job_id":"<uuid>"}'            # מפעיל שוב את ה-workflow לג'וב קיים
python3 cloud/video_api.py health_set '{"key":"…","value":"ok"}'
```
- קריאת הערות של הראל: `state` (עם `VIDEO_REVIEW_TOKEN`) או `job_claim` של ג'וב `notes`.
- הפעלת worker: רק `enqueue` / `redispatch` (הפונקציה עושה workflow_dispatch). לא מריצים workflow ידנית עם טוקן מומצא.
- עדכון סטטוס: `project_upsert` (רק השדות שהשתנו), `comment_update`, `monday_status`.

## מה אסור לך — לעולם
1. **לא לעקוף שער.** `PREFLIGHT.json` עם `ready_for_harel=true` הוא התנאי היחיד ל"מוכן לבדיקה". אין "מוכן" בלי גימור מלא (כתוביות, מוזיקה, בירול, MG, hook_fx, קאבר) וכל הבדיקות: `qa_gates` · `vision_check` + גיליונות · תמלול חוזר של FINAL · `verify-fixes` על כל הערה מהסבב הקודם.
2. **לא לתזמן בלי הראל.** תזמון ב-Metricool רק אחרי `approve_cover_caption` שהראל לחץ בעמוד, רק מ-`schedule_approval.artifact_path` עם sha256 תואם, ורק לתאריך מעמודת `date_mkrpvw3n` בגאנט (UTC). אחרי תזמון: אימות בקריאה חוזרת לפני "תוזמן!". ג'וב `schedule` רץ ב-worker (`h_schedule`, Metricool דרך op=metricool, L161); כל חריגה (אין טוקן, FINAL לא תואם, אימות נכשל, מותג לא מועדון) ⇒ ג'וב runner=claude. אין תאריך בגאנט ⇒ ממתינים, לא בוחרים תאריך.
3. **לא לשלוח הודעה או מייל לאף אדם.** תקלה שדורשת את הראל ⇒ `health_set` (באנר בעמוד), לא מייל.
4. **לא לגעת בצבע, לא לדחוס FINAL, לא להאיץ סרטון כדי לעמוד באורך.** האורך נקבע ע"י התוכן.
5. **לא לשנות סף בלי מדידה.** כל סף נגזר מסרטונים שהראל אישר (`tools/reference_profile.json`). אין שער חוסם עם סף לא-מדוד.
6. **לא לבטל לקח.** כל לקח רשום ב-`tools/lesson_registry.py` עם אוכף; `--audit` חייב לעבור. לקח חדש = רשומה + אוכף (בדיקה/שער) באותו שינוי.
7. **לא לעבוד על פריטי Monday/Metricool אמיתיים לבדיקות.** בדיקות רק על `p-e2etest` (`test: true`) או עותקים.
8. **לא לשמור מפתחות בקוד.** Anthropic/Monday/GitHub יושבים בכספת של Supabase; ה-runner מקבל רק טוקן חד-פעמי לג'וב.

## שלושת החוזים
1. אין תוצר להראל בלי מבקר-קדם (`tools/preflight_critic.py` → `PREFLIGHT.json`). כשמדווחים "מוכן לבדיקה" מצטטים את פסק-הדין.
2. אין לקח בלי אוכף (`tools/lesson_registry.py --audit`).
3. הבמאי לומד מהראל: `tools/director_lessons.py` רץ לפני כל `--director`.

## חוקי ברזל (נוסח מלא: `skills/rel-social-video-editor/references/iron-rules.md`)
סף נגזר ממדידה · גלאי שמפסיק בשקט גרוע מגלאי שאין · קלט שהשתנה מבטל כל נגזרת · חוק הראייה: אין אמירה על סרטון בלי גיליון שנפתח · תיקנת פעמיים = השכבה הלא-נכונה · מדוד לפני ואחרי · workdir נשמר אחרי כל שלב (`libs_git.sh push-project` + אימות) — אין "בוצע" בלי שמירה מאומתת.

## קופי
מבוסס תמלול בלבד · מנוע הקפשן v4 (`docs/CAPTION-ENGINE.md`) + `tools/caption_gate.py` · CTA אחד · אפס האשטגים · אין URL בקפשן · "מועדון קרוספיט", לעולם לא "חדר כושר" · בלי קו מפריד ארוך (—) · לבבות ❤️🖤 במועדון, 🩵 בתוכן האישי של הראל.

## עלויות
כל קריאת מודל עוברת ב-`tools/llm.py` → `op=llm`. התקרות ב-`video.config.caps` (ברירת מחדל ‎$1.5 לריל, ‎$5 ליום, 2 קריאות Opus לריל) נאכפות בצד השרת. אל תעקוף אותן במסלול ישיר.

## בדיקות
`$REL_PY tools/baseline.py` ירוק לפני commit. שער או worker חדש = בדיקת הזרקת-כשל ב-`tests/`.
