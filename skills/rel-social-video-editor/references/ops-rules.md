# rel-social-video-editor · ops-rules
> נגזר מהמאסטר (v9.40 — 2026-10-04) ע"י tools/skill_pack.py — לא לערוך כאן.

## כללי תפעול מהזיכרון (קנון v9.30)

כללים לסוכן שאינם קוד — כל שורה נבדקת ב-`tools/lessons_canon.py --audit`. מקורם בקבצי ה-feedback של זיכרון הפרויקט; הלקחים שנאכפים בקוד חיים ב-`lesson_registry`.

| slug | הכלל |
|---|---|
| `always_attach_folder_access` | בדיווח על תוצר — לצרף גישה ישירה לתיקייה/לקובץ, לא רק נתיב |
| `always_present_finished_videos_in_chat` | סרטון גמור מוצג בצ'אט (קובץ), לא רק לינק או נתיב |
| `always_update_social_board` | כל שינוי סטטוס/אבן דרך של סרטון מתעדכן בבורד הסושיאל 18395578529 |
| `broll_catalog_stale_path_trap` | נתיב הקטלוג נקרא מ-broll-catalog-config.json (catalog_path) — לא מנחשים |
| `broll_kenburns_supersample` | Ken Burns על סטילס — supersample נגד רעד (rel-broll-creator) |
| `broll_michael_levi_pipeline` | קומפילציות בירול מיכאל לוי — נוסחת הצבע והחיתוך המאושרת (rel-broll-creator) |
| `caption_authentic_voice` | קפשן מדובר ואנושי, מבוסס תסריט, לא פרסומי — דרך rel-cta-psychology |
| `caption_cta_by_post_destination` | CTA לפי רשת: אינסטגרם 'פרטים בביו 👆'; FB/TikTok/YT קישור ישיר |
| `caption_grounded_no_fake_offers` | קפשן רק ממה שנאמר בסרטון — אין הצעות/מבצעים מומצאים |
| `caption_warm_energetic_voice` | קפשן חם ואנרגטי, beat קהילה |
| `captions_app_weak_model_use_turbo_instead` | captions-app: מודל turbo+VAD (לא small בלי VAD) |
| `captions_emoji_readability` | קפשן עם שורות רווח ואימוג'י מידתי — לא 'מגילה' |
| `competitor_diplomatic_captions` | אזכור מתחרים/סטודיואים — דיפלומטי בלבד |
| `content_emails_always_all_source_links` | מייל תוכן (כשנשלח בכלל) כולל את כל הלינקים למקורות |
| `cover_caption_same_round_as_finish` | טיוטת קאבר+קפשן מוכנה באותו סבב גימור |
| `cover_step_direct_metricool_link` | כשהראל מעלה קאבר ידנית — לינק ישיר לפוסט ב-Metricool |
| `cta_no_dry_bio_link` | 'פרטים בביו' לבד אינו CTA — CTA מתאר רווח בהקשר הסרטון |
| `desktop_commander_background_job_shell_hygiene` | לא לשתמש שוב ב-shell שהריץ nohup ... & |
| `document_final_caption_on_board` | אחרי תזמון — Update בבורד עם הקפשן הסופי |
| `facebook_title_always` | תזמון Metricool: facebookData.title תמיד מלא |
| `fb_group_posting_technique` | פרסום בקבוצות FB דרך Chrome — מנגנון ה-JS המאומת |
| `finish_pipeline_needs_desktop_commander` | גימור ארוך רץ ב-Desktop Commander על המק, לא ב-bash של הסנדבוקס |
| `fully_local_no_descript_proven` | Descript מחוץ לזרימה — [DESCRIPT FALLBACK] רק אחרי שני כשלים מקומיים ובאישור |
| `harel_posts_light_blue_heart` | קפשן אישי של הראל = לב תכלת |
| `metricool_api_strips_composer_fields` | location/carouselTags — דרך API v2, ה-MCP מוחק בשקט |
| `metricool_cover_manual_only` | קאבר וידאו ב-Metricool — ידני בקומפוזר בלבד; הסוכן מייצר PNG |
| `metricool_post_checklist` | Definition-of-Done לפוסט Metricool + אימות ויזואלי בקומפוזר |
| `missing_cover_search_project_folder_first` | קאבר 'חסר' — לחפש קודם בתיקיית הפרויקט |
| `monday_date_column_is_utc` | עמודת תאריך+שעה ב-Monday = UTC — מקומי פחות 3, וקריאה חוזרת |
| `monday_upload_via_mac_desktop_commander` | העלאת קבצים גדולים ל-Monday — מהמק דרך Desktop Commander |
| `monthly_corners_fixed_ranges_and_oct7` | פינות חודשיות בטווחי ימים קבועים; אין תוכן ב-7.10 |
| `never_bypass_finish_pipeline` | לעולם לא לבנות שלבי גימור ידנית — רק local_finish_pipeline |
| `never_compress_video_files` | לעולם לא לדחוס/לקודד מחדש FINAL |
| `never_gym_always_crossfit_club` | לעולם לא 'חדר כושר' — מועדון קרוספיט |
| `never_invent_metricool_schedule_date` | תאריך תזמון רק מעמודת התאריך בבורד |
| `never_touch_colors` | לא נוגעים בצבע (חריג: HLG → tonemap) |
| `no_hashtags_in_captions` | אפס האשטגים בכל קפשן ובתגובה הראשונה |
| `personal_brand_light_blue_heart` | הראל = 🩵; המועדון = 🖤❤️ — לא מחליפים |
| `podcast_always_4k` | פרקי 'מדברים כושר' נשארים 4K |
| `podcast_captions_club_brand_not_personal` | כתוביות פודקאסט = מותג מועדון גם בפרופיל האישי |
| `published_vs_scheduled_state_bug` | 'פורסם בפועל' רק אחרי פרסום אמיתי — לא אחרי תזמון |
| `raw_footage_local_first_intake` | קליטת גלם מקומית — לא מעלים למאנדיי |
| `reproduce_exact_run_command` | גימור חוזר — הפקודה המדויקת מרשומת הריצה |
| `review_app_round_tracking` | אחרי תיקון מהערות הראל — POST /api/round/<name>/correct |
| `review_app_stale_process_after_code_update` | אחרי עדכון קוד בשרת — launchctl kickstart, לא nohup |
| `save_skill_overwrites_reference_files` | שמירת סקיל דורסת references/ מקומיים — לסנכרן ולאמת diff |
| `scheduling_always_update_monday_and_app` | כל תזמון מסתיים בעדכון Monday + אפליקציית הרוויו |
| `scheduling_horizon_one_month` | אופק תזמון ~חודש; לא היום/מחר בלי אישור, לא חודשיים+ בלי וידוא |
| `screen_recording_carries_narration` | הקלטת מסך אינה בירול אילם — לתמלל לפני מבנה העריכה |
| `thumbnail_inpaint_captions` | קאבר מסרטון עם כתוביות בלי EXPORT — inpaint על פריים חד, לא טשטוש |
| `thumbnail_match_video_aspect` | הקאבר ביחס של הסרטון (1:1 ↔ 9:16) |
| `two_layer_fix_means_wrong_layer` | תיקון באותה בעיה בשתי שכבות = השכבה הנכונה לא זוהתה |
| `work_folder_names_hebrew_content_based` | תיקיות _work לפי תוכן בעברית, לא תעתיק |

### חידודים לסוכן מהזיכרון (22.9.26 — פערים שהלקח בקוד לא מכסה)
הטבלה למעלה נגזרת מ-`lessons_canon_data.py` (`--ops-table`); השורות כאן ידניות — סדר אבחון והרגלי הרצה שהלקח האכוף לא אומר לסוכן.
- `dedicated_broll_plan_paths_and_content_type_override` — בירול ידני בצ'אט = `broll_plan.json` בתיקיית העבודה + refinish, לא overlay ישיר על FINAL. `overlay_args` ו-`--broll-plan` בנתיב מוחלט: הגימור רץ עם cwd בשורש הפרויקט ו-`--broll-plan` יחסי נפתר מולו.
- `music_manifest_pref_overrides_cli` — החלפת טראק = `project_manifest.json → finish_prefs.music.track` (גובר על `--music`), ואז refinish; `--music` רק בנתיב מלא.
- `music_too_loud_genre_mismatch_not_lufs` · `silence_and_music_are_one_defect` · **L138** — "המוזיקה חזקה מדי": (1) `MIXED.mp4.musicgap.json` — gap ≥ רצפה (25) וחלון מקומי גרוע ≥ ~18.5 (רצפה מקומית 20); חסר `local` ⇒ גומר לפני 14.10.26 ⇒ refinish; (2) פערים ≥0.35ש שבהם המוזיקה חשופה; (3) ז'אנר מול טון הבריף. מפלס משנים דרך `finish_prefs.music.gap_db` (יחסי), לא `music_lufs` מוחלט. אחרי כל שינוי מדיניות — לסרוק את התור ב-Metricool: קבצים שגומרו קודם לא מתעדכנים לבד.
- `edl_restore_scrambles_segment_order` — G6/coverage נכשלים בעשרות אחוזים אחרי restore/sync ⇒ קודם משווים את התוכן המדובר בכל `keep_segment` לסדר `edited.txt` ומסדרים לפי התוכן; רק אחר כך בודקים alignment (סדר לא-כרונולוגי לא נחסם בקוד — חוב גלוי).
- `oct26_batch_refinish_traps` — (1) `cut_qa possible_freeze` על תפר בשוט חצובה סטטי ⇒ מזיזים/מבטלים את התפר ובודקים בגיליון, לא עוקפים את השער. (2) שורת Hook מתוכננת חסרה בתמליל ⇒ קודם `astats` RMS לכל קליפ (הוקלטה בכלל?), רק אז חושדים ב-ASR. (3) הערת "קצב/מהירות" על סרטון עם speed≠1 ⇒ קודם `playbackRate` של נגן האפליקציה וסדר השלבים ב-finish log; לא נוגעים בקובץ לפני כן.
- `whisper_correction_engine_validated_open_gym_40plus` — תיקון תמליל בסדר קבוע: שיבושי אותיות שיטתיים (כ/ק, ח/ה) → מונחים מקצועיים → מספרים ומחירים מוצלבים מול סרטון תאום באותו קמפיין; מה שנשאר עמום = `needs_manual`, לא ניחוש.

### מבחני זהב (התנהגות הסוכן — v9.31)
1. **קלט:** "הסרטון 'בריאות-להרים' יצא 72 שניות אחרי ההידוק (תוכן ערך), תגמור אותו." → **פלט מצופה:** האורך נבדק מול `tools/length_policy.py` (ערך 45-90ש) ונשאר 72ש; אין `--speed` ואין חיתוך ביט כדי לרדת ל-60; הדיווח מצטט את הטווח ואת פלט `qa_gates`. **אסור:** "צריך קצב 1.1 כדי לרדת מ-60".
2. **קלט:** "תזמן את הריל 'על הלוח' ב-Metricool." → **פלט מצופה:** `state==ready_to_schedule` ו-sha256 של הקובץ ב-`approved_final_path` תואם לפני `createScheduledPost`; התאריך מ-`date_mkrpvw3n` (חסר ⇒ עוצרים ושואלים, best-time קובע שעה בלבד); `facebookData.title` מלא; location בפאץ' API v2; אימות ב-`getScheduledPosts` (חוק 16) → Monday "תוזמן!" + תאריך UTC שנקרא חזרה + Update → `state_override:"scheduled"` באפליקציה (שלב 7 סעיף 5) → דיווח בצ'אט. **אסור:** מייל אימות שגרתי · `state_override:"published"` על פוסט שעוד לא עלה (published רק ידני / `providers[].status=PUBLISHED`).
3. **קלט:** "תחליף את הבירול בשנייה 14 ותוריד טיפה את המוזיקה." → **פלט מצופה:** `broll_plan.json` בתיקיית העבודה מתעדכן (נתיבים מוחלטים, קליפ מה-`catalog_path` שבקונפיג, מסך מלא, ≥1.8ש) ו-refinish דרך `run_finish.py` ב-Desktop Commander על המק; לפני הורדת מפלס נבדק ב-`FINISH_REPORT.md` שהדאקינג רץ, והשינוי נכתב ל-`finish_prefs.music.music_lufs`; FINAL החדש מוצג בצ'אט ככרטיס קובץ. **אסור:** overlay ffmpeg ישיר על FINAL, דחיסה או קידוד מחדש של הקובץ הסופי.
