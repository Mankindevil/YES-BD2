import os
import time
import unittest
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.tasks import run_log, run_report
from src.ui.shell import autorun, clone_flow, data, home


@contextmanager
def remaining_page():
    batch = SimpleNamespace(name=data.DAILY_BATCH, config={}, info={})
    children = [
        data.Child(str(i), None, name, name, "play", "plain", True)
        for i, name in enumerate(("快速狩猎", "白嫖抽抽乐", "镜中之战"))
    ]
    with ExitStack() as stack:
        for module, name, value in (
            (data, "task_by_name", lambda name: batch if name == data.DAILY_BATCH else None),
            (data, "batch_children", lambda batch: children),
            (data, "child_done", lambda child: child.key != "2"),
            (data, "last_run", lambda name: {"finished": time.time()}),
            (data, "sync_weekly_ticks", lambda batch: None),
            (data, "map_progress", lambda: None),
            (data, "busy", lambda: False),
            (data, "executor", lambda: None),
            (run_log, "entries", lambda: []),
            (run_report, "load", lambda *args: {}),
            (run_report, "stopped_row", lambda *args: {"key": "2", "name": "镜中之战"}),
            (clone_flow, "busy_in_clone", lambda: False),
            (clone_flow, "available", lambda: False),
            (clone_flow, "background_status", lambda: "后台运行未启用"),
            (autorun, "enabled", lambda: False),
            (autorun, "seconds_left", lambda: None),
        ):
            stack.enter_context(patch.object(module, name, value))
        page = home.HomePage(lambda *args: None, lambda *args: None)
        try:
            page._refresh_idle()
            yield page, batch
        finally:
            page.deleteLater()


class RemainingButtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_stopped_run_keeps_separate_skip_completed_button(self):
        with remaining_page() as (page, batch):
            self.assertFalse(page.resume.isHidden())
            self.assertFalse(page.start_rest.isHidden())
            self.assertIn("跳过已完成", page.start_rest.text())
            self.assertIn("1", page.start_rest.text())
            page.refresh = Mock()
            with patch.object(home.actions, "start") as start:
                page.start_rest.click()
                self.assertEqual("incomplete", start.call_args.args[2])
                self.assertIs(batch, start.call_args.args[0])
                page.start_all.click()
                self.assertEqual("all", start.call_args.args[2])

    def test_remaining_start_disabled_when_busy(self):
        with remaining_page() as (page, _):
            with patch.object(data, "busy", return_value=True):
                page._refresh_idle()
            self.assertFalse(page.start_rest.isEnabled())


if __name__ == "__main__":
    unittest.main()
