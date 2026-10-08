import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from src.tasks.map_trade.navigator_constants import FIELD_KEYCAP_TEMPLATES
from src.tasks.map_trade.vision import TEMPLATE_DIR, Vision

# Where the caps sit in a native 1080p field frame (live 2026-09-30).
CAP_POSITIONS = {"箱庭按键C": (1575, 82), "箱庭按键H": (1788, 82)}


def _field_frame(size=(1920, 1080), seed=0):
    rng = np.random.default_rng(seed)
    frame = rng.integers(170, 255, size=(1080, 1920, 3), dtype=np.uint8)  # snow-like
    for spec in FIELD_KEYCAP_TEMPLATES:
        cap = cv2.imread(str(TEMPLATE_DIR / spec.file_name))
        x, y = CAP_POSITIONS[spec.name]
        frame[y:y + cap.shape[0], x:x + cap.shape[1]] = cap
    if size != (1920, 1080):
        frame = cv2.resize(frame, size, interpolation=cv2.INTER_CUBIC)
    return frame


class FieldKeycapTest(unittest.TestCase):
    def setUp(self):
        task = SimpleNamespace(config={}, info_set=lambda *a: None, log_warning=print)
        self.vision = Vision(task)

    def _passes(self, frame):
        return all(
            self.vision.passes(self.vision.match(frame, spec), spec)
            for spec in FIELD_KEYCAP_TEMPLATES
        )

    def test_caps_on_bright_snow_pass_at_every_resolution(self):
        for size in ((1920, 1080), (2560, 1440), (3840, 2160)):
            self.assertTrue(self._passes(_field_frame(size)), size)

    def test_dimmed_or_missing_caps_fail(self):
        frame = _field_frame()
        self.assertFalse(self._passes((frame * 0.4).astype(np.uint8)))
        self.assertFalse(self._passes(np.full_like(frame, 220)))


if __name__ == "__main__":
    unittest.main()
