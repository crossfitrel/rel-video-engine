# TESTING v9.13
עודכן 30.7.2026

## הרצה
```bash
cd "Social Video Editing System"
~/.rel-whisper/bin/python -m unittest discover -s tests   # 153 בדיקות (31 שערים · 32 רינדור · 28 מנוע החלטה)
python3 -m unittest discover -s tests        # פחות — אלה שדורשות PIL/ffmpeg מדולגות
python3 tools/system_doctor.py [--json]      # בריאות סביבה מלאה
python3 tools/golden.py run                  # regression דטרמיניסטי (5 cases)
python3 tests/e2e_driver.py <שם-עותק>        # E2E מלא מול השרת החי (עותקי בדיקה בלבד!)
```

## מה מכוסה
* **`tests/test_gates_block.py` (v8.6, 31 בדיקות) — שער שלב 0 של מיגרציית V2.**
  מזריק כשל אמיתי לכל שער ומוודא שהוא **באמת** חוסם, לא שהקוד קיים:
  caption_safety (פיסוק ששורד צריבה / חפיפה / מונוטוניות / תו ערבי) ·
  canon_lint (קובץ בירול חסר, כתוביות, ושקט על תיקייה נקייה) ·
  cut_qa (פריים שחור בגבול חיתוך על וידאו סינתטי אמיתי + חלוקת גבולות ב-speed) ·
  sh() timeout → rc=124 · tighten xfade+speed מקצה לקצה ·
  review-app: 409 על עריכה בזמן גימור (5 endpoints), 409 על base_token מיושן,
  404/400 במקום 500 · בדיקות מבניות: כל השערים לפני הקידום ל-FINAL, שערי הציר
  מחוץ ל-else של המסלול המלא, ‎--allow-missed 0 בהערכת הצעות למידה.
  **הכלל:** בדיקה שלא מזריקה כשל לא מוכיחה שהשער חוסם.
* **`tests/test_render_v2.py` (v8.7, 24 בדיקות) — מנוע הרינדור.**
  לוגיקה טהורה: כימות הציר המצטבר לפריימים (כולל שחזור הדריפט של ffmpeg שנמדד
  ‎+0.373ש), חיתוך cues/בירולים לגבולות סגמנט עם היסט-מקור מתוקן, יציבות מפתח
  המטמון (טקסט/תזמון/crf/band/frames מפסילים · **מוזיקה לא**), שימור תגי צבע.
  אינטגרציה עם ffmpeg: ספירת הפריימים של המאסטר = סכום `n_frames` בדיוק ·
  ריצה שנייה כולה מהמטמון · **שינוי כתובית פוסל סגמנט אחד בלבד** · הפלט בפרמטרי
  המסירה (1080×1920, yuv420p, תיוג צבע) · prune שומר את הסגמנטים הנוכחיים.
  ובדיקות חיווט: `--render-engine` קיים וברירת המחדל v1, v2 מדלג על קידוד
  הכתוביות וה-deliver, **וכל השערים של שלב 0 עדיין רצים ב-v2**.
* **`tests/test_artifacts.py` (v9.4, 21 בדיקות) — Artifact Store, הזרקת כשל אמיתית.**
  עשרת התרחישים שהוגדרו כחובה, כל אחד מזריק את הכשל ולא רק בודק מסלול תקין:
  5 ריצות מוצלחות → 5 סרטונים נגישים · ריצה כושלת אחרי הצלחה שומרת את המאושר ·
  ריצה כושלת לא מקבלת `output_hash` של FINAL ישן · מועמד חדש לא מזיז
  `approved_final` · הערה על גרסה ישנה פותחת **אותה** גרסה (וגם הערת legacy) ·
  `cleanup_work --keep-finals 0 --apply` לא נוגע ב-artifacts ולא מוחק FINAL_prev
  לא-מארוכב · אישור תזמון ננעל ל-`artifact_id` וגרסה מאושרת פגומה חוסמת תזמון ·
  קריסה באמצע יצירה (הזרקת `IOError` ל-`_link_or_copy`) לא משאירה גרסה חלקית ·
  מיגרציה חוזרת לא יוצרת כפילויות ו-dry-run לא נוגע בקבצים · קובץ חסר /
  checksum שהשתנה = תקלה מפורשת ולא גרסה תקינה. בנוסף: `activate` לוכד את
  ה-FINAL החי לפני ההחלפה, שחזור `pointers.json` שאבד, `reindex` מהדיסק.
* **`tests/test_artifacts_api.py` (v9.4, 7 בדיקות) — דרך `server.py` עצמו**
  (`REL_WORK_ROOT` זמני, `app.test_client`): האפליקציה באמת מגישה כל גרסה
  (השוואת בייטים), ברירת המחדל היא המאושרת, גרסה מאושרת שורדת מועמד חדש +
  ריצה כושלת, גרסה פגומה נחסמת ל-approve/activate (409), הערה נפתרת לגרסה שלה,
  השוואה, ו-activate בלי לאבד דבר.
* `tests/test_core.py` — derive_keep (כולל hook move), cuts_diff, revisions (create/undo/redo/restore/approved/compare), tasks (add/queue/claim/resolve/stale/force/fail), locks (double-acquire, stale-pid recovery, release, resume_flags), registry (UUID יציב, rebuild אחרי מחיקת DB, find, derive_state).
* `tests/test_learning.py` — classify v2 מכיר את כל סוגי האירועים האמיתיים, reason עליון, reason_code מפורש, אירועי רעש מסוננים, ספים ≥6/≥3, golden.compare (false/missed/duration).
* `tests/e2e_driver.py` — 21 בדיקות: זרימת Claude Bridge מלאה, resolve בלי revision נדחה, stale-task נעצר, undo/redo/restore, אישור כפול=ריצה אחת, אין FINAL חלקי בכשל, נעילה משתחררת, resume מדלג recut+whisper.
* Golden Set (`golden/`) — 5 fixtures אמיתיים (words+expected_edl, בלי מדיה): שינה-והתאוששות, טיפ-אחד-HSPU, אופן-גים-השקה, מאסל-מן-רוטטור-קאף, מי-אמר-שמאוחר-מידיי. `golden.py build` מקבע התנהגות; `run --policy X` בודק candidate (false cuts אסורים; ריכוך מוגבל `--allow-missed`).

## כללי בדיקות
* אסור לגעת בפרויקטים אמיתיים ב-`_work` — עותקי בדיקה בלבד (`בדיקת-מערכת-*`).
* אסור בדיקות מול Monday/Metricool אמיתיים.
* E2E "done" מלא הוכח 23.7 על עותק טיפ-אחד: gate PASS → FINAL אחרי QA PASS → cut_qa 6 גבולות → canon PASS_WITH_WARNINGS; "failed+resume" הוכח על עותק שינה.

## v9.13 — בדיקות חדשות (16.8.26)
- `test_lesson_registry.py` — "אין לקח בלי אוכף": אודיט על הריפו האמיתי +
  הזרקת אוכף-שנעלם/שער-שהוחלף-אכיפה (הלקח מ-v9.11: fade/eof שנסוגו בשקט).
- `test_preflight_critic.py` — כל בדיקת-כאב של הראל עם הזרקת-כשל ומקרה נקי,
  כולל "דוקטרינת bed_end מוצהרת גוברת על שומר ה-CTA".
- `test_director_lessons.py` — דטרמיניזם, קיבעון בתוך פרויקט (חוק ברזל 4),
  סינון bursts, בידוד cohort.
סה"כ הסוויטה: **403** (16.8.26). תיקון נלווה: `render.py` ↔ `captions_overlay`
(BRAND_PROFILES) — נשבר בשקט ב-3.8 ונתפס ע"י `test_render_v2`; ראה L27.

## Visual Hook Engine (11.9.26)
> Visual-hook coverage includes off/shadow/NO_OP legacy parity, crop rendering in both engines, speed and source-cut mapping, full-intro offsets, B-roll/caption reservations, original speech preservation, stable digests/cache behavior, stale review tokens, locks and immutable artifacts. Real FFmpeg failure injection must detect black/white one-frame defects, wrong-source frames and A-B-A flashes even at declared transitions. Each new blocking gate has protects/cost_of_blocking/fallback and an injected failure test. Run test_visual_hook*.py, the existing full suite, golden checks, system doctor and gate/lesson audits. Creative thresholds require measured Harel-approved examples; scene energy and effect count alone are reporting metrics, not new blockers.

```bash
~/.rel-whisper/bin/python -m unittest tests.test_visual_hook tests.test_visual_hook_render tests.test_visual_hook_qa tests.test_visual_hook_review   # 134
REL_BROLL_USAGE_COMMIT=0 python3 tools/bench/visual_hook_e2e.py    # עותקים בלבד (.e2e/visual-hook)
python3 tools/bench/visual_hook_scan.py && python3 tools/bench/visual_hook_calibration.py probe
```
נמדד 11.9.26: 693 בדיקות, רק 2 כשלי vision של בירולים שקדמו לשינוי · gate audit 148/0 · lesson audit 63/170/0 · golden OK · doctor 0 FAIL.
