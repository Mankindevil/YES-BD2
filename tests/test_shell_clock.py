"""Times on the pages follow the player's own clock (Leo 2026-10-05).

The game resets at 08:00 UTC+8.  At 01:16 in Taiwan that reset is still
ahead today, so the home page must say 今天 08:00, not 明天 08:00.
"""

import os
import time
import unittest
from unittest import mock

from src.ui.shell import data

# 2026-10-06 01:16 in Taiwan (2026-10-05 17:16 UTC, a Monday there).
TAIWAN_0116 = 1791220560.0


@unittest.skipUnless(hasattr(time, "tzset"), "switching time zones needs time.tzset (not on Windows)")
class PlayerClockTest(unittest.TestCase):
    def setUp(self):
        self._tz = os.environ.get("TZ")

    def tearDown(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()

    def _at(self, zone: str, ts: float):
        os.environ["TZ"] = zone
        time.tzset()
        return mock.patch("time.time", return_value=ts)

    def test_before_the_reset_it_is_today(self):
        with self._at("Asia/Taipei", TAIWAN_0116):
            self.assertEqual(data.next_refresh_text(), "今天 08:00")
            self.assertEqual(data.today_title(), "10月6日 周二")

    def test_after_the_reset_it_is_tomorrow(self):
        with self._at("Asia/Taipei", TAIWAN_0116 + 9 * 3600):
            self.assertEqual(data.next_refresh_text(), "明天 08:00")

    def test_other_time_zones_see_their_own_clock(self):
        with self._at("Asia/Tokyo", TAIWAN_0116):
            self.assertEqual(data.next_refresh_text(), "今天 09:00")
            self.assertEqual(data.sale_refresh_clock(), "00:00")
        with self._at("America/Los_Angeles", TAIWAN_0116):
            self.assertEqual(data.next_refresh_text(), "今天 17:00")
            self.assertEqual(data.weekly_reset_parts(), {"weekday": "日", "time": "17:00"})
        with self._at("Europe/London", TAIWAN_0116):
            self.assertEqual(data.next_refresh_text(), "明天 01:00")

    def test_taiwan_sale_table_switches_at_2300(self):
        with self._at("Asia/Taipei", TAIWAN_0116):
            self.assertEqual(data.sale_refresh_clock(), "23:00")
            self.assertEqual(data.daily_reset_clock(), "08:00")
            self.assertEqual(data.clock_text(TAIWAN_0116), "01:16")


if __name__ == "__main__":
    unittest.main()
