# מערכת עריכת הסושיאל בענן — v10 (10.10.26)

**המטרה:** אפס תלות במק בעריכת ריל. המק נשאר רק לפודקאסט "מדברים כושר".

## איפה כל דבר חי
| מה | איפה |
|---|---|
| קוד, בדיקות, סקילים (מאסטר), הגשר לרוויו | GitHub פרטי `crossfitrel/rel-video-cloud` |
| בריף, סטטוס, גלם (עמודה "קבצים" `file_mkrpfxkz`), סופי ("סרטון מוכן" `file_mm402fp7`) | Monday — גאנט הסושיאל 18395578529 |
| רוויו, הערות בטיימקוד, אישור לגימור, אישור קאבר+קפשן | עמוד Artifact עם db: https://claude.ai/artifact/B799jvngoLRUMYzoz1XqZn |
| ספריות (בירולים, מוזיקה, פונטים, sfx), מצב המערכת, פרויקטים פעילים, ארכיון מסירות | Drive של **hayonhq@gmail.com** → `REL Video Cloud/` (`ספריות/` · `מצב/` · `מסירות/` · `ארכיון/` · `מניפסט/`) |
| ידע שצ'אט קורא (הוראות, קאנון, PIPELINE, references, קטלוגים) | פרויקט claude.ai "Social Video Editing System" |
| הרצה | משימה מתוזמנת בענן כל שעה ("עריכת סושיאל בענן") — `cloud/RUN.md` |

**לעולם לא** מחזירים מדיה או תוצרי עבודה לתיקיית הפרויקט המסונכרנת (iCloud) או לפרויקט claude.ai. תיקיית העבודה בענן: `~/rel-video-work` (`REL_WORK_ROOT`), מחוץ לכל סנכרון.

## הזרימה
1. הראל מעלה גלם מאפליקציית Monday בטלפון ל"קבצים" ומסמן "מוכן לעריכה".
2. הריצה המתוזמנת: מנעול (סטטוס "לאחר צילום, בעריכה" + `[CLOUD-LOCK]`) → הורדה → `cloud/prep.py` (שער HDR, INPUT, תמלול, EDL) → במאי → גימור → PREFLIGHT.
3. רק PREFLIGHT תקין ⇒ פרוקסי רוויו עולה לעמוד, הסטטוס "מוכן לבדיקה".
4. הראל בטלפון: צופה, מעיר בטיימקוד, "שלח לקלאוד" / "אשר והתחל גימור", ואחר כך מאשר קאבר+קפשן.
5. הריצה הבאה מחילה דרך `cloud/review_bridge.py` על אותם endpoints של review-app (Flask בתוך התהליך, בלי שרת) ⇒ revisions, tasks, artifact נעול — כמו במק.
6. תזמון: הסופי ל"סרטון מוכן" → Metricool מושך מ-public_url → אימות `getScheduledPosts` → "תוזמן!" + state=scheduled.
7. גיבוי בסוף כל ריצה: מצב + פרויקט + סופי ל-Drive (md5 נבדק). הגלם נשאר במאנדיי.

## מה הוחלף ממה שהיה תלוי במק
| במק | בענן |
|---|---|
| `tonemap.swift` (AVFoundation) | `tools/hdr_gate.py` — SDR עובר כמו שהוא; HLG → zscale+tonemap hable npl=160 (כויל מול tonemap.swift: SSIM 0.951/0.981 בשני זוגות), דגל `HDR_GATE.json`; PQ מדווח uncalibrated. HDR כבוי באייפון מ-10.10.26 |
| MLX על ה-GPU | ct2 (`REL_ASR_BACKEND=ct2`), אותו מודל ivrit-ai turbo + VAD |
| review-app 5112 (launchd) | עמוד Artifact + db, `cloud/review_bridge.py` |
| Desktop Commander לגימור ארוך | bash ברקע בסשן הענן |
| osxphotos (קציר גלריה) | לא עובר — כלי מק בלבד, לא בזרימת הריל |
| נתיבי `/Users/hayon/...` בקונפיגים | `cloud/env.sh` (שורש אחד) + `cloud/mac_compat.sh` כרשת ביטחון לקונפיגים ישנים |

## טוקן Drive (פעולה חד-פעמית של הראל)
רכיב הענן ניגש ל-Drive של hayonhq דרך rclone. הטוקן **לא** בריפו ולא בקובץ: משתני סביבה של סביבת הענן.
במק: `rclone config show hayonhq` → מעתיקים את שורת `token = {...}` ובהגדרות סביבת הענן (claude.ai/code → Environment → Environment variables) מוסיפים:
```
RCLONE_CONFIG_HAYONHQ_TYPE=drive
RCLONE_CONFIG_HAYONHQ_SCOPE=drive
RCLONE_CONFIG_HAYONHQ_TOKEN={"access_token":...,"refresh_token":...}
```
בלי זה `bootstrap.sh` עוצר בקוד 3 ומודיע — אין עריכה בלי ספריות.
⚠️ rclone מזהיר שה-client_id המשותף שלו יוצא משימוש במהלך 2026 — כדאי ליצור client_id משלך ב-Google Cloud ולהוסיף `RCLONE_CONFIG_HAYONHQ_CLIENT_ID/SECRET`.

## אימות (10.10.26)
- **baseline בענן:** 938 בדיקות כמו במק; 9 נכשלות רק מחוסר ספריות (מוזיקה/בירול/פתיח) עד שה-Drive נמשך, 1 תוקנה (הרשאות root). gates 216/0, lessons 138/0.
- **תמלול:** דיבור נקי — הענן שונה מהמק ב-1 מילה מ-45 (2.2%), בדיוק כמו ההפרש בין שני מנועי המק עצמם; תזמונים זהים. שטח רועש (קהל): הפרש גבוה יותר, באותו סדר גודל כמו MLX↔ct2 במק.
- **ריל מלא במקביל:** ראו `cloud/E2E-REPORT.md`.
