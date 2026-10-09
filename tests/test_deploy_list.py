"""Files the tool opens at run time must ship in the player install.

The installer and one-click update copy only what deploy.txt lists; a player
on v0.1.4 pressed 「第一次设定」 and PowerShell closed at once, because
tools/clone_desktop/setup.ps1 was not shipped.
"""

import unittest
from pathlib import Path

from src.utils import clone_desktop

REPO = Path(__file__).resolve().parents[1]


def shipped(path: Path) -> bool:
    relative = path.resolve().relative_to(REPO).as_posix()
    entries = (REPO / "deploy.txt").read_text(encoding="utf-8").split()
    return any(relative == entry or relative.startswith(entry + "/") for entry in entries)


class DeployListTest(unittest.TestCase):
    def test_clone_desktop_files_ship(self):
        for path in (clone_desktop.SETUP_SCRIPT, clone_desktop.VIEWER_SOURCE):
            with self.subTest(path=path.name):
                self.assertTrue(path.exists())
                self.assertTrue(shipped(path), f"{path.name} is not in deploy.txt")


if __name__ == "__main__":
    unittest.main()
