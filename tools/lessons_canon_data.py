# -*- coding: utf-8 -*-
"""מיפוי קנוני: כל קובץ feedback בזיכרון הפרויקט (22.9.26, 133 קבצים) ← לקח אכוף.

status:
  L          — מכוסה ע"י לקח/ים ב-lesson_registry (האוכף שם)
  superseded — הוחלף; by = הלקח/הכלל שמחליף (לא נמחק — נשמר כהיסטוריה)
  ops        — כלל תפעולי לסוכן (Metricool/Monday/קופי/צ'אט) — לא קוד. האוכף: שורה
               בטבלת "כללי תפעול" ב-SKILL.md שמכילה את ה-slug (נבדק ב---audit)
debt: כלל שעדיין לא נאכף במלואו בקוד — חוב גלוי, לא לקח שאבד.
"""
C = {}

def m(slug, status, ids=(), rule="", debt=None):
    C[slug] = {"status": status, "ids": list(ids), "rule": rule, "debt": debt}

# ── וידאו/עריכה/כתוביות — מכוסים בקוד ──
m("audio_mix_nostdin_dc_terminal", "L", ["L74_ffmpeg_never_reads_stdin"])
m("prep_ffmpeg_nostdin_and_swift_rendersize", "L", ["L74_ffmpeg_never_reads_stdin", "L80_hlg_is_tonemapped_not_graded"])
m("broll_align_to_cuts", "L", ["L02_broll_edge_snaps_to_cut_boundary"])
m("broll_bridging_and_min_length", "L", ["L03_flash_gap_is_a_blink", "L08_min_clip_len_readability"])
m("broll_hard_cut_between_adjacent", "L", ["L01_seam_fade_exposes_speaker"])
m("broll_dept_library_separation", "L", ["L75_broll_brand_identity_is_checked"])
m("broll_personal_vs_club_separation", "L", ["L75_broll_brand_identity_is_checked"])
m("broll_harvest_burned_text_reject", "L", ["L76_burned_text_is_judged_by_eyes"])
m("broll_literal_transcript_anchor", "L", ["L06_anchor_reason_must_quote_sentence", "L34_anchor_sits_on_the_words_it_quotes", "L78_anchor_verdict_is_bound_to_the_final"])
m("broll_plan_always_applied_any_content_type", "L", ["L77_broll_is_judged_where_it_landed"])
m("broll_style_full_frame_no_box", "L", ["L77_broll_is_judged_where_it_landed"])
m("dedicated_broll_plan_paths_and_content_type_override", "L", ["L77_broll_is_judged_where_it_landed"])
m("conversion_broll_always_continuous_montage", "L", ["L09_audience_determines_structure"])
m("e2e_copies_leak_broll_usage", "L", ["L79_e2e_on_copies_never_commits_usage"])
m("edl_boundaries_from_energy_not_whisper", "L", ["L53_cut_boundaries_come_from_energy_not_from_whisper"])
m("edl_cut_concat_demuxer_video_truncation_bug", "L", ["L84_concat_truncation_is_measured_on_video"])
m("edl_merge_threshold_mismatch_ghost_sliver_fixed", "L", ["L03_flash_gap_is_a_blink"])
m("edl_restore_scrambles_segment_order", "L", ["L11_keep_segments_wins_sync"],
  debt="סדר קטעים לא-כרונולוגי אינו נחסם (לפעמים מכוון — הוק מוזז); מתגלה ב-G6 כשל קיצוני")
m("captions_accurate_timing", "L", ["L12_map_words_dont_retranscribe", "L40_word_map_must_use_the_measured_cut"])
m("captions_decollide", "L", ["L82_same_timestamp_words_are_decollided"])
m("captions_rtl_double_reversal_raqm", "L", ["L16_rtl_no_double_reversal", "L71_captions_are_judged_on_the_pixels"])
m("captions_rtl_punctuation_fix", "L", ["L83_rtl_punctuation_lands_left"])
m("never_arabic_characters_hebrew_only", "L", ["L81_no_arabic_codepoints_in_hebrew"])
m("whisper_correction_engine_validated_open_gym_40plus", "L", ["L85_burned_words_are_real_hebrew"])
m("whisper_default_medium_and_asr_glossary", "L", ["L85_burned_words_are_real_hebrew"])
m("whisper_transcript_linguistic_sanity_check", "L", ["L85_burned_words_are_real_hebrew"])
m("faded_colors_check_hlg_first", "L", ["L80_hlg_is_tonemapped_not_graded"])
m("hlg_tonemap_macos_swift", "L", ["L80_hlg_is_tonemapped_not_graded"])
m("landscape_to_vertical_blur_background", "L", ["L89_no_black_bars_blur_fill"])
m("learning_loop_burst_coalescing_fix", "L", ["L91_correction_bursts_count_once"])
m("lessons_dont_survive_an_engine_swap", "L", ["L26_lessons_need_enforcers"])
m("illustration_region_must_be_verified", "L", ["L46_illustration_region_must_be_verified"])
m("music_manifest_pref_overrides_cli", "L", ["L14_music_pref_overrides_cli"])
m("music_sales_only", "L", ["L86_music_bed_in_every_video_full_length"])
m("music_upbeat_not_elevator", "L", ["L13_tone_class_filters_genre", "L86_music_bed_in_every_video_full_length"])
m("music_too_loud_genre_mismatch_not_lufs", "L", ["L54_music_bed_calibrated_down_again", "L13_tone_class_filters_genre"])
m("music_track_offset_skip_quiet_intro", "L", ["L93_music_intro_dip_is_measured"],
  debt="מדווח בלבד (offset מוצע) — הפעלת offset אוטומטי דורשת את האוזן של הראל")
m("pre_take_mumble_and_music_balance", "L", ["L54_music_bed_calibrated_down_again"])
m("silence_and_music_are_one_defect", "L", ["L21_thresholds_from_approved_videos", "L54_music_bed_calibrated_down_again"])
m("silence_gate_nonblocking_post_review", "L", ["L17_review_approval_is_final"])
m("trailing_deadair_gate_tightened_0_9", "L", ["L21_thresholds_from_approved_videos"])
m("speed_tighten_residual_edge_silence", "L", ["L39_speed_must_not_cost_a_re_tighten"])
m("tighten_intro_gesture_jump_cut", "L", ["L87_intro_gesture_is_not_silence"])
m("tighten_finish_trailing_semicolon_bug", "L", ["L90_filtergraph_hygiene"])
m("v2_director_overridden_by_tighten", "L", ["L04_director_is_last_word_on_pacing"])
m("v2_render_crf23_too_soft", "L", ["L88_one_generation_spends_the_bitrate"])
m("video_qa_checklist", "L", ["L24_preflight_before_harel", "L37_no_visual_claim_without_eyes"])
m("no_blocking_gate_on_unmeasured_threshold", "L", ["L18_no_blocking_gate_on_unmeasured_threshold"])
m("osxphotos_confirm_prompt_kills_fetch", "L", ["L92_scheduled_fetch_never_waits_for_confirm"])
m("review_app_server_path_lacks_homebrew", "L", ["L50_server_must_not_depend_on_path"])
m("oct26_batch_refinish_traps", "L", ["L50b_finish_run_from_server_inherits_path", "L45_claude_verifies_fixes_before_harel"])
m("schedule_approval_artifact_id_stale", "L", ["L23_schedule_locks_artifact"])
m("never_reencode_scheduled_media", "L", ["L23_schedule_locks_artifact"])
m("captions_always_via_cta_psychology", "L", ["L41_caption_always_via_cta_psychology"])
m("myth_effect_silent_gap_and_edl_review_consistency", "L", ["L11_keep_segments_wins_sync", "L44_full_intro_must_be_automatic"])
m("harel_conversation_edit_keep_and_speed", "L", ["L25_harel_corrections_reach_director"])
# ── קאברים ──
m("cover_no_caption_bleed_always_export", "L", ["L15_cover_single_entry_with_gates", "L72_the_cover_is_judged_on_the_png"])
m("cover_title_bigger_than_subtitle_sacred_rule", "L", ["L72_the_cover_is_judged_on_the_png"])
m("cover_title_subtitle_always_bigger", "L", ["L15_cover_single_entry_with_gates", "L72_the_cover_is_judged_on_the_png"])
m("covers_always_2_lines_dana_yad", "L", ["L15_cover_single_entry_with_gates", "L72_the_cover_is_judged_on_the_png"])
m("covers_root_cause_gates_v912", "L", ["L15_cover_single_entry_with_gates"])
m("studentit_garbles_hebrew_despite_raqm", "L", ["L72_the_cover_is_judged_on_the_png"],
  debt="סדר אותיות בתוך שורת Studentit מדווח בלבד (תפיסה 50% בהזרקה); 36/36 קאברים חיים נמדדו תקינים")
m("studentit_punctuation_silent_fallback", "L", ["L15_cover_single_entry_with_gates"])
m("thumbnail_consistent_box_position", "L", ["L15_cover_single_entry_with_gates"])
# ── הוחלפו ──
m("60s_hard_cap_policy", "superseded", ["L67_length_follows_content_not_60s"])
m("speed_ramp_over_60s", "superseded", ["L67_length_follows_content_not_60s"])
m("broll_conversion_only", "superseded", ["L09_audience_determines_structure"])
m("broll_swap_local_ffmpeg", "superseded", ["L77_broll_is_judged_where_it_landed"])
m("dana_yad_no_latin_glyphs", "superseded", ["L15_cover_single_entry_with_gates"])
m("danayad_font_garbles_without_raqm", "superseded", ["L15_cover_single_entry_with_gates"])
m("thumbnail_danayad_font_garbled_hebrew", "superseded", ["L15_cover_single_entry_with_gates"])
m("playpen_font_garbles_hebrew", "superseded", ["L15_cover_single_entry_with_gates"])
m("subtitle_size_independent_fit_not_ratio", "superseded", ["L72_the_cover_is_judged_on_the_png"])
m("hdr_hlg_tonemap_before_descript", "superseded", ["L80_hlg_is_tonemapped_not_graded"])
m("music_volume_low", "superseded", ["L54_music_bed_calibrated_down_again"])
m("music_mix_no_ducking_full_length", "superseded", ["L54_music_bed_calibrated_down_again", "L86_music_bed_in_every_video_full_length"])
m("zero_silence_in_reels", "superseded", ["L21_thresholds_from_approved_videos", "L22_seams_cost_more_than_silence"])
m("metricool_two_post_structure", "superseded", ["ops:metricool_post_checklist"])
m("descript_composition_default_4k", "superseded", ["ops:fully_local_no_descript_proven"])
m("descript_import_batch_limit", "superseded", ["ops:fully_local_no_descript_proven"])

# ── כללי תפעול (לא קוד) — השורה ב-SKILL.md היא האוכף ──
OPS = [
 ("always_attach_folder_access", "בדיווח על תוצר — לצרף גישה ישירה לתיקייה/לקובץ, לא רק נתיב"),
 ("always_present_finished_videos_in_chat", "סרטון גמור מוצג בצ'אט (קובץ), לא רק לינק או נתיב"),
 ("always_update_social_board", "כל שינוי סטטוס/אבן דרך של סרטון מתעדכן בבורד הסושיאל 18395578529"),
 ("broll_catalog_stale_path_trap", "נתיב הקטלוג נקרא מ-broll-catalog-config.json (catalog_path) — לא מנחשים"),
 ("broll_kenburns_supersample", "Ken Burns על סטילס — supersample נגד רעד (rel-broll-creator)"),
 ("broll_michael_levi_pipeline", "קומפילציות בירול מיכאל לוי — נוסחת הצבע והחיתוך המאושרת (rel-broll-creator)"),
 ("caption_authentic_voice", "קפשן מדובר ואנושי, מבוסס תסריט, לא פרסומי — דרך rel-cta-psychology"),
 ("caption_cta_by_post_destination", "CTA לפי רשת: אינסטגרם 'פרטים בביו 👆'; FB/TikTok/YT קישור ישיר"),
 ("caption_grounded_no_fake_offers", "קפשן רק ממה שנאמר בסרטון — אין הצעות/מבצעים מומצאים"),
 ("caption_warm_energetic_voice", "קפשן חם ואנרגטי, beat קהילה"),
 ("captions_app_weak_model_use_turbo_instead", "captions-app: מודל turbo+VAD (לא small בלי VAD)"),
 ("captions_emoji_readability", "קפשן עם שורות רווח ואימוג'י מידתי — לא 'מגילה'"),
 ("competitor_diplomatic_captions", "אזכור מתחרים/סטודיואים — דיפלומטי בלבד"),
 ("content_emails_always_all_source_links", "מייל תוכן (כשנשלח בכלל) כולל את כל הלינקים למקורות"),
 ("cover_caption_same_round_as_finish", "טיוטת קאבר+קפשן מוכנה באותו סבב גימור"),
 ("cover_step_direct_metricool_link", "כשהראל מעלה קאבר ידנית — לינק ישיר לפוסט ב-Metricool"),
 ("cta_no_dry_bio_link", "'פרטים בביו' לבד אינו CTA — CTA מתאר רווח בהקשר הסרטון"),
 ("desktop_commander_background_job_shell_hygiene", "לא לשתמש שוב ב-shell שהריץ nohup ... &"),
 ("document_final_caption_on_board", "אחרי תזמון — Update בבורד עם הקפשן הסופי"),
 ("facebook_title_always", "תזמון Metricool: facebookData.title תמיד מלא"),
 ("fb_group_posting_technique", "פרסום בקבוצות FB דרך Chrome — מנגנון ה-JS המאומת"),
 ("finish_pipeline_needs_desktop_commander", "גימור ארוך רץ ב-Desktop Commander על המק, לא ב-bash של הסנדבוקס"),
 ("fully_local_no_descript_proven", "Descript מחוץ לזרימה — [DESCRIPT FALLBACK] רק אחרי שני כשלים מקומיים ובאישור"),
 ("harel_posts_light_blue_heart", "קפשן אישי של הראל = לב תכלת"),
 ("personal_brand_light_blue_heart", "הראל = 🩵; המועדון = 🖤❤️ — לא מחליפים"),
 ("metricool_api_strips_composer_fields", "location/carouselTags — דרך API v2, ה-MCP מוחק בשקט"),
 ("metricool_cover_manual_only", "קאבר וידאו ב-Metricool — ידני בקומפוזר בלבד; הסוכן מייצר PNG"),
 ("metricool_post_checklist", "Definition-of-Done לפוסט Metricool + אימות ויזואלי בקומפוזר"),
 ("missing_cover_search_project_folder_first", "קאבר 'חסר' — לחפש קודם בתיקיית הפרויקט"),
 ("monday_date_column_is_utc", "עמודת תאריך+שעה ב-Monday = UTC — מקומי פחות 3, וקריאה חוזרת"),
 ("monday_upload_via_mac_desktop_commander", "העלאת קבצים גדולים ל-Monday — מהמק דרך Desktop Commander"),
 ("monthly_corners_fixed_ranges_and_oct7", "פינות חודשיות בטווחי ימים קבועים; אין תוכן ב-7.10"),
 ("never_bypass_finish_pipeline", "לעולם לא לבנות שלבי גימור ידנית — רק local_finish_pipeline"),
 ("never_compress_video_files", "לעולם לא לדחוס/לקודד מחדש FINAL"),
 ("never_gym_always_crossfit_club", "לעולם לא 'חדר כושר' — מועדון קרוספיט"),
 ("never_invent_metricool_schedule_date", "תאריך תזמון רק מעמודת התאריך בבורד"),
 ("never_touch_colors", "לא נוגעים בצבע (חריג: HLG → tonemap)"),
 ("no_hashtags_in_captions", "אפס האשטגים בכל קפשן ובתגובה הראשונה"),
 ("podcast_always_4k", "פרקי 'מדברים כושר' נשארים 4K"),
 ("podcast_captions_club_brand_not_personal", "כתוביות פודקאסט = מותג מועדון גם בפרופיל האישי"),
 ("published_vs_scheduled_state_bug", "'פורסם בפועל' רק אחרי פרסום אמיתי — לא אחרי תזמון"),
 ("raw_footage_local_first_intake", "קליטת גלם מקומית — לא מעלים למאנדיי"),
 ("reproduce_exact_run_command", "גימור חוזר — הפקודה המדויקת מרשומת הריצה"),
 ("review_app_round_tracking", "אחרי תיקון מהערות הראל — POST /api/round/<name>/correct"),
 ("review_app_stale_process_after_code_update", "אחרי עדכון קוד בשרת — launchctl kickstart, לא nohup"),
 ("save_skill_overwrites_reference_files", "שמירת סקיל דורסת references/ מקומיים — לסנכרן ולאמת diff"),
 ("scheduling_always_update_monday_and_app", "כל תזמון מסתיים בעדכון Monday + אפליקציית הרוויו"),
 ("scheduling_horizon_one_month", "אופק תזמון ~חודש; לא היום/מחר בלי אישור, לא חודשיים+ בלי וידוא"),
 ("screen_recording_carries_narration", "הקלטת מסך אינה בירול אילם — לתמלל לפני מבנה העריכה"),
 ("thumbnail_inpaint_captions", "קאבר מסרטון עם כתוביות בלי EXPORT — inpaint על פריים חד, לא טשטוש"),
 ("thumbnail_match_video_aspect", "הקאבר ביחס של הסרטון (1:1 ↔ 9:16)"),
 ("two_layer_fix_means_wrong_layer", "תיקון באותה בעיה בשתי שכבות = השכבה הנכונה לא זוהתה"),
 ("work_folder_names_hebrew_content_based", "תיקיות _work לפי תוכן בעברית, לא תעתיק"),
]
for slug, rule in OPS:
    m(slug, "ops", [], rule)
