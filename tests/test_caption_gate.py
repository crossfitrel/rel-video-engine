"""v9.48 — שער הקפשן: קאנון + "משלים, לא משכפל" (הראל 10.10.26)."""
import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import caption_gate as cg  # noqa: E402

TRANSCRIPT = ("אצלי אין תחום אפור, אין אני אנסה. זה או שאני בפנים או שאני בחוץ. "
              "אומרים לעצמנו שאני אנסה, אני אשתדל, בסוף אנחנו נותנים לעצמנו יציאת חירום. "
              "אנחנו הכי חזקים כשדוחפים אותנו לפינה ואין לנו שום אופציה אחרת.")

ECHO_CAPTION = ("אצלי אין אני אנסה. או שאני בפנים, או שאני בחוץ.\n\n"
                "אני אנסה, אני אשתדל, ככה אנחנו נותנים לעצמנו יציאת חירום.\n\n"
                "אנחנו הכי חזקים כשאין לנו שום אופציה אחרת.\n\n"
                "כתבו לי בתגובות 👇")

NOVEL_CAPTION = ("מתי בפעם האחרונה אמרתם \"אני אנסה\" על משהו שבאמת רציתם?\n\n"
                 "תחליפו את המשפט הבא כזה במשפט עם תאריך ושעה. ביום ראשון בשש בבוקר אני שם.\n\n"
                 "החלטה שיש לה יום בלוח השנה כבר מתחילה לקרות.\n\n"
                 "איזו החלטה אתם דוחים כבר חודשים? כתבו לי אותה במילה אחת 👇 🩵")


class TestNovelty(unittest.TestCase):
    def test_echo_caption_fails(self):
        r = cg.gate(ECHO_CAPTION, "ערך", "harel", TRANSCRIPT)
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(r["novelty"]["novel_sentences"], 0)

    def test_novel_caption_passes(self):
        r = cg.gate(NOVEL_CAPTION, "ערך", "harel", TRANSCRIPT)
        self.assertEqual(r["status"], "PASS", r["issues"])
        self.assertGreaterEqual(r["novelty"]["novel_sentences"], 1)

    def test_no_transcript_warns_not_blocks(self):
        r = cg.gate(ECHO_CAPTION, "ערך", "harel", "")
        self.assertEqual(r["status"], "PASS")
        self.assertTrue(any("אין תמליל" in w for w in r["warns"]))

    def test_cta_line_not_counted(self):
        r = cg.novelty("משפט חדש לגמרי על ספסל ומגנזיום.\nאני אנסה או שאני בפנים", TRANSCRIPT)
        self.assertEqual(r["body_sentences"], 1)


class TestCanon(unittest.TestCase):
    def test_em_dash_blocks(self):
        i, _ = cg.lint("משפט — עם קו ארוך", "ערך")
        self.assertTrue(any("קו מפריד" in x for x in i))

    def test_gym_word_blocks(self):
        i, _ = cg.lint("זה לא עוד חדר כושר", "ערך")
        self.assertTrue(any("חדר כושר" in x for x in i))

    def test_standalone_bio_blocks(self):
        i, _ = cg.lint("שורה ראשונה\n\nפרטים בביו 👆", "המרה")
        self.assertTrue(any("משפט עומד" in x for x in i))

    def test_bio_as_tail_ok(self):
        i, _ = cg.lint("רוצים להתחיל? קבעו פגישת יעדים ונבנה מסלול, בלי התחייבות, בלינק שבביו 👆", "המרה")
        self.assertFalse(any("משפט עומד" in x for x in i))

    def test_goals_meeting_is_30_min(self):
        i, _ = cg.lint("פגישת יעדים של 20 דקות", "המרה")
        self.assertTrue(any("30" in x for x in i))
        i2, _ = cg.lint("פגישת יעדים של כ-30 דקות, בלינק שבביו 👆", "המרה")
        self.assertFalse(any("30 דקות" in x for x in i2))

    def test_heart_colors_by_brand(self):
        i, _ = cg.lint("תודה 🩵", "קהילה", "club")
        self.assertTrue(any("תכלת" in x for x in i))
        i2, _ = cg.lint("תודה ❤️🖤", "קהילה", "harel")
        self.assertTrue(any("🩵" in x for x in i2))

    def test_negative_parallelism_warns(self):
        _, w = cg.lint("זה לא כושר, זה אורח חיים.", "ערך")
        self.assertTrue(any("זה לא X" in x for x in w))

    def test_emoji_bullets_warn(self):
        _, w = cg.lint("פתיחה\n\n💪 פסקה\n\n📓 פסקה", "ערך")
        self.assertTrue(any("תבליט" in x for x in w))


class TestRegistryHook(unittest.TestCase):
    def test_set_draft_rejects_echo_caption(self):
        from relvid import registry as reg
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "_whisper_text.txt").write_text(TRANSCRIPT, encoding="utf-8")
            (p / "project_manifest.json").write_text(json.dumps(
                {"name": "t", "content_type": "value", "brand": "personal"}), encoding="utf-8")
            with self.assertRaises(ValueError) as cm:
                reg.set_schedule_approval(p, "set_draft", caption_draft=ECHO_CAPTION)
            self.assertIn("CAPTION-GATE FAIL", str(cm.exception))
            m = reg.set_schedule_approval(p, "set_draft", caption_draft=NOVEL_CAPTION,
                                          caption_meta={"move": "יישום", "sb7": "תוכנית"})
            sa = m["schedule_approval"]
            self.assertEqual(sa["caption_gate"]["status"], "PASS")
            self.assertEqual(sa["caption_meta"]["move"], "יישום")


if __name__ == "__main__":
    unittest.main()
