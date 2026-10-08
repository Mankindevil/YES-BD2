import gettext
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.shell import about_page
from src.ui.shell.about_page import CREDITS, NOTICE, AboutPage, souseha_url

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "i18n"


class _FakeUpdateCard(QWidget):
    update_available_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.checks = 0

    def check_for_updates(self):
        self.checks += 1


class _FakeItem(QObject):
    def __init__(self):
        super().__init__()
        self.badge = ""

    def set_badge(self, text, kind=""):
        self.badge = text


class AboutPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_credits_name_what_the_tool_uses(self):
        # Leo (2026-10-05): BetterGI, souseha's 图鉴 and 時樂淵's 跑商 sheet.
        names = {credit.name for credit in CREDITS}
        for name in ("ok-bd2", "ok-script", "BetterGI", "ChildStream", "MaaBD2", "BD2DB 图鉴"):
            self.assertIn(name, names)
        sheet = next(credit for credit in CREDITS if credit.name == "跑商售卖物品表")
        self.assertIn("時樂淵", sheet.who)
        self.assertEqual(sheet.url, "https://space.bilibili.com/14949646")

    def test_souseha_opens_in_the_ui_language(self):
        self.assertEqual(souseha_url("zh_TW"), "https://browndust2-db.souseha.com/tw/")
        self.assertEqual(souseha_url("zh_CN"), "https://browndust2-db.souseha.com/cn/")
        self.assertEqual(souseha_url("en_US"), "https://browndust2-db.souseha.com/en/")
        self.assertEqual(souseha_url("ja_JP"), "https://browndust2-db.souseha.com/ja/")
        self.assertEqual(souseha_url("ko_KR"), "https://browndust2-db.souseha.com/ko/")
        self.assertEqual(souseha_url("fr_FR"), "https://browndust2-db.souseha.com/")

    def test_notice_and_credits_follow_every_language(self):
        texts = list(NOTICE) + [credit.what for credit in CREDITS]
        texts += ["关于", "版本、更新和致谢", "使用须知", "致谢（参考或使用了这些项目）"]
        texts += ["BD2DB 图鉴", "跑商售卖物品表", "思源黑体 Noto Sans", "版本 {version}"]
        for language in ("en_US", "ja_JP", "ko_KR"):
            catalog = gettext.translation("ok", CATALOG_ROOT, languages=[language])
            for text in texts:
                self.assertNotEqual(catalog.gettext(text), text, (language, text))

    def test_update_controls_move_to_the_new_page(self):
        card = _FakeUpdateCard()
        window = SimpleNamespace(about_tab=SimpleNamespace(update_card=card))
        item = _FakeItem()
        sidebar = SimpleNamespace(items={"about": item})
        page = AboutPage(window, sidebar)
        self.assertIs(page.update_card, card)
        self.assertTrue(page.isAncestorOf(card))
        page.check_for_updates()
        self.assertEqual(card.checks, 1)
        card.update_available_changed.emit(True)
        self.assertTrue(item.badge)
        self.assertTrue(page.update_pill.text())
        card.update_available_changed.emit(False)
        self.assertEqual(item.badge, "")

    def test_source_checkout_has_no_update_controls_but_a_github_row(self):
        page = AboutPage(SimpleNamespace(about_tab=None))
        self.assertIsNone(page.update_card)
        self.assertEqual(about_page.PROJECT_URL, "https://github.com/nobell001/YES-BD2")
        urls = [row.url for row in page.findChildren(about_page.LinkRow)]
        self.assertEqual(len(urls), len(CREDITS) + 1)
        self.assertIn(about_page.PROJECT_URL, urls)
        self.assertNotIn("", urls)


if __name__ == "__main__":
    unittest.main()
