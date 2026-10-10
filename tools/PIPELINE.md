## v9.37 (4.10.26) — שכבת Motion Graphics — runbook
**החלטה קודם, רינדור אחר כך. רגע בינוני גרוע מאפס.** סקיל: `rel-motion-graphics` · עיצוב: `tools/motion/MOTION.md`.
```bash
# 1. מועמדים מהתמליל (לא החלטה)
~/.rel-whisper/bin/python tools/motion_build.py propose --workdir W
# 2. Claude כותב W/motion_plan.json (ייחוס: ~/rel-video-work/_motion_demo/grips/motion_plan.json)
#    זמנים מ-words_final (ציר סופי) · כל טקסט מהתמליל או facts עם source · zone: auto/body/top
# 3. שערים לפני רינדור
~/.rel-whisper/bin/python tools/motion_build.py check --workdir W
# 4. לולאת ביקורת: Read על W/MG_SNAPS.jpg, ציון 1-10 × 7 צירים, עד ≥8
~/.rel-whisper/bin/python tools/motion_build.py snap --workdir W --base W/EXPORT_TIGHT.mp4 --at 1.2,7.5,…
# 5. גימור — השלב motion רץ לבד כשיש motion_plan.json (on = חובה, off = מדלג)
~/.rel-whisper/bin/python tools/local_finish_pipeline.py --workdir W … --motion auto
# 6. Read על W/MG_SHEET.jpg + MOTION_REPORT.json לפני הצגה להראל
```
שלב `motion`: אחרי בירול/פתיח קבוע, לפני מוזיקה. `suppress_captions` ⇒ `words_captions_mg.json` לצריבה ול-V7. בירול מתחת ל-MG נמדד על הבסיס שלפני ה-MG. חוסמים: MG0 MG1 MG2 MG4 MG5 MG6 MG8 · מדווחים: MG3 MG7.


## v9.35 (23.9.26) — L104: ייצוב קצוות קליפים במקור — ⚠️ בוטל 24.9 (הראל: ההאטה נראית). נשאר L105 בלבד
גלם אייפון רב-קליפי: כל קליפ נפתח/נסגר בלחיצה על הטלפון ⇒ פלאש של 1-5 פריימים בגבול החיתוך
("קפיצה מוזרה של קטע כפול"). אחרי concat ולפני EDL:
`~/.rel-whisper/bin/python tools/clip_edge_stabilize.py --workdir W` — מחליף רק וידאו של ראש/זנב
לא-יציב ב"האטה רציפה" של הפריימים היציבים (משך ואודיו זהים ⇒ תמלול/EDL/tight_keeps תקפים). מקור ב-`_trash/clips_prestab/`,
דוח `clip_edge_report.json`. הקלטות מסך מדולגות (`--skip`). אוכף: `cut_qa` דגל `flash_frame` (מדווח).
אחרי ייצוב INPUT — גימור מלא (לא `--refinish`: EXPORT_TIGHT ישן).

## המחשה ויזואלית (v9.20) — runbook

**החלטה קודם, ציור אחר כך. ברירת המחדל היא אפס.**

```bash
# 1. האם הסרטון הזה בכלל מרוויח המחשה, ואיפה
python3 tools/illustration_gate.py --workdir W --explain
#    decision=none  → סיימנו. זו התשובה השכיחה והתקינה.
#    decision=illustrate → ממשיכים, עם החלון והציטוט שהוא החזיר.

# 2. איורים — Gemini / Nano Banana דרך rel-chatgpt-graphics (אפס עלות).
#    תצוגה אחורית תמיד; תצוגה קדמית רק אם הישות חיה בצד השני.
#    בפרומפט לתצוגה הקדמית חובה שלילה אנטומית מפורשת
#    ("עמוד השכמה לא נראה"), אחרת המודל מחזיר את אותה תצוגה.

# 3. מסכות — **מפרידים במקור, לא באלגוריתם** (L49). שני שרירים סמוכים
#    שנוגעים בצבע אינם ניתנים להפרדה מהאיור. מבקשים מ-Gemini רינדור שני של
#    אותה קומפוזיציה עם צבע-מפתח רווי לכל שריר (כחול/ירוק/צהוב) ומחלצים
#    לפי גוון. האטלס למסכות בלבד — הלוח שמוצג לצופה נשאר האיור היפה.
python3 tools/illustration_build.py atlas --out W/illus \
    --atlas W/illus/atlas.png --base W/illus/base.png --crop '[x0,y0,x1,y1]'
#    → atlas_report.json כולל registration.iou (נמדד 0.9157 באטלס הראשון).
#      IoU נמוך = מסכות שנראות סבירות ומאירות את המקום הלא-נכון ⇒ אטלס מחדש.
#
#    מסלול נסיגה בלבד — תפר ידני. **שם נכנסה הטעות של הטרס מינור (21.8.26):**
#    python3 tools/illustration_build.py segment --base W/illus/base.png --out W/illus
#    python3 tools/illustration_build.py masks --out W/illus --crop '[..]' \
#        --assign '{"infra":[2],"supra":[1]}' --seam '{"..."}'

# 4. ⚠️ אימות ישות→אזור — IL5, נכשל-סגור
python3 tools/illustration_build.py regions --workdir W --illus W/illus \
    --plates '{"post":"base_crop.jpg","ant":"ant_crop.jpg"}' \
    --map '{"אינפרספינטוס":"infra","סאבסקפולריס":{"region":"sub","plate":"ant"}}'
#    → Read על W/illustration_check.png. כל ישות צבועה על הלוח שלה.
#    תואם ⇒ verified=true בכל רשומה. לא תואם ⇒ מתקנים את התפר וחוזרים.
#    **בלי זה שום דבר לא נכנס לסרטון.**

# 5-7. קומפוזיציה → רינדור → קלף
python3 tools/illustration_build.py compose --workdir W --illus W/illus \
    --cues W/cues.json --dur 6.0 --plates '{"post":"base_crop.jpg"}'
python3 tools/illustration_build.py render --workdir W
python3 tools/illustration_build.py card --workdir W --base W/FINAL.mp4 --at 22.6
#    המיקום נפתר מהפריים (פנים + רצועת כתוביות + מפת עומס). מעדיף את
#    **רצועת הגוף — מתחת לראש, מעל הכתוביות** — וממורכז אופקית,
#    והרקע של האיור מוסר. IL8 חוסם אם אין מיקום שאינו נוגע בפנים.
#    בדיקה יבשה לפני ההרכבה:
#    python3 tools/illustration_place.py --video W/FINAL.mp4 --from 22.6 --to 28.6
#    הפלט מדווח: גודל+מיקום · האם ברצועה המועדפת ואם לא — למה · יחס
#    הפנים שנשמרו/נמצאו (יחס נמוך = גלאי רועש, המיקום על בסיס רעוע)

# 8. רישום לצורך קצב על פני הקטלוג
python3 tools/illustration_gate.py --workdir W --record 1
```

**שתי מלכודות (L48):** אם הפריים יוצא שחור וה-DOM נראה תקין — או שהרנטיים
של HyperFrames לא הוסר (`render` מסיר אותו), או שנכס לא הוטמע base64
(`mask-image` מ-`file://` מוחזר ERR_FAILED והשכבה נעלמת בשקט).

**מינון:** אחת לסרטון · שנייה רק מעל 84 ובמרחק ≥4ש עם `exception_reason` ·
לא על Hook/CTA · לא מעל בירול · לא בתוכן המרה.

# צנרת עריכת סושיאל v7 — Runbook (R.E.L)

## Visual Hook Engine (11.9.26) — פתיחה חזותית אופציונלית

> After recut/tighten/speed and final-word reconciliation, resolve the clean body, B-roll/layer reservations and full-intro status. Off follows the legacy path unchanged. Shadow writes visual-hook analysis/candidates/plan/report without applying pixels. Applied hooks render from a frozen plan: v1 uses visual_base in all B-roll branches; v2 compiles per-segment hooks before B-roll/captions. Never overwrite EXPORT. Continue existing music/captions/loudness/delivery/intro/QA flow. Hook QA validates frame count, speech preservation, source identity, reservations and declared transitions; declared cuts never exempt accidental flashes or corrupt frames. Existing approval, locks, preflight, artifact promotion and schedule checksum checks remain mandatory. Use tools/visual_hook.py analyze/plan/preview/validate for isolated diagnostics; test E2E only on copies in _work/.e2e/.

```bash
# אבחון מבודד (לא נוגע ב-EXPORT, לא מגמר):
python3 tools/visual_hook.py analyze  _work/<שם>
python3 tools/visual_hook.py plan     _work/<שם> --mode shadow
python3 tools/visual_hook.py preview  _work/<שם> --render-engine v1 --side-by-side
python3 tools/visual_hook.py validate _work/<שם>          # exit 2 = HOOK_REVIEW_STALE
# גימור עם תוכנית מאושרת (בדרך כלל מהאפליקציה):
python3 tools/local_finish_pipeline.py ... --visual-hook shadow --visual-hook-plan <approved.json>
```

## v9.18 (18.8.26) — אימות תיקונים: קלאוד בודק לפני הראל

אחרי כל גימור של סבב תיקונים (נוצרה גרסה עם `fixes`) — **חובה, לפני
שמדווחים "מוכן לבדיקה"** (L45, נאכף ב-P14 של preflight):

```bash
python3 tools/review_cli.py verify-fixes PROJECT --reel
# → FIX_VERIFY.json + fix_verify/<artifact>/sheet_*.jpg + CHECK_REEL.mp4
# → Read על כל גיליון (זו הצפייה — חוק הראייה), ואז פסיקה פר-פריט:
python3 tools/review_cli.py fix-verdict PROJECT cmt_XXX verified --evidence "..."
python3 tools/review_cli.py fix-verdict PROJECT cmt_YYY not_fixed --note "..."   # חוזר לתור
python3 tools/fix_verify.py --workdir W [--artifact ID] [--reel]                 # ישיר, בלי registry
```

- מדידה ≠ פסיקה: `machine.status` הוא ראיה; verified רק אחרי קריאת הגיליון.
- `not_fixed` ⇒ לתקן + גימור נוסף לפני מסירה. לא מוסרים סבב שידוע שנכשל.
- האפליקציה: צ'יפ 🤖 פר-פריט, "🖼 ראיות", כפתור "🤖 בדוק רק מה שלא אומת"
  (review_plan_focus), ו-CHECK_REEL דרך `/fixverify-media/...`.
- דיווח להראל: "תוקנו ואומתו N/M, נשאר לך ~Xש" + פסק-דין preflight.

## v9.15 (17.8.26) — האצה בלי הידוק מחדש
```bash
# תוכנית פערים שכבר הוכרעה (במאי / הראל באפליקציה) + האצה, בלי חיתוך שתיקות נוסף:
~/.rel-whisper/bin/python tools/run_finish.py --workdir "_work/{שם}" \
  --content-type value --brand rel --tighten on --speed 1.15 --min-sil 99
```
`--speed` נאכף רק בתוך שלב ההידוק, ולכן עד כה כל האצה גררה סבב חיתוך
שתיקות נוסף מעל תוכנית שכבר עברה שיפוט. נמדד (על-הלוח-כוח-וגיל): תוכנית
של 7 תפרים יצאה עם 15 — 0.117/ש → 0.259/ש, מעל התקרה. `--min-sil 99` הופך
את השלב ל-speed-only: אפס שתיקות נחתכות, ההאצה מוחלת. `--tighten off`
נשאר המסלול הנכון כשאין האצה. לקח L39 · `tests/test_speed_without_retighten.py`.

## v9.14 (17.8.26) — חוק הראייה
```bash
# הצפייה עצמה — bundle של גיליונות מגע + תמליל + קצב:
python3 scripts/video_eyes.py analyze VIDEO.mp4 --clean
python3 scripts/video_eyes.py analyze RAW.mp4 --no-audio --max-frames 24   # שיוך גלם
python3 scripts/video_eyes.py strip CUT.mp4 00:01:23 --window 2 --count 12 # הערה של הראל → חותמת זמן
python3 scripts/video_eyes.py frame EXPORT.mp4 00:00:07.5                  # פריים לקאבר
# ואז — Read על כל contact_*.jpg ועל transcript.txt. זו הצפייה. אין לה תחליף.

# המדידה — מספר לכל שער ראייה:
python3 tools/vision_check.py --video FINAL.mp4 --workdir "_work/{שם}"   # → VISION.json
python3 tools/vision_check.py --build-reference <המאושרים>               # סף עגול → סף מדוד
```
**חוזה עבודה:** אין אמירה על תוצר — הוק, שוט, קפשן, קאבר, "הסרטון טוב" —
בלי שהגיליונות נפתחו בסשן הזה. `report.md` הוא מטא-דאטה. כל הערה בחותמת
זמן. שערי V1-V7 **מדווחים ולא חוסמים** עד שיימדדו (`--build-reference`) —
עקרון "אין שער חוסם עם סף לא-מדוד". `P13_vision_bundle` ב-preflight תופס
תוצר שאיש לא פתח, ו-bundle ישן מה-FINAL = ממצא high.

## v9.13 (16.8.26) — מבקר-קדם, לקחים אכופים, למידה מ-n=1
```bash
# פסק-הדין "אם הראל צופה עכשיו — מה הוא מתקן?" (רץ אוטומטית בגימור, שלב 9f2):
python3 tools/preflight_critic.py --workdir "_work/{שם}"      # → PREFLIGHT.json
# רשומת הלקחים — כל לקח עם אוכף; נכשל כשאוכף נעלם (שער ב-doctor):
python3 tools/lesson_registry.py --audit
# הלקחים + דפוסי התיקון של הראל לבמאי (רץ אוטומטית לפני --director):
python3 tools/director_lessons.py --workdir "_work/{שם}" [--rebuild]
# האפליקציה: GET /api/next · /api/claude-brief · /api/preflight/{שם}
```
**חוזה עבודה:** כשמדווחים להראל "מוכן לבדיקה" — מצטטים את פסק-הדין של
PREFLIGHT.json. כל פידבק חדש שמוטמע בקוד = רשומת לקח חדשה + אוכף
(lesson_registry), כחלק מהגדרת "בוצע".

**נכון ל-25.7.2026 | מקור אמת לפעולות: `skills/rel-social-video-editor/SKILL.md` (v7.8)**
**עיקרון: מקומי מקצה-לקצה. אפס Descript. הרוויו של הראל — ב-review-app (פורט 5112).**

## v7 — פקודות ה-Editorial OS (מהשורש)
```bash
python3 tools/system_doctor.py                 # בריאות מערכת (גם --json)
python3 tools/review_cli.py projects --json    # registry חי לכל הפרויקטים
python3 tools/review_cli.py tasks --json       # התור לקלאוד; claim/resolve/fail — ראה SKILL שלב 4.5
python3 tools/review_cli.py revisions "שם" / undo / redo / restore "שם" REV
python3 tools/review_cli.py rebuild-index      # בנייה מחדש של SQLite מהדיסק (בטוח תמיד)
# v7.7 — סנכרון ציר האפליקציה למה שנחתך בפועל (חובה אחרי כל עריכת edl.json בצ'אט):
python3 tools/review_cli.py sync "שם" --summary "מה תיקנתי"   # review.cuts ← keep_segments + revision
python3 tools/review_cli.py sync-status "שם" --json           # in_sync/drift/edl_ahead/final_ahead
python3 tools/review_cli.py sync-all --json                   # סריקה+תיקון בכל הפרויקטים (--dry-run לבדיקה)
~/.rel-whisper/bin/python tools/run_finish.py --workdir "_work/שם" --content-type value --brand rel
                                               # גימור ידני תחת נעילה+run record (מה שהאפליקציה מריצה)
python3 tools/canon_lint.py --workdir "_work/שם"     # policy-as-code לפני אישור/תזמון
~/.rel-whisper/bin/python tools/cut_qa.py --video EXPORT_TIGHT.mp4 --keeps tight_keeps.json
python3 tools/golden.py run                    # regression (חובה לפני כל שינוי policy)
python3 tools/learn_from_edits.py --propose    # למידה v2 — shadow בלבד; החלה רק עם --approve אחרי PASS
python3 tools/ops_dashboard.py                 # מדדי תפעול
python3 tools/note_corrections.py --workdir "_work/שם"          # תצוגה מקדימה של תיקוני ההערות
python3 tools/note_corrections.py --promote                      # קידום שיבוש חוזר למילון הגלובלי
python3 -m unittest discover -s tests          # 54 בדיקות יחידה
```
FINAL.mp4 נוצר **רק אחרי qa_gates PASS** (עד אז FINAL_PENDING.mp4; FINAL קודם מגובה FINAL_prev_*).
gate אודיו חוסם ≥0.6ש (לא 1.5 — תיעוד ישן). מוזיקה: brand-assets/music, חוק אי-חזרה 90 יום.

```
Monday "מוכן לעריכה"
   │  match_intake (שיוך גלם מקומי)
   ▼
[מק] דחיסה crf23 (HLG? tonemap.swift קודם) → INPUT.mp4 → Whisper (align_words)
   → edl_build → edl_cut → ROUGH.mp4 + edl.json + intent_card.md
   ▼
[review-app :5112] הראל רואה את כל החיתוכים על הציר, מתקן בקליק
   (ביטול/הוספה/גבולות/Hook/טקסט) → ניגון מדלג או PREVIEW אמיתי
   │  כל תיקון → corrections.jsonl (לולאת הלמידה)
   ▼  "אשר והמשך לגימור" = [APPROVE-PUBLISH] (APPROVAL.json)
[local_finish_pipeline — אוטומטי] recut EXPORT (נקי, נשמר!)
   → words: **מיפוי דטרמיניסטי** של whisper_raw לציר הקאט (v7.9 — לא מתמללים
     פעמיים; תמלול חוזר הוא fallback בלבד, אחרי שבדיקת שפיות נכשלה)
   → notefix (v7.8: תיקוני 'מילה*' מההערות שלך → תמליל, בלי קלאוד)
   → align_reconcile (טקסט מתוקן + תזמון אמיתי + de-collide)
   → tighten אקוסטי מודע-דיבור (-40dB + הגנת word-start; מקס 2 חיתוכים/5ש; CTA 8ש אחרונות ≥0.8ש בלבד)
   → [speed_fit אוטומטי רק אם >180ש (length_policy.HARD_MAX): סולם 1.05→1.15 — v9.25: אין יותר האצה לצורך 60ש]
   → **coverage + gate אפס-שקט — v8.6: רצים גם ב---refinish** (words חוסם; אודיו ≥0.6ש = אזהרה)
   → B-roll overlay (fade 0.12) → [fixed_intro]
   → **v8.6: תמלול אימות ל-G6b יוצא לרקע כאן** (על האודיו הנקי, לפני המוזיקה)
   → מוזיקה -46 + דאקינג 8dB (דיבור -54) (rotation, 90 יום)
   → כתוביות PIL (רצועה בלבד, veryfast/crf16) → loudness -14 → deliver crf23
   → **v8.6 — כל השערים לפני הקידום ל-FINAL**, ואם מישהו מהם חוסם התוצר נשאר
     FINAL_PENDING + gate_blockers.json:
       verify_asr_wait → cut_qa (חוסם: black_frame/freeze) → caption_safety (חוסם)
       → G9 לקסיקון (חוסם) → **v9.29 caption_vision — V7 על הפיקסלים (חוסם:
         reversed ≥3&≥20% · missing ≥2 · tofu; השאר מדווח ל-P20)**
       → broll_seam (דיווח) → canon_lint (חוסם: 8 HARD_FAIL) → qa_gates (חוסם)
   → קידום ל-FINAL.mp4 + FINISH_REPORT.md (כולל שורת ⏱ זמני שלבים)
   → FINAL_PROVENANCE.json (v7.7 — ממה בדיוק נבנה: revision/edl_hash/keeps/tighten/speed)
   ▼
[למידה] learn_from_edits --apply → כיול edl-policy.json + דוח "מה נלמד"
   ▼
[תיוק והעלאה] resolve_output_path → {מחלקה}/{חודש}/{סרטון}/ → העלאה ל"סרטון מוכן" → מייל
   ▼
[review-app: אישור קאבר+קפשן — v7.2] קלאוד כותב טיוטת קפשן + מוודא thumbnail.png
   → POST /api/schedule-review {action:set_draft} → state="awaiting_schedule_approval"
   → הראל באפליקציה: מאשר (נועל checksum FINAL באותו רגע → state="ready_to_schedule")
      או מבקש שינוי (→ comment בתור קלאוד, כמו הערת עריכה רגילה)
   ▼  "תרוץ על מה שמוכן" = לסרוק רק state=="ready_to_schedule"
[Metricool] לוודא state==ready_to_schedule + checksum תואם ל-FINAL.mp4 בפועל (אחרת [STALE-FINAL], לא לתזמן)
   → createScheduledPost עם approved_final_path/caption_approved/cover_path בלבד
   (פוסט אחד, כל הרשתות, titles×3, firstComment) → API קודם, ידני-קומפוזר אחרון
   → מייל אימות (נתיב+checksum+קפשן+קאבר+מועד) לפני "תוזמן!" → Update "תוזמן!" + "קפשן סופי:"
```

## פקודות — העתק-הרץ (בתוך `_work/{שם}/`)

```bash
# הכנה מקומית (מק)
ffmpeg -nostdin -y -i RAW.mov -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -ar 48000 -ac 2 -movflags +faststart clip1_1080.mp4   # HLG? tonemap.swift קודם
/Users/hayon/.rel-whisper/bin/python ../../tools/align_words.py INPUT.mp4 whisper_raw.json auto he
#   auto = ivrit-ai/whisper-large-v3-turbo-ct2 + VAD (v7.8) — ראה ASR-BENCH.md
#   v9.30-eff: אותו מודל רץ ב-MLX על ה-GPU (~/.rel-mlx, tools/asr_mlx.py) — פי ~3 מהר, WER לא גרוע;
#   כל כשל ⇒ נסיגה ל-ct2 · REL_ASR_BACKEND=ct2 לכפות את הישן · doctor: "asr backend"
python3 ../../tools/edl_build.py --words whisper_raw.json --out-dir . --video INPUT.mp4 --end {DUR} [--loose-script brief.txt]
python3 ../../tools/edl_cut.py --video INPUT.mp4 --edl edl.json --out ROUGH.mp4

# רוויו (הראל): דאבל-קליק "review-app/▶ הפעל רוויו R.E.L.command" → http://127.0.0.1:5112
# בריאות: curl -s 127.0.0.1:5112/health

# גימור מלא (רץ אוטומטית מהאישור באפליקציה; ידנית:)
~/.rel-whisper/bin/python ../../tools/local_finish_pipeline.py --workdir . \
  --content-type value --title "כותרת קאבר"    # conversion: --content-type conversion --broll-plan broll_plan.json

# למידה (אחרי כל אישור)
python3 ../../tools/learn_from_edits.py --apply

# תיוק
python3 ../../tools/resolve_output_path.py --dept "{מחלקה}" --name "{פריט}" --month "{חודש שנה}"  # → DC move
```

## חוקי ברזל (תמצית — המלא בסקיל)
- Hook קדוש · אנטי חיתוך-יתר · אורך לפי סוג תוכן (tools/length_policy.py: המרה/הוק 20-45 · ערך/סיפור/חיבור 45-90 · פודקאסט 45-90 · נימוק מעל 90 (פודקאסט 120) · קשיח 12-180) · אפס דד-אייר נמדד · פאוזות מכוונות נשמרות.
- כתוביות מקומיות בלבד: מילה אחת, בלי `.` `,` `…`, Assistant ExtraBold + ‎#871d1f, סטטיות, de-collide (מובנה ב-align_reconcile), RTL-wrap.
- בלי טקסטים גרפיים / לוגו / פתיחים (חריגים: פתיח מאסל-מן מלא; אפקט מעבר שנביר+ניפוץ-זכוכית בפינת ניפוץ מיתוסים — קטלוג ב-`תוצרי-אנימציה/פתיחים-קבועים/catalog.json`) · B-roll **בכל סוגי התוכן** (ההגבלה ל-conversion בוטלה ב-v7.8), mute, מהקטלוג, overlay על EXPORT נקי, הפרדת מחלקות קשיחה.
- מוזיקה תמיד: **‎-46 LUFS** עם דאקינג 8dB (דיבור ‎-54), אורך מלא; רגוע ("calm") לתוכן לא-מכירתי; מכירה ‎-32 מותר; אסור שיר מסחרי. היסטוריית כיול: ‎-30→‎-38→‎-46→‎-44→‎-46 (10.9.26). פירוט מלא: `AUDIO-MIX.md`.
- 1080×1920 · crf23 העלאות · **שרשרת ה-crf בפועל: 23(INPUT)→18(recut)→18(tighten)→20(broll)→16(captions)→23(deliver) = 4-7 קידודים מלאים ו-4-6 דורות AAC.** זה חוב מתועד שמנוע הרינדור של V2 (גרף סגמנטים + מטמון) בא לפתור — לא "crf18 ביניים" כפי שנכתב כאן עד v8.6 · אסור ultrafast · אסור לגעת בצבע (HLG→tonemap.swift) ·
  אסור re-encode למדיה מתוזמנת · קאבר תואם-יחס · band-center 0.725 נעול.
- העלאות כבדות: nohup על המק, בדיקה אחת · כל כתיבה אטומית (tmp→replace).
- Gate-ים של הראל: [APPROVE-PUBLISH] באפליקציית הרוויו · **אישור קאבר+קפשן באפליקציה (v7.2)** · מייל אישור לפני כל תזמון. תמיד.
- **v7.2 — אסור לתזמן Metricool בלי checksum תואם.** לפני `createScheduledPost`: `state=="ready_to_schedule"` בלבד, ולהשתמש רק ב-`schedule_approval.approved_final_path/checksum/caption_approved/cover_path`. אחרי תזמון מוצלח — מייל אימות (נתיב+checksum+קפשן+קאבר) חובה לפני שמסמנים "תוזמן!". שורש: למנוע תזמון בטעות של גרסה ישנה/לא-סופית — אין "בטח זה בסדר".
- **אסור Descript בזרימה הראשית** — fallback חירום `[DESCRIPT FALLBACK]` באישור הראל בלבד.

## כלים
| כלי | תפקיד |
|---|---|
| scripts/video_eyes | העיניים: גיליונות מגע מונחי-תנועה + תמליל + שוטים + שתיקות |
| vision_check | חוק הראייה במספרים: VISION.json, V1-V7, `--build-reference` |
| edl_build / edl_cut | עריכה דטרמיניסטית מקומית (EDL) + חיתוך frame-accurate |
| review-app/ | מסך הרוויו והתיקון של הראל (תחליף Descript) — פורט 5112 |
| local_finish_pipeline | הגימור כולו בקריאה אחת: recut→whisper→reconcile→gate→מוזיקה→כתוביות→QA |
| learn_from_edits | לולאת הלמידה: corrections.jsonl → כיול edl-policy.json |
| align_reconcile | טקסט מתוקן + תזמון אמיתי, de-collide ומונוטוניות מובנים |
| broll_catalog / broll_pick / animation_overlay | קטלוג בירולים, בחירה, overlay מקומי (mute) |
| preflight_critic | v9.13 — המבקר האחרון לפני הראל: PREFLIGHT.json עם ready_for_harel |
| lesson_registry / director_lessons | v9.13 — לקחים אכופים (--audit בדוקטור) · דפוסי-הראל לבמאי |
| qa_gates | כל שערי ה-QA בריצה אחת: G1/G1b/G2/G3/G4/G5/G5b/G6/**G6b**/**G6c**/G7/G8 — 5 חוסמים (G1, G3, G5, G6, G6b) |
| cut_qa / caption_safety / canon_lint | v8.6 — שלושת אלה **חוסמים** לפני הקידום ל-FINAL (עד v7.11 היו דיווח בלבד / קוד מת) |
| caption_vision | v9.29 — V7: כל cue ב-FINAL מול הרינדור הצפוי וההפוך · CAPTION_VISION.json + caption_vision_sheet.jpg · `--calibrate` |
| thumbnail/cover_vision | v9.29 — G-COVER5 בתוך cover_make: שורות/גודל/דליפה/סדר גליפים על ה-PNG · `--calibrate` |
| bench/baseline_v7.py | מדידת 13 ה-KPIs של מיגרציית V2 (before/after) |
| migrate_work_root.py | העברת תיקיית העבודה מ-iCloud לדיסק מקומי (+ `--rollback`) |
| relvid/paths.py | מקור אמת אחד לנתיב תיקיית העבודה (env → paths.json → ברירת מחדל) |
| finish_local / captions_build / captions_qa | גייט שקט, ASS (סנדבוקס), מדידת סנכרון |
| captions-app/captions_overlay | צריבת כתוביות PIL על המק (בלי libass) |
| audio_mix | מיקס מוזיקה LUFS + measure |
| thumbnail/* | קאבר ממותג (frame_select → thumbnail_build; cover_inpaint לחירום) |
| relvid.registry: set_schedule_approval / POST /api/schedule-review | v7.2 — שער אישור קאבר+קפשן + נעילת checksum לפני תזמון |
| match_intake / resolve_output_path | שיוך גלם ↔ בורד · ניתוב תוצרים |

*היסטוריה: `PIPELINE-v5-archive.md`. השינוי המרכזי ב-v6: Descript הוסר מהזרימה; הרוויו והכירורגיה עברו ל-review-app; הגימור אוטומטי מהאישור; לולאת למידה סגורה.*
