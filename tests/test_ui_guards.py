import unittest

import numpy as np

from src.ui.live_screenshot import LiveScreenshotWidget
from src.ui.shell.safe import guarded


class GuardedTest(unittest.TestCase):
    def test_exception_is_swallowed_and_logged_once(self):
        calls = []

        def boom():
            calls.append(1)
            raise ValueError("bad")

        run = guarded("test", boom)
        self.assertIsNone(run())
        self.assertIsNone(run())
        self.assertEqual(len(calls), 2)

    def test_runtime_error_calls_on_gone(self):
        stopped = []

        def gone():
            raise RuntimeError("Internal C++ object already deleted")

        guarded("test", gone, lambda: stopped.append(True))()
        self.assertEqual(stopped, [True])

    def test_result_passes_through(self):
        self.assertEqual(guarded("test", lambda x: x + 1)(1), 2)


class PreviewFitTest(unittest.TestCase):
    def test_shrinks_to_fit_keeping_shape(self):
        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
        out = LiveScreenshotWidget._fit(frame, (480, 400))
        self.assertEqual(out.shape[:2], (270, 480))

    def test_never_enlarges(self):
        frame = np.zeros((90, 160, 3), dtype=np.uint8)
        self.assertIs(LiveScreenshotWidget._fit(frame, (480, 270)), frame)
        self.assertIs(LiveScreenshotWidget._fit(frame, None), frame)


if __name__ == "__main__":
    unittest.main()
