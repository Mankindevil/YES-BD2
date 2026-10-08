import unittest

from src.tasks.fiend_hunt.preflight import check_folder


def files(*turns):
    return {turn: f"t{turn}.png" for turn in turns}


class FolderCheckTest(unittest.TestCase):
    def test_every_turn_there_starts(self):
        checked = check_folder(files(1, 3, 5, 7), [], 1)
        self.assertEqual((), checked.missing)
        self.assertIsNone(checked.problem)

    def test_a_gap_is_said_before_the_fight(self):
        checked = check_folder(files(1, 3, 7, 9), [], 1)
        self.assertEqual((5,), checked.missing)
        self.assertIn("5", checked.problem)

    def test_the_turn_the_game_is_on_must_be_there(self):
        self.assertEqual((1,), check_folder(files(3, 5, 7), [], 1).missing)

    def test_a_fight_picked_up_later_needs_only_the_turns_ahead(self):
        self.assertIsNone(check_folder(files(1, 5, 7), [], 5).problem)

    def test_the_game_past_the_last_screenshot(self):
        self.assertIn("只到第 7 回合", check_folder(files(5, 7), [], 9).problem)

    def test_no_fixed_number_of_turns(self):
        # Leo 2026-10-01: not every boss has 23 turns.
        checked = check_folder(files(1, 3, 5), [], 1)
        self.assertIsNone(checked.problem)
        self.assertIn("第 5 回合为止", checked.summary()[-1])
        self.assertIsNone(check_folder(files(*range(1, 32, 2)), [], 1).problem)

    def test_turns_go_by_two_unless_the_screenshots_go_by_one(self):
        self.assertEqual((3, 7), check_folder(files(1, 5, 9), [], 1).missing)
        self.assertEqual((), check_folder(files(1, 2, 3), [], 1).missing)
        self.assertEqual((3,), check_folder(files(1, 2, 4), [], 1).missing)

    def test_unusable_images_are_listed(self):
        note = "截图 a.png 不是俯视视角（先按「切换视角」再截），跳过"
        checked = check_folder(files(1), [note], None)
        self.assertIsNone(checked.problem)
        self.assertTrue(any("1 张不能用" in line and "a.png" in line for line in checked.summary()))

    def test_unreadable_game_turn_starts_from_the_first_screenshot(self):
        self.assertEqual(3, check_folder(files(3, 5), [], None).start)


if __name__ == "__main__":
    unittest.main()
