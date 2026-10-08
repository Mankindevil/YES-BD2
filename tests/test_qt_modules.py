"""The installer leaves out PySide6's Addons wheel (pyproject override), so
the tool may only use Qt modules shipped in pyside6-essentials."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Python modules inside pyside6-essentials 6.9.1
ESSENTIALS = {
    "QtConcurrent", "QtCore", "QtDBus", "QtDesigner", "QtGui", "QtHelp",
    "QtNetwork", "QtOpenGL", "QtOpenGLWidgets", "QtPrintSupport", "QtQml",
    "QtQuick", "QtQuickControls2", "QtQuickTest", "QtQuickWidgets", "QtSql",
    "QtSvg", "QtSvgWidgets", "QtTest", "QtUiTools", "QtWidgets", "QtXml",
}
QT_MODULE = re.compile(r"\bPySide6\.(Qt\w+)")


class QtModulesTest(unittest.TestCase):
    def test_code_uses_only_essentials_modules(self):
        used = {}
        for path in [ROOT / "main.py", *(ROOT / "src").rglob("*.py")]:
            for module in QT_MODULE.findall(path.read_text(encoding="utf-8")):
                used.setdefault(module, path.relative_to(ROOT).as_posix())
        outside = {module: path for module, path in used.items() if module not in ESSENTIALS}
        self.assertEqual({}, outside)

    def test_requirements_leave_out_the_addons_wheel(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("pyside6-essentials==", requirements)
        self.assertNotIn("pyside6-addons==", requirements)


if __name__ == "__main__":
    unittest.main()
