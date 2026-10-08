"""A failed daily task goes back home (live 2026-09-28: goddess stayed in
the square, junk gear in the bag)."""

import unittest
from unittest import mock

from src.tasks.BaseBD2Task import BaseBD2Task


class HomeGuardTest(unittest.TestCase):
    def _classes(self, opt_in):
        class Task(BaseBD2Task):
            recover_home_on_failure = opt_in

            def __init__(self, result):
                self._action_interval_lock = None  # as BaseBD2Task.__init__ sets
                self.result = result
                self.home_calls = 0

            def run(self):
                if isinstance(self.result, BaseException):
                    raise self.result
                return self.result

            def _leave_home_after_failed_run(self):
                self.home_calls += 1

            def _go_home_before_run(self):
                self.before_calls = getattr(self, "before_calls", 0) + 1

        return Task

    def test_failed_run_goes_home(self):
        task = self._classes(True)(False)
        self.assertFalse(task.run())
        self.assertEqual(1, task.home_calls)

    def test_successful_run_does_not(self):
        task = self._classes(True)(True)
        self.assertTrue(task.run())
        self.assertEqual(0, task.home_calls)

    def test_crashed_run_goes_home_and_still_raises(self):
        task = self._classes(True)(ValueError("boom"))
        with self.assertRaises(ValueError):
            task.run()
        self.assertEqual(1, task.home_calls)

    def test_stop_during_run_does_not_go_home(self):
        from ok.task.exceptions import TaskDisabledException

        task = self._classes(True)(TaskDisabledException())
        with self.assertRaises(TaskDisabledException):
            task.run()
        self.assertEqual(0, task.home_calls)

    def test_tasks_without_the_flag_are_untouched(self):
        # Trigger tasks return False for "nothing to do".
        task = self._classes(False)(False)
        self.assertFalse(task.run())
        self.assertEqual(0, task.home_calls)

    def test_home_starting_tasks_go_home_first(self):
        cls = self._classes(True)
        cls.start_from_home = True
        task = cls(True)
        task.run()
        self.assertEqual(1, task.before_calls)
        plain = self._classes(True)(True)
        plain.run()
        self.assertEqual(0, getattr(plain, "before_calls", 0))

    def test_stop_is_never_swallowed(self):
        from ok.task.exceptions import TaskDisabledException

        task = self._classes(True)(False)
        with mock.patch(
            "src.tasks.recovery.recover_to_home", side_effect=TaskDisabledException()
        ):
            with self.assertRaises(TaskDisabledException):
                BaseBD2Task._leave_home_after_failed_run(task)

    def test_daily_tasks_opt_in(self):
        from src.tasks.DailyTask import DailyTask
        from src.tasks.FreeGachaTask import FreeGachaTask
        from src.tasks.GearTasks import DailyRefineTask
        from src.tasks.JunkGearTask import JunkGearTask
        from src.tasks.MapTradeTask import MapTradeTask
        from src.tasks.PVPTask import PVPTask
        from src.tasks.QuickHuntTask import QuickHuntTask
        from src.tasks.SquareGoddessTask import SquareGoddessTask

        for cls in (DailyTask, FreeGachaTask, DailyRefineTask, JunkGearTask, MapTradeTask,
                    PVPTask, QuickHuntTask, SquareGoddessTask):
            with self.subTest(cls=cls.__name__):
                self.assertTrue(cls.recover_home_on_failure)
                self.assertTrue(getattr(cls.run, "_bd2_home_guard", False))


if __name__ == "__main__":
    unittest.main()
