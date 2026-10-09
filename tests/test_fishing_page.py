import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.fishing.runner import DEFAULTS, LIMITS
from src.ui.shell import fishing_page as page_module


class FishingPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.task = SimpleNamespace(
            name="自动钓鱼",
            config=dict(DEFAULTS),
            default_config=dict(DEFAULTS),
            config_type={key: {"min": low, "max": high} for key, (low, high) in LIMITS.items()},
            config_description={},
            fishing_status={},
        )
        self.current = self.remote = None
        self.ready = True
        patches = (
            patch.object(page_module.data, "task_by_name", return_value=self.task),
            patch.object(page_module.data, "current_task", side_effect=lambda: self.current),
            patch.object(page_module.data, "busy", side_effect=lambda: self.current is not None),
            patch.object(page_module.clone_flow, "remote_task", side_effect=lambda: self.remote),
            patch.object(
                page_module.clone_flow, "busy_in_clone", side_effect=lambda: self.remote is not None
            ),
            patch.object(
                page_module.clone_flow, "background_status", return_value="桌面分身已就绪"
            ),
            patch.object(page_module.clone_flow, "available", return_value=True),
            patch.object(page_module.clone_desktop, "in_clone", return_value=False),
            patch.object(page_module, "BACKEND", Mock(is_file=lambda: self.ready)),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.page = page_module.FishingPage()
        self.addCleanup(self.page.deleteLater)

    def test_backend_missing_disables_start(self):
        self.ready = False
        self.page.refresh()
        self.assertFalse(self.page.start_button.isEnabled())
        self.assertFalse(self.page.clone_button.isEnabled())
        self.assertFalse(self.page.pause_button.isEnabled())

    def test_time_limits_are_visible_and_editable(self):
        for key, expected in (("最长运行分钟", 30), ("等待进入钓场秒数", 180)):
            label, control, _sync = self.page.form._rows[key]
            self.assertFalse(label.isHidden())
            self.assertFalse(control.isHidden())
            self.assertEqual(expected, control.value())
        self.page.form._rows["最长运行分钟"][1].setValue(10)
        self.assertEqual(10, self.task.config["最长运行分钟"])

    def test_active_fishing_locks_settings_and_enables_stop(self):
        self.current = self.task
        self.task.fishing_status = {"本次收获": 2}
        self.page.refresh()
        self.assertFalse(self.page.form.isEnabled())
        self.assertFalse(self.page.start_button.isEnabled())
        self.assertTrue(self.page.stop_button.isEnabled())
        self.assertIn("2", self.page.status.text())

    def test_clone_controls_route_to_remote_task(self):
        self.remote = SimpleNamespace(
            name="自动钓鱼",
            remote=True,
            paused=False,
            status={"fishing": {"本次收获": 12}},
        )
        self.page.refresh()
        self.assertIn("12", self.page.status.text())
        with patch.object(page_module.clone_desktop, "send_control") as send:
            self.page._pause()
            send.assert_called_with("pause")
            self.remote.paused = True
            self.page._pause()
            send.assert_called_with("resume")
            self.page._stop()
            send.assert_called_with("stop")

    def test_start_clone_uses_existing_desktop_flow(self):
        with patch.object(page_module.clone_flow, "ask_and_start") as start:
            self.page._start_clone()
            start.assert_called_once_with(self.page.window(), self.task)

    def test_other_task_prevents_fishing_start_and_remote_controls(self):
        self.current = SimpleNamespace(name="一键完成日常")
        self.page.refresh()
        self.assertFalse(self.page.start_button.isEnabled())
        self.assertFalse(self.page.pause_button.isEnabled())
        self.assertFalse(self.page.stop_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
