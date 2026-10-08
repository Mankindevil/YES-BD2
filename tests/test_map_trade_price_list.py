"""The 价目表 (owned only) tells which planned items are worth a shop visit."""

import unittest
from types import SimpleNamespace

from src.tasks.map_trade.models import CalendarEntry
from src.tasks.map_trade.trader_price_list import owned_rates


def box(name, cx, cy, width=60, height=24):
    return SimpleNamespace(
        name=name, x=cx - width / 2, y=cy - height / 2, width=width, height=height
    )


def row(name, y, rate):
    # Positions from the user's demo (1080 reference, 2026-09-27).
    return [
        box(name, 830, y + 8),
        box("1,875", 800, y + 36),
        box("当前", 1110, y),
        box("2,250", 1220, y),
        box(f"↑{rate}%", 1320, y),
        box("剧情游戏卡16", 1440, y),
        box("每月27日", 1120, y + 42),
        box("↑120%", 1320, y + 42),
    ]


class OwnedRatesTest(unittest.TestCase):
    def test_only_todays_rate_counts_not_the_monthly_best(self):
        boxes = row("卢戈山参烤串", 394, 118) + row("火圣石", 504, 118)
        # Each row's 每月N日 line reads 120%; only 当前 matters.
        self.assertEqual([("卢戈山参烤串", False), ("火圣石", False)], owned_rates(boxes))

    def test_items_at_120_today(self):
        boxes = row("苹果", 394, 120) + row("穿山甲鳞片", 504, 120) + row("火圣石", 614, 118)
        self.assertEqual(
            [("苹果", True), ("穿山甲鳞片", True), ("火圣石", False)], owned_rates(boxes)
        )


class KeepOwnedTest(unittest.TestCase):
    def _trader(self, owned):
        from src.tasks.map_trade.trader import Trader

        trader = object.__new__(Trader)
        logs = []
        trader.task = SimpleNamespace(log_info=logs.append, log_warning=logs.append)
        trader.vision = SimpleNamespace(simplify=lambda value: value)
        trader.owned_items_at_max_rate = lambda: owned
        return trader, logs

    def test_planned_items_missing_from_the_bag_are_dropped(self):
        trader, logs = self._trader({"苹果"})
        entries = [CalendarEntry("苹果", "S6"), CalendarEntry("穿山甲鳞片", "S16")]
        self.assertEqual(["苹果"], [e.item for e in trader._keep_owned_at_max_rate(entries)])
        self.assertTrue(any("穿山甲鳞片" in message for message in logs))

    def test_nothing_at_120_means_nothing_to_sell(self):
        trader, _ = self._trader(set())
        self.assertEqual([], trader._keep_owned_at_max_rate([CalendarEntry("苹果", "S6")]))

    def test_an_unreadable_list_keeps_the_old_shop_search(self):
        trader, _ = self._trader(None)
        entries = [CalendarEntry("苹果", "S6")]
        self.assertEqual(entries, trader._keep_owned_at_max_rate(entries))

    def test_traditional_glyphs_still_match(self):
        trader, _ = self._trader({"蘋果"})
        kept = trader._keep_owned_at_max_rate([CalendarEntry("苹果", "S6")])
        self.assertEqual(["苹果"], [e.item for e in kept])


if __name__ == "__main__":
    unittest.main()
