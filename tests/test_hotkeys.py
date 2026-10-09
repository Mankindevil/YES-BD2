import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ui.shell import hotkeys


class FakeRecordTask:
    def __init__(self, key=None):
        self.config = {} if key is None else {"录制按键": key}


class HotkeysTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.file = Path(self.folder.name) / "configs" / "hotkeys.json"
        patcher = patch.object(hotkeys, "KEYS_FILE", self.file)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.folder.cleanup)

    def test_defaults(self):
        self.assertEqual(
            {"pause": "F9", "stop": "F10", "record": "F8"}, hotkeys.keys(FakeRecordTask())
        )

    def test_choices_are_f6_to_f12(self):
        self.assertEqual(("F6", "F7", "F8", "F9", "F10", "F11", "F12"), hotkeys.KEY_CHOICES)

    def test_record_key_comes_from_the_fiend_task(self):
        self.assertEqual("F7", hotkeys.keys(FakeRecordTask("F7"))["record"])

    def test_picking_a_used_key_swaps(self):
        task = FakeRecordTask("F8")
        current = hotkeys.set_key("pause", "F10", task)
        self.assertEqual({"pause": "F10", "stop": "F9", "record": "F8"}, current)
        self.assertEqual(current, hotkeys.keys(task))

    def test_record_key_swaps_with_pause_and_is_saved_on_the_task(self):
        task = FakeRecordTask("F8")
        current = hotkeys.set_key("record", "F9", task)
        self.assertEqual({"pause": "F8", "stop": "F10", "record": "F9"}, current)
        self.assertEqual("F9", task.config["录制按键"])

    def test_old_record_key_f9_never_shares_with_pause(self):
        # Before 10-09 the record key could already be F9 or F10.
        current = hotkeys.keys(FakeRecordTask("F9"))
        self.assertEqual("F9", current["record"])
        self.assertEqual(3, len(set(current.values())))

    def test_broken_file_falls_back(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text("{oops", encoding="utf-8")
        self.assertEqual("F9", hotkeys.keys(FakeRecordTask())["pause"])

    def test_unknown_key_is_ignored(self):
        task = FakeRecordTask()
        self.assertEqual(hotkeys.keys(task), hotkeys.set_key("pause", "F1", task))


if __name__ == "__main__":
    unittest.main()
