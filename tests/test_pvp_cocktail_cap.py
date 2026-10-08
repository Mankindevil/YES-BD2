"""镜中之战: 倍数 x 场数 never above the 40 free cocktails (Leo 2026-10-05)."""

import unittest

from src.tasks.PVPTask import FREE_COCKTAILS_PER_DAY, capped_battle_count


class CocktailCapTest(unittest.TestCase):
    def test_count_is_lowered_to_fit_forty_cocktails(self):
        self.assertEqual(40, FREE_COCKTAILS_PER_DAY)
        self.assertEqual(1, capped_battle_count(40, 1))
        self.assertEqual(1, capped_battle_count(40, 3))
        self.assertEqual(4, capped_battle_count(10, 5))
        self.assertEqual(13, capped_battle_count(3, 20))
        self.assertEqual(2, capped_battle_count(20, 2))

    def test_max_stays_max(self):
        # MAX already uses only what the free cocktails allow.
        self.assertEqual(0, capped_battle_count(40, 0))


if __name__ == "__main__":
    unittest.main()
