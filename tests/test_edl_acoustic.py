"""L53 — גבול חיתוך נגזר מאנרגיה, לא מתזמוני whisper."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import edl_acoustic as ea  # noqa: E402


class TestSpeechSpans(unittest.TestCase):
    def test_spans_are_complement_of_silences(self):
        sil = [(0.0, 3.5), (11.0, 13.0), (75.9, None)]
        spans = ea.speech_spans(sil, 77.0)
        self.assertEqual(spans, [[3.5, 11.0], [13.0, 75.9]])

    def test_leading_silence_is_dropped(self):
        spans = ea.speech_spans([(0.0, 3.5)], 10.0)
        self.assertEqual(spans[0][0], 3.5)


class TestPadding(unittest.TestCase):
    def _segs(self, merged, total=100.0):
        segs = []
        for s, e in merged:
            st, en = max(0.0, s - ea.HEAD_PAD), min(total, e + ea.TAIL_PAD)
            if segs and st < segs[-1]["end"] + ea.MIN_SEP:
                st = segs[-1]["end"] + ea.MIN_SEP
            segs.append({"start": round(st, 2), "end": round(en, 2)})
        return segs

    def test_head_pad_never_eats_into_speech(self):
        """הבאג של 'לסיכום': תחילת קטע אחרי האונסט בולעת את המילה."""
        merged = [[70.56, 75.93]]
        seg = self._segs(merged)[0]
        self.assertLess(seg["start"], 70.56,
                        "תחילת הקטע חייבת להקדים את האונסט האקוסטי")
        self.assertAlmostEqual(70.56 - seg["start"], ea.HEAD_PAD, places=2)

    def test_tail_pad_is_short(self):
        """הבאג של 'המבט למסך': זנב ארוך משאיר דובר יושב בשקט."""
        merged = [[42.42, 43.51]]
        seg = self._segs(merged)[0]
        self.assertLessEqual(seg["end"] - 43.51, 0.25,
                             "זנב ארוך מ-0.25ש = שקט נראה לעין אחרי סוף הדיבור")

    def test_adjacent_segments_keep_min_separation(self):
        segs = self._segs([[10.0, 11.0], [11.05, 12.0]])
        self.assertGreaterEqual(segs[1]["start"] - segs[0]["end"], ea.MIN_SEP - 1e-6)


class TestConstants(unittest.TestCase):
    def test_pads_are_measured_not_guessed(self):
        self.assertGreater(ea.HEAD_PAD, 0.0)
        self.assertLessEqual(ea.TAIL_PAD, ea.HEAD_PAD,
                             "זנב אף פעם לא ארוך מהובלה — עודף שקט בסוף נראה לעין")


if __name__ == "__main__":
    unittest.main()
