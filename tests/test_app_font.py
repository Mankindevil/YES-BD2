import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel, fontFamilies, setFontFamilies

from src.ui.quest_theme import APP_FONT_FAMILIES, apply_app_font, font_families


class AppFontTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ui_font_stack_is_applied_to_qfluent_and_qt(self):
        previous_families = fontFamilies()
        previous_app_font = QApplication.instance().font()
        self.addCleanup(setFontFamilies, previous_families, False)
        self.addCleanup(QApplication.instance().setFont, previous_app_font)

        apply_app_font()
        self.assertTrue(QApplication.instance().property("bd2_bundled_font_loaded"))
        families = list(font_families())
        self.assertEqual(fontFamilies(), families)
        self.assertEqual(QApplication.instance().font().families(), families)
        label = BodyLabel("中文 English")
        self.assertEqual(label.font().families(), families)
        label.close()

    def test_simplified_ui_puts_noto_sans_sc_first(self):
        self.assertEqual("Noto Sans TC", APP_FONT_FAMILIES[0])
        self.assertEqual("Noto Sans TC", font_families("zh_TW")[0])
        self.assertEqual("Noto Sans TC", font_families("en_US")[0])
        self.assertEqual("Noto Sans SC", font_families("zh_CN")[0])

    def test_bundled_fonts_cover_both_scripts(self):
        from PySide6.QtGui import QFontDatabase

        apply_app_font()
        families = set(QFontDatabase.families())
        self.assertIn("Noto Sans TC", families)
        self.assertIn("Noto Sans SC", families)


if __name__ == "__main__":
    unittest.main()
