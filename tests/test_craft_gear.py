import unittest
from types import SimpleNamespace

from src.tasks.CraftGearTask import is_n_recipe, n_first_cell, parse_craft_result


def ocr(text, cx, cy, width=30, height=30):
    return SimpleNamespace(
        name=text, x=cx - width / 2, y=cy - height / 2, width=width, height=height
    )


class CraftListTest(unittest.TestCase):
    # Section headers read from the live 装备制作 list, 2026-09-26.
    def test_first_n_cell_below_the_n_header(self):
        boxes = [ocr("SR", 742, 177), ocr("R", 735, 478), ocr("G", 754, 129), ocr("N", 736, 778)]
        self.assertEqual((780, 863), n_first_cell(boxes))

    def test_no_n_header_or_header_at_the_bottom_edge(self):
        self.assertIsNone(n_first_cell([ocr("SR", 742, 177), ocr("R", 735, 478)]))
        self.assertIsNone(n_first_cell([ocr("N", 736, 1000)]))


class RecipeTitleTest(unittest.TestCase):
    def test_n_recipe_split_or_joined(self):
        self.assertTrue(is_n_recipe([ocr("佣兵剑", 306, 104), ocr("N", 246, 103)]))
        self.assertTrue(is_n_recipe([ocr("N佣兵剑?", 303, 101)]))

    def test_other_rarities_are_refused(self):
        self.assertFalse(is_n_recipe([ocr("R", 246, 103), ocr("骑士剑", 306, 104)]))
        self.assertFalse(is_n_recipe([ocr("UR", 246, 103)]))
        self.assertFalse(is_n_recipe([]))

    def test_only_the_title_line_counts(self):
        # Wider crop (live): the slot line 武器 and 拥有0个 sit below the title.
        boxes = [ocr("N", 245, 103), ocr("佣兵剑", 308, 104), ocr("武器", 272, 140)]
        self.assertTrue(is_n_recipe(boxes))
        self.assertFalse(is_n_recipe([ocr("佣兵剑", 308, 104), ocr("N", 200, 176)]))


class CraftResultTest(unittest.TestCase):
    def test_live_result_text(self):
        text = (
            "强化结果 尝试强化制作的1个装备中的1个 "
            "已分解在制作的1个装备中，已达到目标强化值的1个装备。 精炼粉末×8 分解结果"
        )
        self.assertEqual((1, 1), parse_craft_result(text))
        self.assertIsNone(parse_craft_result("强化结果"))


class DialogRowTest(unittest.TestCase):
    # Row reads from the live 强化设置 dialog, 2026-09-26.
    def test_number_under_the_label(self):
        from src.tasks.enhance_dialog import row_number

        self.assertEqual(
            4, row_number([ocr("单个目标强化值", 669, 338), ocr("4", 607, 369)], "单个目标强化值")
        )
        self.assertEqual(
            3, row_number([ocr("装备制作数量", 664, 575), ocr("3", 607, 610)], "装备制作数量")
        )

    def test_missing_label_or_unclear_number(self):
        from src.tasks.enhance_dialog import row_number

        self.assertIsNone(row_number([ocr("4", 607, 369)], "单个目标强化值"))
        self.assertIsNone(
            row_number([ocr("单个目标强化值", 669, 338), ocr("A", 607, 369)], "单个目标强化值")
        )
        self.assertIsNone(
            row_number(
                [ocr("装备制作数量", 664, 575), ocr("1", 607, 610), ocr("135", 651, 646)],
                "装备制作数量",
            )
        )


if __name__ == "__main__":
    unittest.main()


class CraftCancelTest(unittest.TestCase):
    def _task(self, texts):
        from src.tasks.CraftGearTask import CraftGearTask

        task = object.__new__(CraftGearTask)
        task.log_warning = lambda *a, **k: None
        task.clicks = []
        task._click_reference = lambda x, y, after_sleep=0: task.clicks.append((x, y))
        reads = iter(texts)
        task._dialog_text = lambda: next(reads)
        return task

    def test_second_cancel_only_while_the_dialog_is_open(self):
        task = self._task(["", "强化设置"])
        self.assertTrue(task._cancel_settings())
        self.assertEqual(1, len(task.clicks))

    def test_reports_a_dialog_that_stays(self):
        task = self._task(["强化设置 单个目标强化值"] * 2)
        self.assertFalse(task._cancel_settings())
        self.assertEqual(2, len(task.clicks))


class CraftSettingRangeTest(unittest.TestCase):
    def _task(self, config):
        from src.tasks.CraftGearTask import CraftGearTask

        task = object.__new__(CraftGearTask)
        task.config = dict(config)
        task.config_type = {
            "强化目标等级": {"min": 1, "max": 9},
            "制作数量": {"min": 1, "max": 10},
        }
        task.logs = []
        task.log_info = lambda message, **k: task.logs.append(message)
        return task

    def test_values_in_range_are_kept(self):
        task = self._task({"强化目标等级": 5, "制作数量": 10})
        self.assertEqual(5, task._setting_in_range("强化目标等级", 5))
        self.assertEqual(10, task._setting_in_range("制作数量", 1))
        self.assertEqual([], task.logs)

    def test_saved_value_out_of_range_is_pulled_back_and_saved(self):
        # Live 4K 2026-10-06: a stray saved value failed the weekly craft at once.
        task = self._task({"强化目标等级": 12, "制作数量": 0})
        self.assertEqual(9, task._setting_in_range("强化目标等级", 5))
        self.assertEqual(1, task._setting_in_range("制作数量", 1))
        self.assertEqual({"强化目标等级": 9, "制作数量": 1}, task.config)
        self.assertEqual(2, len(task.logs))

    def test_unreadable_or_missing_value_uses_the_default(self):
        task = self._task({"制作数量": "abc"})
        self.assertEqual(1, task._setting_in_range("制作数量", 1))
        self.assertEqual(5, task._setting_in_range("强化目标等级", 5))
        self.assertEqual({"制作数量": 1}, task.config)
