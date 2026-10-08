import tempfile
import unittest
from pathlib import Path

from src.tasks.fiend_hunt.fight import ScreenReadError
from src.tasks.fiend_hunt.record import FightRecord, TurnState, load_record, save_record
from src.tasks.fiend_hunt.recording import record_fight
from src.tasks.fiend_hunt.saves import delete_turn

ORDER = ("克蕾西亚", "马莫尼勒", "艾尼尔")
CELLS = {"克蕾西亚": (2, 0), "马莫尼勒": (1, 3), "艾尼尔": (2, 1)}


def state(turn, **changes):
    fields = dict(turn=turn, team=1, order=ORDER, cells=CELLS) | changes
    return TurnState(**fields)


class ScriptedGame:
    """Each phase() call is the next moment of a fight the player is playing.

    A step is (phase, turn, key): what the game shows, its TURN, and whether
    the player pressed the save key at that moment.
    """

    def __init__(self, steps, reads, battle_fails=0):
        self.steps = list(steps)
        self.reads = {turn: list(results) for turn, results in reads.items()}
        self.turn = None
        self.key = False
        self.battles = []
        self.battle_fails = battle_fails  # presses of BATTLE that fail first

    # SaveKey
    def pressed(self):
        key, self.key = self.key, False
        return key

    # RecordingScreen
    def phase(self):
        if not self.steps:
            return "end"
        phase, self.turn, self.key = self.steps.pop(0)
        return phase

    def read_turn(self):
        return self.turn

    def read_state(self, turn):
        results = self.reads[turn]
        result = results.pop(0) if len(results) > 1 else results[0]
        if isinstance(result, Exception):
            raise result
        return result

    def save_screenshot(self, path):
        Path(path).write_bytes(b"png")

    def press_battle(self):
        if self.battle_fails:
            self.battle_fails -= 1
            raise ScreenReadError("按 BATTLE 前画面不对")
        self.battles.append(self.turn)

    def wait_after_battle(self):
        if not self.steps or self.steps[0][0] == "end":
            self.steps = self.steps[1:]
            return "end"
        return "planning"


class RecordFightTest(unittest.TestCase):
    def run_script(self, steps, reads, **options):
        game = ScriptedGame(steps, reads, **options)
        with tempfile.TemporaryDirectory() as folder:
            outcome = record_fight(game, game, folder, title="测试", sleep=lambda _: None)
            files = sorted(path.name for path in Path(folder).iterdir())
            saved = load_record(Path(folder) / "record.json") if "record.json" in files else None
        return game, outcome, files, saved

    def test_saves_each_turn_and_presses_battle_itself(self):
        steps = [
            ("planning", 1, False),
            ("planning", 1, True),
            ("planning", 3, True),
            ("end", None, False),
        ]
        reads = {1: [state(1)], 3: [state(3, cells=dict(CELLS, 克蕾西亚=(1, 0)))]}

        game, outcome, files, saved = self.run_script(steps, reads)

        self.assertTrue(outcome.finished)
        self.assertEqual([1, 3], game.battles)
        self.assertEqual({1: reads[1][0], 3: reads[3][0]}, outcome.record.turns)
        self.assertEqual(outcome.record, saved)
        self.assertEqual(["record.json", "turn01.png", "turn03.png"], files)

    def test_burst_levels_are_saved_with_the_turn(self):
        class BurstGame(ScriptedGame):
            def read_bursts(self, state):
                return {"克蕾西亚": 2} if state.turn == 1 else {}

        steps = [("planning", 1, True), ("planning", 3, True), ("end", None, False)]
        reads = {1: [state(1)], 3: [state(3)]}
        game = BurstGame(steps, reads)
        with tempfile.TemporaryDirectory() as folder:
            outcome = record_fight(game, game, folder, title="测试", sleep=lambda _: None)
            saved = load_record(Path(folder) / "record.json")

        self.assertTrue(outcome.finished)
        self.assertEqual({"克蕾西亚": 2}, saved.turns[1].bursts)
        self.assertEqual({}, saved.turns[3].bursts)

    def test_turn_started_with_battle_by_hand_is_noted_as_unsaved(self):
        steps = [
            ("planning", 1, True),
            ("planning", 3, False),
            ("battle", None, False),
            ("planning", 5, True),
            ("end", None, False),
        ]
        reads = {1: [state(1)], 5: [state(5)]}

        game, outcome, _files, saved = self.run_script(steps, reads)

        self.assertEqual((3,), outcome.unsaved_turns)
        self.assertEqual([1, 5], sorted(saved.turns))
        self.assertEqual([1, 5], game.battles)

    def test_failed_read_saves_nothing_until_the_key_is_pressed_again(self):
        steps = [
            ("planning", 1, True),
            ("planning", 1, False),
            ("planning", 1, True),
            ("end", None, False),
        ]
        reads = {1: [ScreenReadError("读不清"), state(1)]}

        game, outcome, _files, saved = self.run_script(steps, reads)

        self.assertEqual([1], game.battles)
        self.assertEqual([1], sorted(saved.turns))

    def test_key_pressed_during_battle_does_not_carry_over(self):
        steps = [
            ("planning", 1, True),
            ("battle", None, True),
            ("planning", 3, False),
            ("battle", None, False),
            ("end", None, False),
        ]
        reads = {1: [state(1)], 3: [state(3)]}

        game, outcome, _files, _saved = self.run_script(steps, reads)

        self.assertEqual([1], game.battles)
        self.assertEqual((3,), outcome.unsaved_turns)

    def test_saved_turn_the_tool_could_not_battle_is_left_to_the_player(self):
        steps = [
            ("planning", 1, True),
            ("planning", 1, False),
            ("battle", None, False),
            ("planning", 3, True),
            ("end", None, False),
        ]
        reads = {1: [state(1)], 3: [state(3)]}

        game, outcome, _files, saved = self.run_script(steps, reads, battle_fails=1)

        self.assertTrue(outcome.finished)
        self.assertEqual([3], game.battles)  # the player pressed BATTLE on turn 1
        self.assertEqual([1, 3], sorted(saved.turns))
        self.assertEqual((), outcome.unsaved_turns)

    def test_team_going_back_is_not_saved(self):
        team_b = dict(team=2, order=("黛安娜",), cells={"黛安娜": (1, 1)})
        steps = [
            ("planning", 1, True),
            ("planning", 3, True),
            ("planning", 3, False),
            ("end", None, False),
        ]
        reads = {1: [state(1, **team_b)], 3: [state(3)]}

        game, outcome, _files, saved = self.run_script(steps, reads)

        self.assertEqual([1], game.battles)
        self.assertEqual([1], sorted(saved.turns))


class EditSaveTest(unittest.TestCase):
    """Recording into an existing save edits it (Leo 2026-10-01)."""

    def existing(self, folder, turns=(1, 3, 5)):
        record = FightRecord(
            turns={turn: state(turn) for turn in turns},
            title="旧存档",
            screenshots={turn: f"turn{turn:02d}.png" for turn in turns},
        )
        for turn in turns:
            (Path(folder) / f"turn{turn:02d}.png").write_bytes(b"old")
        save_record(record, Path(folder) / "record.json")

    def test_turns_are_kept_and_a_turn_recorded_again_is_overwritten(self):
        moved = state(3, cells=dict(CELLS, 克蕾西亚=(1, 0)))
        game = ScriptedGame([("planning", 3, True), ("end", None, False)], {3: [moved]})
        lines = []
        with tempfile.TemporaryDirectory() as folder:
            self.existing(folder)
            outcome = record_fight(game, game, folder, sleep=lambda _: None, log=lines.append)
            saved = load_record(Path(folder) / "record.json")
            shot = (Path(folder) / "turn03.png").read_bytes()
        self.assertEqual([1, 3, 5], sorted(saved.turns))
        self.assertEqual(moved, saved.turns[3])
        self.assertEqual(state(1), saved.turns[1])
        self.assertEqual("旧存档", saved.title)
        self.assertEqual(b"png", shot)
        self.assertTrue(any("第 3 回合已覆盖" in line for line in lines))
        self.assertTrue(outcome.finished)

    def test_a_turn_deleted_on_the_page_meanwhile_stays_deleted(self):
        holder = {}

        class DeletingGame(ScriptedGame):
            def phase(self):
                if len(self.steps) == 2:  # the player deletes turn 1 mid-recording
                    delete_turn(holder["folder"], 1)
                return super().phase()

        game = DeletingGame(
            [("planning", 7, False), ("planning", 7, True), ("end", None, False)], {7: [state(7)]}
        )
        with tempfile.TemporaryDirectory() as folder:
            holder["folder"] = Path(folder)
            self.existing(folder)
            record_fight(game, game, folder, sleep=lambda _: None)
            saved = load_record(Path(folder) / "record.json")
            files = sorted(path.name for path in Path(folder).iterdir())
        self.assertEqual([3, 5, 7], sorted(saved.turns))
        self.assertEqual(["record.json", "turn03.png", "turn05.png", "turn07.png"], files)


if __name__ == "__main__":
    unittest.main()


class SafeSaveTest(unittest.TestCase):
    """A save is never left half written, nor overwritten when it can't be read."""

    def test_the_record_is_replaced_whole(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "record.json"
            save_record(FightRecord({1: state(1)}, title="t"), path)
            save_record(FightRecord({1: state(1), 3: state(3)}, title="t"), path)
            self.assertEqual([1, 3], sorted(load_record(path).turns))
            self.assertEqual(["record.json"], [p.name for p in Path(folder).iterdir()])

    def test_an_unreadable_record_is_not_recorded_over(self):
        game = ScriptedGame([("planning", 3, True), ("end", None, False)], {3: [state(3)]})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "record.json"
            path.write_text('{"turns": [', encoding="utf-8")  # cut short
            with self.assertRaises(ScreenReadError):
                record_fight(game, game, folder, sleep=lambda _: None)
            self.assertEqual('{"turns": [', path.read_text(encoding="utf-8"))
            self.assertEqual([], game.battles)
