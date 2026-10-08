import unittest
from types import SimpleNamespace

import numpy as np

from src.tasks.map_trade.navigator_story import badge_area_unchanged
from src.utils.image_utils import stabilize_template_match


def _result(center=(300, 400), size=(40, 40)):
    return SimpleNamespace(center=center, size=size)


class BadgeStillTest(unittest.TestCase):
    def test_same_picture_keeps_the_identification(self):
        frame = np.random.default_rng(1).integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
        self.assertTrue(badge_area_unchanged(frame, frame.copy(), _result()))

    def test_moved_bar_needs_a_new_look(self):
        frame = np.random.default_rng(1).integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
        moved = np.roll(frame, 30, axis=1)
        self.assertFalse(badge_area_unchanged(frame, moved, _result()))

    def test_change_far_away_does_not_matter(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        other = frame.copy()
        other[900:, 1500:] = 255
        self.assertTrue(badge_area_unchanged(frame, other, _result()))


class ShortStableWindowTest(unittest.TestCase):
    def test_three_agreeing_samples_are_enough(self):
        match = SimpleNamespace(position=(100, 100), size=(40, 40), score=0.99, pixel_score=0.95)
        calls = []

        def sample():
            calls.append(1)
            return match, (1080, 1920, 3)

        stable = stabilize_template_match(
            match,
            (1080, 1920, 3),
            sample_match=sample,
            passes=lambda _m: True,
            sleep=lambda _s: None,
            window_samples=3,
            minimum_hits=3,
        )
        self.assertIsNotNone(stable)
        self.assertEqual(2, len(calls))
