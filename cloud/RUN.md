# ריצת ענן — מה סשן מתוזמן עושה (v10)

> המשימה המתוזמנת "עריכת סושיאל בענן" מפעילה כל שעה סשן ענן נקי עם ההוראה: "פעל לפי cloud/RUN.md בריפו crossfitrel/rel-video-cloud".
> כל חוקי הברזל, שלושת החוזים ושערי האישור של הסקיל `rel-social-video-editor` בתוקף. אין מייל להראל חוץ מכשל שדורש אותו. אין התראות שגרתיות במאנדיי.

## 0. סריקה זולה קודם (בלי bootstrap)
1. `ArtifactData list actions` (query `consumed == false`) + `list comments` (status `sent`) בעמוד הרוויו.
2. `get_board_items_page` על הגאנט: "מוכן לעריכה" **עם קובץ ב"קבצים"**; ו-`projects` ב-db במצב `ready_to_schedule`.
3. אין כלום ⇒ מסיימים כאן. בלי הודעות, בלי מייל, בלי bootstrap.

## 0.5 הכנה (רק כשיש עבודה, ≈4 דק')
```
add_repo crossfitrel/rel-video-cloud (push) → git clone --depth 1 … /home/claude/rel-video-cloud
cd /home/claude/rel-video-cloud && bash cloud/bootstrap.sh        # venv, מודל, puppeteer, ספריות+מצב מ-Drive של hayonhq
```
`bootstrap` יוצא בקוד 3 כש-`RCLONE_CONFIG_HAYONHQ_TOKEN` חסר ⇒ לא עורכים (בלי ספריות אין בירול/מוזיקה/פונטים).
במקרה כזה: `ArtifactData set system/health {"drive":"missing_token","at":<UTC>,"note":"צריך להגדיר טוקן Drive בסביבת הענן — CLOUD.md"}` — העמוד מציג באנר. **בלי מייל** (הריצה חוזרת כל שעה; מייל היה הופך לספאם).
כל כשל אחר שדורש את הראל ⇒ אותו מסמך health + באנר; מייל רק אם זה חוסם פרסום מתוזמן בתוך 24 שעות.
טוענים את הסקיל `rel-social-video-editor` ואת ה-reference של השלב בלבד.

## 1. מה הראל עשה בטלפון (עמוד הרוויו)
עמוד: https://claude.ai/artifact/B799jvngoLRUMYzoz1XqZn  (db: projects · comments · actions)
```
ArtifactData list comments  --out_dir /tmp/rv/in     ;  ArtifactData list actions --out_dir /tmp/rv/in
for each project referenced: bash cloud/state_sync.sh pull-project "<workdir>"
$REL_PY cloud/review_bridge.py apply --in /tmp/rv/in --out /tmp/rv/out
ArtifactData batch  ← /tmp/rv/out/db_writes.json            # consumed + סטטוס הערות
```
אחרי `apply`: הערות שהגיעו נמצאות בתור הקלאוד של הפרויקט ⇒ Claude Bridge רגיל (`review_cli.py tasks/claim/resolve`) → גימור → `verify-fixes` + Read על הגיליונות + `fix-verdict`. אישור לגימור ⇒ `approve` כבר הריץ את ה-runner; ממתינים ל-`finish_status.json` (גימור ארוך: ברקע + בדיקה כל דקה; 0% CPU לאורך זמן = תקיעה). אישור קאבר+קפשן ⇒ הפרויקט `ready_to_schedule` ⇒ שלב 4.

## 2. גלם חדש מהגאנט (טריגר)
```
get_board_items_page 18395578529  filter: color_mkrp4sgm any_of [11]  (מזהה התווית "מוכן לעריכה"; בכתיבה תמיד {"label": "..."}, לא index)  + includeColumns file_mkrpfxkz
```
- רק פריט **עם קובץ ב"קבצים"**. פריט בלי קובץ = לא שלנו (ארכיון Throwdown שעדיין מקומי) — מדלגים בשקט.
- **מנעול נגד ריצה כפולה:** לפני כל עבודה — סטטוס → {"label":"לאחר צילום, בעריכה"} + Update יחיד `[CLOUD-LOCK <session-id> <UTC>]`. ריצה אחרת מסננת רק את "מוכן לעריכה" ולכן לא תיגע בו. מנעול בן יותר מ-3 שעות בלי `[AUTO-EDIT` אחריו = ריצה שמתה ⇒ מחזירים ל"מוכן לעריכה" ומדווחים בצ'אט הריצה.
- הורדה: `get_assets` → `public_url` (תקף שעה) → `curl -L -o raw/NN.ext` מיד.
- `$REL_PY cloud/prep.py --name "<שם-עברי-לפי-תוכן>" --item <id> --dept <מחלקה> --title "<כותרת>" raw/*` (שער HDR, INPUT, תמלול, EDL, ROUGH).
- שלבים 1.5–2.5 של הסקיל כרגיל: ⟦SCRIPT⟧/⟦EDIT-LAYER⟧ מה-Updates, `video_eyes` + Read, `director_lessons` → `--director`, HOOK_PLAN, motion_plan אם יש רגע ברמה גבוהה.
- גימור (`local_finish_pipeline.py`) → `PREFLIGHT.json`. **רק `ready_for_harel` ⇒ {"label":"מוכן לבדיקה"}.** אחרת — מתקנים וחוזרים; לא מוסרים להראל.

## 3. פרסום לעמוד הרוויו
```
$REL_PY cloud/review_bridge.py export --out /tmp/rv/out        # projects.json + uploads_needed.json
for u in uploads_needed: video ⇒ review_bridge.py proxy --src <src> --out <proxy>  (≤14MB, 720p, צפייה בלבד)
   Artifact publish url=<review> asset:true file_path=<proxy|cover>  → url
   $REL_PY cloud/review_bridge.py record-asset --project <workdir> --kind video|cover --sha <sha> --url <url>
export שוב → ArtifactData batch set projects/<doc_id> מ-projects.json (if_version למסמך קיים)
```
Update אחד בפריט (`edit_update` אם קיים): `[AUTO-EDIT v2 DRAFT]` + לינק לעמוד + משך + פסק-דין ה-PREFLIGHT. לא מייל.

## 4. תזמון (state == ready_to_schedule בלבד)
- הקובץ רק מ-`schedule_approval.artifact_path` + `artifacts.verify().ok` + sha256 מול `artifact_checksum`.
- העלאה ל-`file_mm402fp7` ("סרטון מוכן"): `get_asset_upload_url` → PUT מהענן (curl) → `finalize_asset_upload` → `get_assets` → public_url.
- הקאבר: אותו מסלול ל-public_url ⇒ `videoThumbnailUrl`.
- `createScheduledPost` — התאריך **רק** מ-`date_mkrpvw3n` (UTC בבורד!), מותג לפי מחלקה (constants.md).
- **אימות:** `getScheduledPosts` חוזר — מועד, רשתות, קפשן מדויק, קאבר ב-static.metricool.com. לא תואם ⇒ `[SCHEDULE VERIFY FAILED]`, לא מסמנים.
- רק אחרי אימות: {"label":"תוזמן!"} + Update `[SCHEDULED-METRICOOL]` + `POST /api/meta/<name> state_override=scheduled` דרך הגשר + עדכון מסמך projects (state=scheduled).

## 5. גיבוי וסגירה
```
bash cloud/state_sync.sh push-project "<workdir>"     # כל פרויקט שנגעו בו (md5 נבדק)
bash cloud/state_sync.sh push                          # רוטציית מוזיקה, usage, לקחים, אינדקס
bash cloud/state_sync.sh archive-final "<workdir>" "<artifact_path>"   # אחרי תזמון
git add -A && git commit && git push                   # רק שינויי קוד/לקחים שנעשו בריצה (לא מדיה)
```
דיווח הריצה בצ'אט שלה בלבד: מה נכנס, מה נמסר להראל, מה נעצר ולמה. אין מייל אם הכל תקין.

## שעונים שנמדדו (10.10.26, 2 ליבות)
bootstrap בלי Drive 3:10 דק' · תמלול 65ש אודיו ≈ 25ש · שער HDR ל-HLG 65ש ≈ 3:20 דק' (SDR מהיר בהרבה) · גימור מלא — ראו CLOUD.md.
