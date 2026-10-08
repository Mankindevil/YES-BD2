"""Colour checks under simulated display distortions (Leo 2026-09-30: HDR
and similar settings must not break the judgement)."""

import unittest
from pathlib import Path

import cv2
import numpy as np

from src.utils.colour_check import COLOUR_DISTANCE_MAX, check_capture_colours
from src.utils.colour_rules import switch_yellow_ratio

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ANCHORS = Path(__file__).resolve().parents[1] / "recognition-assets" / "template-assets" / "colour_check"


def _lut(fn):
    return np.clip(np.round(fn(np.arange(256, dtype=np.float64))), 0, 255).astype(np.uint8)


def _srgb_to_linear(v):
    v = v / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(l):
    l = np.clip(l, 0.0, 1.0)
    return 255.0 * np.where(l <= 0.0031308, l * 12.92, 1.055 * np.power(l, 1 / 2.4) - 0.055)


def hdr_washout(frame, k=2.5):
    """8-bit capture of an SDR window with Windows HDR on (clipped)."""
    return cv2.LUT(frame, _lut(lambda v: _linear_to_srgb(_srgb_to_linear(v) * k)))


def darker(frame, gamma=1.25):
    return cv2.LUT(frame, _lut(lambda v: 255.0 * (v / 255.0) ** gamma))


def saturated(frame, factor=1.3):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def _home_frame():
    """A synthetic 2560x1440 home top bar: the three icons on dark pills."""
    frame = np.full((1440, 2560, 3), (200, 170, 60), np.uint8)
    scale = 2560 / 1920
    for name, (x, y, w, h) in (
        ("gem", (1031, 44, 31, 24)),
        ("coin", (1163, 42, 30, 30)),
        ("silver", (1339, 40, 33, 34)),
    ):
        patch = cv2.imread(str(ANCHORS / f"{name}.png"))
        big = cv2.resize(patch, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_CUBIC)
        top, left = round(y * scale), round(x * scale)
        frame[top : top + big.shape[0], left : left + big.shape[1]] = big
    return frame


class YellowSwitchTest(unittest.TestCase):
    def test_on_and_off_survive_brighter_darker_and_saturated(self):
        on = cv2.imread(str(FIXTURES / "bag_detail_on.png"))
        off = cv2.imread(str(FIXTURES / "bag_detail_off.png"))
        for name, fn in (
            ("none", lambda f: f),
            ("hdr", hdr_washout),
            ("darker", darker),
            ("dim", lambda f: cv2.LUT(f, _lut(lambda v: _linear_to_srgb(_srgb_to_linear(v) / 1.5)))),
            ("saturated", saturated),
        ):
            self.assertGreater(switch_yellow_ratio(fn(on)), 0.15, name)
            self.assertEqual(0.0, switch_yellow_ratio(fn(off)), name)


class CaptureColourCheckTest(unittest.TestCase):
    def test_normal_colours_pass(self):
        check = check_capture_colours(_home_frame())
        self.assertIsNotNone(check.distance)
        self.assertLessEqual(check.distance, COLOUR_DISTANCE_MAX)
        self.assertFalse(check.distorted)

    def test_hdr_darker_or_saturated_colours_are_flagged(self):
        for name, fn in (("hdr", hdr_washout), ("dim", lambda f: darker(f, 1.6)), ("saturated", saturated)):
            check = check_capture_colours(fn(_home_frame()))
            self.assertTrue(check.distorted, f"{name}: {check.detail}")

    def test_no_home_top_bar_is_unknown_not_distorted(self):
        check = check_capture_colours(np.zeros((1440, 2560, 3), np.uint8))
        self.assertIsNone(check.distance)
        self.assertFalse(check.distorted)


if __name__ == "__main__":
    unittest.main()
