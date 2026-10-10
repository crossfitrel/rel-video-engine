# קנון הלקחים — מערכת עריכת הסושיאל

> **נגזר אוטומטית** מ-`tools/lesson_registry.py` + `tools/lessons_canon_data.py` (`python3 tools/lessons_canon.py --render`). לא לערוך ידנית.

**99 לקחים אכופים** · 133 קבצי feedback ממופים: 64 מכוסים בלקח · 16 הוחלפו · 53 כללי תפעול (בסקיל).

## חובות גלויים (לקח קיים, אכיפה חלקית)

- `edl_restore_scrambles_segment_order` — סדר קטעים לא-כרונולוגי אינו נחסם (לפעמים מכוון — הוק מוזז); מתגלה ב-G6 כשל קיצוני
- `music_track_offset_skip_quiet_intro` — מדווח בלבד (offset מוצע) — הפעלת offset אוטומטי דורשת את האוזן של הראל
- `studentit_garbles_hebrew_despite_raqm` — סדר אותיות בתוך שורת Studentit מדווח בלבד (תפיסה 50% בהזרקה); 36/36 קאברים חיים נמדדו תקינים

## app

- **L23_schedule_locks_artifact** — אישור קאבר+קפשן נועל artifact_id+checksum; התזמון לוקח אך ורק את הקובץ הנעול ומאמת checksum — נגד תזמון גרסה שגויה שאי אפשר לתקן אחרי פרסום.
  - אוכפים: registry.py (code), registry.py (code)
  - מקורות בזיכרון: schedule_approval_artifact_id_stale, never_reencode_scheduled_media
- **L40_a_fix_belongs_to_a_version** — תיקון שייך לגרסה, ולכן הוא נחתם ברשומת הגרסה **ברגע היצירה** (fixes). בדיקה של תיקון = ניגון הנקודה שלו בציר של הגרסה הזו (טיימקוד ממופה דרך keep_segments+speed), לא צפייה חוזרת בסרטון המלא. שיוך שהוסק בדיעבד מסומן 'משוער', ונקודה שנחתכה מסומנת cut_out — לעולם לא מוצג טיימקוד שנראה ודאי ומצביע למקום אחר.
  - אוכפים: changelog.py (code), changelog.py (code), artifacts.py (code), server.py (code), test_changelog.py (test)
- **L42_review_app_simple_mode_is_default** — מסך הרוויו של הראל = צפייה → הערות → שלח לקלאוד/אשר, בפעולה ראשית אחת. 'מצב פשוט' הוא ברירת המחדל: שורת הערה מתחת לנגן (נצמדת לזמן ולגרסה), 'שלח הכל לקלאוד' אחד, וכרטיס 'מה עכשיו' עם כפתור אחד שנגזר מהמצב. כלי העריכה חיים ב'מצב מתקדם' — קליק אחד, שום יכולת לא נמחקת. פאנל האישור הסופי והתקדמות הגימור הם כרטיסים מתחת לנגן — לעולם לא קבורים בלשונית.
  - אוכפים: index.html (code), index.html (code), index.html (code), index.html (code)
- **L43_one_theme_system_across_apps** — מצב לילה נבנה פעם אחת לכל האפליקציות: data-theme על html + מפתח localStorage + מחזור אוטומטי→יום→לילה, באותה פלטה כמו rel.fit/tasks. צבע נושא לא נכתב כהקס קשיח בגוף האפליקציה — רק טוקן var(); קנבס, שלא מבין var(), קורא את הטוקנים מ-getComputedStyle (tlPal) ומתרענן בהחלפת ערכה.
  - אוכפים: index.html (code), index.html (code), index.html (code)
- **L45_claude_verifies_fixes_before_harel** — סבב תיקונים לא נמסר להראל לפני שקלאוד אימת **כל תיקון** בראיות: fix_verify מודד (מילים בכתוביות · גבול EDL · LUFS · חפיפת בירול) ומפיק גיליון-מגע פר-פריט; קלאוד קורא את הגיליונות ב-Read ופוסק fix-verdict (verified / not_fixed / needs_eye). not_fixed מחזיר את ההערה לתור לפני שהראל בכלל פתח את הסרטון, והסבב של הראל (review_plan focus) מנגן רק את מה שלא אומת. אין דיווח 'תוקן ואומת' בלי פסיקה רשומה.
  - אוכפים: fix_verify.py (code), changelog.py (code), changelog.py (code), review_cli.py (code), preflight_critic.py (code), test_fix_verify.py (test)
  - מקורות בזיכרון: oct26_batch_refinish_traps
- **L50_server_must_not_depend_on_path** — שרת ארוך-חיים לא מאתר בינארים חיצוניים דרך PATH. השרת מופעל לעיתים בלי סביבת login, ואז `/opt/homebrew/bin` חסר: `subprocess.run(["ffmpeg"…])` זורק FileNotFoundError, המטפל הגלובלי מחזיר 404 "פרויקט לא נמצא", והתמונות נשברות **בשקט** — עם שגיאה שמצביעה על הבעיה הלא-נכונה. כל בינארי נפתר בנתיב מוחלט (`_ffmpeg_bin`), וכשל בינארי מקבל קוד שגיאה משלו (FFMPEG_MISSING) ולא מתחזה לכשל תוכן.
  - אוכפים: server.py (code), server.py (code), test_review_app_binaries.py (test)
  - מקורות בזיכרון: review_app_server_path_lacks_homebrew
- **L50b_finish_run_from_server_inherits_path** — גם הגימור שהשרת מפעיל יורש את ה-PATH הקטוע: edl_cut נפל על ffmpeg חסר אחרי 0.4ש, ו-python3 היה 3.9 של המערכת. הריצה מקבלת סביבה עם נתיבי Homebrew (runner._tool_env), והצינור עצמו מקדים אותם בעלייה (ensure_tool_path) — שתי שכבות, כי גם הרצה ידנית מסביבה חלקית חייבת לעבוד.
  - אוכפים: runner.py (code), local_finish_pipeline.py (code), vision_check.py (code)
  - מקורות בזיכרון: oct26_batch_refinish_traps
- **L59_player_speed_only_on_input** — קצב הנגינה באפליקציה חל רק על INPUT (סימולציית העריכה). FINAL/PREVIEW כבר מכילים את ה-speed בקובץ; ניגון שלהם ב-playbackRate=speed מאיץ פעמיים, והמוזיקה — שבקובץ בקצב המקורי — נשמעת מואצת. גם defaultPlaybackRate נקבע, כי טעינת src מאפסת את הקצב.
  - אוכפים: index.html (code)

## audio

- **L54_music_bed_calibrated_down_again** — מצע המוזיקה כויל -44→-46 LUFS (דיבור -52→-54 בדאקינג 8). הכיוון נגזר מההערות: מאז 23.7 — 14 'חזק מדי/להנמיך' מול 0 'חלש מדי'; -55 נמדד כ'מעט נמוך' ו--52 כ'טיפה חזק'. שינוי נוסף רק עם ראיה כפולה (הערה + מפלס ידני באפליקציה), לא לפי תחושה.
  - אוכפים: local_finish_pipeline.py (code), AUDIO-MIX.md (doc)
  - מקורות בזיכרון: music_too_loud_genre_mismatch_not_lufs, pre_take_mumble_and_music_balance, silence_and_music_are_one_defect, music_volume_low ⟲, music_mix_no_ducking_full_length ⟲

## broll

- **L02_broll_edge_snaps_to_cut_boundary** — קצה בירול מיושר לגבול החיתוך ולא לעצמו: חצייה של 2 פריימים (0.067ש) מעבר לגבול, אחרת פריים-הגבול נשאר חשוף. אין הארכה חלקית ואין הזזה — מה שלא נחצה יוצא cut_slivers (חוב), לא מוסתר.
  - אוכפים: broll_director.py (code), broll_director.py (code), test_broll_cut_snap.py (test)
  - מקורות בזיכרון: broll_align_to_cuts
- **L03_flash_gap_is_a_blink** — חזרה של 0.3-1.2ש לפנים בין שני אירועים ויזואליים היא הבהוב, לא נשימה. חור ≤FLASH_GAP נסגר בהחלקה קדימה של הקליפ המוקדם; הקליפ הבא לא זז לעולם.
  - אוכפים: broll_director.py (code)
  - מקורות בזיכרון: broll_bridging_and_min_length, edl_merge_threshold_mismatch_ghost_sliver_fixed
- **L06_anchor_reason_must_quote_sentence** — בירול-עוגן נכנס רק אם הנימוק מצטט את המשפט (צירוף שתי מילים רצופות או מילת תוכן ≥5 אותיות). תיאור של הקליפ אינו נימוק. נושא-על אינו יחידת התאמה.
  - אוכפים: broll_director.py (code)
  - מקורות בזיכרון: broll_literal_transcript_anchor
- **L07_no_broll_better_than_wrong_broll** — confidence<0.75 ⇒ אין בירול. אין מכסה; 0 בירולים היא תשובה תקפה. סרטון בלי בירול טוב מסרטון עם בירול לא-קשור — העדפה, לא פשרה.
  - אוכפים: broll_director.py (code), broll_director.py (code)
- **L08_min_clip_len_readability** — בירול קצר מ-1.8ש אינו מפוענח — הבהוב. לא ממלאים כדי שיהיה.
  - אוכפים: broll_director.py (code)
  - מקורות בזיכרון: broll_bridging_and_min_length
- **L09_audience_determines_structure** — המרה = קהל קר = מצע רציף (יעד 70%, בלי חזרה לפנים באמצע חוץ מפעימת trust); ערך/חיבור = עוגנים בלבד. חורי-פנים במצע נסגרים בקוד; מה שנשאר מדווח bed_face_holes, לא מוסתר.
  - אוכפים: broll_director.py (code), broll_director.py (code), broll_director.py (code)
  - מקורות בזיכרון: conversion_broll_always_continuous_montage, broll_conversion_only ⟲
- **L19_people_is_not_audience** — התווית משקרת, הפריים לא: people (מי בפריים, מאימות ויזואלי) ≠ audience (פילטר בחירה). אין פנים בפריים ⇒ אין אימות זהות — בגד ומבנה גוף אינם ראיה.
  - אוכפים: system_doctor.py (code), test_gender_balance.py (test)
- **L34_anchor_sits_on_the_words_it_quotes** — הציטוט אינו רק תנאי קבלה לעוגן — הוא גם קובע את **הזמן** שלו. עוגן שמושם תמיד בתחילת החלון מאייר בחלון ארוך מילים אחרות לגמרי מאלה שהצדיקו אותו.
  - אוכפים: broll_director.py (code), test_anchor_lands_on_the_quote.py (test)
  - מקורות בזיכרון: broll_literal_transcript_anchor
- **L46_illustration_region_must_be_verified** — בהמחשה אנטומית, האזור שנדלק על המילה נגזר מהאיור — לא מהתמליל — ולכן אינו יודע מה שמו. כל מיפוי ישות→אזור עובר אימות מפורש מול האיור (illustration_regions.json עם verified לכל ישות + תמונת בדיקה שמראה כל אזור צבוע על האיור). בלי אימות ההמחשה **אינה מוחלת**. אימות שלא נעשה אינו 'כנראה בסדר'.
  - אוכפים: illustration_gate.py (code), illustration_gate:IL5_region_verified (gate), test_illustration_gate.py (test)
  - מקורות בזיכרון: illustration_region_must_be_verified
- **L49_separate_at_the_source_not_with_an_algorithm** — שני שרירים סמוכים שנוגעים בצבע באיור **אינם ניתנים להפרדה** ממנו: שלוש שיטות נוסו ונכשלו (ארוזיה מורפולוגית · חיתוך לפי בהירות · חיתוך לפי רצועת הגיד החיוורת) כי לא קיים באיור חתך שאפשר למצוא. הפתרון אינו אלגוריתם טוב יותר אלא **קלט שניתן להפריד**: מבקשים מהמאייר רינדור שני של אותה קומפוזיציה עם צבע-מפתח רווי לכל שריר (`atlas`), גוזרים ממנו את המסכות לפי גוון, ומודדים את הרישום מול האיור היפה (IoU). האטלס משמש למסכות בלבד — מה שהצופה רואה נשאר האיור.
  - אוכפים: illustration_build.py (code), illustration_gate.py (code), illustration_gate:IL7_atlas_registration (gate), test_illustration_gate.py (test)
- **L75_broll_brand_identity_is_checked** — בירול של הראל (ספריית 'הראל חיון' / personal_tags / identity מאימות ויזואלי) לא נכנס לתוכן מועדון — והבדיקה נעשית על מה שנצרב ב-FINAL, לא רק בבחירה.
  - אוכפים: broll_vision_qa.py (code), broll_pick.py (code), test_vision_gates_v930.py (test)
  - מקורות בזיכרון: broll_dept_library_separation, broll_personal_vs_club_separation
- **L76_burned_text_is_judged_by_eyes** — טקסט גרפי צרוב בבירול נשפט בעין (פסק-דין מודלי burned_text בגיליון העיגון), לא בגלאי פיקסלים: גלאי 'טקסט סטטי על מצלמה שזזה' נמדד על 532 קליפים ונתן ציונים גבוהים לצילומי חצובה עם רקע סטטי — לא מפריד, ולכן מדווח בלבד.
  - אוכפים: broll_vision_qa.py (code), broll_vision_qa.py (code), test_vision_gates_v930.py (test)
  - מקורות בזיכרון: broll_harvest_burned_text_reject
- **L77_broll_is_judged_where_it_landed** — בירול נשפט במקום שבו נחת ב-FINAL מול מה שנצרב בפועל (items_applied במניפסט), לא מול התוכנית: FINAL מושווה לרינדור הצפוי של הקליפ (אותו גרף overlay — מסך מלא, blur 0) ולבסיס של הדובר.
  - אוכפים: broll_vision_qa.py (code), broll_vision_qa.py (code), local_finish_pipeline.py (code), test_vision_gates_v930.py (test)
  - מקורות בזיכרון: broll_plan_always_applied_any_content_type, broll_style_full_frame_no_box, dedicated_broll_plan_paths_and_content_type_override, broll_swap_local_ffmpeg ⟲
- **L78_anchor_verdict_is_bound_to_the_final** — 'הבירול מאייר את המשפט' הוא שיפוט מודלי — נשמר כדאטה (BROLL_ANCHOR_VERDICT) עם sha של ה-FINAL; FINAL שהשתנה הופך את הפסיקה ל-stale; בלי פסיקה = 'לא נמדד', לא PASS.
  - אוכפים: broll_vision_qa.py (code), broll_vision_qa.py (code), test_vision_gates_v930.py (test)
  - מקורות בזיכרון: broll_literal_transcript_anchor

## captions

- **L12_map_words_dont_retranscribe** — לא מתמללים פעמיים — התמלול המקורי ממופה לציר החתוך (map_words_to_keeps), ושער כיסוי מוודא שאין דיבור בלי כתוביות.
  - אוכפים: edl_utils.py (code)
  - מקורות בזיכרון: captions_accurate_timing
- **L16_rtl_no_double_reversal** — עם Pillow שנבנה מול libraqm, הפעלת get_display נוספת יוצרת היפוך כפול — טקסט לוגי גולמי עם direction=rtl בלבד.
  - אוכפים: captions_overlay.py (code)
  - מקורות בזיכרון: captions_rtl_double_reversal_raqm
- **L70_turbo_vad_drops_noisy_speech** — turbo עם VAD על INPUT מפספס דיבור רועש (קהל, מוזיקה ברחבה); קטע שנשמר עם פחות מ-0.6 מילים/ש הוא חשד לחור בכתוביות. מדווח (הסף לא נמדד מול מאושרים), והתיקון הוא האזנה חוזרת ב-large-v3 בלי VAD על הקליפ — לא ניחוש מילים.
  - אוכפים: intake_guard.py (code), intake_guard.py (code), preflight_critic.py (code), preflight:P18_caption_density (gate), test_intake_guard.py (test)
- **L71_captions_are_judged_on_the_pixels** — הכתוביות נשפטות על הפריים של ה-FINAL, לא על המילים: כל cue מושווה לרינדור הצפוי (אותו קוד שצורב) ולרינדור ההפוך. היפוך RTL כפול משוחזר ע"י מחרוזת הפוכה — direction=ltr ב-raqm זהה לנכון ולכן אינו ייחוס. חוסם רק דגל שנמדד נקי על המאושרים; ציר מילים שלא תואם ל-FINAL הוא ממצא, לא רעש.
  - אוכפים: caption_vision.py (code), caption_vision.py (code), caption_vision.py (code), local_finish_pipeline.py (code), preflight_critic.py (code), caption_vision:reversed (gate), caption_vision:missing (gate), test_vision_gates_v929.py (test), test_vision_gates_v929.py (test)
  - מקורות בזיכרון: captions_rtl_double_reversal_raqm
- **L81_no_arabic_codepoints_in_hebrew** — אין תו ערבי בכתוביות/שמות קבצים עבריים — אותיות מתחלפות חזותית ועוברות כל בדיקת מילים.
  - אוכפים: caption_safety.py (code), caption_safety:arabic_char (gate)
  - מקורות בזיכרון: never_arabic_characters_hebrew_only
- **L82_same_timestamp_words_are_decollided** — מילים סמוכות עם אותו timestamp (אינטרפולציה) מפוזרות לחלונות נפרדים ומונוטוניים — אחרת אחת דורסת את השנייה ונעלמת מהמסך.
  - אוכפים: align_reconcile.py (code)
  - מקורות בזיכרון: captions_decollide
- **L83_rtl_punctuation_lands_left** — סימני ? ! בסוף cue עברי נוחתים משמאל: ב-libass כל cue עטוף RLE/PDF; ב-PIL raqm עם direction=rtl — והפיקסלים נבדקים ב-V7.
  - אוכפים: captions_build.py (code), caption_vision.py (code)
  - מקורות בזיכרון: captions_rtl_punctuation_fix
- **L85_burned_words_are_real_hebrew** — כל מילה שנצרבת היא עברית מוכרת: גלוסרי ASR לשיבושים חוזרים + שער לקסיקון G9 חוסם. 'לא ממציאים' אינו מצדיק להשאיר מילה שלא קיימת.
  - אוכפים: caption_lexicon_qa.py (code), align_words.py (code)
  - מקורות בזיכרון: whisper_correction_engine_validated_open_gym_40plus, whisper_default_medium_and_asr_glossary, whisper_transcript_linguistic_sanity_check

## copy

- **L41_caption_always_via_cta_psychology** — קפשן הוא ה-CTA בפועל, ולכן הוא לא נכתב מקול בלבד. כל טיוטת קפשן מגובשת דרך `rel-cta-psychology` — הסקיל נטען **לפני** הכתיבה, לא כתיקון אחרי. סקילי הקול (rel-content-creator / rel-reel-caption-generator / harel-whatsapp-voice) קובעים איך זה נשמע; rel-cta-psychology קובע את מבנה הצעד הבא.
  - אוכפים: SKILL.md (code), SKILL.md (code)
  - מקורות בזיכרון: captions_always_via_cta_psychology

## cover

- **L72_the_cover_is_judged_on_the_png** — קאבר נשפט על ה-PNG שיצא, לא על הקלט לבונה: שתי שורות בפיקסלים, כותרת גדולה מתת-כותרת בגודל-גופן שנאמד מהדיו, אין כתובית מחוץ לקופסה, וסדר הגליפים תואם פריסה ידנית תו-אחר-תו (ייחוס שלא עובר דרך shaping). הסבולת יחסית לגובה השורה — Studentit הוא קו דק ונענש על עובי ולא על צורה.
  - אוכפים: cover_vision.py (code), cover_make.py (code), cover_make:G-COVER5_png_vision (gate), test_vision_gates_v929.py (test), test_vision_gates_v929.py (test)
  - מקורות בזיכרון: cover_no_caption_bleed_always_export, cover_title_bigger_than_subtitle_sacred_rule, cover_title_subtitle_always_bigger, covers_always_2_lines_dana_yad, studentit_garbles_hebrew_despite_raqm, subtitle_size_independent_fit_not_ratio ⟲

## covers

- **L15_cover_single_entry_with_gates** — כל קאבר עובר דרך בונה יחיד (cover_make), תמיד מ-EXPORT נקי, תמיד 2 שורות, תמיד Studentit — כשערים חוסמים בקוד, לא כנוהל בסקיל. נוהל אפשר לשכוח; שער לא.
  - אוכפים: cover_make.py (code), cover_make:G-COVER1_clean_source (gate), cover_make:G-COVER2_two_lines (gate), test_cover_gates.py (test)
  - מקורות בזיכרון: cover_no_caption_bleed_always_export, cover_title_subtitle_always_bigger, covers_always_2_lines_dana_yad, covers_root_cause_gates_v912, studentit_punctuation_silent_fallback, thumbnail_consistent_box_position, dana_yad_no_latin_glyphs ⟲, danayad_font_garbles_without_raqm ⟲, thumbnail_danayad_font_garbled_hebrew ⟲, playpen_font_garbles_hebrew ⟲

## edit

- **L43_bed_covered_seam_is_not_a_visible_seam** — תפר שנופל בתוך מיטת הבירול אינו קפיצה נראית: הוא מוסתר מאחורי הקליפ. לכן הוא לא נספר בתקציב `CUTS_PER_SEC`, וסף החיסכון שלו יורד ל-`MIN_SAVING_PER_CUT_COVERED` במקום `MIN_SAVING_PER_CUT`. תפר חשוף על פני הדובר ממשיך בדיוק כמו קודם — שם הקליברציה של הראל תקפה. בלי ההבחנה הזאת המערכת משלמת מחיר של תפר-נראה על חיתוכים שאין בהם מה לראות, ולכן מוותרת עליהם ומשאירה אוויר מת.
  - אוכפים: edit_plan.py (code), edit_plan.py (code), test_bed_covered_seams.py (test)
- **L87_intro_gesture_is_not_silence** — שקט בתוך מחווה פיזית בפתיחה (מחיאת כף, תנועה לפני מילה) אינו שקט לחיתוך: --intro-keep ו---max-word-dur ביחד.
  - אוכפים: tighten_finish.py (code), local_finish_pipeline.py (code)
  - מקורות בזיכרון: tighten_intro_gesture_jump_cut

## gates

- **L55_retake_in_opening_is_not_the_hook** — טייק פתיחה שגוי שנאמר שוב מיד אחריו אינו ההוק — ההוק הוא הטייק החוזר. canon_lint מזהה חזרה של 3 המילים הראשונות בתוך 30ש ומזיז את חלון ההגנה (6ש) לטייק החוזר. בלי זה, הסרת הטייק השגוי (חוק 'טייק אחרון') נחסמה כ'מחיקת ההוק'.
  - אוכפים: canon_lint.py (code), test_canon_hook_retake.py (test)
- **L57_declared_transition_never_hides_a_flash** — מעבר מוצהר בתוכנית אינו פוטר פריים שחור/לבן בודד, A→B→A או תמונה ממקור לא נכון — הבדיקות רצות גם בנקודת המעבר, מול המקור הנקי (חשכה מהצילום אינה נענשת). G8 הישן לא הוחלש.
  - אוכפים: visual_hook_qa.py (code), visual_hook_qa:VH5_introduced_flash (gate), qa_gates:G8_opening_flash (gate), test_visual_hook_qa.py (test)
- **L60_canon_exception_is_data_not_a_workaround** — שער קאנון שצודק במקרה שאין לו דרך לדעת עליו מקבל **חריגה מוצהרת כנתון** — לא עקיפה בקוד, לא הנמכת סף, ולא כיבוי. החריגה נרשמת ב-project_manifest.json תחת canon_exceptions עם נימוק (20+ תווים), מאשר ותאריך, ומורידה HARD_FAIL ל-WARNING בלבד — לעולם לא ל-PASS — כשהנימוק נכנס לדוח. רשימת ההיתר (CANON_EXCEPTABLE) צרה בכוונה: חריגה גורפת היא ביטול השער. חריגה שנפסלה מדווחת ולא נבלעת. **נגזרת:** שער שרמתו נקבעת במשתנה עדיין שער — דפוס הסריקה ב-gate_registry חייב לתפוס גם את הצורה הזו, אחרת השער נראה לאודיט כמי שנעלם.
  - אוכפים: canon_lint.py (code), canon_lint.py (code), gate_registry.py (code), test_canon_exception.py (test)

## music

- **L13_tone_class_filters_genre** — טון הבריף קובע ז'אנר, לא רק סוג התוכן: המרה בטון רגוע מסוננת מ-phonk/trap/rock_sport/edm. תיקון של אותה בעיה בשתי שכבות = השכבה הנכונה לא זוהתה.
  - אוכפים: local_finish_pipeline.py (code), test_v99_tone_trust_envelope.py (test)
  - מקורות בזיכרון: music_upbeat_not_elevator, music_too_loud_genre_mismatch_not_lufs
- **L14_music_pref_overrides_cli** — בחירת מוזיקה של הראל ננעלת במניפסט (track_auto) וגוברת על --music בגימורים הבאים — אחרת גימור מהיר מחליף לו את הטראק שבחר.
  - אוכפים: local_finish_pipeline.py (code)
  - מקורות בזיכרון: music_manifest_pref_overrides_cli
- **L66_pixabay_license_not_immune_to_content_id** — רישיון Pixabay מתיר שימוש אבל לא מחסן מפני Content ID: אותה הקלטה יכולה להיות רשומה במקביל אצל מנהל-זכויות צד-שלישי (למשל HAAWK), ויוטיוב חוסם את הסרטון גלובלית למרות רישיון תקין. טראק שנתבע/נחסם עובר מיד ל-brand-assets/music/_disabled/ (ה-glob הלא-רקורסיבי ב-pick_music מוציא אותו מהרוטציה אוטומטית) ומסומן banned+banned_reason בקטלוג — לעולם לא רק מוסר בשקט בלי תיעוד של הסיבה.
  - אוכפים: local_finish_pipeline.py (code), music-catalog.json (doc)
- **L86_music_bed_in_every_video_full_length** — מצע מוזיקה בכל סרטון, בכל סוג תוכן, לאורך מלא בלי אובדן זנב; אנרגטי ולא 'מעלית'. הכלל 'רק מכירה' בוטל 22.6.26.
  - אוכפים: local_finish_pipeline.py (code), local_finish_pipeline.py (code)
  - מקורות בזיכרון: music_sales_only, music_upbeat_not_elevator, music_mix_no_ducking_full_length ⟲
- **L93_music_intro_dip_is_measured** — טראק שצונח לקטע שקט ב-8ש הראשונות נמדד בכל מיקס ומדווח עם offset מוצע — loudnorm מנרמל ממוצע ולא פותר דיפ מקומי. לא מוחל אוטומטית: שינוי שמיעתי דורש את האוזן של הראל.
  - אוכפים: audio_mix.py (code), test_vision_gates_v930.py (test)
  - מקורות בזיכרון: music_track_offset_skip_quiet_intro

## pipeline

- **L04_director_is_last_word_on_pacing** — שיפוט שרץ לפני מנוע-כללים לא שינה כלום — השכבה האחרונה שנוגעת בציר קובעת. תחת --director ההידוק (tighten) כבוי; הבמאי קובע כל פער.
  - אוכפים: local_finish_pipeline.py (code)
  - מקורות בזיכרון: v2_director_overridden_by_tighten
- **L11_keep_segments_wins_sync** — ל-edl.json שתי שכבות; עריכה שנוגעת רק ב-keep_segments משאירה את האפליקציה על ציר ישן. הכיוון תמיד אחד: keep_segments מנצח ו-review.cuts נבנה ממנו מחדש.
  - אוכפים: sync.py (code)
  - מקורות בזיכרון: edl_restore_scrambles_segment_order, myth_effect_silent_gap_and_edl_review_consistency
- **L17_review_approval_is_final** — אחרי שהראל סקר ואישר ברוויו — שער שקט חוסם היה דורס את הפסק שלו; G2 נשאר מדווח, לא חוסם. אישור הראל = המילה האחרונה.
  - אוכפים: qa_gates:G2_silence (gate)
  - מקורות בזיכרון: silence_gate_nonblocking_post_review
- **L24_preflight_before_harel** — אף תוצר לא מוצג להראל בלי צפיית-מבקר מסכמת: PREFLIGHT.json עם פסק-דין ready_for_harel וממצאים ממוינים. עריכות-מחדש הן כשל של המערכת, לא של הראל.
  - אוכפים: preflight_critic.py (code), local_finish_pipeline.py (code), test_preflight_critic.py (test)
  - מקורות בזיכרון: video_qa_checklist
- **L32_asr_can_truncate_silently** — תמלול יכול להיקטע באמצע קובץ בלי שגיאה. כל שערי הכתוביות שואלים 'האם המילים שיש מסונכרנות' ואף אחד לא שאל 'האם יש מילים לכל הדיבור' — ולכן כשל כזה עובר בציון מלא. מודדים דיבור-אחרון מול מילה-אחרונה, ומדווחים.
  - אוכפים: candidates.py (code), candidates.py (code), test_asr_coverage.py (test)
- **L51_a_detector_that_quietly_stops_detecting** — גלאי שמפסיק לעבוד בשקט גרוע מגלאי שאין. OpenCV 5 הפסיק לארוז את קבצי ה-Haar, ושלושה כלים (`candidates` · `broll_vision` · `illustration_place`) עוטפים את הטעינה ב-try/except ונופלים בשקט ל'אין פנים'. לכן: (א) שער ב-doctor שמדווח כשהקסקייד חסר; (ב) שער שנשען על מדידה **מסמן** כשלא נמדד ואינו חוסם על סמך חוסר — `measured: false` הוא דאטה, לא PASS.
  - אוכפים: illustration_place.py (code), illustration_place.py (code), system_doctor.py (code), test_illustration_place.py (test)
- **L52_a_false_positive_erases_the_area_it_lands_on** — חיובי-שגוי של גלאי אינו רק רעש — הוא **מוחק את האזור שעליו נחת**. Haar זיהה "פנים" על חליפת השרירים המודפסת של מאסל מן (4 קופסאות על החזה, בגודל דומה לפנים האמיתיות), וזה הפך את כל רצועת הגוף לאזור אסור ודחף את ההמחשה בחזרה מעל הראש. שטח לבדו אינו מבדיל — שניהם באותו סדר גודל. מה שמבדיל הוא **התמדה**: מאשכלים לפי מרכז ומדרגים (שיעור הפריימים שנראה) × (שטח ממוצע); מתחת ל-60% מהמוביל — לא פנים. היחס שנשמר/נמצא מדווח, כי יחס נמוך אומר שהמיקום נשען על גלאי רועש.
  - אוכפים: illustration_place.py (code), illustration_place.py (code), test_illustration_place.py (test)
- **L53_cut_boundaries_come_from_energy_not_from_whisper** — תזמוני whisper מרופדים בשני הקצוות ואינם מפת דיבור. חיתוך EDL לפיהם נכשל בשני הכיוונים באותו סרטון: whisper טען שהמילה האחרונה בבלוק נגמרת ב-44.41 בעוד הדיבור נגמר אקוסטית ב-43.51 (0.90ש ריפוד) ⇒ הקטע השאיר כמעט שנייה של הדובר יושב בשקט ומוריד מבט; ובאותו סרטון whisper טען שהמילה הבאה מתחילה ב-71.07 בעוד האונסט האמיתי 70.69 (0.38ש) ⇒ תחילת המילה נבלעה. **גבול חיתוך נגזר מאנרגיה (silencedetect); whisper קובע מה נאמר, לא מתי.** נגזרת שנייה: --skip-whisper/מיפוי-מילים מזרים את אותו ריפוד לכתוביות — בסבב תיקון על טיימינג מריצים --no-map-words.
  - אוכפים: edl_acoustic.py (code), edl_acoustic.py (code), test_edl_acoustic.py (test), test_edl_acoustic.py (test)
  - מקורות בזיכרון: edl_boundaries_from_energy_not_whisper
- **L56_visual_hook_off_by_default_no_unseen_treatment** — פתיחה חזותית: ברירת מחדל off; auto בלי קוהורט מאושר = NO_OP; טיפול מוחל רק מתוכנית שנצפתה ואושרה (digest), ואישור בלי תצוגה טרייה = אין טיפול (לא כשל). NO_OP היא החלטה תקינה.
  - אוכפים: visual_hook_policy.json (code), local_finish_pipeline.py (code), visual_hook.py (code), test_visual_hook.py (test), test_visual_hook_review.py (test)
- **L67_length_follows_content_not_60s** — אורך הריל נקבע ע"י סוג התוכן — הכי קצר שמנחית את הרעיון במלואו — ולא ע"י תקרת 60ש. המרה/הוק לקהל קר: 20-45ש; ערך/הסבר/סיפור/חיבור: 45-90ש; נימוק אמיתי מעל 90 לכל סוג (הראל 19.9 ערב, v9.26); פודקאסט: 45-90ש (נימוק מעל 120). חוסם רק 12-180ש. לעולם לא מאיצים סרטון רק כדי להיכנס מתחת ל-60 — ההוק (view-rate 3ש, rho=0.83 מול reach) הוא הלוחץ, לא האורך (rho=0.10 על 40 ריילס).
  - אוכפים: length_policy.py (code), local_finish_pipeline.py (code), qa_gates:G1c_length_reason (gate), test_length_policy.py (test), test_length_policy.py (test), מחקר-אורך-ריל-19.9.26.md (doc)
  - מקורות בזיכרון: 60s_hard_cap_policy ⟲, speed_ramp_over_60s ⟲
- **L68_fixed_clip_must_invalidate_cache** — קליפ שתוקן במקור (סיבוב, צנזור בנביחה) חייב להחליף את העותק בתיקיית העבודה ולמחוק כל נגזרת שנבנתה מהעותק הישן (INPUT, תמלולים, ROUGH) — אחרת הבנייה החוזרת מרנדרת את הגלם הישן בלי שום שגיאה. השוואה בגודל וב-mtime, לא בקיום.
  - אוכפים: intake_guard.py (code), intake_guard.py (code), intake_guard:I2_stale_clip_copy (gate), test_intake_guard.py (test)
- **L69_sideways_raw_is_judged_by_frame** — גלם שצולם לאורך ונשמר landscape עם rotation (180/0) יוצא עם הדמות על הצד. המטא-דאטה רק מעוררת חשד — הפריים מכריע (פנים ב-0°/90°/180°/270°). חשד ⇒ דיווח בכניסה ובפרה-פלייט עם הצעת תיקון, ואז עין על הפריים. לא חוסם: נמדד 2.7% חיובי-שגוי על 257 קליפים. אין גלאי ⇒ measured:false, לא PASS שקט.
  - אוכפים: intake_guard.py (code), preflight_critic.py (code), intake_guard.py (code), intake_guard:I1_orientation (gate), preflight:P19_orientation (gate), test_intake_guard.py (test)
- **L74_ffmpeg_never_reads_stdin** — ffmpeg שרץ מתוך תהליך לעולם לא קורא stdin (-nostdin / stdin=DEVNULL). ffmpeg שיורש TTY מחכה ל-[q] ונכשל רק כשמריצים מטרמינל אינטראקטיבי — תקלה שנראית כמו באג בפרמטרים.
  - אוכפים: audio_mix.py (code), captions_overlay.py (code), test_vision_gates_v930.py (test)
  - מקורות בזיכרון: audio_mix_nostdin_dc_terminal, prep_ffmpeg_nostdin_and_swift_rendersize
- **L79_e2e_on_copies_never_commits_usage** — ריצת גימור על עותקים/תצוגה מקדימה לא כותבת usage גלובלי של בירולים (REL_BROLL_USAGE_COMMIT=0) — אחרת בדיקות מזהמות את רוטציית הבחירה של סרטונים אמיתיים.
  - אוכפים: local_finish_pipeline.py (code), test_vision_gates_v930.py (test)
  - מקורות בזיכרון: e2e_copies_leak_broll_usage
- **L92_scheduled_fetch_never_waits_for_confirm** — משיכה מתוזמנת לא יכולה לחכות לאישור אינטראקטיבי: osxphotos רץ עם --update, אחרת Abort שקט ו-0 הורדות.
  - אוכפים: gallery_cut.py (code)
  - מקורות בזיכרון: osxphotos_confirm_prompt_kills_fetch

## plan

- **L05_no_volatile_metadata_in_pass_payload** — ערך שמשתנה בלי שהתוכנית השתנתה (גודל קובץ · רשימת שערים · last_used_days · זמן-ריצה) לא נכנס ל-payload של פאס — כל אחד מהם שבר --backend replay.
  - אוכפים: edit_director.py (code), test_scorer_payload_stability.py (test)
- **L10_hook_and_cta_are_sacred** — לא בירול על ה-Hook (4ש ראשונות) ולא על ה-CTA (8ש אחרונות); ב-tighten אזור ה-CTA נחתך רק על שקט ≥0.8ש. Hook מאוחר מועבר לפתיחה, לא נחתך.
  - אוכפים: broll_director.py (code), edl_build.py (code)
- **L21_thresholds_from_approved_videos** — כל סף קצב/שקט/תפרים נגזר ממדידה של סרטונים שהראל אישר (reference_profile, 16 סרטונים) — לא מניחוש. envelope_score הוא ציון נמדד, לא ציון עצמי.
  - אוכפים: reference_profile.json (code), output_profile:envelope_score (gate)
  - מקורות בזיכרון: silence_and_music_are_one_defect, trailing_deadair_gate_tightened_0_9, zero_silence_in_reels ⟲
- **L22_seams_cost_more_than_silence** — אחוז השקט אינו המטרה — קיצוץ פער חוסך 0.2ש ועולה תפר נראה. חיתוך רק אם החיסכון ≥0.50ש; עדיף 20% שקט עם 10 תפרים מ-16% עם 24.
  - אוכפים: director.plan_v1.3.md (code)
  - מקורות בזיכרון: zero_silence_in_reels ⟲
- **L25_harel_corrections_reach_director** — התיקונים של הראל (corrections.jsonl מכל הפרויקטים, לפי cohort) נכנסים לפיילוד של הבמאי כ-harel_lessons — למידה מ-n=1, לא רק כיול ספים ב-n≥6. הקובץ דטרמיניסטי (בלי חותמות-זמן) כדי לא לשבור replay.
  - אוכפים: director_lessons.py (code), edit_director.py (code), test_director_lessons.py (test)
  - מקורות בזיכרון: harel_conversation_edit_keep_and_speed
- **L28_prompt_promises_must_reach_the_payload** — פרומפט שמורה למודל לשפוט לפי מדד — והמסננת של ה-payload לא מעבירה את המדד — מייצר החלטה שנראית מנומקת ומבוססת על None. כל שדה שהפרומפט מזכיר בשמו חייב להופיע ב-_slim_candidate.keep.
  - אוכפים: edit_director.py (code), test_director_payload_visual_fields.py (test)
- **L29_code_that_edits_a_value_owns_its_legality** — קוד שרשאי לשנות ערך שהמודל ביקש (best_split/KEEP_NUDGE) אחראי לכך שהערך יישאר חוקי מול כל שער חוסם. אחרת נוצר מצב שאין ממנו יציאה: אף ערך שהבמאי יבקש לא יעבור, כי מה שנכשל נוצר **אחרי** הבקשה שלו.
  - אוכפים: edit_plan.py (code), test_moving_gap_ceiling.py (test)
- **L30_a_gap_the_body_moves_through_is_a_shot** — פער שהדובר עובר בו מסלול גוף רציף אינו שתיקה אלא שוט, ותקרת הפאוזה (שנגזרה מפאוזות-שקט על תמונה סטטית) אינה חלה עליו כפי שהיא. ההקלה מותנית בתנועה מוכחת (pose_range ≥0.25, פי-10 מהחציון), חסומה ל-0.84ש, ומדווחת — ושער התנוחה ממשיך לחול במלואו.
  - אוכפים: edit_plan.py (code), test_moving_gap_ceiling.py (test)
- **L31_sentence_text_must_keep_its_first_word** — שיוך מילה→משפט חייב להיות לפי קרבה ולא לפי הכלה בחלון זמן: גבולות המשפטים נבנים מזמנים **מוצמדים** (snap_words_to_audio) והמילים נקראות מ-whisper_raw הלא-מוצמד. ההפרש שיטתי ותמיד באותו כיוון — המילה הראשונה של כל משפט נופלת החוצה.
  - אוכפים: edit_director.py (code), test_sentence_text_keeps_first_word.py (test)
- **L33_two_policies_on_one_cut_is_a_bug** — שני שערים שחלוקים על אותו חיתוך אינם שער — הם תקלה. ההוק מתחיל במילה הראשונה; שקט שלפניה אינו הוק ואינו נספר ב-hook_protected.
  - אוכפים: canon_lint.py (code), test_hook_lead_silence.py (test)
- **L35_a_seam_is_a_boundary_not_a_decision** — תקציב התפרים נמדד בגבולות בין קטעים שנשמרו, לא במספר החלטות החיתוך. החלטות צמודות (פער שקוצץ + המשפט שהוסר אחריו) יוצאות כגוש אחד ומייצרות קפיצה אחת על המסך.
  - אוכפים: edit_plan.py (code), test_seam_count_is_visible_seams.py (test)
- **L36_open_visual_must_not_end_after_speech_starts** — חלון 'לפני הדיבור' נבנה מהמילה הראשונה **אחרי** ההצמדה לאנרגיה, וההצמדה רשאית להזיז מילה מאוחר יותר — ואז החלון בולע את תחילת הדיבור. הבנייה חייבת לקחת את המוקדם מבין ההתחלה המוצמדת לגולמית.
  - אוכפים: candidates.py (code), test_open_visual_never_eats_speech.py (test)
- **L47_illustration_is_rationed_not_available** — המחשה ויזואלית היא אירוע, לא פיצ'ר. ברירת המחדל היא אפס; אחת לסרטון; שתיים רק דרך חריגה מנומקת שחוצה סף גבוה בהרבה ומדווחת. בנוסף — קצב על פני הקטלוג: אם המחשות הופיעו ביותר מסרטון אחד מתוך חמשת האחרונים, הסף עולה. תוכן המרה מוחרג לגמרי (מצע בירולים רציף).
  - אוכפים: illustration_gate.py (code), illustration_gate.py (code), illustration_gate:IL3_dosage_budget (gate), illustration_gate:IL1_content_type_eligible (gate), test_illustration_gate.py (test)
- **L91_correction_bursts_count_once** — קליקים חוזרים של הראל על אותו חיתוך תוך שניות הם אירוע אחד בלולאת הלמידה (BURST_GAP_SEC) — אחרת הראיות מתנפחות.
  - אוכפים: learn_from_edits.py (code)
  - מקורות בזיכרון: learning_loop_burst_coalescing_fix

## preflight

- **L60_cta_keyword_must_match_the_flow** — מילת המפתח שה-Flow האוטומטי מאזין לה, המילה שנאמרת בקול ב-CTA והטקסט על המסך הם דבר אחד. אי-התאמה הורגת את כל שרשרת המסירה **בשקט** — הסרטון נראה מצוין ואף אחד לא מקבל כלום. מילת מפתח שלא נאמרת בתמליל = חוב צילום, לא נושא לעריכה.
  - אוכפים: preflight_critic.py (code), preflight:P17_ai_app (gate), test_preflight_ai_app.py (test), test_preflight_ai_app.py (test)
- **L61_problem_first_never_tool_first** — סרטון AI-אפליקציה נפתח בבעיה קונקרטית בגוף ראשון, לא בשם הכלי ולא ב-AI. המבנה: בעיה → מה בניתי → מה זה פתר. שם הכלי ב-4 השניות הראשונות = ממצא.
  - אוכפים: preflight_critic.py (code), test_preflight_ai_app.py (test), SKILL.md (doc)
- **L62_home_screen_moment_belongs_next_to_the_cta** — הצופה מקבל לינק ולא יודע שזה הופך לאפליקציה על הטלפון שלו. קטע "הוספה למסך הבית" באורך 5-10ש צמוד לרגע ה-CTA סוגר את הפער. חומר חסר = shot_debt מוצהר, לא ויתור שקט.
  - אוכפים: preflight_critic.py (code), test_preflight_ai_app.py (test)
- **L63_value_goes_out_on_two_channels** — הערך נמסר בשני ערוצים ולא באחד: DM אוטומטי למי שהגיב, ודף הקישורים בביו (Metricool SmartLink) למי שלא. ערוץ אחד בלבד מאבד את כל מי שצפה ולא הגיב, ואת כל מי שמגיע לפרופיל חודש אחרי.
  - אוכפים: preflight_critic.py (code), test_preflight_ai_app.py (test), SKILL.md (doc)

## process

- **L18_no_blocking_gate_on_unmeasured_threshold** — אין שער חוסם עם סף לא-מדוד. 60MB היה מספר עגול בשער חוסם ותוקן ידנית בכל ריצה — הופרד לדיווח.
  - אוכפים: qa_gates:G5c_size (gate), gate_registry.py (code)
  - מקורות בזיכרון: no_blocking_gate_on_unmeasured_threshold
- **L26_lessons_need_enforcers** — לקח בלי אוכף (קוד/בדיקה/שער) הוא נוהל שיישכח בהחלפת המנוע הבאה. הרשומה הזאת נבדקת ב---audit כשער ב-system_doctor.
  - אוכפים: system_doctor.py (code), test_lesson_registry.py (test)
  - מקורות בזיכרון: lessons_dont_survive_an_engine_swap
- **L37_no_visual_claim_without_eyes** — אמירה על מה שיש בסרטון — הוק, שוט, כתובית, קאבר, QA — נשענת על פתיחת גיליונות המגע בפועל, לא על report.md, שם הקובץ או התסריט המתוכנן. כל הערה נושאת חותמת זמן, אחרת אינה ניתנת לתיקון. bundle ראייה ישן מהקובץ שהוא מתאר נפסל — הוא מתאר וידאו אחר.
  - אוכפים: vision_check.py (code), preflight_critic.py (code), video_eyes.py (doc), test_vision_law.py (test)
  - מקורות בזיכרון: video_qa_checklist
- **L38_a_round_threshold_is_not_a_gate** — סף שהגיע כמספר עגול בהנחיה (0.3ש למילה ראשונה · 2.0ש לשינוי · 1.2ש לשתיקה · 3.5ש לחלון סטטי) נכנס כמדווח, לא כחוסם, עד שנמדד מול סרטונים שהראל אישר. נמדד בפועל: reference_profile מראה longest_pause חציון 0.81ש ומקסימום 5.83ש ב-16 המאושרים — סף חוסם של 1.2ש היה פוסל את הראל לעצמו.
  - אוכפים: vision_check.py (code), vision_check.py (code), test_vision_law.py (test)

## publishing

- **L64_public_artifact_is_pinned_never_latest** — דף אפליקציה מתארח כ-Artifact של קלוד. לינק ציבורי (General access = Anyone with the link) **תמיד נעוץ לגרסה מספרית** — האפשרות Latest חסומה כל עוד הגישה ציבורית. לכן כל פרסום מחדש לא מגיע לקהל עד שמזיזים ידנית את Shared version, ואין על זה שום שגיאה. אימות: כפתור ה-Share עצמו אומר sharing pinned version {n}.
  - אוכפים: SKILL.md (doc), README.md (doc)
- **L65_activated_flow_must_prove_zero_backfill** — אוטומציית תגובה→DM מופעלת רק אחרי שנמדד שהיא לא נגעה בתגובות הקיימות: מיד אחרי Activate בודקים ברשימת ה-Flows ש-Sends=0 ו-Last execution ריק. הראל שולח ידנית לפני שהאוטומציה קיימת, ולכן backfill = הודעה שנייה לאותם אנשים, נזק בלתי הפיך.
  - אוכפים: פלייבוק-Flow-תגובה-ל-DM.md (doc), SKILL.md (doc)

## render

- **L01_seam_fade_exposes_speaker** — fade על אלפא בתפר פנימי של בירול מוריד את שקיפות הבירול וחושף את הדובר בדיוק בקאט (נמדד: 3 פריימים = 0.1ש). בתפר פנימי אין fade, ו-eof_action=repeat.
  - אוכפים: render.py (code), render.py (code), render:segment_stall_budget (gate)
  - מקורות בזיכרון: broll_hard_cut_between_adjacent
- **L20_stall_fallback_measured_not_counted** — ספירה אינה מנבאת התנהגות: התקיעה ב-v2 היא per-segment (seek מדויק+overlay), לא per-count. -noaccurate_seek נמדד ונכשל על הפקודה האמיתית ולכן לא בקוד; הנפילה ל-v1 היא ה-fallback הפעיל, וההחלטה נמדדת.
  - אוכפים: FFMPEG-STALL.md (doc), local_finish_pipeline.py (code), render.py (code)
- **L27_render_captions_interface_is_a_contract** — מנוע הרינדור v2 צורך את captions_overlay דרך פרופיל המותג (BRAND_PROFILES/BRAND_ALIASES) — לא דרך קבועים גלובליים. שינוי ממשק בכלי אחד בלי לבדוק את הצרכן השני = שבירה שקטה שרק בדיקת אינטגרציה תופסת.
  - אוכפים: render.py (code), captions_overlay.py (code), test_render_v2.py (test)
- **L39_speed_must_not_cost_a_re_tighten** — האצה (--speed) ותכנון פערים הן שתי החלטות נפרדות, ואסור שהאחת תגרור את השנייה. עד v9.15 --speed נאכף רק בתוך שלב ההידוק, ולכן כל תוכנית שהפערים בה כבר הוכרעו — ע"י הבמאי או ע"י הראל באפליקציה — שילמה על ההאצה בחיתוך שתיקות נוסף. ההאצה מתבצעת מעכשיו במסלול speed-only (--min-sil 99): אותו שלב, אפס שתיקות נחתכות.
  - אוכפים: local_finish_pipeline.py (code), local_finish_pipeline.py (code), test_speed_without_retighten.py (test)
  - מקורות בזיכרון: speed_tighten_residual_edge_silence
- **L40_word_map_must_use_the_measured_cut** — מיפוי המילים לציר הקאט חייב להיכייל לאורך ה-EXPORT **שנמדד**, לא לסכום משכי ה-keep המתוכננים. edl_cut מעגל כל מקטע כלפי מעלה לגבול פריים — כחצי פריים לתפר — וההפרש מצטבר, ולכן הכתוביות מקדימות ביחס ישר למספר התפרים.
  - אוכפים: local_finish_pipeline.py (code), qa_gates:G6c_caption_drift_bias (gate), test_word_map_calibration.py (test)
  - מקורות בזיכרון: captions_accurate_timing
- **L42_overlay_input_must_be_trimmed** — כל קלט בירול נפתח עם `-t` באורך החלון שלו. בלי זה הקלט המשני ארוך מהחלון, ו-`eof_action=repeat` (L: v8.4) מחזיק את הפריים האחרון של **הבסיס** עד שכל הקלטים נגמרים — כלומר הסרטון מתארך מעבר לווידאו ומסתיים בתמונה קפואה. הבדיקה: אורך EXPORT+BROLL חייב להיות שווה לאורך EXPORT_TIGHT.
  - אוכפים: animation_overlay.py (code), test_overlay_no_tail_freeze.py (test)
- **L44_full_intro_must_be_automatic** — נכס שמתועד בקטלוג אבל אף שלב בצנרת לא מרכיב אותו — לא קיים. פורמט עם `פתיח מלא` מזוהה **מהכותרת/הבריף** (לא מהתמליל — הדובר לא אומר 'מאסל מן' בגוף הסרטון) ומודבק אוטומטית אחרי `deliver` ולפני השערים. שלושה כללי הרכבה שנמדדו: (1) concat demuxer עם -c copy משאיר duration ישן בזרם ו-avg_frame_rate יוצא מדומה — המסלול הוא mp4→mpegts→concat→mp4; (2) אורך אודיו ≠ אורך וידאו בפתיח שובר את החיבור — חותכים לאורך הווידאו; (3) הפתיח מנורמל **למפלס הגוף הנמדד**, לא לערך קבוע.
  - אוכפים: fixed_intro.py (code), fixed_intro.py (code), fixed_intro.py (code), local_finish_pipeline.py (code), test_full_intro.py (test)
  - מקורות בזיכרון: myth_effect_silent_gap_and_edl_review_consistency
- **L48_css_mask_from_file_url_is_blocked** — CSS mask-image מקובץ מקומי (file://) נחסם ב-Chrome ומחזיר ERR_FAILED — והשכבה הממוסכת נעלמת **בשקט**, בלי שגיאה בקונסולה ובלי שינוי ב-computed style. כל מסכה ותמונה בקומפוזיציה מוטמעות base64 inline. וברינדור מקומי מסירים את סקריפט הרנטיים של HyperFrames — הוא מרוקן את הקומפוזיציה.
  - אוכפים: illustration_build.py (code), illustration_build.py (code), test_illustration_gate.py (test)
- **L50_placement_is_solved_from_the_frame_not_hardcoded** — מיקום ההמחשה בפריים **נפתר מהפריים עצמו** ולא מוזן כמספר קבוע: קופסאות פנים (אזור אסור מוחלט) + רצועת הכתוביות (מהקאנון) + מפת עומס (תנועה וקצוות). **הרצועה המועדפת היא מתחת לראש ומעל הכתוביות** — רצועת הגוף: בקו המבט, גבוהה פי שניים מהמקום שמעל הראש (ולכן הקלף גדול וקריא יותר), ובלי התקרה והדגלונים שהופכים המחשה לבאנר מודבק. העדפה ולא חוק: רצועה נמוכה מ-0.16 ⇒ נסיגה למקום הטוב הבא, עם דיווח למה. שובר-שוויון: מרכוז אופקי, ואז שטח. אין מיקום חוקי ⇒ ההמחשה יורדת — כיסוי פנים אינו פשרה. ובנוסף: **אין רקע שחור** — האיור צף מעל הווידאו, עם הילה כהה ש**עוצמתה נגזרת מ-`busy_cost` שכבר נמדד**: רחבה ריקה כמעט לא צריכה הילה, חליפת שרירים מודפסת בולעת את האיור בלעדיה.
  - אוכפים: illustration_place.py (code), illustration_place.py (code), illustration_build.py (code), illustration_place:IL8_face_occlusion (gate), test_illustration_place.py (test)
- **L58_hook_engine_changes_picture_only_in_both_engines** — המנוע משנה תמונה בלבד: audio_mode=preserve, אותו מספר פריימים, EXPORT הנקי לא נדרס (cut_qa/קאבר צורכים אותו), ואותה תוכנית קפואה ב-v1, ב-v2 וב-fallback — אף ענף בירול ב-v1 לא מקבל ‎--base EXPORT כשיש טיפול.
  - אוכפים: hook_render.py (code), local_finish_pipeline.py (code), render.py (code), test_visual_hook_render.py (test), test_visual_hook_render.py (test)
- **L80_hlg_is_tonemapped_not_graded** — גלם HLG/HDR מומר ל-SDR ב-tonemap של macOS (tonemap.swift), לא ב-ffmpeg ולא בתיקון צבע ידני. 'צבעים דהויים' = לבדוק color_transfer קודם.
  - אוכפים: render.py (code), registry.py (code)
  - מקורות בזיכרון: prep_ffmpeg_nostdin_and_swift_rendersize, faded_colors_check_hlg_first, hlg_tonemap_macos_swift, hdr_hlg_tonemap_before_descript ⟲
- **L84_concat_truncation_is_measured_on_video** — concat demuxer עם -c copy יכול לקטוע את ערוץ הווידאו בשקט (exit 0, אודיו ממשיך). משך נבדק על ערוץ הווידאו עצמו, ובכשל ה-join נבנה מחדש ב-concat filter — לא רק נכשל אחרי שהקובץ השבור נכתב.
  - אוכפים: edl_cut.py (code), edl_cut.py (code), test_vision_gates_v930.py (test)
  - מקורות בזיכרון: edl_cut_concat_demuxer_video_truncation_bug
- **L88_one_generation_spends_the_bitrate** — ב-v2 יש דור קידוד אחד — שם מוציאים את התקציב (crf19/medium), לא crf23/veryfast שנבחר כשהיו 4-7 דורות.
  - אוכפים: render.py (code)
  - מקורות בזיכרון: v2_render_crf23_too_soft
- **L89_no_black_bars_blur_fill** — מקור שאינו 9:16 ממלא את הפריים ברקע מטושטש של אותו פריים — אף פעם פסים שחורים (קאבר ובירול).
  - אוכפים: thumbnail_build.py (code), animation_overlay.py (code)
  - מקורות בזיכרון: landscape_to_vertical_blur_background
- **L90_filtergraph_hygiene** — filter_complex נבנה בלי ';' עודף בסוף — ffmpeg מחזיר 'No such filter: ' על גרף תקין.
  - אוכפים: tighten_finish.py (code)
  - מקורות בזיכרון: tighten_finish_trailing_semicolon_bug

## vision

- **L73_measured_does_not_mean_promoted** — למדוד שער זה לא לקדם אותו לחוסם. ההחלטה נגזרת מהמדידה ונשמרת כדאטה (promote + why_not_blocking): סף קאנוני שהיה פוסל סרטון מאושר, או שער בלי מחלקה שלילית, נשאר מדווח — עם המעטפת בפירוט.
  - אוכפים: vision_check.py (code), vision_check.py (code), vision_check.py (code), test_vision_gates_v929.py (test)

## הוחלפו (היסטוריה — לא ליישם)

- `60s_hard_cap_policy` → L67_length_follows_content_not_60s
- `broll_conversion_only` → L09_audience_determines_structure
- `broll_swap_local_ffmpeg` → L77_broll_is_judged_where_it_landed
- `dana_yad_no_latin_glyphs` → L15_cover_single_entry_with_gates
- `danayad_font_garbles_without_raqm` → L15_cover_single_entry_with_gates
- `descript_composition_default_4k` → ops:fully_local_no_descript_proven
- `descript_import_batch_limit` → ops:fully_local_no_descript_proven
- `hdr_hlg_tonemap_before_descript` → L80_hlg_is_tonemapped_not_graded
- `metricool_two_post_structure` → ops:metricool_post_checklist
- `music_mix_no_ducking_full_length` → L54_music_bed_calibrated_down_again, L86_music_bed_in_every_video_full_length
- `music_volume_low` → L54_music_bed_calibrated_down_again
- `playpen_font_garbles_hebrew` → L15_cover_single_entry_with_gates
- `speed_ramp_over_60s` → L67_length_follows_content_not_60s
- `subtitle_size_independent_fit_not_ratio` → L72_the_cover_is_judged_on_the_png
- `thumbnail_danayad_font_garbled_hebrew` → L15_cover_single_entry_with_gates
- `zero_silence_in_reels` → L21_thresholds_from_approved_videos, L22_seams_cost_more_than_silence
