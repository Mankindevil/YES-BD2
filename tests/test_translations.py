import gettext
import re
import unittest
from pathlib import Path

from scripts.compile_translations import compile_catalog, read_catalog

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = REPOSITORY_ROOT / "i18n"
LANGUAGES = ("en_US", "ja_JP", "ko_KR", "zh_TW")


def _catalog(language: str) -> Path:
    return CATALOG_ROOT / language / "LC_MESSAGES" / "ok.po"


class TranslationCatalogTests(unittest.TestCase):
    def test_english_catalog_loads_and_translates_project_ui(self):
        translation = gettext.translation("ok", CATALOG_ROOT, languages=["en_US"])

        self.assertEqual("Run All Dailies", translation.gettext("一键完成日常"))
        self.assertEqual("Quick Hunt", translation.gettext("快速狩猎"))
        self.assertEqual("Mirror Wars battle multiplier", translation.gettext("竞技场战斗倍数"))

    def test_game_names_follow_souseha(self):
        # Leo (2026-10-03): game words use the BD2DB (souseha) wording.
        expected = {
            "en_US": {"火晶片": "Firechip", "压制": "Overpower", "香草牛排": "Herb Steak"},
            "ja_JP": {"火晶片": "ファイヤーチップ", "压制": "制圧", "香草牛排": "ハーブステーキ"},
            "ko_KR": {"火晶片": "파이어칩", "压制": "제압", "香草牛排": "허브 스테이크"},
            "zh_TW": {"火晶片": "火片", "御剑传": "劍傳", "美丽无望": "不可能的美麗"},
        }
        for language, words in expected.items():
            translation = gettext.translation("ok", CATALOG_ROOT, languages=[language])
            for source, target in words.items():
                self.assertEqual(target, translation.gettext(source), (language, source))

    def test_templates_keep_their_blanks(self):
        for language in LANGUAGES:
            for msgid, message in read_catalog(_catalog(language)).items():
                self.assertEqual(
                    sorted(re.findall(r"\{[a-z]+\}", msgid)),
                    sorted(re.findall(r"\{[a-z]+\}", message)),
                    (language, msgid),
                )

    def test_compiled_catalog_matches_po_source(self):
        for language in LANGUAGES:
            source = _catalog(language)
            messages = read_catalog(source)

            self.assertTrue(all(message for msgid, message in messages.items() if msgid))
            self.assertEqual(
                compile_catalog(messages), source.with_suffix(".mo").read_bytes(), language
            )


if __name__ == "__main__":
    unittest.main()
