# -*- coding: utf-8 -*-
"""P17 — סרטוני "הראל חיון" על בניית אפליקציות/פרומפטים עם AI (v9.23).

כל בדיקה כאן מזריקה כשל אחד שהראל ביקש למנוע ב-12.9.26, ומוודאת שהמבקר
מרים אותו. השורש: השרשרת "תגובה במילת מפתח ⇒ DM אוטומטי ⇒ לינק" מתה
**בשקט** כשה-CTA בסרטון אומר מילה אחרת מזו שה-Flow מאזין לה.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import preflight_critic as PF


def mkw(tmp, *, dept="הראל חיון", words=None, brief=None):
    w = Path(tmp)
    (w / "project_manifest.json").write_text(
        json.dumps({"dept": dept, "name": "t"}, ensure_ascii=False), encoding="utf-8")
    (w / "words_final.json").write_text(
        json.dumps(words or [], ensure_ascii=False), encoding="utf-8")
    if brief is not None:
        (w / "ai_app_brief.json").write_text(
            json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    return w


def say(pairs):
    """[(מילה, start)] → רשימת מילים עם end=start+0.3."""
    return [{"word": t, "start": s, "end": s + 0.3} for t, s in pairs]


BODY = say([("רשימת", 6.0), ("הקניות", 6.4), ("בבית", 6.8),
            ("בניתי", 8.0), ("אפליקציה", 8.4), ("עם", 9.0), ("קלוד", 9.4),
            ("פרומפט", 12.0)])
CTA = say([("תכתבו", 50.0), ("קניות", 50.5), ("בתגובות", 51.0)])

FULL_BRIEF = {
    "keyword": "קניות",
    "cta_text": "תכתבו קניות בתגובות",
    "home_screen": {"asset": "hs.mp4", "at": 46.0, "dur": 7.0},
    "chat_broll": {"status": "present", "clip": "c.mp4"},
    "delivery": {"dm_flow": "metricool:flow-1", "smartlink": "https://x/y"},
    "app_link": "https://claude.ai/app",
}


def checks(f):
    return [x for x in f if x["check"] == "P17_ai_app"]


class TestAiAppPreflight(unittest.TestCase):

    def test_clean_brief_produces_no_findings(self):
        with tempfile.TemporaryDirectory() as t:
            w = mkw(t, words=BODY + CTA, brief=FULL_BRIEF)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertEqual(checks(f), [], checks(f))

    def test_club_video_is_not_touched(self):
        with tempfile.TemporaryDirectory() as t:
            w = mkw(t, dept="קרוספיט אריאל", words=BODY + CTA)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertEqual(checks(f), [])

    def test_detected_topic_without_brief_is_high(self):
        with tempfile.TemporaryDirectory() as t:
            w = mkw(t, words=BODY + CTA)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any(x["severity"] == PF.HIGH for x in checks(f)))

    def test_keyword_never_spoken_is_high(self):
        with tempfile.TemporaryDirectory() as t:
            b = dict(FULL_BRIEF, keyword="מעקב", cta_text="תכתבו מעקב בתגובות")
            w = mkw(t, words=BODY + CTA, brief=b)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any(x["severity"] == PF.HIGH and "לא נאמרת" in x["detail"]
                                for x in checks(f)), checks(f))

    def test_cta_text_not_containing_keyword_is_high(self):
        with tempfile.TemporaryDirectory() as t:
            b = dict(FULL_BRIEF, cta_text="תכתבו לינק בתגובות")
            w = mkw(t, words=BODY + CTA, brief=b)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any(x["severity"] == PF.HIGH and "אינו מכיל" in x["detail"]
                                for x in checks(f)), checks(f))

    def test_keyword_only_early_is_flagged_outside_cta_zone(self):
        with tempfile.TemporaryDirectory() as t:
            w = mkw(t, words=say([("קניות", 3.0)]) + BODY, brief=FULL_BRIEF)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any("מחוץ לאזור ה-CTA" in x["detail"] for x in checks(f)),
                            checks(f))

    def test_opening_with_tool_name_is_flagged(self):
        with tempfile.TemporaryDirectory() as t:
            w = mkw(t, words=say([("קלוד", 0.5), ("בנה", 1.2)]) + BODY + CTA,
                    brief=FULL_BRIEF)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any("פותחת בשם הכלי" in x["detail"] for x in checks(f)),
                            checks(f))

    def test_missing_home_screen_segment(self):
        with tempfile.TemporaryDirectory() as t:
            b = dict(FULL_BRIEF); b.pop("home_screen")
            w = mkw(t, words=BODY + CTA, brief=b)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any("מסך הבית" in x["detail"] for x in checks(f)))

    def test_missing_smartlink_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            b = dict(FULL_BRIEF, delivery={"dm_flow": "metricool:flow-1"})
            w = mkw(t, words=BODY + CTA, brief=b)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any("דף הקישורים בביו" in x["detail"] for x in checks(f)),
                            checks(f))

    def test_undecided_chat_broll_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            b = dict(FULL_BRIEF, chat_broll={})
            w = mkw(t, words=BODY + CTA, brief=b)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any("בירול הצ'אט" in x["detail"] for x in checks(f)))

    def test_missing_app_link_is_high(self):
        with tempfile.TemporaryDirectory() as t:
            b = dict(FULL_BRIEF); b.pop("app_link")
            w = mkw(t, words=BODY + CTA, brief=b)
            f = []
            PF.check_ai_app_video(f, w, 55.0)
            self.assertTrue(any(x["severity"] == PF.HIGH and "app_link" in x["detail"]
                                for x in checks(f)))


if __name__ == "__main__":
    unittest.main()
