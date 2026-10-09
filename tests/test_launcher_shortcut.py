import tempfile
import unittest
from pathlib import Path

from src.compat.launcher_shortcut import needs_retarget, retarget, shortcut_paths


class FakeShortcut:
    def __init__(self, target, icon="C:\\app\\icon.ico,0"):
        self.TargetPath = target
        self.Arguments = '"C:\\app\\data\\apps\\yes-bd2\\.pyappify-shortcut.py"'
        self.WorkingDirectory = "C:\\app\\data\\apps\\yes-bd2\\working"
        self.IconLocation = icon
        self.saved = False

    def Save(self):
        self.saved = True


class FakeShell:
    def __init__(self, shortcut):
        self.shortcut = shortcut

    def CreateShortcut(self, _path):
        return self.shortcut


class LauncherShortcutTest(unittest.TestCase):
    def test_paths_are_start_menu_and_desktop_with_the_app_name(self):
        paths = shortcut_paths("yes-bd2", Path("S"), Path("D"))
        self.assertEqual([Path("S/yes-bd2.lnk"), Path("D/yes-bd2.lnk")], paths)

    def test_python_shortcut_is_pointed_at_the_launcher_keeping_its_icon(self):
        with tempfile.TemporaryDirectory() as folder:
            link = Path(folder) / "yes-bd2.lnk"
            link.write_bytes(b"")
            launcher = Path(folder) / "yes-bd2.exe"
            shortcut = FakeShortcut(str(Path(folder) / "python" / "pythonw.exe"))
            self.assertTrue(retarget(link, launcher, FakeShell(shortcut)))
            self.assertTrue(shortcut.saved)
            self.assertEqual(str(launcher), shortcut.TargetPath)
            self.assertEqual("", shortcut.Arguments)
            self.assertEqual(str(launcher.parent), shortcut.WorkingDirectory)
            self.assertEqual("C:\\app\\icon.ico,0", shortcut.IconLocation)

    def test_shortcut_already_on_the_launcher_is_left_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            link = Path(folder) / "yes-bd2.lnk"
            link.write_bytes(b"")
            launcher = Path(folder) / "yes-bd2.exe"
            shortcut = FakeShortcut(str(launcher))
            self.assertFalse(retarget(link, launcher, FakeShell(shortcut)))
            self.assertFalse(shortcut.saved)

    def test_missing_shortcut_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            shortcut = FakeShortcut("python")
            self.assertFalse(
                retarget(Path(folder) / "yes-bd2.lnk", Path(folder) / "x.exe", FakeShell(shortcut))
            )
            self.assertFalse(shortcut.saved)

    def test_needs_retarget(self):
        self.assertFalse(needs_retarget("", Path("C:/a/yes-bd2.exe")))
        self.assertTrue(needs_retarget("C:/a/python/pythonw.exe", Path("C:/a/yes-bd2.exe")))


if __name__ == "__main__":
    unittest.main()
