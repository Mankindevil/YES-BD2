"""With the app set to Traditional Chinese, untranslated text is converted."""

import unittest
from types import SimpleNamespace

from src.ui.traditional import is_traditional, to_traditional, wrap_tr


class TraditionalTest(unittest.TestCase):
    def _app(self, locale, catalog=None):
        catalog = catalog or {}

        def original(self, key):
            return catalog.get(key, key)

        app = SimpleNamespace(locale=SimpleNamespace(name=lambda: locale))
        tr = wrap_tr(original)
        return lambda key: tr(app, key)

    def test_untranslated_text_turns_traditional_on_zh_tw(self):
        tr = self._app("zh_TW")
        self.assertEqual("一鍵完成日常", tr("一键完成日常"))
        self.assertEqual("設定", tr("设置"))  # Taiwan wording

    def test_simplified_and_other_locales_are_untouched(self):
        self.assertEqual("一键完成日常", self._app("zh_CN")("一键完成日常"))
        self.assertEqual("一键完成日常", self._app("en_US")("一键完成日常"))

    def test_a_real_translation_wins(self):
        tr = self._app("zh_TW", {"跑商": "跑商（自訂）"})
        self.assertEqual("跑商（自訂）", tr("跑商"))

    def test_locale_names(self):
        self.assertTrue(is_traditional("zh_TW"))
        self.assertTrue(is_traditional("zh-HK"))
        self.assertFalse(is_traditional("zh_CN"))
        self.assertEqual("鏡中之戰", to_traditional("镜中之战"))


if __name__ == "__main__":
    unittest.main()
