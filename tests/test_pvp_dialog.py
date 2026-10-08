import unittest

from src.utils.pvp_dialog import (
    adjust_step,
    parse_battle_count,
    parse_free_cocktails,
    parse_multiplier,
    parse_start_cost,
)


class PvpDialogParsingTest(unittest.TestCase):
    # OCR strings read from the live dialog, 2026-09-26.
    def test_multiplier(self):
        self.assertEqual(1, parse_multiplier("1倍"))
        self.assertEqual(10, parse_multiplier("🍹 10倍"))
        self.assertIsNone(parse_multiplier("设置鲜血鸡尾酒消耗量"))

    def test_battle_count(self):
        self.assertEqual(1, parse_battle_count("自动战斗1次"))
        self.assertEqual(2, parse_battle_count("自动战斗 2次"))
        self.assertIsNone(parse_battle_count("自动战斗"))

    def test_start_cost_ignores_the_icon(self):
        self.assertEqual(1, parse_start_cost("战斗开始🍹1"))
        self.assertEqual(20, parse_start_cost("取消 战斗开始●20"))
        self.assertIsNone(parse_start_cost("取消"))

    def test_free_cocktails_is_the_pool_before_the_paid_amount(self):
        self.assertEqual(36, parse_free_cocktails("20:20 36/40 +1.42K"))
        self.assertEqual(36, parse_free_cocktails("36/40+1.42K"))
        self.assertIsNone(parse_free_cocktails("+1.42K"))


class AdjustStepTest(unittest.TestCase):
    def test_reaches_any_multiplier_from_min(self):
        for target in range(1, 41):
            current, presses = 1, 0
            while (step := adjust_step(current, target, 5)) is not None:
                current += {"big_plus": 5, "big_minus": -5, "plus": 1, "minus": -1}[step]
                presses += 1
                self.assertLess(presses, 20)
            self.assertEqual(target, current)

    def test_overshoot_steps_back(self):
        self.assertEqual("big_minus", adjust_step(20, 10, 5))
        self.assertEqual("minus", adjust_step(11, 10, 10))
        self.assertIsNone(adjust_step(2, 2, 10))


if __name__ == "__main__":
    unittest.main()
