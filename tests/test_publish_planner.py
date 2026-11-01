import datetime as dt, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
import publish_planner as P


class PublishPlanner(unittest.TestCase):
    """L163: תאריך פרסום נקבע אוטומטית בשלב ההפקה."""
    def test_corner_range(self):
        d, t, _ = P.plan("טיפ אחד: וול-בול", {dt.date(2026, 11, 9)}, dt.date(2026, 11, 1))
        self.assertTrue(9 <= d.day <= 13 and d.month == 11); self.assertEqual(t, "19:00")
        self.assertNotEqual(d, dt.date(2026, 11, 9))

    def test_never_oct7_or_short_notice(self):
        d, _, _ = P.plan("משהו", set(), dt.date(2026, 10, 5))
        self.assertNotEqual((d.month, d.day), (10, 7)); self.assertGreaterEqual((d - dt.date(2026, 10, 5)).days, 2)

    def test_spreads_away_from_taken(self):
        taken = {dt.date(2026, 11, 3) + dt.timedelta(days=i) for i in range(0, 30) if i % 2 == 0}
        d, _, _ = P.plan("ערך כללי", taken, dt.date(2026, 11, 1))
        self.assertNotIn(d, taken)

    def test_avoids_friday_when_possible(self):
        # 1.11.26 בפועל: 9,10(?),11 תפוסים בערב; 13.11 שישי ⇒ 12.11
        taken = {dt.date(2026, 11, 9), dt.date(2026, 11, 11)}
        d, _, _ = P.plan("טיפ אחד: וול-בול", taken, dt.date(2026, 11, 1))
        self.assertNotEqual(d.weekday(), 4); self.assertTrue(9 <= d.day <= 13)

    def test_muscle_man_late(self):
        self.assertEqual(P.plan("מאסל מן: סנאץ'", set(), dt.date(2026, 11, 20))[1], "22:00")

    def test_utc_conversion_winter(self):
        self.assertEqual(P.to_monday_utc(dt.date(2026, 11, 11), "19:00"), ("2026-11-11", "17:00:00"))


if __name__ == "__main__":
    unittest.main()
