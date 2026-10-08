import unittest

from src.tasks.fiend_hunt.planner import apply_drags, apply_order_swaps
from src.tasks.fiend_hunt.record import TurnState
from src.tasks.fiend_hunt.turn_plan import TurnMismatch, action_matches, pick_order, plan_turn

ORDER = ("克蕾西亚", "马莫尼勒", "艾尼尔", "杰尼斯", "班塔纳")
START = {
    "克蕾西亚": (2, 0),
    "马莫尼勒": (1, 3),
    "艾尼尔": (2, 1),
    "杰尼斯": (2, 2),
    "班塔纳": (2, 3),
}


def state(cells=START, order=ORDER, turn=1, team=1, dead=(), skills=None):
    return TurnState(turn=turn, team=team, order=order, cells=cells, dead=dead, skills=skills or {})


class PlanTurnTest(unittest.TestCase):
    def test_matching_screen_is_ready(self):
        actions = plan_turn(state(), state())
        self.assertTrue(actions.ready)

    def test_moves_units_and_fixes_the_order(self):
        saved_cells = {
            "克蕾西亚": (1, 0),
            "马莫尼勒": (1, 3),
            "艾尼尔": (2, 1),
            "杰尼斯": (1, 1),
            "班塔纳": (0, 3),
        }
        saved_order = ("克蕾西亚", "马莫尼勒", "班塔纳", "杰尼斯", "艾尼尔")
        live = state(turn=7)
        saved = state(saved_cells, saved_order, turn=7)

        actions = plan_turn(live, saved)

        self.assertFalse(actions.ready)
        self.assertFalse(actions.switch_team)
        self.assertEqual(saved_cells, apply_drags(live.cells, actions.drags))
        self.assertEqual(3, len(actions.drags))
        self.assertEqual(list(saved_order), apply_order_swaps(live.order, actions.order_swaps))
        self.assertEqual(((2, 4),), actions.order_swaps)

    def test_team_switch_comes_alone(self):
        team_b = {"黛安娜": (1, 1), "魔法革新者": (0, 1)}
        saved = state(team_b, ("黛安娜", "魔法革新者"), turn=13, team=2)

        actions = plan_turn(state(turn=13), saved)

        self.assertTrue(actions.switch_team)
        self.assertEqual((), actions.drags)
        self.assertEqual((), actions.order_swaps)

    def test_team_cannot_switch_back(self):
        live = state({"黛安娜": (1, 1)}, ("黛安娜",), turn=15, team=2)
        with self.assertRaises(TurnMismatch):
            plan_turn(live, state(turn=15, team=1))

    def test_a_death_the_save_does_not_have_stops(self):
        # TURN 11 of the third test fight: 马莫尼勒 died after TURN 9 and the
        # list moved everyone below her up one slot.
        order = ("克蕾西亚", "艾尼尔", "杰尼斯", "班塔纳")
        live = state(order=order, turn=11, dead=["马莫尼勒"])
        with self.assertRaisesRegex(TurnMismatch, "马莫尼勒 已阵亡"):
            plan_turn(live, state(turn=11))

    def test_a_death_that_did_not_happen_stops(self):
        order = ("克蕾西亚", "艾尼尔", "杰尼斯", "班塔纳")
        saved = state(order=order, turn=11, dead=["马莫尼勒"])
        with self.assertRaisesRegex(TurnMismatch, "马莫尼勒 还活着"):
            plan_turn(state(turn=11), saved)

    def test_tombstone_stays_while_the_others_move(self):
        order = ("克蕾西亚", "艾尼尔", "杰尼斯", "班塔纳")
        saved_cells = dict(START, 克蕾西亚=(2, 1), 艾尼尔=(2, 0))
        live = state(order=order, turn=13, dead=["马莫尼勒"])
        saved = state(saved_cells, order, turn=13, dead=["马莫尼勒"])

        actions = plan_turn(live, saved)

        self.assertEqual(saved_cells, apply_drags(live.cells, actions.drags))
        tombstone = START["马莫尼勒"]
        self.assertTrue(all(tombstone not in (d.source, d.target) for d in actions.drags))

    def test_tombstone_on_another_cell_stops(self):
        order = ("克蕾西亚", "艾尼尔", "杰尼斯", "班塔纳")
        saved_cells = dict(START, 马莫尼勒=(0, 3))
        live = state(order=order, turn=13, dead=["马莫尼勒"])
        saved = state(saved_cells, order, turn=13, dead=["马莫尼勒"])
        with self.assertRaises(TurnMismatch):
            plan_turn(live, saved)

    def test_missing_summon_stops(self):
        saved_cells = dict(START, 魔法革新者=(0, 2))
        with self.assertRaisesRegex(TurnMismatch, "魔法革新者"):
            plan_turn(state(turn=5), state(saved_cells, turn=5))

    def test_different_order_members_stop(self):
        live = state(order=("克蕾西亚", "马莫尼勒", "艾尼尔", "杰尼斯"))
        with self.assertRaises(TurnMismatch):
            plan_turn(live, state())

    def test_skills_that_differ_are_listed(self):
        live = state(skills={"克蕾西亚": "1", "马莫尼勒": "2"})
        saved = state(skills={"克蕾西亚": "1", "马莫尼勒": "3"})

        actions = plan_turn(live, saved)

        self.assertEqual({"马莫尼勒": "3"}, dict(actions.skill_changes))
        self.assertFalse(actions.ready)

    def test_skill_that_could_not_be_read_stops(self):
        with self.assertRaisesRegex(TurnMismatch, "读不到 马莫尼勒"):
            plan_turn(state(), state(skills={"马莫尼勒": "2"}))

    def test_save_without_skills_skips_the_check(self):
        self.assertTrue(plan_turn(state(skills={"马莫尼勒": "2"}), state()).ready)

    def test_cards_can_be_left_for_later(self):
        actions = plan_turn(state(), state(skills={"马莫尼勒": "攻击"}), skills=False)

        self.assertTrue(actions.ready)

    def test_chart_skill_is_any_skill_card(self):
        live = state(skills={"马莫尼勒": "技能2", "克蕾西亚": "攻击"})
        saved = state(skills={"马莫尼勒": "技能", "克蕾西亚": "技能"})

        actions = plan_turn(live, saved)

        self.assertEqual({"克蕾西亚": "技能"}, dict(actions.skill_changes))

    def test_other_turn_stops(self):
        with self.assertRaises(TurnMismatch):
            plan_turn(state(turn=3), state(turn=5))


class CardTest(unittest.TestCase):
    def test_saved_card_matches(self):
        self.assertTrue(action_matches("攻击", "攻击"))
        self.assertTrue(action_matches("技能1·B3", "技能"))
        self.assertFalse(action_matches("技能1", "技能2"))
        self.assertFalse(action_matches("攻击", "技能"))
        self.assertFalse(action_matches("击退", "技能"))
        self.assertFalse(action_matches(None, "攻击"))

    def test_attacks_are_picked_before_skills(self):
        changes = {"甲": "技能1", "乙": "攻击", "丙": "技能", "丁": "击退"}

        self.assertEqual(
            [("乙", "攻击"), ("丁", "击退"), ("甲", "技能1"), ("丙", "技能")], pick_order(changes)
        )


if __name__ == "__main__":
    unittest.main()
