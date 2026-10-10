# ARCHITECTURE — Social Video Editing System v8.8
עודכן 30.7.2026 (v8.6 שלב 0 · v8.7 שלב 2 של מיגרציית V2)

## Visual Hook Engine (11.9.26) — שלב וידאו אופציונלי

> Visual Hook Engine is an optional local, video-only stage after the resolved recut/tighten/speed/word-reconciliation timeline and before body visual composition. It creates a frozen visual_hook_plan.json consumed by both v1 and v2. v1 routes the derived visual_base through existing B-roll; v2 compiles the same plan into source segments before B-roll and captions. Clean EXPORT remains unchanged. Speech, EDL, body frame count, caption timing and existing audio behavior are preserved. NO_OP and SMART_PUNCH_IN are supported; other registry recipes remain disabled unless explicitly released. Missing preference defaults to off; shadow creates evidence without changing media. Full format intros default to NO_OP. Applied plan, render receipt and report are frozen with the candidate artifact and bound to existing approval/checksum rules.

קוד: `tools/relvid/visual_hook.py` (החלטה) · `tools/relvid/hook_render.py` (v1 perspective על הגוף הנקי ⇒ `VISUAL_BASE`; v2 קומפילציה פר-סגמנט לשרשרת `[base]`) · `tools/visual_hook_qa.py` (VH1-VH8) · `tools/visual_hook.py` (CLI). מדיניות: `tools/visual_hook_policy.json` (לא חלק מ-edl-policy.json).

**סטטוס (11.9.26):** מיושם ונבדק על עותקים; הראל אישר את השוואת הפיילוט (מי-אמר-שמאוחר-מידיי ×1.04, סקאלת-הבריאות ×1.06). ברירת מחדל `off`, אין קוהורט `auto`. דוח: `handoff/visual-hook-engine/IMPLEMENTATION_REPORT.md`.

## שינויי v8.8 (שלב 1) — מנוע ההחלטה

**מרחב החלטות סופי במקום ייצור זמנים.** `candidates.py` מונה דטרמיניסטית את כל
נקודות העריכה האפשריות עם תכונות נמדדות. המודל בוחר ומתייג מתוך הקבוצה הזו
בלבד; `provider.validate_answer` דוחה כל מזהה שאינו קיים בה. הזיה של timecode
אינה "נדירה" — היא בלתי אפשרית מבנית.

**חמישה פאסים** (`edit_director.py`): מפיק (בריף: קהל/מטרה/CTA יחיד) → הבנה
(קשת סיפור, סיווג פאוזות לפי ראיה, סיכוני נטישה) → במאי (תוכנית עם ביטחון,
נימוק, רווח וסיכון לכל החלטה) → ביצוע דטרמיניסטי (validator → `edl.json` →
מנוע הרינדור) → מבקר **עיוור לנימוקים** → ציון ברובריקה. מתחת לסף — חזרה
אוטומטית לפאס התכנון עם focus קונקרטי, עד `--director-max-loops`.

**שכבת ספק** (`relvid/provider.py`): `api` · `chat` (כרטיסי בקשה בדיסק, עובד
בלי מפתח) · `replay` (מה-cache בלבד). מפתח ה-cache נגזר מ-(תפקיד, תוכן קובץ
הפרומפט, payload קנוני) — content addressed. **כלל:** שום מטא-דאטה משתנה
(חותמת זמן, מזהה ריצה, שם תיקייה) לא נכנס ל-payload של פאס — אחרת המפתח משתנה
בכל ריצה וה-cache אף פעם לא נפגע.

**רצפה פיזית:** `tighten_to ≥ 0.20ש`. האוויר שנשמר מתחלק לשני צידי החיתוך, ולכן
מתחת לזה הגבול נוחת קרוב מדי למילה. זה ההסבר ל-0.22ש של v1.

**מקור פר-סגמנט:** `segment_sources.json` מצהיר איזה סגמנט נלקח מאיזה קובץ.
נכשל קשה על קובץ חסר, חלון באורך שונה, או תגי צבע שאינם תואמים ל-INPUT.

## שינויי v8.7 (שלב 2) — מנוע רינדור
```
v1:  INPUT →crf23  recut →crf18  tighten →crf18  broll →crf20  music(copy)
     captions →crf16  loudness(copy)  deliver →crf23      = 4-7 דורות וידאו
v2:  segment_i(cut+broll+captions) →crf23   ×N במקביל
     concat -c copy → master.mkv (h264 + PCM)
     audio_mix -c:v copy → FINAL                          = דור וידאו אחד
```
* `relvid/render.py` — `Segment`/`Timeline`, מפתח מטמון לפי hash תוכן, רינדור
  מקבילי, `concat -c copy`. הסגמנטים מגיעים מ-`sync.tight_keeps_in_source`
  (אותה פונקציה שהאפליקציה מציירת ממנה) — אין מתמטיקת צירים חדשה.
* **ספירת פריימים נאכפת** (`n_frames` + `-frames:v`) על הציר המצטבר — בלי זה
  נמדד דריפט של +0.373ש. **ההאצה נמדדת** מהמדיה ולא נלקחת משדה.
* **תגי צבע עוברים כמו שהם** (`setparams`) — לא כופים bt709, כי קיים INPUT
  אמיתי מתויג bt2020.
* המוזיקה **לא** במפתח המטמון ⇒ שינוי מוזיקה/מפלס = אפס רינדור וידאו.
* מאחורי `--render-engine v2`; ברירת המחדל v1 עד שהשער `bench/render_ab.py`
  יורחב מעבר ל-5 פרויקטים.

## שינויי v8.6 (שלב 0)
* **תיקיית העבודה יצאה מ-iCloud** → `~/rel-video-work`. הנתיב נפתר דרך
  `relvid/paths.py` (env `REL_WORK_ROOT` → `tools/paths.json` → ברירת מחדל
  היסטורית `SYSDIR/_work`), כך שבלי הקונפיג ההתנהגות זהה לחלוטין לקודם.
  שורש: eviction באמצע גימור + סריקה של 38 תיקיות על filesystem מסונכרן בכל
  טעינת דף. תוצרים סופיים ממשיכים ל-iCloud כרגיל. חזרה: `migrate_work_root.py --rollback`.
* **כל השערים רצים לפני הקידום ל-FINAL** ונאספים ל-`blockers`; כשל משאיר
  `FINAL_PENDING.mp4` + `gate_blockers.json`. `cut_qa`, `caption_safety` ו-`canon_lint`
  הפכו מדיווח/קוד-מת לשערים חוסמים.
* **G6b** — שער כתוביות שנמדד מהמדיה: ASR חוזר על האודיו הנקי (לפני המוזיקה),
  רץ ברקע במקביל ל-music/captions/loudness/deliver ולכן עולה ~1.7ש wall-clock
  במקום ~27ש. G6 הישן משווה שתי נגזרות של אותו חישוב ומדווח 0.000ש תמיד.
* **`sh()` תופס TimeoutExpired** → rc=124, ולכן ריצה תקועה מסומנת `failed`
  במקום להישאר `running` לנצח ב-`finish_status.json`.
* **review-app:** 6 endpoints שכותבים בודקים נעילת גימור (409), `/api/save` מוגן
  מ-lost-update דרך `edl_token`, ו-`errorhandler` מחזיר 404/400 במקום 500 HTML.

## עקרונות
1. **הקבצים על הדיסק הם מקור האמת.** SQLite (`_work/.index/registry.db`) הוא אינדקס בלבד — נבנה מחדש בכל עת מ-`project_registry.py rebuild` / `review_cli.py rebuild-index`.
2. **זהות פרויקט = `project_id`** (UUID ב-`project_manifest.json`), לא שם תיקייה. רינון לא שובר כלום.
3. **כל כתיבה מהותית אטומית** (tmp+os.replace — `relvid.atomic_write_json`).
4. **שום דבר לא נדרס בשקט:** כל שינוי EDL/תמליל = revision; FINAL קודם מגובה `FINAL_prev_*`; revision מאושר מסומן ולא נמחק.
5. Python + Flask + HTML יחיד. אפס תלויות חדשות מעבר לקיים (stdlib, sqlite3, PIL, ffmpeg).

## שכבות
```
Monday (בריף/סטטוס)  →  הכנה דטרמיניסטית             →  review-app (5112)        →  גימור
match_intake             align_words → edl_build →        server.py + index.html      run_finish.py (נעילה/run)
                         edl_cut → ROUGH                  revisions·comments·runs       └ local_finish_pipeline.py
                                                                                          recut→whisper→reconcile→
ספריית הליבה: tools/relvid/                                                              tighten→gate→broll→music→
  __init__ (אטומיות/hash)· edl_utils (derive_keep/diff)                                  captions→loudness→qa→
  registry (מניפסט+SQLite)· revisions · tasks · runner                                   FINAL(רק אחרי PASS)→cut_qa→canon
Claude Bridge: tools/review_cli.py  ·  בריאות: tools/system_doctor.py
למידה: learn_from_edits (v2 shadow) → policy-proposals → golden.py regression → אישור הראל → edl-policy.json (+policy-history)
```

## מצב פר-פרויקט (בתוך `_work/{שם}/`)
`project_manifest.json` (זהות+media health) · `edl.json` (+`edl.machine.json` בסיס) ·
`revisions/` (snapshots+index) · `comments.json` (הערות מובנות/משימות קלאוד) ·
`runs/` (רשומות ריצה+לוגים) · `.finish.lock` (נעילת ריצה, תיקייה אטומית) ·
`finish_status.json` · `corrections.jsonl` (למידה) · `qa_report.json` · `cut_qa_report.json` ·
`canon_report.json` · `gate_fail.json` · `APPROVAL.json` · `review_rounds.json` (legacy v6) ·
`note_corrections.json` (v7.8 — מה תוקן אוטומטית מההערות ומה נשאר עמום).

**מדידה (v7.8):** כל שלב גימור נמדד ונשמר — `finish_status.json → timings`,
`runs/run_*.json → stage_timings/total_secs`, שורת ⏱ ב-`FINISH_REPORT.md`.
האפליקציה גוזרת מזה הערכת זמן-נותר (חציון ריצות מוצלחות קודמות). הכלל:
לא מייעלים שלב בלי מספר לפני ואחרי — ראה `ASR-BENCH.md` כדוגמה.

## מצב תפעולי (נגזר, לא מתחרה ב-Monday)
`not_started → in_review → approved → running → final`, ענף `failed` (עם blocker). נגזר מקבצים ב-`registry.derive_state`.

## החלטות ארכיטקטורה
* **אין git** בתיקיית iCloud (מדיה כבדה + סנכרון = קונפליקטים). ה-versioning = Revision Engine.
* הנעילה נוצרת כבר ב-spawn (מסומנת `spawning`) ותהליך הריצה מאמץ אותה — סוגר את חלון ה-race של אישור כפול; נעילה יתומה (pid מת / spawning>120ש) משוחררת אוטומטית.
* resume: אם הריצה הקודמת נכשלה/קרסה וה-EDL לא השתנה — `--no-recut --skip-whisper`.
* Descript: מחוץ לזרימה. שרידים פעילים נוקו (brand-assets, review_suggestions.md, align_reconcile). fallback חירום מתועד בלבד.
