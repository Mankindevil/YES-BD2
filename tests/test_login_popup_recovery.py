"""Regressions for stacked sign-in rewards and early daily-batch release."""

import json
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from src.tasks import recovery
from src.tasks.BaseBD2Task import BaseBD2Task
from tests import test_auto_login_sequence


class LoginPopupRecoveryTest(unittest.TestCase):
    def task(self):
        task = test_auto_login_sequence.AutoLoginSequenceTest._task(self)
        task._state = "waiting"
        task.capture_frame = lambda: np.full((108, 192, 3), 200, np.uint8)
        task.mark_logged_in = mock.Mock()
        task._release_login_gated_batch = mock.Mock()
        task.operate_click = mock.Mock()
        task._check_capture_colours = mock.Mock()
        task._match_home_button = lambda frame: (
            SimpleNamespace(score=1.0), SimpleNamespace(),
        )
        task._passes = lambda *args: True
        task._passes_dimmed_home = lambda *args: True
        task._home_brightness_ratio = lambda frame: 1.0
        task._home_gacha_ocr_text = lambda frame: "抽抽乐"
        return task

    def test_stacked_popups_reset_stability_even_when_home_signals_pass(self):
        task = self.task()
        names = []
        task.ocr = lambda **kwargs: [SimpleNamespace(name=name) for name in names]
        with mock.patch("src.tasks.trigger.AutoLoginTask.monotonic") as clock:
            clock.return_value = 100
            task.run()  # clear home, but only the first frame
            self.assertFalse(task._finished)
            clock.return_value = 102
            names[:] = ["签到成功", "登录加成", "每天签到时"]
            task.run()
            self.assertIsNone(task._home_bright_since)
            clock.return_value = 104
            names[:] = ["公告", "公告", "2026年10月11日"]
            task.run()
            self.assertEqual(2, task.operate_click.call_count)
            task._release_login_gated_batch.assert_not_called()
            names.clear()
            clock.return_value = 106
            task.run()
            clock.return_value = 108
            task.run()
            self.assertFalse(task._finished)
            clock.return_value = 110
            task.run()
        self.assertTrue(task._finished)
        task.mark_logged_in.assert_called_once()
        task._release_login_gated_batch.assert_called_once()

    def test_starting_on_signin_does_not_wait_for_login_screen(self):
        task = self.task()
        task.ocr = lambda **kwargs: [
            SimpleNamespace(name=name) for name in ("签到成功", "登录加成")
        ]
        task._home_confirmation_signals = mock.Mock(side_effect=AssertionError("covered"))
        task.run()
        self.assertEqual("clearing", task._state)
        task.operate_click.assert_called_once()
        task.mark_logged_in.assert_not_called()

    def test_recovery_success_still_requires_stable_home(self):
        task = self.task()
        with (
            mock.patch.object(recovery, "in_game_page", return_value=True),
            mock.patch.object(recovery, "recover_to_home", return_value=True),
        ):
            self.assertTrue(task._finish_by_recovery())
        self.assertEqual("clearing", task._state)
        self.assertFalse(task._finished)
        task._release_login_gated_batch.assert_not_called()
        task.mark_logged_in.assert_not_called()

    def test_batch_in_game_shortcut_stays_gated(self):
        task = self.task()
        self.assertFalse(task.finish_in_game())
        self.assertEqual("clearing", task._state)
        task.mark_logged_in.assert_not_called()

    def test_known_notice_uses_panel_close_at_each_supported_size(self):
        task = self.task()
        task.ocr = lambda **kwargs: [
            SimpleNamespace(name=name)
            for name in ("公告", "公告", "2026年10月11日")
        ]
        for width, height in ((1920, 1080), (2560, 1440), (3840, 2160)):
            with self.subTest(size=(width, height)):
                frame = np.full((height, width, 3), 200, np.uint8)
                self.assertTrue(recovery.dismiss_login_overlay(task, frame))
                task.operate_click.assert_called_with(1328 / 1920, 275 / 1080, after_sleep=1.0)

    def test_single_notice_or_purchase_is_not_a_login_overlay(self):
        for names in (("公告", "2026年10月11日"), ("购买签到礼包", "确认", "登录")):
            boxes = [SimpleNamespace(name=name) for name in names]
            self.assertIsNone(recovery._login_overlay_point(boxes))

    def test_saved_failure_notice_ocr_targets_the_visible_close_button(self):
        # Output of real OCR on 2026-10-11's failure capture (fixture beside it).
        data = json.loads(
            (Path(__file__).parent / "fixtures/login_notice_ocr.json").read_text(encoding="utf-8")
        )
        boxes = [SimpleNamespace(**item) for item in data]
        point, label = recovery._login_overlay_point(boxes)
        close = next(box for box in boxes if box.name == "X" and 1250 < box.x < 1380)
        self.assertEqual("公告列表", label)
        self.assertLess(abs(point[0] * 1920 - (close.x + close.width / 2)), 10)
        self.assertLess(abs(point[1] * 1080 - (close.y + close.height / 2)), 10)

    def test_home_recovery_clears_overlay_even_with_auto_login_disabled(self):
        task = self.task()
        task._enabled = False
        task.ocr = lambda **kwargs: [
            SimpleNamespace(name=name) for name in ("签到成功", "登录加成")
        ]
        navigator = SimpleNamespace(
            task=task, vision=SimpleNamespace(capture=task.capture_frame),
            _home_confirmation_signals=lambda frame: (True, 2, 230, "抽抽乐"),
        )
        self.assertFalse(recovery._home_now(navigator))
        task.operate_click.assert_called_once()
        self.assertFalse(task._enabled)

    def test_failed_home_guard_never_runs_child_or_recovers_twice(self):
        class Task(BaseBD2Task):
            start_from_home = True
            recover_home_on_failure = True

            def run(self):
                raise AssertionError("must not run through a login popup")

        task = object.__new__(Task)
        task._action_interval_lock = None
        task.info_set = mock.Mock()
        task._go_home_before_run = mock.Mock(return_value=False)
        task._leave_home_after_failed_run = mock.Mock()
        scope = SimpleNamespace(result=None)
        with (
            mock.patch("src.tasks.BaseBD2Task.game_size.fix_or_warn"),
            mock.patch("src.tasks.BaseBD2Task.problem_report.run_scope", return_value=nullcontext(scope)),
            mock.patch("src.tasks.BaseBD2Task.problem_report.note_problem"),
        ):
            self.assertFalse(task.run())
        self.assertIs(scope.result, False)
        task._leave_home_after_failed_run.assert_not_called()

    def test_disabled_login_reports_disabled(self):
        task = self.task()
        task.config["_enabled"] = False
        task._set_stage = mock.Mock()
        task._set_action = mock.Mock()
        task.on_create()
        task._set_stage.assert_called_with("已停用")
        self.assertFalse(task._enabled)
