"""The character list's upkeep: official notices first, souseha later (Leo 2026-10-07)."""

import copy
import unittest
from datetime import date

from src.tasks.fiend_hunt import character_pool as pool

# Copied from the 2026-10-06 zh-tw notice (10月 8日（四）定期維護), shortened.
NOTICE_TW = (
    "20. 爆發技能新增時裝說明21. PICK UP及新角色介紹"
    "1) 殘破木乃伊涅肯達莉亞的服裝和涅肯達莉亞的專用裝備“雪白遺骸”將出現在本次Pickup中。"
    "- 殘破木乃伊涅肯達莉亞的服裝：2026年 10月 8日（四）維護後 ~ 2026年 10月 22日（四）維護前可獲得"
    "3) 大魔女的後裔西利亞的服裝和西利亞的專用裝備“泰拉遮瑕膏“將出現在本次Pickup中"
    "5) 【復刻】軟萌兔女郎提爾的服裝和提爾的專用裝備“布里歐納克“將出現在本次Pickup中"
    "7) 無名新人的服裝和無名的專用裝備“某物“將出現在本次Pickup中"
)
# The same maintenance in the other languages (copied, shortened).
TEXTS = {
    "zh_cn": "21. Pick Up及新增角色说明-「残破木乃伊内肯达莉亚」服装及内肯达莉亚的专属装备"
    "「莱夫科斯遗骸」将加入Pick Up。1）「残破木乃伊 内肯达莉亚」服装：2026年 10月 8日",
    "en": "21. Pickup and New Character Information- Unraveling Mummy Nekyndalia Costume and "
    "Nekyndalia's Exclusive Gear, Leukos Leipsana will be available for Pickup."
    "1) Unraveling Mummy Nekyndalia Costume: After the October 7 maintenance",
    "ja": "21. ピックアップ及び新規キャラクターのご案内"
    "コスチューム「ゆるゆるミイラ ネケンダリア」と"
    "専用装備「レウコス・リプサナ」がピックアップに登場します。",
    "ko": "21. 픽업 및 신규 캐릭터 안내- 헐거운 미라 네켄달리아 코스튬과 네켄달리아의 전용 장비 "
    "레프코스 립사나가 픽업에 등장합니다.1) 헐거운 미라 네켄달리아 코스튬 : 2026년 10월 8일",
}


def character(cid, tw, cn, en, ja, ko, costumes):
    return {
        "id": cid,
        "name_zh_tw": tw,
        "name_zh_cn": cn,
        "name_en": en,
        "name_ja": ja,
        "name_ko": ko,
        "costumes": costumes,
    }


def costume(cid, tw, **more):
    return {"id": cid, "name_zh_tw": tw, "name_zh_cn": tw, **more}


def listing():
    return {
        "characters": [
            character(
                "Nekyndalia",
                "涅肯達莉亞",
                "内肯达莉亚",
                "Nekyndalia",
                "ネケンダリア",
                "네켄달리아",
                [costume("Nekyndalia_1", "致命之眼", name_en="Deadeye")],
            ),
            character(
                "Celia",
                "西利亞",
                "西利亚",
                "Celia",
                "セリア",
                "셀리아",
                [costume("Celia_1", "詛咒之星"), costume("Celia_2", "大魔女的後裔")],
            ),
            character(
                "Tyr",
                "提爾",
                "提尔",
                "Tyr",
                "ティル",
                "티르",
                [costume("Tyr_1", "星光守護者")],
            ),
        ]
    }


class NoticeTest(unittest.TestCase):
    def test_pickup_sentences(self):
        self.assertEqual(
            [
                ("殘破木乃伊涅肯達莉亞", False),
                ("大魔女的後裔西利亞", False),
                ("軟萌兔女郎提爾", True),
                ("無名新人", False),
            ],
            pool.pickups(NOTICE_TW),
        )

    def test_maintenance_subjects(self):
        self.assertTrue(pool.is_maintenance(" 📢 10月 8日（四）定期維護"))
        self.assertTrue(pool.is_maintenance("📢 7月 16日（四）定期維護和更新(修改)"))
        self.assertFalse(pool.is_maintenance("📢 9月23日（三））例行維護補償說明"))
        self.assertFalse(pool.is_maintenance("10月 1日（四）無維護更新內容"))

    def test_only_the_new_costume_is_added(self):
        data = listing()
        report = pool.add_from_notice(
            data, "N1", date(2026, 10, 6), NOTICE_TW, TEXTS, simplify=lambda text: "简" + text
        )
        # 西利亞's is listed, 提爾's is a rerun, 無名 isn't a character the list has
        self.assertEqual(["涅肯達莉亞 殘破木乃伊", "?無名新人"], report)
        added = data["characters"][0]["costumes"][-1]
        self.assertTrue(added["temporary"])
        self.assertEqual(pool.temporary_id("Nekyndalia", "殘破木乃伊"), added["id"])
        self.assertEqual(
            ("殘破木乃伊", "残破木乃伊", "Unraveling Mummy", "ゆるゆるミイラ", "헐거운 미라"),
            tuple(added[f"name_{lang}"] for lang in pool.LANGS),
        )
        self.assertEqual(("", [], []), (added["skill_zh_cn"], added["sp"], added["burst_sp"]))
        self.assertEqual(1, len(data["characters"][1]["costumes"]) - 1)  # 西利亞 unchanged
        self.assertEqual(1, len(data["characters"][2]["costumes"]))  # 提爾 unchanged

    def test_running_twice_adds_once(self):
        data = listing()
        pool.add_from_notice(data, "N1", date(2026, 10, 6), NOTICE_TW, TEXTS)
        again = pool.add_from_notice(data, "N1", date(2026, 10, 6), NOTICE_TW, TEXTS)
        self.assertEqual(["?無名新人"], again)
        self.assertEqual(2, len(data["characters"][0]["costumes"]))

    def test_a_name_written_differently_is_the_same_costume(self):
        # 2026-04-09: the notice wrote 潛藏之夢, souseha 潛藏的夢
        entry = {"costumes": [costume("Sonya_1", "潛藏的夢")]}
        self.assertTrue(pool.known_costume(entry, "潛藏之夢"))
        self.assertFalse(pool.known_costume(entry, "賣南瓜的少女"))

    def test_nothing_added_when_souseha_just_added_one(self):
        # 2026-08-13: the notice wrote 客棧暖陽, souseha 客棧的陽光 (added that week)
        data = listing()
        data["characters"][0]["costumes"].append(
            costume("Nekyndalia_2", "別的名字", added="2026-10-05")
        )
        report = pool.add_from_notice(data, "N1", date(2026, 10, 6), NOTICE_TW, TEXTS)
        self.assertEqual(["?無名新人"], report)

    def test_missing_languages_stay_empty(self):
        data = listing()
        pool.add_from_notice(
            data, "N1", date(2026, 10, 6), NOTICE_TW, {}, simplify=lambda text: "简" + text
        )
        added = data["characters"][0]["costumes"][-1]
        self.assertEqual("简殘破木乃伊", added["name_zh_cn"])  # converted from zh-tw
        self.assertEqual(("", "", ""), (added["name_en"], added["name_ja"], added["name_ko"]))

    def test_an_old_costume_in_the_same_notice_is_not_taken(self):
        text = (
            "Pickup and New Character Information- 1) Deadeye Nekyndalia Costume: rerun. "
            "2) Unraveling Mummy Nekyndalia Costume: After"
        )
        self.assertEqual(
            "Unraveling Mummy",
            pool.costume_name(text, "en", "Nekyndalia", ["Deadeye"]),
        )


class SousehaMergeTest(unittest.TestCase):
    def old_with_temporary(self):
        data = listing()
        pool.add_from_notice(data, "N1", date(2026, 10, 6), NOTICE_TW, TEXTS)
        return data

    def test_temporary_kept_until_souseha_lists_it(self):
        old = self.old_with_temporary()
        new = copy.deepcopy(listing())
        self.assertEqual([], pool.merge_souseha(old, new, date(2026, 10, 9)))
        ids = [c["id"] for c in new["characters"][0]["costumes"]]
        self.assertEqual(["Nekyndalia_1", pool.temporary_id("Nekyndalia", "殘破木乃伊")], ids)
        self.assertNotIn("aliases", new)
        # nothing changed: the same file as before
        self.assertEqual(old, new)

    def test_souseha_entry_replaces_it_and_saves_still_find_it(self):
        old = self.old_with_temporary()
        new = copy.deepcopy(listing())
        new["characters"][0]["costumes"].append(costume("Nekyndalia_2", "白縷輕纏木乃伊"))
        report = pool.merge_souseha(old, new, date(2026, 10, 9))
        self.assertEqual(["涅肯達莉亞 殘破木乃伊 → 白縷輕纏木乃伊"], report)
        ids = [c["id"] for c in new["characters"][0]["costumes"]]
        self.assertEqual(["Nekyndalia_1", "Nekyndalia_2"], ids)
        self.assertEqual(
            {pool.temporary_id("Nekyndalia", "殘破木乃伊"): "Nekyndalia_2"}, new["aliases"]
        )
        self.assertEqual("2026-10-09", new["characters"][0]["costumes"][1]["added"])

    def test_first_seen_dates_are_kept(self):
        old = listing()
        old["characters"][0]["costumes"][0]["added"] = "2026-06-04"
        new = copy.deepcopy(listing())
        pool.merge_souseha(old, new, date(2026, 10, 9))
        self.assertEqual("2026-06-04", new["characters"][0]["costumes"][0]["added"])
        self.assertNotIn("added", new["characters"][1]["costumes"][0])  # before dates were kept

    def test_several_new_ones_go_by_name(self):
        old = self.old_with_temporary()
        new = copy.deepcopy(listing())
        new["characters"][0]["costumes"] += [
            costume("Nekyndalia_2", "泳裝", name_en="Swimsuit"),
            costume("Nekyndalia_3", "殘破的木乃伊", name_en="Unraveling Mummy"),
        ]
        pool.merge_souseha(old, new, date(2026, 10, 9))
        self.assertEqual(
            "Nekyndalia_3", new["aliases"][pool.temporary_id("Nekyndalia", "殘破木乃伊")]
        )


if __name__ == "__main__":
    unittest.main()
