"""Character cartridges (角色游戏卡) in the weekly map run (Leo 2026-09-30)."""

import unittest
from types import SimpleNamespace

import numpy as np

from src.tasks.map_trade.collector import chapter_filter
from src.tasks.map_trade.models import CARD_BY_ID, COLLECTABLE_CARDS, CollectionMapRole
from src.tasks.map_trade.navigator import Navigator
from src.tasks.map_trade.navigator_constants import (
    CHARACTER_CATEGORY_HIGHLIGHT_REGION,
    CHARACTER_CATEGORY_POINT,
    STORY_CATEGORY_HIGHLIGHT_REGION,
    STORY_CATEGORY_POINT,
)
from src.tasks.map_trade.vision import normalize_text


class CharacterCardModelTest(unittest.TestCase):
    def test_cards_one_to_seven_are_collected(self):
        # Card 3 added 2026-10-03; 8-10 carry no 吸取/压制 badges.
        characters = [card for card in COLLECTABLE_CARDS if card.category == "character"]

        self.assertEqual([1, 2, 3, 4, 5, 6, 7], [card.number for card in characters])
        self.assertTrue(CARD_BY_ID["Q_cp3"].collectable)
        self.assertEqual("角色卡5", CARD_BY_ID["Q_cp5"].label)
        self.assertEqual("第14章", CARD_BY_ID["Q_sp14"].label)

    def test_first_safe_map_then_up_to_two_battle_maps(self):
        main, battle_1 = CollectionMapRole.MAIN_AREA, CollectionMapRole.BATTLE_AREA_1
        battle_2 = CollectionMapRole.BATTLE_AREA_2
        expected = {
            1: ((main, "学校1楼"), (battle_1, "学校地下")),
            2: (
                (main, "避难所166"),
                (battle_1, "废墟地道（前段）"),
                (battle_2, "废墟地道（后段）"),
            ),
            3: ((main, "上流社会派对会场"), (battle_1, "地下秘密拍卖场"), (battle_2, "禁闭室")),
            4: ((main, "商场4楼"), (battle_1, "商场3楼"), (battle_2, "商场2楼")),
            5: ((main, "童话镇"), (battle_1, "魔女居林")),
            6: ((main, "西风镇"), (battle_1, "西风竹林"), (battle_2, "妖怪森林")),
            7: ((main, "凯那尔工业1楼"), (battle_1, "卡勒塔市")),
        }
        for number, targets in expected.items():
            with self.subTest(number=number):
                card = CARD_BY_ID[f"Q_cp{number}"]
                self.assertEqual(targets, tuple((t.role, t.title) for t in card.targets))

    def test_card_three_walks_to_its_cell_and_restarts_via_eileen(self):
        from src.tasks.map_trade.models import (
            RESTART_NAV_ENTRIES,
            RESUMING_WALK_CARD_IDS,
            TOWN_NAV_ENTRIES,
            WALK_LABEL_EDGES,
        )

        self.assertIn(("Q_cp3", "battle_area_1", "battle_area_2"), WALK_LABEL_EDGES)
        self.assertIn(("Q_cp3", "battle_area_2", "battle_area_1"), WALK_LABEL_EDGES)
        self.assertEqual("艾琳", TOWN_NAV_ENTRIES["Q_cp3"])
        self.assertEqual("艾琳", RESTART_NAV_ENTRIES["Q_cp3"])
        # Only card 3 leaves a patrol catch alone; ch14 keeps its ✕ handling.
        self.assertEqual(frozenset({"Q_cp3"}), RESUMING_WALK_CARD_IDS)

    def test_filter_takes_chapters_and_character_cards(self):
        self.assertEqual({14, "R1"}, chapter_filter("14、R1"))
        self.assertEqual({f"R{n}" for n in range(1, 8)}, chapter_filter("R1-R7"))
        self.assertEqual({"R2"}, chapter_filter("r2"))
        self.assertEqual({8, 9, 10}, chapter_filter("8-10"))
        self.assertIsNone(chapter_filter("全部"))
        self.assertEqual("R4", CARD_BY_ID["Q_cp4"].filter_key)
        self.assertEqual(4, CARD_BY_ID["Q_sp4"].filter_key)


class CharacterMapTitleTest(unittest.TestCase):
    def test_a_longer_map_name_is_not_its_prefix(self):
        card = CARD_BY_ID["Q_cp5"]

        self.assertEqual(
            ("main_area",), Navigator._target_keys_in_text(card, normalize_text("安全 童话镇 普通"))
        )
        self.assertEqual(
            (), Navigator._target_keys_in_text(card, normalize_text("安全 童话镇旅馆 普通"))
        )

    def test_parentheses_misread_by_ocr_still_name_the_map(self):
        # Live 2K: "废墟地道（前段）" read "废墟地道道前段", "（后段）" "直后段".
        card = CARD_BY_ID["Q_cp2"]

        self.assertEqual(
            ("battle_area_1",),
            Navigator._target_keys_in_text(card, normalize_text("战斗废墟地道道前段s出现风属性怪物")),
        )
        self.assertEqual(
            ("battle_area_2",),
            Navigator._target_keys_in_text(card, normalize_text("战斗废墟地道直后段s出现风属性怪物")),
        )


class CharacterTabTest(unittest.TestCase):
    def _navigator(self, highlight):
        clicks = []
        vision = SimpleNamespace(
            capture=lambda: np.zeros((1080, 1920, 3), np.uint8),
            ocr_text=lambda _frame, _name: "最近 店长游戏卡 剧情游戏卡 角色游戏卡",
            simplify=lambda text: text,
            bright_neutral_ratio=lambda _frame, region: highlight.get(region, 0.0),
        )
        task = SimpleNamespace(
            operate_click=lambda x, y, after_sleep=0: clicks.append((x, y)),
            sleep=lambda *_args: None,
            log_warning=lambda *_args: None,
        )
        return Navigator(task, vision), clicks

    def test_character_tab_is_clicked_and_confirmed_by_its_own_highlight(self):
        navigator, clicks = self._navigator({CHARACTER_CATEGORY_HIGHLIGHT_REGION: 0.084})

        self.assertTrue(navigator._select_story_category("character"))
        self.assertEqual([CHARACTER_CATEGORY_POINT], clicks)

    def test_story_highlight_does_not_confirm_the_character_tab(self):
        navigator, _clicks = self._navigator({STORY_CATEGORY_HIGHLIGHT_REGION: 0.079})

        self.assertFalse(
            navigator._wait_for_story_category(timeout=0.2, category="character", warn=False)
        )
        self.assertTrue(navigator._wait_for_story_category(timeout=0.2))
        self.assertEqual((725 / 1920, 877 / 1080), CHARACTER_CATEGORY_POINT)
        self.assertNotEqual(STORY_CATEGORY_POINT, CHARACTER_CATEGORY_POINT)


if __name__ == "__main__":
    unittest.main()
