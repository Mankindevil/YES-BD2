"""Fighting from screenshots alone (shots.py).

Fixtures: the same practice fight recorded twice on the 2K PC (self_2k_a and
self_2k_b, 2026-10-01), TURN 7 (TEAM1, 5 units) and TURN 15 (TEAM2 with a
summon), scaled to 1080p with only the list, TEAM label, grid, floor and
TURN/BATTLE kept (tests/fixtures/fiend_hunt/README.md).  Both runs stood
everyone on the same cells, so run b's screenshot is what run a's live
screen must be matched against.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.tasks.fiend_hunt import layout, shots, vision
from src.tasks.fiend_hunt.fight import replay_fight
from src.tasks.fiend_hunt.record import FightRecord, TurnState
from src.tasks.fiend_hunt.turn_plan import TurnMismatch
from tests.helpers.recognition_fixtures import load_fhd_bgr
from tests.test_fiend_hunt_fight import T1, T3, T5, FakeBattle

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fiend_hunt"

T7 = TurnState(
    7,
    1,
    ("克蕾西亚", "马莫尼勒", "艾尼尔", "杰尼斯", "班塔纳"),
    {"马莫尼勒": (1, 3), "艾尼尔": (2, 1), "杰尼斯": (1, 1), "班塔纳": (0, 3), "克蕾西亚": (1, 0)},
)
T15 = TurnState(
    15,
    2,
    ("帕莱特", "黛安娜", "鲁", "魔法增幅器ET001", "海伦娜", "格兰希特"),
    {
        "帕莱特": (1, 2),
        "黛安娜": (0, 3),
        "鲁": (1, 0),
        "魔法增幅器ET001": (0, 2),
        "海伦娜": (1, 1),
        "格兰希特": (1, 3),
    },
)


def fixture(run: str, turn: int) -> np.ndarray:
    return load_fhd_bgr(FIXTURES / f"shots_2k_{run}_t{turn:02d}.png")


class Grid:
    """The live screen as ScreenshotTurns._place sees it."""

    record = None

    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame

    def grid_frame(self) -> np.ndarray:
        return self.frame


class ListMatchTest(unittest.TestCase):
    def test_every_entry_is_found_by_its_portrait(self):
        for state in (T7, T15):
            live, shot = fixture("a", state.turn), fixture("b", state.turn)

            found = shots.match_list(live, state.order, shot)

            self.assertEqual(dict(enumerate(state.order)), found, state.turn)

    def test_entries_are_found_in_a_shuffled_list(self):
        # The screenshot's list is in another order than the live one: the
        # entries keep their portraits, the live names just sit elsewhere.
        live, shot = fixture("a", 7), fixture("b", 7)
        shuffled = tuple(reversed(T7.order))

        found = shots.match_list(live, shuffled, shot)

        self.assertEqual(dict(enumerate(shuffled)), found)


class CostumeTest(unittest.TestCase):
    """TURN 1 on the 2K PC (list_2k_t01_bursts.png) against the card columns
    from the 4K PC's TURN 1 (cards_t1_*): 克蕾西亚 and 班塔纳 attack in a
    costume other than the one the 4K list showed (the 4K test stop)."""

    COLUMNS = {
        "克蕾西亚": "cards_t1_attack_lit.png",
        "马莫尼勒": "cards_t1_skill_lit.png",
        "班塔纳": "cards_t1_knockback_lit.png",
    }

    def test_attack_entries_are_found_among_the_units_costumes(self):
        shot = load_fhd_bgr(FIXTURES / "list_2k_t01_bursts.png")
        likeness = {}
        for unit, name in self.COLUMNS.items():
            column = load_fhd_bgr(FIXTURES / name)
            cards = vision.card_count(column)
            likeness[unit] = {
                slot: vision.costume_likeness(column, cards, shot, slot) for slot in range(5)
            }

        self.assertEqual({0: "克蕾西亚", 1: "马莫尼勒", 4: "班塔纳"}, shots.pick_costumes(likeness))

    def test_unclear_or_doubled_costumes_are_left_out(self):
        likeness = {
            "a": {0: 0.97, 1: 0.95},  # two slots: both taken by a
            "b": {0: 0.5, 1: 0.5},
            "c": {2: 0.9},
            "d": {2: 0.85},  # c and d too close on slot 2
        }

        self.assertEqual({}, shots.pick_costumes(likeness))


class Wardrobe:
    """The live list for ScreenshotTurns._dress: ``before`` until a card is
    picked, then ``after``; slot 0's card column from the 4K PC."""

    record = None

    def __init__(self, before, after, picks_work=True):
        self.frames = [before, after]
        self.picks = []
        self.picks_work = picks_work

    def list_frame(self):
        return self.frames[1 if self.picks else 0]

    def card_column(self, slot):
        column = load_fhd_bgr(FIXTURES / "cards_t1_attack_lit.png")
        return column, vision.card_count(column), 0

    def clear_selection(self):
        pass

    def pick_skill(self, slot, card):
        self.picks.append((slot, card))
        return self.picks_work


class DressTest(unittest.TestCase):
    ORDER = ("克蕾西亚", "马莫尼勒", "艾尼尔", "杰尼斯", "班塔纳")

    def setUp(self):
        # 2K TURN 1 as the screenshot; live, 克蕾西亚 (slot 0, on attack)
        # shows the costume the 4K list showed instead.
        self.shot = load_fhd_bgr(FIXTURES / "list_2k_t01_bursts.png")
        self.live = self.shot.copy()
        other = load_fhd_bgr(FIXTURES / "list_t1_start.png")
        top, bottom = 100, 205  # slot 0's entry
        self.live[top:bottom] = other[top:bottom]

    def test_attacker_in_another_costume_puts_the_screenshots_on(self):
        screen = Wardrobe(self.live, self.shot)
        solver = shots.ScreenshotTurns(screen, FIXTURES, {}, None, None)

        solver._dress(1, self.ORDER, self.shot)

        self.assertEqual([(0, "技能1"), (0, "攻击")], screen.picks)

    def test_costume_that_does_not_take_stops(self):
        screen = Wardrobe(self.live, self.live)
        solver = shots.ScreenshotTurns(screen, FIXTURES, {}, None, None)

        with self.assertRaises(TurnMismatch):
            solver._dress(1, self.ORDER, self.shot)

    def test_same_costumes_change_nothing(self):
        screen = Wardrobe(self.shot, self.shot)
        solver = shots.ScreenshotTurns(screen, FIXTURES, {}, None, None)

        solver._dress(1, self.ORDER, self.shot)

        self.assertEqual([], screen.picks)


class PlacementTest(unittest.TestCase):
    def test_each_unit_is_placed_on_its_screenshot_cell(self):
        for state in (T7, T15):
            solver = shots.ScreenshotTurns(Grid(fixture("a", state.turn)), FIXTURES, {}, None, None)

            placed, lead = solver._place(state, fixture("b", state.turn))

            self.assertEqual(dict(state.cells), placed, state.turn)
            self.assertGreaterEqual(lead, shots.PLACE_MARGIN_MIN, state.turn)

    def test_best_placement_takes_the_highest_sum(self):
        likeness = {
            "a": {(0, 0): 0.9, (0, 1): 0.8},
            "b": {(0, 0): 0.85, (0, 1): 0.2},
        }

        placed, lead = shots.best_placement(likeness)

        self.assertEqual({"a": (0, 1), "b": (0, 0)}, placed)
        self.assertAlmostEqual(1.65 - 1.1, lead)

    def test_two_lookalikes_leave_no_lead(self):
        likeness = {"a": {(0, 0): 0.7, (0, 1): 0.7}, "b": {(0, 0): 0.7, (0, 1): 0.7}}

        _, lead = shots.best_placement(likeness)

        self.assertLess(lead, shots.PLACE_MARGIN_MIN)


class Board:
    """A live grid that draws one summon as a block on the cell it stands on;
    drags move it (ScreenshotTurns._try_cells)."""

    record = None

    def __init__(self, cell, visible=True, missed=()):
        self.cell = cell
        self.visible = visible
        self.drags = []
        self.missed = set(missed)  # which drags (0 = first) miss their unit

    @staticmethod
    def draw(cell):
        frame = np.full((1080, 1920, 3), 120, np.uint8)
        if cell is not None:
            left, top, right, bottom = (round(v) for v in layout.cell_box(cell))
            frame[top + 10 : bottom - 10, left + 15 : right - 15] = (40, 200, 230)
        return frame

    def grid_frame(self):
        return self.draw(self.cell if self.visible else None)

    def drag(self, drag):
        self.drags.append(drag)
        if drag.source != self.cell or len(self.drags) - 1 in self.missed:
            return  # nobody there to move, or the drag missed
        self.cell = drag.target

    def lit_slot(self, cell):
        return 2 if cell == self.cell else None  # the summon is list slot 3 in these tests


class TryCellsTest(unittest.TestCase):
    ROBOT = "魔法增幅器ET001"

    def state(self, robot_cell):
        cells = {"a": (1, 0), "b": (1, 1), self.ROBOT: robot_cell}
        return TurnState(15, 2, ("a", "b", self.ROBOT), cells)

    def test_a_summon_goes_where_the_screenshot_shows_it(self):
        board = Board((2, 3))
        solver = shots.ScreenshotTurns(board, FIXTURES, {}, None, None)

        live = solver._try_cells(15, self.state((2, 3)), self.ROBOT, Board.draw((0, 2)))

        self.assertEqual((0, 2), live.cells[self.ROBOT])
        self.assertEqual((0, 2), board.cell)
        tried = {drag.target for drag in board.drags}
        self.assertNotIn((1, 0), tried)  # never onto someone else
        self.assertNotIn((1, 1), tried)

    def test_a_summon_already_in_place_stays(self):
        board = Board((0, 2))
        solver = shots.ScreenshotTurns(board, FIXTURES, {}, None, None)

        live = solver._try_cells(15, self.state((0, 2)), self.ROBOT, Board.draw((0, 2)))

        self.assertEqual((0, 2), live.cells[self.ROBOT])
        self.assertEqual((0, 2), board.cell)

    def test_a_last_drag_that_misses_is_seen_and_redone(self):
        # Summons are left out of the check before BATTLE, so a missed drag
        # onto the chosen cell must not go unnoticed: held, and redone.
        board = Board((2, 3), missed={0})

        live = self.badge_solver(board)._try_cells(
            15, self.state((2, 3)), self.ROBOT, fixture("b", 15)
        )

        self.assertEqual((0, 2), live.cells[self.ROBOT])
        self.assertEqual((0, 2), board.cell)
        self.assertEqual(2, len(board.drags))

    def test_a_drag_that_keeps_missing_stops(self):
        board = Board((2, 3), missed=range(shots.TRY_DRAGS))

        with self.assertRaises(TurnMismatch):
            self.badge_solver(board)._try_cells(
                15, self.state((2, 3)), self.ROBOT, fixture("b", 15)
            )
        self.assertNotEqual((0, 2), board.cell)

    def test_a_missed_first_try_falls_back_to_trying_every_cell(self):
        board = Board((2, 3), missed={0})  # the move to the likeliest cell misses
        solver = shots.ScreenshotTurns(board, FIXTURES, {}, None, None)

        live = solver._try_cells(15, self.state((2, 3)), self.ROBOT, Board.draw((0, 2)))

        self.assertEqual((0, 2), live.cells[self.ROBOT])
        self.assertEqual((0, 2), board.cell)

    def test_no_cell_standing_out_stops(self):
        board = Board((2, 3), visible=False)
        solver = shots.ScreenshotTurns(board, FIXTURES, {}, None, None)

        with self.assertRaises(TurnMismatch):
            solver._try_cells(15, self.state((2, 3)), self.ROBOT, Board.draw((0, 2)))

    def test_the_badge_shows_the_summons_cell(self):
        self.assertEqual([(0, 2)], [cell for _, cell in vision.badge_cells(fixture("b", 15))])
        self.assertEqual([], vision.badge_cells(fixture("b", 7)))  # no summon on TURN 7

    def badge_solver(self, board):
        return shots.ScreenshotTurns(
            board, FIXTURES, {}, None, None, is_summon=lambda unit: unit == self.ROBOT
        )

    def test_a_summon_goes_to_its_badge_in_one_drag(self):
        board = Board((2, 3))

        live = self.badge_solver(board)._try_cells(
            15, self.state((2, 3)), self.ROBOT, fixture("b", 15)
        )

        self.assertEqual((0, 2), live.cells[self.ROBOT])
        self.assertEqual([((2, 3), (0, 2))], [(d.source, d.target) for d in board.drags])

    def test_a_summon_on_its_badge_is_not_moved(self):
        board = Board((0, 2))

        live = self.badge_solver(board)._try_cells(
            15, self.state((0, 2)), self.ROBOT, fixture("b", 15)
        )

        self.assertEqual((0, 2), live.cells[self.ROBOT])
        self.assertEqual([], board.drags)

    def test_placement_leaves_summons_to_the_trial(self):
        moved = dict(T15.cells, **{self.ROBOT: (2, 3)})
        state = TurnState(15, 2, T15.order, moved)
        solver = shots.ScreenshotTurns(
            Grid(fixture("a", 15)),
            FIXTURES,
            {},
            None,
            None,
            is_summon=lambda unit: unit == self.ROBOT,
        )

        placed, lead = solver._place(state, fixture("b", 15))

        others = {u: c for u, c in T15.cells.items() if u != self.ROBOT}
        self.assertEqual(others, {u: c for u, c in placed.items() if u != self.ROBOT})
        self.assertEqual((2, 3), placed[self.ROBOT])  # left for the trial
        self.assertGreaterEqual(lead, shots.PLACE_MARGIN_MIN)


class CheckTest(unittest.TestCase):
    def test_arranged_as_the_screenshot_passes(self):
        for state in (T7, T15):
            wrong = shots.misplaced(
                fixture("a", state.turn), state.cells, fixture("b", state.turn), shots.ALL_CELLS
            )

            self.assertEqual([], wrong, state.turn)

    def test_another_turns_screenshot_is_caught(self):
        wrong = shots.misplaced(fixture("a", 7), T7.cells, fixture("b", 15), shots.ALL_CELLS)

        self.assertNotEqual([], wrong)

    def test_check_raises_before_battle(self):
        solver = shots.ScreenshotTurns(
            Grid(fixture("a", 7)),
            FIXTURES,
            {7: "shots_2k_b_t15.png"},
            None,
            load_fhd_bgr,
        )

        with self.assertRaises(TurnMismatch):
            solver.check(7, T7)


class FindScreenshotsTest(unittest.TestCase):
    def test_planning_screenshots_are_found_by_their_turn(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            shutil.copy(FIXTURES / "shots_2k_b_t07.png", folder / "a.png")
            shutil.copy(FIXTURES / "shots_2k_b_t15.png", folder / "b.png")
            shutil.copy(FIXTURES / "shots_2k_b_t15.png", folder / "c.png")
            (folder / "notes.txt").write_text("not a screenshot", encoding="utf-8")
            turns = iter([7, 15, 15])
            notes = []

            found = shots.find_screenshots(
                folder, lambda frame: next(turns), load_fhd_bgr, notes.append
            )

        self.assertEqual({7: "a.png", 15: "c.png"}, found)  # the later file of a turn wins
        self.assertEqual(1, len(notes))

    def test_turn_from_the_file_name_when_it_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            shutil.copy(FIXTURES / "shots_2k_b_t07.png", folder / "turn21.png")
            shutil.copy(FIXTURES / "shots_2k_b_t15.png", folder / "截图.png")
            notes = []

            found = shots.find_screenshots(folder, lambda frame: None, load_fhd_bgr, notes.append)

        self.assertEqual({21: "turn21.png"}, found)
        self.assertEqual(2, len(notes))

    def test_other_screens_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            shutil.copy(FIXTURES / "team2_planning_t13.png", folder / "isometric.png")
            shutil.copy(FIXTURES / "battle_end.png", folder / "end.png")
            shutil.copy(FIXTURES / "held_cell_slot4.png", folder / "selected.png")
            notes = []

            found = shots.find_screenshots(folder, lambda frame: 13, load_fhd_bgr, notes.append)

        self.assertEqual({}, found)
        self.assertEqual(3, len(notes))
        self.assertTrue(any("选中" in note for note in notes))


class LookingBattle(FakeBattle):
    """A FakeBattle whose cards always look as in the screenshot."""

    record = None

    def same_card(self, turn, slot):
        return True

    def grid_frame(self):
        return self.snapshot()  # stands in for the frame: _place below reads it


class KnownTurns(shots.ScreenshotTurns):
    """ScreenshotTurns that reads the list and the cells right, then after
    ``wrong_first`` rounds of placement guesses (neighbours not yet in place)."""

    def __init__(self, screen, plans, wrong_first=0):
        files = {turn: f"turn{turn:02d}.png" for turn in plans}
        super().__init__(screen, Path("."), files, lambda shot: shot.team, None)
        self.plans = plans
        self.wrong_first = wrong_first
        self.placements = 0

    def shot(self, turn):
        return self.plans[turn]

    def _dress(self, turn, order, shot):
        pass

    def _order(self, turn, live, shot):
        return shot.order

    def _place(self, live, shot):
        self.placements += 1
        cells = {unit: shot.cells[unit] for unit in shot.order}
        if self.placements <= self.wrong_first:
            first, second = shot.order[:2]
            cells[first], cells[second] = cells[second], cells[first]
        return cells, 1.0


class SolveTest(unittest.TestCase):
    def setUp(self):
        bursts = mock.patch.object(shots, "shot_bursts", lambda shot, order: dict(shot.bursts))
        bursts.start()
        self.addCleanup(bursts.stop)

    def test_fight_with_no_saved_turn_is_played_from_the_screenshots(self):
        battle = LookingBattle()
        solver = KnownTurns(battle, {1: T1, 3: T3, 5: T5})

        outcome = replay_fight(battle, FightRecord({}), solve=solver.solve, check=lambda t, s: None)

        self.assertTrue(outcome.finished)
        for saved in (T1, T3, T5):
            pressed = battle.battles[saved.turn]
            self.assertEqual((saved.order, saved.cells), (pressed.order, pressed.cells))

    def test_placement_is_looked_at_again_after_a_move(self):
        battle = LookingBattle()
        solver = KnownTurns(battle, {1: T1, 3: T3, 5: T5}, wrong_first=1)

        outcome = replay_fight(battle, FightRecord({}), solve=solver.solve)

        self.assertTrue(outcome.finished)
        self.assertEqual(T1.cells, battle.battles[1].cells)

    def test_wrong_placement_is_caught_by_the_check(self):
        battle = LookingBattle()
        solver = KnownTurns(battle, {1: T1, 3: T3, 5: T5}, wrong_first=99)

        def check(turn, state):
            if state.cells != T1.cells:
                raise TurnMismatch("不像")

        outcome = replay_fight(battle, FightRecord({}), solve=solver.solve, check=check)

        self.assertEqual(1, outcome.stopped_at)
        self.assertEqual({}, battle.battles)

    def test_placement_that_keeps_changing_is_left_to_the_check(self):
        battle = LookingBattle()
        solver = KnownTurns(battle, {1: T1, 3: T3, 5: T5})
        rounds = []

        def place(live, shot):  # always wants the first two swapped
            rounds.append(live.turn)
            first, second = live.order[:2]
            cells = {unit: live.cells[unit] for unit in live.order}
            cells[first], cells[second] = cells[second], cells[first]
            return cells, 1.0

        solver._place = place

        outcome = replay_fight(
            battle,
            FightRecord({}),
            solve=solver.solve,
            check=mock.Mock(side_effect=TurnMismatch("不像")),
        )

        self.assertEqual(1, outcome.stopped_at)
        self.assertEqual([1] * shots.PLACE_ROUNDS, rounds)

    def test_placement_it_is_unsure_of_stops(self):
        battle = LookingBattle()
        solver = KnownTurns(battle, {1: T1, 3: T3, 5: T5})
        solver._place = lambda live, shot: ({u: live.cells[u] for u in live.order}, 0.01)

        outcome = replay_fight(battle, FightRecord({}), solve=solver.solve)

        self.assertEqual(1, outcome.stopped_at)
        self.assertIn("认不准", outcome.reason)


if __name__ == "__main__":
    unittest.main()
