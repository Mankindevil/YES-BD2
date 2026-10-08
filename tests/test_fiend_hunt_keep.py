import tempfile
import unittest
from pathlib import Path

from src.tasks.fiend_hunt.keep import KEPT_SHOTS, KeptFight
from src.tasks.fiend_hunt.record import FightRecord, TurnState, load_record
from src.tasks.fiend_hunt.turn_plan import TurnMismatch

ROBOT = "魔法增幅器ET001"


def state(turn, robot=(0, 2), bursts=None):
    cells = {"a": (1, 0), "b": (1, 1), ROBOT: robot}
    return TurnState(turn, 2, ("a", "b", ROBOT), cells, bursts=bursts or {})


class Shots:
    """Writes a placeholder file for each screenshot."""

    def __init__(self):
        self.saved = []
        self.waited = False

    def save_screenshot(self, path):
        Path(path).write_bytes(b"png")
        self.saved.append(Path(path))

    def wait_saved(self):
        self.waited = True


class Solver:
    def __init__(self, wrong=()):
        self.wrong = set(wrong)

    def solve(self, turn, record):
        solved = state(turn, bursts={"a": 2})
        return FightRecord({**record.turns, turn: solved}, record.title), solved

    def check(self, turn, live):
        if turn in self.wrong:
            raise TurnMismatch("不像")


def fight(kept, turns):
    record = FightRecord({}, "截图")
    for turn in turns:
        record, live = kept.solve(turn, record)
        kept.check(turn, state(turn, robot=(2, 3)))
    return tuple(turns)


class KeptFightTest(unittest.TestCase):
    def test_a_finished_fight_becomes_a_save_beside_the_screenshots(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / "mine.png").write_bytes(b"player")
            screen = Shots()
            kept = KeptFight(screen, folder, Solver(), "截图")

            path = kept.keep(fight(kept, (1, 3)))

            self.assertEqual(folder / "record.json", path)
            self.assertTrue(screen.waited)
            record = load_record(path)
            self.assertEqual({1, 3}, set(record.turns))
            # as left at BATTLE, with the bursts worked out from the screenshot
            self.assertEqual((2, 3), record.turns[3].cells[ROBOT])
            self.assertEqual({"a": 2}, dict(record.turns[3].bursts))
            self.assertEqual(f"{KEPT_SHOTS}/turn03.png", record.screenshots[3])
            self.assertTrue((folder / record.screenshots[3]).is_file())
            self.assertEqual(b"player", (folder / "mine.png").read_bytes())
            # the player's folder keeps only its own images at the top
            self.assertEqual(["mine.png"], sorted(p.name for p in folder.glob("*.png")))

    def test_a_turn_that_fails_its_check_is_not_kept(self):
        with tempfile.TemporaryDirectory() as root:
            kept = KeptFight(Shots(), Path(root), Solver(wrong={3}), "截图")
            record = FightRecord({}, "截图")
            record, _ = kept.solve(3, record)
            with self.assertRaises(TurnMismatch):
                kept.check(3, state(3))
            self.assertIsNone(kept.keep((3,)))
            self.assertFalse((Path(root) / "record.json").exists())

    def test_an_existing_save_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "record.json").write_text("mine", encoding="utf-8")
            kept = KeptFight(Shots(), Path(root), Solver(), "截图")
            self.assertIsNone(kept.keep(fight(kept, (1,))))
            self.assertEqual("mine", (Path(root) / "record.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
