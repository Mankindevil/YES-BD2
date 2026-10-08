import random
import unittest

from src.tasks.fiend_hunt.planner import (
    Drag,
    FormationPlanError,
    all_cells,
    apply_drags,
    apply_order_swaps,
    plan_drags,
    plan_order_swaps,
)


def cycle_count(current, target):
    """Closed cycles among misplaced units (each saves one drag)."""
    occupant = {cell: unit for unit, cell in current.items()}
    seen = set()
    cycles = 0
    for start in current:
        if start in seen or current[start] == target[start]:
            continue
        unit = start
        while unit is not None and unit not in seen and current[unit] != target[unit]:
            seen.add(unit)
            unit = occupant.get(target[unit])
        if unit == start:
            cycles += 1
    return cycles


class PlanDragsTest(unittest.TestCase):
    def assert_plan(self, current, target, expected_count=None, fixed=()):
        drags = plan_drags(current, target, fixed=fixed)
        self.assertEqual(target, apply_drags(current, drags))
        if expected_count is not None:
            self.assertEqual(expected_count, len(drags))
        return drags

    def test_same_formation_needs_no_drag(self):
        formation = {"a": (2, 0), "b": (1, 3)}
        self.assertEqual([], plan_drags(formation, formation))

    def test_move_into_empty_cell(self):
        drags = self.assert_plan({"a": (2, 0)}, {"a": (0, 1)}, 1)
        self.assertEqual([Drag((2, 0), (0, 1))], drags)

    def test_two_units_trading_places_is_one_swap(self):
        self.assert_plan({"a": (2, 0), "b": (2, 1)}, {"a": (2, 1), "b": (2, 0)}, 1)

    def test_three_cycle_takes_two_swaps(self):
        current = {"a": (0, 0), "b": (1, 1), "c": (2, 2)}
        target = {"a": (1, 1), "b": (2, 2), "c": (0, 0)}
        self.assert_plan(current, target, 2)

    def test_chain_into_empty_cell_moves_the_front_unit_first(self):
        # a -> b's cell, b -> empty (0, 3): b must leave before a arrives,
        # otherwise the first drag would be a swap and cost an extra drag.
        current = {"a": (2, 0), "b": (2, 1)}
        target = {"a": (2, 1), "b": (0, 3)}
        drags = self.assert_plan(current, target, 2)
        self.assertEqual(Drag((2, 1), (0, 3)), drags[0])

    def test_souseha_turn_one_to_turn_three(self):
        # CprilKat chart: T1 row 2 = 1 3 4 5, (1,3) = 2; T3 moves 4 and 5
        # to the top row (0,1) and (0,0).
        t1 = {1: (2, 0), 2: (1, 3), 3: (2, 1), 4: (2, 2), 5: (2, 3)}
        t3 = {1: (2, 0), 2: (1, 3), 3: (2, 1), 4: (0, 1), 5: (0, 0)}
        self.assert_plan(t1, t3, 2)

    def test_summon_counts_as_its_own_unit(self):
        current = {"帕莱特": (1, 2), "summon": (0, 2), "海伦娜": (1, 1)}
        target = {"帕莱特": (1, 2), "summon": (1, 1), "海伦娜": (2, 1)}
        self.assert_plan(current, target, 2)

    def test_fixed_unit_is_never_dragged_or_displaced(self):
        current = {"a": (0, 0), "b": (0, 1), "s": (1, 1)}
        target = {"a": (0, 1), "b": (0, 0), "s": (1, 1)}
        drags = self.assert_plan(current, target, 1, fixed=["s"])
        self.assertTrue(all((1, 1) not in (d.source, d.target) for d in drags))

    def test_fixed_unit_off_target_is_refused(self):
        with self.assertRaises(FormationPlanError):
            plan_drags({"s": (1, 1)}, {"s": (1, 2)}, fixed=["s"])

    def test_different_units_are_refused(self):
        with self.assertRaises(FormationPlanError):
            plan_drags({"a": (0, 0), "b": (0, 1)}, {"a": (0, 0)})

    def test_bad_cells_are_refused(self):
        with self.assertRaises(FormationPlanError):
            plan_drags({"a": (3, 0)}, {"a": (0, 0)})
        with self.assertRaises(FormationPlanError):
            plan_drags({"a": (0, 0), "b": (0, 0)}, {"a": (0, 0), "b": (0, 1)})

    def test_drag_from_empty_cell_is_refused(self):
        with self.assertRaises(FormationPlanError):
            apply_drags({"a": (0, 0)}, [Drag((1, 1), (0, 0))])

    def test_random_formations_use_the_fewest_drags(self):
        rng = random.Random(20260930)
        cells = all_cells()
        for _ in range(2000):
            count = rng.randint(1, 6)
            units = list(range(count))
            current = dict(zip(units, rng.sample(cells, count), strict=True))
            target = dict(zip(units, rng.sample(cells, count), strict=True))
            misplaced = sum(current[u] != target[u] for u in units)
            self.assert_plan(current, target, misplaced - cycle_count(current, target))


class PlanOrderSwapsTest(unittest.TestCase):
    def assert_swaps(self, current, target, expected_count):
        swaps = plan_order_swaps(current, target)
        self.assertEqual(list(target), apply_order_swaps(current, swaps))
        self.assertEqual(expected_count, len(swaps))
        return swaps

    def test_same_order_needs_no_swap(self):
        self.assert_swaps(["a", "b", "c"], ["a", "b", "c"], 0)

    def test_two_entries_trade_places(self):
        swaps = self.assert_swaps(["a", "b", "c", "d", "e"], ["a", "d", "c", "b", "e"], 1)
        self.assertEqual([(1, 3)], swaps)

    def test_rotation_of_three_takes_two_swaps(self):
        self.assert_swaps(["a", "b", "c"], ["c", "a", "b"], 2)

    def test_mismatched_members_are_refused(self):
        with self.assertRaises(FormationPlanError):
            plan_order_swaps(["a", "b"], ["a", "c"])
        with self.assertRaises(FormationPlanError):
            plan_order_swaps(["a", "a"], ["a", "a"])

    def test_random_orders_use_the_fewest_swaps(self):
        rng = random.Random(930)
        for _ in range(500):
            size = rng.randint(1, 6)
            current = list(range(size))
            target = rng.sample(current, size)
            # fewest transpositions = size - number of cycles
            position = {unit: index for index, unit in enumerate(current)}
            seen, cycles = set(), 0
            for start in range(size):
                if start in seen:
                    continue
                cycles += 1
                index = start
                while index not in seen:
                    seen.add(index)
                    index = position[target[index]]
            self.assert_swaps(current, target, size - cycles)


if __name__ == "__main__":
    unittest.main()
