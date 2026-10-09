import os
import sys
import unittest
from unittest import mock

import main

def _path(*parts):
    """An absolute path in this system's own form (C:\\... on Windows)."""
    return os.path.abspath(os.path.join(os.sep, *parts))


ROOT = _path("Users", "张三", "AppData", "Local", "yes-bd2")
WORKING = os.path.join(ROOT, "data", "apps", "yes-bd2", "working")
LINK = _path("ProgramData", "YES-BD2", "links", "abc")
ZIP = _path("Python312", "python312.zip")


def _under(base, *parts):
    return os.path.join(base, *parts)


class AsciiPathTest(unittest.TestCase):
    """Chinese letters in the install folder (2026-10-09 review; 4K test: the
    short name on Chinese Windows is still Chinese, so a link is used)."""

    def _run(self, script, prefix, link=LINK, cwd=WORKING):
        argv = [script]
        path = [os.path.dirname(script), _under(prefix, "Lib", "site-packages"), ZIP]
        moved = []
        asked = []

        def link_for(target):
            asked.append(target)
            return link

        with (
            mock.patch.object(sys, "platform", "win32"),
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(sys, "path", path),
            mock.patch.object(sys, "prefix", prefix),
            mock.patch.object(sys, "executable", _under(prefix, "Scripts", "pythonw.exe")),
            mock.patch.object(main, "_link_for", side_effect=link_for),
            mock.patch("os.getcwd", return_value=cwd),
            mock.patch("os.chdir", side_effect=moved.append),
        ):
            main.use_ascii_paths()
            return argv, path, moved, asked, sys.executable

    def test_english_folder_is_left_alone(self):
        script = _path("Games", "yes-bd2", "data", "apps", "yes-bd2", "working", "main.py")
        argv, path, moved, asked, _exe = self._run(script, _path("Games", "yes-bd2", ".venv"))
        self.assertEqual(argv, [script])
        self.assertEqual(moved, [])
        self.assertEqual(asked, [])

    def test_whole_install_goes_through_the_link(self):
        argv, path, moved, asked, exe = self._run(
            _under(WORKING, "main.py"), _under(ROOT, ".venv")
        )
        linked = _under(LINK, "data", "apps", "yes-bd2", "working")
        self.assertEqual(asked, [ROOT])
        self.assertEqual(argv, [_under(linked, "main.py")])
        self.assertEqual(path, [linked, _under(LINK, ".venv", "Lib", "site-packages"), ZIP])
        self.assertEqual(moved, [linked])
        self.assertEqual(exe, _under(LINK, ".venv", "Scripts", "pythonw.exe"))
        self.assertTrue(all(entry.isascii() for entry in path))

    def test_source_checkout_links_what_tool_and_python_share(self):
        checkout = _path("Users", "张三", "code", "bd2-auto")
        argv, path, moved, asked, _exe = self._run(
            _under(checkout, "main.py"), _under(checkout, ".venv"), cwd=checkout
        )
        self.assertEqual(asked, [checkout])
        self.assertEqual(argv, [_under(LINK, "main.py")])

    def test_no_link_keeps_the_paths(self):
        # ok-script then shows its own English-path message, as before.
        script = _under(WORKING, "main.py")
        argv, path, moved, asked, _exe = self._run(script, _under(ROOT, ".venv"), link=None)
        self.assertEqual(argv, [script])
        self.assertEqual(moved, [])


if __name__ == "__main__":
    unittest.main()
