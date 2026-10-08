"""The built-in character list and telling skill cards by costume (Leo 2026-10-06)."""

import unittest
from pathlib import Path

from src.tasks.fiend_hunt import costumes, vision
from tests.helpers.recognition_fixtures import load_fhd_bgr

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fiend_hunt"


# by id: souseha rewords costume names now and then (2026-10-08 「纠察队」 became
# 「纪律部」), the ids stay
def ids(found):
    return {row: costume.id for row, costume in found.items()}


class CharacterBookTest(unittest.TestCase):
    def test_every_costume_has_a_portrait(self):
        book = costumes.book()
        every = [costume for group in book.by_character.values() for costume in group]
        self.assertGreater(len(every), 150)
        missing = [
            costume.id
            for costume in every
            if not costume.temporary and costumes.portrait(costume.id) is None
        ]
        self.assertEqual([], missing)

    def test_costumes_by_in_game_name(self):
        book = costumes.book()
        self.assertEqual(
            ["Glacia_1", "Glacia_2", "Glacia_3"],
            [costume.id for costume in book.costumes("克蕾西亚")],
        )
        self.assertEqual((), book.costumes("魔法增幅器ET001"))  # summons have none
        self.assertTrue(book.costume("Glacia_1").skill)

    def test_characters_carry_star_element_and_a_portrait(self):
        book = costumes.book()
        glacia = next(c for c in book.characters if c.name == "克蕾西亚")
        self.assertIn(glacia.star, (3, 4, 5))
        self.assertIn(glacia.element, ("fire", "water", "wind", "light", "dark"))
        self.assertIsNotNone(costumes.picture(glacia.costume))
        self.assertEqual(len(book.by_character), len(book.characters))


class CardCostumeTest(unittest.TestCase):
    """4K and 2K card columns: each unlit, usable skill card shows its costume."""

    def column(self, name, character):
        frame = load_fhd_bgr(FIXTURES / name)
        count, lit = vision.card_count(frame), vision.lit_card(frame)
        return costumes.column_costumes(frame, count, lit, costumes.book().costumes(character))

    def test_three_skill_cards_while_the_attack_is_lit(self):
        found = self.column("cards_t1_attack_lit.png", "克蕾西亚")
        self.assertEqual({2: "Glacia_1", 3: "Glacia_2", 4: "Glacia_3"}, ids(found))

    def test_four_skill_cards(self):
        found = self.column("cards_t13_four_skills.png", "鲁")
        self.assertEqual({2: "Rou_1", 3: "Rou_2", 4: "Rou_3", 5: "Rou_4"}, ids(found))

    def test_knockback_lit(self):
        found = self.column("cards_t1_knockback_lit.png", "班塔纳")
        self.assertEqual({2: "Ventana_1", 3: "Ventana_2", 4: "Ventana_3"}, ids(found))

    def test_the_lit_card_is_left_out(self):
        # 马莫尼勒 on her 2nd skill: the lit card's art isn't the portrait's.
        found = self.column("cards_t1_skill_lit.png", "马莫尼勒")
        self.assertEqual({2: "Mamonir_1"}, ids(found))

    def test_a_card_on_cooldown_is_told_in_grey(self):
        # 2K: 帕莱特's 1st skill on cooldown (dimmed), the 2nd lit.
        self.assertEqual({2: "Palette_1"}, ids(self.column("cards_2k_t19_palette.png", "帕莱特")))
        # 4K: her 2nd skill greyed on cooldown, the attack lit
        found = self.column("cards_t21_bright_skill_art.png", "帕莱特")
        self.assertEqual({2: "Palette_1", 3: "Palette_2"}, ids(found))

    def test_cards_greyed_by_preempt_are_told_in_grey(self):
        found = self.column("cards_t13_preempt_on.png", "格兰希特")
        self.assertEqual(
            {2: "Granhildr_1", 3: "Granhildr_2", 4: "Granhildr_3", 5: "Granhildr_4"}, ids(found)
        )

    def test_another_characters_costumes_are_never_taken(self):
        found = self.column("cards_t1_attack_lit.png", "鲁")
        self.assertEqual({}, found)


class TemporaryCostumeTest(unittest.TestCase):
    """A costume only the official notice has (no portrait yet, Leo 2026-10-07),
    on 克蕾西亚's real card column: 爱丽丝, 纠察队, 天守传人 with 天守传人 new."""

    def setUp(self):
        self.frame = load_fhd_bgr(FIXTURES / "cards_t1_attack_lit.png")
        self.count, self.lit = vision.card_count(self.frame), vision.lit_card(self.frame)
        known = costumes.book().costumes("克蕾西亚")
        self.alice, self.patrol = known[0], known[1]
        self.new = costumes.Costume("official_Claasia_x", "克蕾西亚", "新服装", temporary=True)

    def column(self, wardrobe):
        return costumes.column_costumes(self.frame, self.count, self.lit, tuple(wardrobe))

    def test_the_card_left_is_the_new_costume(self):
        found = self.column([self.alice, self.patrol, self.new])
        self.assertEqual({2: "Glacia_1", 3: "Glacia_2", 4: "official_Claasia_x"}, ids(found))

    def test_more_costumes_than_cards_guesses_nothing(self):
        # she owns a 4th costume not on the cards: the new card stays unread
        other = costumes.book().costumes("鲁")[0]
        found = self.column([self.alice, self.patrol, other, self.new])
        self.assertEqual({2: "Glacia_1", 3: "Glacia_2"}, ids(found))

    def test_without_the_notice_the_new_card_could_be_taken_for_another(self):
        # why the notice's costume is added: with it missing, the counts
        # match and the new card would be named after the costume left
        other = costumes.book().costumes("鲁")[0]
        found = self.column([self.alice, self.patrol, other])
        self.assertEqual(other.name, found[4].name)

    def test_picture_falls_back_to_the_original_costume(self):
        book = costumes.book()
        character = next(c for c in book.characters if c.name == "内肯达莉亚")
        new = next(c for c in book.costumes("内肯达莉亚") if c.temporary)
        self.assertEqual(character.costume, book.picture_id("内肯达莉亚", new.id))

    def test_an_alias_finds_the_costume_that_replaced_it(self):
        book = costumes.CharacterBook(
            {"克蕾西亚": (self.alice,)}, aliases={"official_Claasia_x": self.alice.id}
        )
        self.assertEqual(self.alice, book.costume("official_Claasia_x"))
        self.assertEqual(self.alice.id, book.canonical("official_Claasia_x"))


if __name__ == "__main__":
    unittest.main()


class SkillNameTest(unittest.TestCase):
    def test_level_word_and_plus_are_ignored(self):
        found = costumes.costume_by_skill("特级三重箭矢+5", costumes.book().costumes("艾尼尔"))
        self.assertEqual("Eleaneer_1", found.id)

    def test_punctuation_and_a_slipped_glyph(self):
        palette = costumes.book().costumes("帕莱特")
        self.assertEqual("Palette_2", costumes.costume_by_skill("紫罗兰极限突袭", palette).id)
        self.assertEqual("Palette_1", costumes.costume_by_skill("让你见识真正的杰做", palette).id)

    def test_nothing_or_another_characters_skill(self):
        eleaneer = costumes.book().costumes("艾尼尔")
        self.assertIsNone(costumes.costume_by_skill("", eleaneer))
        self.assertIsNone(costumes.costume_by_skill("紫罗兰☆极限突袭", eleaneer))


try:
    from onnxocr.onnx_paddleocr import ONNXPaddleOcr
except ImportError:  # pragma: no cover - the tool always ships onnxocr
    ONNXPaddleOcr = None


@unittest.skipIf(ONNXPaddleOcr is None, "onnxocr not installed")
class LitSkillTest(unittest.TestCase):
    """Leo 2026-10-06: the lit card's art changes, its name in the header doesn't."""

    def test_header_names_the_lit_costume(self):
        engine = ONNXPaddleOcr(use_angle_cls=False, use_openvino=True)

        def ocr(image):
            return [line[1][0] for line in (engine.ocr(image)[0] or [])]

        frame = load_fhd_bgr(FIXTURES / "cards_4k_eleaneer_skill1_lit.png")
        self.assertEqual(2, vision.lit_card(frame))
        text = vision.read_skill_name(frame, ocr)
        found = costumes.costume_by_skill(text, costumes.book().costumes("艾尼尔"))
        self.assertEqual("Eleaneer_1", found.id)
        # and the other two cards by their art
        others = costumes.column_costumes(
            frame, vision.card_count(frame), 2, costumes.book().costumes("艾尼尔")
        )
        self.assertEqual({3: "Eleaneer_2", 4: "Eleaneer_3"}, ids(others))

    def test_headers_from_a_fight_video(self):
        # Leo's bilibili screenshots (2026-10-06), a 4K fight scaled down:
        # the level word in front, a ☆ inside the name.
        engine = ONNXPaddleOcr(use_angle_cls=False, use_openvino=True)

        def ocr(image):
            return [line[1][0] for line in (engine.ocr(image)[0] or [])]

        for fixture, unit, costume in (
            ("header_video_mamonir_ocean.png", "马莫尼勒", "Mamonir_2"),
            ("header_video_diana_element.png", "黛安娜", "Diana_1"),
        ):
            with self.subTest(unit=unit):
                text = vision.read_skill_name(load_fhd_bgr(FIXTURES / fixture), ocr)
                found = costumes.costume_by_skill(text, costumes.book().costumes(unit))
                self.assertEqual(costume, found.id if found else None)

    def test_no_name_with_the_attack_lit(self):
        frame = load_fhd_bgr(FIXTURES / "cards_4k_eleaneer_attack_lit.png")
        found = costumes.column_costumes(
            frame,
            vision.card_count(frame),
            vision.lit_card(frame),
            costumes.book().costumes("艾尼尔"),
        )
        self.assertEqual({2: "Eleaneer_1", 3: "Eleaneer_2", 4: "Eleaneer_3"}, ids(found))


class LearnCostumesTest(unittest.TestCase):
    """While recording, each unit's cards are told once and the lit one by name."""

    def screen(self, header=""):
        from types import SimpleNamespace

        from src.tasks.fiend_hunt.screen import GameFightScreen

        return GameFightScreen(
            SimpleNamespace(),
            ["艾尼尔"],
            screen_input=SimpleNamespace(),
            capture=lambda: None,
            ocr=lambda image: [header] if header else [],
            sleep=lambda seconds: None,
        )

    def column(self, name):
        frame = load_fhd_bgr(FIXTURES / name)
        return frame, vision.card_count(frame), vision.lit_card(frame)

    def test_attack_lit_teaches_every_skill_card(self):
        screen = self.screen()
        worn = screen._learn_costumes("艾尼尔", self.column("cards_4k_eleaneer_attack_lit.png"))
        self.assertIsNone(worn)
        self.assertEqual(
            {"技能1": "Eleaneer_1", "技能2": "Eleaneer_2", "技能3": "Eleaneer_3"},
            screen.unit_cards["艾尼尔"],
        )

    def test_lit_skill_is_told_by_its_name(self):
        screen = self.screen("特级三重箭矢")
        worn = screen._learn_costumes("艾尼尔", self.column("cards_4k_eleaneer_skill1_lit.png"))
        self.assertEqual("Eleaneer_1", worn)
        self.assertEqual("Eleaneer_1", screen.unit_cards["艾尼尔"]["技能1"])

    def test_unreadable_name_is_the_one_costume_left(self):
        # 艾尼尔 has 3 costumes and 3 skill cards: the other two told by art.
        screen = self.screen()
        worn = screen._learn_costumes("艾尼尔", self.column("cards_4k_eleaneer_skill1_lit.png"))
        self.assertEqual("Eleaneer_1", worn)
        self.assertEqual("Eleaneer_1", screen.unit_cards["艾尼尔"]["技能1"])

    def test_unreadable_name_falls_back_to_what_was_learned(self):
        screen = self.screen()
        screen.unit_cards["艾尼尔"] = {"技能1": "Eleaneer_1"}
        worn = screen._learn_costumes("艾尼尔", self.column("cards_4k_eleaneer_skill1_lit.png"))
        self.assertEqual("Eleaneer_1", worn)

    def test_units_the_list_lacks_are_left_alone(self):
        screen = self.screen("特级三重箭矢")
        frame = self.column("cards_4k_eleaneer_skill1_lit.png")
        self.assertIsNone(screen._learn_costumes("魔法增幅器ET001", frame))
        self.assertNotIn("魔法增幅器ET001", screen.unit_cards)


class RecordingCostumesTest(unittest.TestCase):
    def test_a_card_told_later_fills_earlier_turns(self):
        from src.tasks.fiend_hunt.record import TurnState
        from src.tasks.fiend_hunt.recording import _merged_cards, _with_costumes

        cells = {"艾尼尔": (2, 1)}
        turns = {
            1: TurnState(1, 1, ("艾尼尔",), cells, skills={"艾尼尔": "技能2"}),
            3: TurnState(3, 1, ("艾尼尔",), cells, skills={"艾尼尔": "攻击"}),
        }
        cards = _merged_cards({}, {"艾尼尔": {"技能2": "Eleaneer_2"}})
        filled = _with_costumes(turns, cards)
        self.assertEqual({"艾尼尔": "Eleaneer_2"}, filled[1].costumes)
        self.assertEqual({}, filled[3].costumes)

    def test_newer_sightings_win(self):
        from src.tasks.fiend_hunt.recording import _merged_cards

        merged = _merged_cards(
            {"艾尼尔": {"技能1": "Eleaneer_2"}}, {"艾尼尔": {"技能2": "Eleaneer_2"}}
        )
        self.assertEqual({"艾尼尔": {"技能2": "Eleaneer_2"}}, merged)
