import unittest
from pathlib import Path

from src.tasks.fiend_hunt.chart import build_chart, team_members, timelines
from src.tasks.fiend_hunt.record import FightRecord, TurnState


class ChartTest(unittest.TestCase):
    def record(self):
        first = TurnState(
            1,
            1,
            ("甲", "乙"),
            {"甲": (2, 0), "乙": (1, 3)},
            skills={"乙": "技能2"},
            bursts={"乙": 3},
        )
        later = TurnState(3, 1, ("甲",), {"甲": (2, 1), "乙": (1, 3)}, dead={"乙"})
        return FightRecord(turns={1: first, 3: later}, title="t", source="recorded")

    def test_saved_cards_and_deaths_are_kept(self):
        turns = build_chart(self.record(), Path("."), lambda _path: None)
        first, later = turns
        self.assertEqual(
            [(u.slot, u.name, u.cell) for u in first.units], [(0, "甲", (2, 0)), (1, "乙", (1, 3))]
        )
        self.assertEqual((first.units[1].action, first.units[1].burst), ("技能2", 3))
        self.assertEqual(first.units[0].action, "")  # no screenshot, no saved card: unknown
        dead = later.units[-1]
        self.assertTrue(dead.dead)
        self.assertIsNone(dead.slot)
        self.assertEqual(later.by_cell()[(1, 3)].name, "乙")

    def test_team_members_in_first_seen_order(self):
        self.assertEqual(
            team_members(build_chart(self.record(), Path("."), lambda _p: None)), {1: ["甲", "乙"]}
        )

    def test_timeline_per_unit(self):
        lines = timelines(build_chart(self.record(), Path("."), lambda _p: None))
        first, later = lines[1]["乙"]
        self.assertEqual((first[0], first[1].action), (1, "技能2"))
        self.assertEqual(later[0], 3)
        self.assertTrue(later[1].dead)

    def test_portraits_come_from_the_character_list(self):
        # Leo 2026-10-06: not cut from the game's screenshots.
        state = TurnState(
            1,
            1,
            ("黛安娜", "魔法增幅器ET001"),
            {"黛安娜": (0, 3), "魔法增幅器ET001": (1, 3)},
            skills={"黛安娜": "技能", "魔法增幅器ET001": "技能1"},
            bursts={"黛安娜": 0, "魔法增幅器ET001": 0},
            costumes={"黛安娜": "Diana_2"},
        )
        record = FightRecord(turns={1: state}, title="t", screenshots={1: "turn01.png"})
        loads = []
        diana, amplifier = build_chart(record, Path("."), lambda path: loads.append(path))[0].units
        self.assertEqual([], loads)  # nothing read off the screenshot
        self.assertTrue(diana.listed and amplifier.listed)
        self.assertEqual((256, 256, 4), diana.portrait.shape)
        self.assertEqual("Diana_2", diana.costume)


if __name__ == "__main__":
    unittest.main()


class KeptTurnsTest(unittest.TestCase):
    """A turn unchanged since the last build isn't built, nor its screenshot read, again."""

    def test_only_changed_turns_read_their_screenshot(self):
        import tempfile

        first = TurnState(1, 1, ("甲",), {"甲": (2, 0)})
        second = TurnState(3, 1, ("甲",), {"甲": (2, 1)})
        with tempfile.TemporaryDirectory() as folder:
            for name in ("turn01.png", "turn03.png"):
                (Path(folder) / name).write_bytes(b"x")
            shots = {1: "turn01.png", 3: "turn03.png"}
            record = FightRecord(turns={1: first, 3: second}, screenshots=shots)
            loads = []

            def load(path):
                loads.append(path.name)
                return None

            kept = {}
            build_chart(record, Path(folder), load, kept)
            self.assertEqual({"turn01.png", "turn03.png"}, set(loads))
            loads.clear()
            moved = TurnState(3, 1, ("甲",), {"甲": (1, 1)})
            turns = build_chart(
                FightRecord(turns={1: first, 3: moved}, screenshots=shots), Path(folder), load, kept
            )
            self.assertEqual({"turn03.png"}, set(loads))
            self.assertEqual((1, 1), turns[1].units[0].cell)
            self.assertEqual(2, len(kept))
