import re
import unittest
from pathlib import Path

from qfluentwidgets import FluentIcon

SRC = Path(__file__).resolve().parents[1] / "src"


class FluentIconsExistTest(unittest.TestCase):
    def test_every_used_icon_exists(self):
        # Live 2026-10-04: FluentIcon.GIFT is not in the installed version and
        # the tool died on start, before any window showed.
        used = set()
        for path in SRC.rglob("*.py"):
            used |= set(re.findall(r"FluentIcon\.([A-Z_]+)", path.read_text(encoding="utf-8")))
        missing = sorted(name for name in used if not hasattr(FluentIcon, name))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
