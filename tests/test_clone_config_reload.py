import json
import tempfile
import unittest
from pathlib import Path

from src.utils import clone_desktop

try:
    from ok.util.config import Config
except Exception:  # ok-script is installed on Windows only
    Config = None


@unittest.skipIf(Config is None, "ok-script not installed")
class CloneConfigReloadTest(unittest.TestCase):
    """Leo 2026-10-09: a setting changed outside must reach the run in the clone."""

    def test_setting_saved_outside_reaches_the_tool_in_the_clone(self):
        default = {"舞台移动方式": "鼠标点击舞台", "战斗场数": "1"}
        with tempfile.TemporaryDirectory() as folder:
            inside = Config("PVPTask", default, folder=folder)
            outside = Config("PVPTask", default, folder=folder)
            outside["舞台移动方式"] = "键盘WASD走到舞台"
            self.assertEqual(inside["舞台移动方式"], "鼠标点击舞台")

            self.assertTrue(clone_desktop.reload_config(inside))

            self.assertEqual(inside["舞台移动方式"], "键盘WASD走到舞台")
            self.assertEqual(inside["战斗场数"], "1")

    def test_broken_file_keeps_what_is_in_memory(self):
        default = {"舞台移动方式": "鼠标点击舞台"}
        with tempfile.TemporaryDirectory() as folder:
            inside = Config("PVPTask", default, folder=folder)
            Path(inside.config_file).write_text("{broken", encoding="utf-8")

            self.assertFalse(clone_desktop.reload_config(inside))

            self.assertEqual(inside["舞台移动方式"], "鼠标点击舞台")
            self.assertEqual(Path(inside.config_file).read_text(encoding="utf-8"), "{broken")

    def test_missing_keys_fall_back_to_defaults_without_saving(self):
        default = {"舞台移动方式": "鼠标点击舞台", "战斗场数": "1"}
        with tempfile.TemporaryDirectory() as folder:
            inside = Config("PVPTask", default, folder=folder)
            Path(inside.config_file).write_text(
                json.dumps({"舞台移动方式": "键盘WASD走到舞台"}), encoding="utf-8"
            )

            self.assertTrue(clone_desktop.reload_config(inside))

            self.assertEqual(dict(inside), {"舞台移动方式": "键盘WASD走到舞台", "战斗场数": "1"})


if __name__ == "__main__":
    unittest.main()
