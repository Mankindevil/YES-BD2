"""Daily and weekly runs warn once on a game size the tool was not tested on.

A player on 2026-10-09 ran the game in a smaller window: 跑图 slid the
cartridge bar and clicked the map's back button for minutes on end.  Leo
chose 「提醒但照跑」: tell the player, then run anyway.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from src.tasks.BaseBD2Task import BaseBD2Task
from src.utils import game_size


def executor(width, height, connected=True):
    method = SimpleNamespace(width=width, height=height, connected=lambda: connected)
    window = SimpleNamespace(exists=True, width=width, height=height)
    manager = SimpleNamespace(capture_method=method, hwnd_window=window)
    return SimpleNamespace(device_manager=manager)


class GameSizeTest(unittest.TestCase):
    def setUp(self):
        game_size._last_notified["at"] = 0.0

    def test_supported_sizes(self):
        for size in ((1920, 1080), (2560, 1440), (3840, 2160), (1919, 1080), (3840, 2158)):
            with self.subTest(size=size):
                self.assertTrue(game_size.supported(*size))

    def test_other_16_9_sizes_are_not(self):
        for size in ((1280, 720), (1464, 819), (1600, 900), (1366, 768), (1920, 1050)):
            with self.subTest(size=size):
                self.assertFalse(game_size.supported(*size))

    def test_no_game_window_is_not_a_stop(self):
        self.assertIsNone(game_size.unsupported_size(None))
        manager = SimpleNamespace(
            capture_method=None, hwnd_window=SimpleNamespace(exists=False, width=0, height=0)
        )
        self.assertIsNone(game_size.unsupported_size(SimpleNamespace(device_manager=manager)))

    def test_capture_size_wins_over_window(self):
        found = executor(1920, 1080)
        found.device_manager.hwnd_window.width = 1464
        self.assertEqual((1920, 1080), game_size.current_size(found))
        found.device_manager.capture_method.connected = lambda: False
        self.assertEqual((1464, 1080), game_size.current_size(found))

    def test_notice_once_per_gap(self):
        self.assertTrue(game_size.should_notify(1000.0))
        self.assertFalse(game_size.should_notify(1100.0))
        self.assertTrue(game_size.should_notify(1000.0 + game_size.NOTIFY_GAP_SECONDS + 1))

    def test_message_names_the_size_and_the_fix(self):
        text = game_size.message((1464, 819))
        self.assertIn("1464×819", text)
        self.assertIn("游戏视窗大小", text)


class GuardedRunTest(unittest.TestCase):
    def setUp(self):
        game_size._last_notified["at"] = 0.0

    def _task(self, size, opt_in=True):
        class Task(BaseBD2Task):
            recover_home_on_failure = opt_in
            start_from_home = opt_in

            @property
            def executor(self):
                return self._executor

            def __init__(self):
                self._action_interval_lock = None
                self._executor = executor(*size)
                self.ran = 0
                self.home_calls = 0
                self.before_calls = 0
                self.info = {}
                self.warnings = []

            def run(self):
                self.ran += 1
                return True

            def info_set(self, key, value):
                self.info[key] = value

            def log_warning(self, message, notify=False):
                self.warnings.append((message, notify))

            def _leave_home_after_failed_run(self):
                self.home_calls += 1

            def _go_home_before_run(self):
                self.before_calls += 1

        return Task()

    def test_unsupported_size_warns_and_still_runs(self):
        task = self._task((1464, 819))
        self.assertTrue(task.run())
        self.assertEqual(1, task.ran)
        self.assertEqual(1, task.before_calls)
        self.assertEqual(0, task.home_calls)
        self.assertIn("1464×819", task.info[game_size.NOTICE_KEY])
        self.assertNotIn("状态", task.info)
        self.assertEqual([True], [notify for _text, notify in task.warnings])

    def test_second_run_soon_after_does_not_notify_again(self):
        self._task((1280, 720)).run()
        task = self._task((1280, 720))
        task.run()
        self.assertEqual([False], [notify for _text, notify in task.warnings])

    def test_supported_size_runs(self):
        task = self._task((2560, 1440))
        self.assertTrue(task.run())
        self.assertEqual(1, task.ran)
        self.assertEqual([], task.warnings)

    def test_trigger_tasks_are_untouched(self):
        # Auto-login and other trigger tasks must still run on any size.
        task = self._task((1280, 720), opt_in=False)
        self.assertTrue(task.run())
        self.assertEqual(1, task.ran)


class BatchTest(unittest.TestCase):
    def test_batch_warns_once_and_runs_its_children(self):
        try:
            from src.tasks.DailyBatchTask import DailyBatchTask
        except ImportError as exc:  # pragma: no cover - Windows-only imports
            self.skipTest(str(exc))

        class Batch(DailyBatchTask):
            executor = executor(1600, 900)

        batch = object.__new__(Batch)
        batch.config = {"启用": True}
        batch.info = {}
        batch.log_warning = mock.Mock()
        batch.info_set = lambda key, value: batch.info.__setitem__(key, value)
        batch._auto_login_pending = lambda: False
        batch._take_run_mode = lambda mode: mode
        batch._run_children = mock.Mock(return_value=True)
        batch._begin_report = mock.Mock()
        game_size._last_notified["at"] = 0.0
        with mock.patch("src.tasks.DailyBatchTask.run_report.finish"):
            self.assertTrue(batch.run())
        batch._run_children.assert_called_once()
        self.assertIn("1600×900", batch.info[game_size.NOTICE_KEY])
        self.assertTrue(batch.log_warning.call_args.kwargs["notify"])


if __name__ == "__main__":
    unittest.main()
