import importlib.util
import unittest

from src.tasks.fiend_hunt.names import settle_name, snap_name

TEAM = ["克蕾西亚", "马莫尼勒", "艾尼尔", "杰尼斯", "班塔纳"]


class SnapNameTest(unittest.TestCase):
    def test_exact_name(self):
        self.assertEqual("杰尼斯", snap_name("杰尼斯", TEAM))

    def test_spaces_and_dots_are_ignored(self):
        self.assertEqual("马莫尼勒", snap_name(" 马莫·尼勒 ", TEAM))

    def test_costume_title_next_to_the_name(self):
        self.assertEqual("克蕾西亚", snap_name("天守继承者 克蕾西亚", TEAM))

    def test_one_wrong_character_is_forgiven(self):
        self.assertEqual("克蕾西亚", snap_name("克蕾西垭", TEAM))

    def test_unknown_name_is_not_forced(self):
        self.assertIsNone(snap_name("黛安娜", TEAM))
        self.assertIsNone(snap_name("", TEAM))
        self.assertIsNone(snap_name("尼", TEAM))

    def test_close_call_between_two_names_is_refused(self):
        self.assertIsNone(snap_name("艾尼斯", ["艾尼尔", "杰尼斯"]))

    def test_longest_name_inside_wins(self):
        self.assertEqual("艾尼尔二", snap_name("艾尼尔二", ["艾尼尔", "艾尼尔二"]))
        self.assertEqual("艾尼尔二", snap_name("X艾尼尔二", ["艾尼尔", "艾尼尔二"]))

    @unittest.skipUnless(importlib.util.find_spec("opencc"), "opencc not installed")
    def test_traditional_name_matches_the_simplified_client(self):
        self.assertEqual("马莫尼勒", snap_name("馬莫尼勒", TEAM))


class SettleNameTest(unittest.TestCase):
    def reads(self, *texts):
        self.taken = []
        for text in texts:
            self.taken.append(text)
            yield text

    def test_known_name_settles_on_the_first_read(self):
        self.assertEqual("艾尼尔", settle_name(self.reads("艾尼尔", "never read"), TEAM))
        self.assertEqual(["艾尼尔"], self.taken)

    def test_new_character_is_taken_when_two_reads_agree(self):
        self.assertEqual("黛安娜", settle_name(self.reads("黛安娜", " 黛安娜", "x"), TEAM))
        self.assertEqual(2, len(self.taken))

    def test_one_letter_name_is_taken_too(self):
        self.assertEqual("鲁", settle_name(self.reads("鲁", "鲁"), TEAM))

    def test_reads_that_disagree_settle_nothing(self):
        self.assertIsNone(settle_name(self.reads("黛安娜", "黛安那", "黛安娜"), TEAM))

    def test_agreement_must_be_in_a_row(self):
        self.assertEqual("黛安娜", settle_name(self.reads("黛安", "黛安娜", "黛安娜"), TEAM))
        self.assertIsNone(settle_name(self.reads("黛安娜", "", "黛安娜"), TEAM))

    def test_garbage_is_never_a_name(self):
        self.assertIsNone(settle_name(self.reads("12", "12", "Lv25", "Lv25"), TEAM))
        self.assertIsNone(settle_name(self.reads("", ""), TEAM))
        self.assertIsNone(
            settle_name(
                self.reads("长长长长长长长长长长长长长", "长长长长长长长长长长长长长"), TEAM
            )
        )

    def test_new_name_holding_a_short_known_one_stays_new(self):
        known = [*TEAM, "鲁"]
        self.assertEqual("鲁卡斯", settle_name(self.reads("鲁卡斯", "鲁卡斯"), known))

    def test_known_name_is_preferred_to_a_new_one(self):
        self.assertEqual("克蕾西亚", settle_name(self.reads("克蕾西垭", "克蕾西垭"), TEAM))


if __name__ == "__main__":
    unittest.main()
