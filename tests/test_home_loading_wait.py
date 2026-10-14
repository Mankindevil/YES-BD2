import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from src.tasks.task_vision_mixin import TaskVisionMixin


class HomeLoadingWaitTest(unittest.TestCase):
    def test_real_loading_failure_frame_gets_loading_allowance(self):
        from src.tasks.recovery import _transition_frame

        path = Path(__file__).parent / "fixtures/home_loading_60.jpg"
        frame = cv2.imread(str(path))
        self.assertIsNotNone(frame)
        self.assertTrue(_transition_frame(frame[::4, ::4]))

    def task(self, *, home_at=float("inf"), dark=True):
        task = TaskVisionMixin()
        task.config = {"主页确认等待秒数": 10.0, "loading 消失等待秒数": 35.0}
        clock = [0.0]
        frame = np.full((108, 192, 3), 22 if dark else 180, np.uint8)
        task.capture_frame = lambda: frame
        task._home_confirmation_signals = lambda *_: (
            (True, 2, 255.0, "抽抽乐") if clock[0] >= home_at else (False, 0, 22.0, "")
        )
        task.sleep = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
        task.info_set = Mock()
        task.log_info = Mock()
        task._home_p95_threshold = lambda: 185.0
        task.clear_temporary_home_announcement_if_needed = Mock()
        return task, clock

    def test_loading_longer_than_home_timeout_can_finish(self):
        task, clock = self.task(home_at=18.0)
        with patch("src.tasks.task_vision_mixin.monotonic", side_effect=lambda: clock[0]):
            self.assertTrue(task._wait_for_home_confirmation("公会签到", interval=1.0))
        self.assertEqual(18.0, clock[0])
        task.clear_temporary_home_announcement_if_needed.assert_not_called()

    def test_stuck_loading_has_one_bounded_allowance(self):
        task, clock = self.task()
        with patch("src.tasks.task_vision_mixin.monotonic", side_effect=lambda: clock[0]):
            self.assertFalse(task._wait_for_home_confirmation("公会签到", interval=1.0))
        self.assertEqual(36.0, clock[0])
        task.clear_temporary_home_announcement_if_needed.assert_not_called()

    def test_explicit_short_timeout_and_nonloading_screen_are_not_extended(self):
        for dark, timeout, expected in ((True, 4.0, 5.0), (False, None, 11.0)):
            with self.subTest(dark=dark, timeout=timeout):
                task, clock = self.task(dark=dark)
                with patch("src.tasks.task_vision_mixin.monotonic", side_effect=lambda: clock[0]):
                    self.assertFalse(
                        task._wait_for_home_confirmation(
                            "主页",
                            interval=1.0,
                            timeout=timeout,
                        )
                    )
                self.assertEqual(expected, clock[0])


if __name__ == "__main__":
    unittest.main()
