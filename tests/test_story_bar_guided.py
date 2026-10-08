import unittest
from types import SimpleNamespace

import numpy as np

from src.tasks.map_trade.navigator import Navigator


def _navigator(offsets, wheels, looks, found_on=None):
    """Navigator whose badge-row reads give ``offsets`` in turn; the full look
    succeeds on look number ``found_on`` (1-based) or never."""

    navigator = object.__new__(Navigator)
    navigator.task = SimpleNamespace(info_set=lambda *_args: None)
    navigator.vision = SimpleNamespace(capture=lambda: np.zeros((1080, 1920, 3), np.uint8))
    reads = iter(offsets)
    navigator._story_bar_offset = lambda _frame: next(reads)
    navigator._wheel_story_bar = lambda toward_larger, notches: wheels.append((toward_larger, notches))

    def look():
        looks.append(1)
        return "found" if found_on == len(looks) else None

    return navigator, look


def _reads(*pairs):
    navigator = object.__new__(Navigator)
    navigator._visible_story_reads = lambda _frame: list(pairs)
    return navigator


class BarOffsetTest(unittest.TestCase):
    def test_start_of_the_bar(self):
        # Live 2K: cards 1-10 at x = 92 + 180 * (n - 1); card 1 was not read.
        navigator = _reads(*((n, 92 + 180 * (n - 1)) for n in (2, 4, 5, 6, 7, 8, 9, 10)))
        offset = navigator._story_bar_offset(None)
        # Seven lone digits also fit cards 12-19, but "10" settles it.
        self.assertAlmostEqual(92, navigator._story_card_x(offset, 1), delta=5)

    def test_a_stray_read_is_dropped(self):
        # "1" among cards 8-17 (live): it cannot sit where card 1 would be.
        pairs = [(n, 92 + 180 * (n - 8)) for n in (8, 9, 12, 13, 16, 17)] + [(1, 700)]
        offset = _reads(*pairs)._story_bar_offset(None)
        self.assertAlmostEqual(92, _reads()._story_card_x(offset, 8), delta=5)

    def test_lost_leading_one(self):
        # End of the bar (live 2K): 13, 16, 19 read as 3, 6, 9 beside 12 and 15.
        x = {12: 319, 13: 499, 15: 859, 16: 1038, 19: 1579}
        offset = _reads((3, x[13]), (6, x[16]), (9, x[19]), (12, x[12]), (15, x[15]))._story_bar_offset(None)
        self.assertAlmostEqual(859, _reads()._story_card_x(offset, 15), delta=5)

    def test_too_few_reads(self):
        self.assertIsNone(_reads((4, 632), (9, 1532))._story_bar_offset(None))


class GuidedWheelTest(unittest.TestCase):
    # offset 0.49: cards 1-10 on screen (card n at x = (n - 0.49) * 180).

    def test_wheels_straight_to_the_card_then_looks_once(self):
        wheels, looks = [], []
        navigator, look = _navigator([0.49, 6.0], wheels, looks, found_on=1)

        self.assertEqual("found", navigator._scan_story_bar_guided(15, look))
        # Card 15 at x=2612: (2612 - 960) / 180 = 9.2 cards -> 16 notches, capped.
        self.assertEqual([(True, 14)], wheels)
        self.assertEqual([1], looks)

    def test_toward_smaller_numbers(self):
        wheels, looks = [], []
        navigator, look = _navigator([10.2, 1.0], wheels, looks, found_on=1)

        navigator._scan_story_bar_guided(3, look)
        self.assertEqual([(False, 14)], wheels)

    def test_unreadable_row_falls_back_without_wheeling(self):
        wheels, looks = [], []
        navigator, look = _navigator([None], wheels, looks)

        self.assertIsNone(navigator._scan_story_bar_guided(15, look))
        self.assertEqual(([], []), (wheels, looks))

    def test_a_bar_that_does_not_move_falls_back(self):
        wheels, looks = [], []
        navigator, look = _navigator([0.49, 0.49], wheels, looks)

        self.assertIsNone(navigator._scan_story_bar_guided(15, look))
        self.assertEqual(1, len(wheels))
        self.assertEqual([], looks)

    def test_failed_look_nudges_and_looks_again(self):
        wheels, looks = [], []
        # Card 15 in view at the end of the bar (offset 10.2, x=864).
        navigator, look = _navigator([10.2, 9.6], wheels, looks, found_on=2)

        self.assertEqual("found", navigator._scan_story_bar_guided(15, look))
        self.assertEqual([(False, 2)], wheels)  # x < 960: nudge toward smaller
        self.assertEqual(2, len(looks))

    def test_callers_failed_look_is_not_repeated(self):
        wheels, looks = [], []
        navigator, look = _navigator([10.2, 10.2, 10.2], wheels, looks)

        self.assertIsNone(navigator._scan_story_bar_guided(15, look, looked=True))
        # Nudged toward the middle, the bar did not move, nudged back; no look
        # at an unchanged view.
        self.assertEqual([(False, 2), (True, 2)], wheels)
        self.assertEqual([], looks)


if __name__ == "__main__":
    unittest.main()
