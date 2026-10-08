"""Stop must stop: batches and recovery re-raise the executor's stop signals."""

import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from ok.task.exceptions import TaskDisabledException

from src.tasks import recovery, run_report
from src.tasks.DailyBatchTask import (
    DailyBatchChild,
    DailyBatchTask,
    WeeklyBatchTask,
)
from src.tasks.map_trade.models import ScreenState
from src.tasks.trigger.AutoLoginTask import AutoLoginTask

_report_dir = None


def setUpModule():
    # Batches save a run report; keep it out of the real configs folder.
    global _report_dir
    _report_dir = tempfile.TemporaryDirectory()
    run_report.set_report_file(f"{_report_dir.name}/run_reports.json")


def tearDownModule():
    run_report.set_report_file(None)
    _report_dir.cleanup()


class _StoppingChild:
    name = "stopping"

    def __init__(self):
        self.config = {"启用": False}

    def info_clear(self):
        pass

    def run(self):
        raise TaskDisabledException()


def _batch(children, specs, config):
    task = object.__new__(DailyBatchTask)
    task.child_tasks = specs
    task.config = config
    task.info = {}
    task.info_set = lambda key, value: task.info.__setitem__(key, value)
    task.log_info = task.log_warning = task.log_error = lambda *a, **k: None
    task._executor = SimpleNamespace(
        get_task_by_class=lambda cls: children.get(cls),
        reset_scene=lambda check_enabled=False: None,
    )
    task._auto_login_pending = lambda: False
    return task


class StopPropagationTest(unittest.TestCase):
    def test_stop_inside_a_child_is_not_treated_as_a_failure(self):
        class Stopping:
            pass

        class Later:
            pass

        child = _StoppingChild()
        later = mock.Mock()
        task = _batch(
            {Stopping: child, Later: later},
            (DailyBatchChild("停止项", Stopping), DailyBatchChild("后续项", Later)),
            {"启用": True, "停止项": True, "后续项": True},
        )
        with (
            mock.patch.object(DailyBatchTask, "_recover_home") as recover,
            mock.patch("src.tasks.scheduler.default_store"),
        ):
            with self.assertRaises(TaskDisabledException):
                DailyBatchTask.run(task)
        recover.assert_not_called()
        later.run.assert_not_called()
        self.assertEqual({"启用": False}, child.config)

    def test_stop_swallowed_by_a_child_still_stops_the_batch(self):
        """ok-script clears its current task before raising the stop, so a
        child whose broad except swallows it just returns False; the batch's
        own flag must still stop everything (review 2026-09-26)."""

        class Swallowing:
            pass

        class Later:
            pass

        task = None

        class _SwallowingChild(_StoppingChild):
            def run(self):
                task._enabled = False  # Stop pressed during this child
                return False

        later = mock.Mock()
        task = _batch(
            {Swallowing: _SwallowingChild(), Later: later},
            (DailyBatchChild("吞掉停止", Swallowing), DailyBatchChild("后续项", Later)),
            {"启用": True, "吞掉停止": True, "后续项": True, "失败后继续": True},
        )
        task._enabled = True
        with (
            mock.patch.object(DailyBatchTask, "_recover_home") as recover,
            mock.patch("src.tasks.scheduler.default_store"),
        ):
            with self.assertRaises(TaskDisabledException):
                DailyBatchTask.run(task)
        recover.assert_not_called()
        later.run.assert_not_called()

    def test_recovery_re_raises_stop_from_the_navigator(self):
        class StoppingNavigator:
            def __init__(self, task, vision):
                pass

            def classify(self):
                return ScreenState.SANDBOX

            def return_home(self):
                raise TaskDisabledException()

        task = SimpleNamespace(info_set=lambda *a: None, log_warning=mock.Mock())
        with mock.patch.object(recovery, "Navigator", StoppingNavigator):
            with self.assertRaises(TaskDisabledException):
                recovery.recover_to_home(task)
        task.log_warning.assert_not_called()


class LoginReleaseTest(unittest.TestCase):
    def test_login_releases_both_daily_and_weekly_batches(self):
        login = object.__new__(AutoLoginTask)
        login._executor = SimpleNamespace()
        with (
            mock.patch.object(DailyBatchTask, "release_after_login") as daily,
            mock.patch.object(WeeklyBatchTask, "release_after_login") as weekly,
        ):
            login._release_login_gated_batch()
        daily.assert_called_once()
        weekly.assert_called_once()


if __name__ == "__main__":
    unittest.main()
