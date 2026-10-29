# מערכת עריכת הסושיאל — v11 "זול ועצמאי" (29.10.26)

**המטרה:** מחשוב בלי קרדיטים של Claude, שיפוט במודלים זולים, מצב ורוויו מחוץ ל-Artifact, וגיבוי ל-Codex/ChatGPT. כל חוקי הברזל, שלושת החוזים ושערי האישור נשארו כמו שהם.

| מה | איפה (v11) |
|---|---|
| מצב: projects · comments · actions · jobs · runs · costs · system_health · config | Supabase `xfsvbpqbfmqlwgyusrww`, סכמה `video` (סגורה ל-anon; הכל דרך פונקציית edge `video`) |
| פרוקסי וקאברים | Supabase Storage, bucket פרטי `video-review` (sha256 נבדק בהורדה חוזרת) |
| עמוד הרוויו | **rel.fit/review** → Netlify `rel-video-review` (מקור: `review-web/`). כניסה בקישור אישי `#k=` שנשמר בטלפון |
| מחשוב | GitHub Actions `.github/workflows/video-worker.yml` → `cloud/worker.py run` (prep · notes · finish · cover) |
| שיפוט | `tools/llm.py` → `op=llm` בפונקציה. Haiku: סיווג, הגיון לשוני, בירול-לתווית · Sonnet: במאי, הוק, קפשן, vision, מיפוי הערות · Opus: הסלמה בלבד |
| טריגר | webhook של Monday (660374019, סטטוס בגאנט) + כפתורי העמוד → `video.jobs` → workflow_dispatch. אין polling |
| workdirs | ענף `libs` (`push-project` אחרי כל שלב + משיכה חוזרת והשוואה, L143) |
| Artifact הישן B799… | ארכיון לקריאה בלבד עם הפניה |
| Codex/ChatGPT | `AGENTS.md` + `cloud/video_api.py` |

**סודות (רק בכספת של Supabase, אף פעם לא בריפו):** `monday_token` (קיים) · `video_admin_key` · `video_review_token` · `anthropic_api_key` · `github_dispatch_token` (PAT עם Actions: write על הריפו בלבד). ה-runner מקבל רק טוקן חד-פעמי לג'וב (14 שעות).

**מה רץ איפה:** חישוב דטרמיניסטי + Sonnet ⇒ Actions. תזמון Metricool ⇒ צעד Claude קצר (ג'וב `schedule`, runner=claude), כי אין טוקן Metricool בכספת. שיפוט שמעבר ל-Sonnet (שער שנכשל פעמיים, הערה לא ממופה, PREFLIGHT לא עבר) ⇒ ג'וב `judge` לסשן Claude אחד וממוקד.

**תקרות עלות:** `video.config.caps` (‎$1.5 לריל · ‎$5 ליום · 2 קריאות Opus לריל), נאכפות בשרת. דוח: `python3 cloud/video_api.py costs '{}'` או `video.v_cost_per_day`.

**מדידה:** ראו `cloud/BENCH-v11.md`.

---

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
| הרצה | (v10, הוחלף) מ-v11: אירוע בלבד, אין משימה מתוזמנת — `cloud/RUN.md` |

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

## ספריות ומצב — ענף `libs` בריפו הפרטי (בלי טוקן, מ-11.10.26)
משימות מתוזמנות של claude.ai רצות בסביבת `cloud_default`, שלא קוראת משתני סביבה של claude.ai/code — טוקן Drive לא יכול להגיע אליהן (נבדק 11.10.26 בריצת אימות: `token_present:false` אחרי שהראל הדביק). לכן:
- הספריות (בירולים 3.2GB, מיכאל לוי, brand-assets כולל מוזיקה, tools-assets, פתיחים קבועים) והמצב (קבצי מצב + פרויקטים פעילים) יושבים בענף `libs` של `crossfitrel/rel-video-cloud`, נגישים דרך ה-git proxy של הסשן — אותו מסלול כמו הקוד.
- `cloud/libs_git.sh` (pull · push · pull-project · push-project · archive-final). `state_sync.sh` מעביר אליו אוטומטית כשאין `RCLONE_CONFIG_HAYONHQ_TOKEN`.
- קובץ מעל 90MB נשמר כחלקים `*.relsplit.000…` + `*.relsplit.sha256` ומורכב ומאומת בפריסה.
- ארכיון ה-FINAL = עמודת "סרטון מוכן" במאנדיי; `archive-final` רושם sha256 ב-`state/מסירות/ledger.txt`.
- Drive של hayonhq נשאר גיבוי ומקור הקציר (בירולים חדשים מהמק): אחרי קציר במק → `rclone copy` לתיקייה זמנית → דחיפה לענף `libs` (או דרך סשן שמחזיק את הספרייה).
- rclone נשאר אופציונלי: אם קיים טוקן בסביבה, `state_sync.sh` עובד מול Drive כמו קודם.

## מעבר רשמי (12.10.26)
- הראל אישר מהטלפון ⇒ `com.rel.review-app` במק כובה (`launchctl unload`, הפיך ב-`load`; ה-plist לא נמחק). העמוד בטלפון הוא הרוויו היחיד.
- העלאה ל-Monday מהענן נמדדה: PUT של 60MB ל-URL חתום של Monday = HTTP 200 ב-57ש (~1.1MB/s) — לא צריך את מסלול Desktop Commander במק.
- נשאר במק בכוונה: פודקאסט "מדברים כושר" (+ captions-app 5111 והטאנל שלו). קציר בירולים מגלריית Photos (osxphotos) הוא כלי מק בלבד; בירול חדש מגיע לענן רק אחרי דחיפה לענף `libs` (סשן Claude עם המק מחובר: stage → `libs_git` stage_tree → push).

## אימות מעבר ל-libs (11.10.26)
- **ריצה מתוזמנת אמיתית (cloud_default, בלי טוקן):** bootstrap 0 · `[libs_git] pull ✓ · בירולים 638 · מוזיקה 342` · unittest 951/0 · doctor 0 FAIL · gates 217/0 · lessons 142/0.
- **ריל מלא בענן (עותק E2E של אביגיל):** גימור מלא עבר, PREFLIGHT "מוכן להראל" (0 high), loudness ‎-14.1/TP ‎-0.9, V7 54/54, canon+qa PASS, SSIM מול FINAL של המק 0.9985. נמצא ותוקן בדרך: L136 (ראיית בירול אבדה בהעתקה), L137 (שער G_music_gap נפל ב-0.03 LU — עכשיו לולאה סגורה).

## אימות (10.10.26)
- **baseline בענן (ריצה אחרונה, 199ש):** 941 בדיקות · 935 עוברות · 6 נכשלות רק מחוסר ספריות שעוד לא נמשכו מ-Drive (מאגר הבירולים עם ראיות vision, נכס הפתיח הקבוע, ספריית המוזיקה המלאה) — נסגרות כשהטוקן מוגדר. doctor 0 FAIL · gates 216/0 · lessons 140/0 · skill pack תואם (v10.0).
- **שער HDR:** מכויל מול tonemap.swift על ריל מאושר: SSIM 0.981 על INPUT, 0.971 FINAL↔FINAL.
- **סקילים:** rel-social-video-editor v10.0 הותקן (v13 ב-claude.ai) + a-rel-router, rel-broll-creator, rel-audience-video-editor, rel-thumbnail-creator עודכנו (VIDEO-CANON v10, hdr_gate, סנכרון בירולים ל-Drive אחרי קציר).
- **פרויקט claude.ai:** ידע 1,996,132 → 828,443 מתוך 2,000,000 (62 מסמכים). 853 קבצי המדיה שהועלו לפרויקט (5.6GB) — עותק מאומת ב-Drive (מניפסט `מניפסט/manifest-2026-10-10.tsv`, md5 לכל קובץ); הסרתם מהפרויקט ממתינה לאישור הראל. שומר: `tools/project_hygiene.py` + L134.
- **תמלול:** דיבור נקי — הענן שונה מהמק ב-1 מילה מ-45 (2.2%), בדיוק כמו ההפרש בין שני מנועי המק עצמם; תזמונים זהים. שטח רועש (קהל): הפרש גבוה יותר, באותו סדר גודל כמו MLX↔ct2 במק.
- **ריל מלא במקביל:** ראו `cloud/E2E-REPORT.md`.
