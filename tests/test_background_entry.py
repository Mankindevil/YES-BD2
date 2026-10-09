"""Background setup is discoverable and never starts tasks from settings."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.ui.shell import clone_flow
from src.ui.shell.page import Page
from src.ui.shell.settings import SettingsPage


class BackgroundEntryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clone = Mock()
        self.clone.in_clone.return_value = False
        self.clone.supported.return_value = True
        self.clone.ready.return_value = False
        self.clone.hello_only.return_value = False
        self.clone.viewer_removed.return_value = False
        self.clone.SETUP_STATE.exists.return_value = False
        self.dialog = Mock()
        self.dialog.exec.return_value = True
        for target, value in (
            ("src.ui.shell.clone_flow.clone_desktop", self.clone),
            ("qfluentwidgets.MessageBox", Mock(return_value=self.dialog)),
            ("src.ui.shell.clone_flow.data.busy", Mock(return_value=False)),
            ("src.ui.shell.clone_flow.open_clone", Mock(return_value=True)),
            ("src.ui.shell.clone_flow.message", Mock()),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_first_run_sets_up_without_launching_a_task(self):
        self.assertFalse(clone_flow.ask_and_start(None, SimpleNamespace(), "all"))
        self.clone.run_setup.assert_called_once_with()
        clone_flow.open_clone.assert_not_called()

    def test_cancel_does_not_change_windows_or_start(self):
        self.dialog.exec.return_value = False
        self.assertFalse(clone_flow.prepare_background(None))
        self.clone.run_setup.assert_not_called()
        clone_flow.open_clone.assert_not_called()

    def test_ready_launch_forwards_the_selected_task_and_mode(self):
        self.clone.ready.return_value = True
        window, task = object(), object()
        self.assertTrue(clone_flow.ask_and_start(window, task, "all"))
        clone_flow.open_clone.assert_called_once_with(window, task, "all")
        self.clone.run_setup.assert_not_called()

    def test_settings_only_explains_when_ready(self):
        self.clone.ready.return_value = True
        self.assertFalse(clone_flow.prepare_background(None, for_run=False))
        clone_flow.open_clone.assert_not_called()
        self.clone.run_setup.assert_not_called()

    def test_opening_background_setup_cancels_pending_foreground_autorun(self):
        from src.ui.shell import autorun

        with patch.object(autorun, "_due", 12345.0):
            self.dialog.exec.return_value = False
            self.assertFalse(clone_flow.prepare_background(None))
            self.assertIsNone(autorun._due)

    def test_task_started_during_dialog_blocks_setup(self):
        clone_flow.data.busy.side_effect = [False, True]
        self.assertFalse(clone_flow.prepare_background(None))
        self.clone.run_setup.assert_not_called()
        clone_flow.open_clone.assert_not_called()
        clone_flow.message.assert_called_once()

    def test_unsupported_system_is_explained_without_setup(self):
        self.clone.supported.return_value = False
        self.assertIn("不支持", clone_flow.background_status())
        self.assertFalse(clone_flow.prepare_background(None))
        clone_flow.message.assert_called_once()
        self.clone.run_setup.assert_not_called()

    def test_hello_only_opens_settings_instead_of_launching(self):
        self.clone.ready.return_value = True
        self.clone.hello_only.return_value = True
        self.assertFalse(clone_flow.prepare_background(None))
        self.clone.open_sign_in_options.assert_called_once_with()
        clone_flow.open_clone.assert_not_called()

    def test_missing_viewer_explains_repair(self):
        self.clone.viewer_removed.return_value = True
        self.assertIn("缺失", clone_flow.background_status())
        self.assertFalse(clone_flow.prepare_background(None))
        self.clone.run_setup.assert_called_once_with()

    def test_setup_spawn_failure_is_reported(self):
        self.clone.run_setup.side_effect = OSError("test failure")
        self.assertFalse(clone_flow.prepare_background(None))
        clone_flow.message.assert_called_once()

    def test_settings_card_visible_before_setup_and_refreshes_after(self):
        page = SettingsPage.__new__(SettingsPage)
        Page.__init__(page, "testBackground", "设置")
        with patch("src.utils.clone_desktop", self.clone):
            page._build_clone()
        self.addCleanup(page.deleteLater)
        self.assertFalse(page.clone_card.isHidden())
        self.assertFalse(page.clone_setup_button.isHidden())
        self.assertTrue(page.clone_setup_button.isEnabled())
        self.assertTrue(page.clone_undo_row.isHidden())
        self.clone.ready.return_value = True
        page._refresh_clone()
        self.assertFalse(page.clone_undo_row.isHidden())
        self.clone.supported.return_value = False
        page._refresh_clone()
        self.assertFalse(page.clone_card.isHidden())
        self.assertFalse(page.clone_setup_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
