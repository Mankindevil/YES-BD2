"""Free cocktails left below one battle end the day cleanly (live 2026-09-29)."""

import unittest


class FreeCocktailsShortTest(unittest.TestCase):
    def _verify(self, cost, free, battles, multiplier=18, count=2):
        from src.tasks.PVPTask import PVPTask

        task = object.__new__(PVPTask)
        task.info_set = lambda *a: None
        task.log_info = lambda *a, **k: None
        warnings = []
        task.log_warning = lambda message, **_k: warnings.append(message)
        task.sleep = lambda *a: None
        # A free count short of the run is read again and must agree.
        values = iter((cost, free, battles, free))
        task._read_until = lambda _reader: next(values)
        task._free_ap_switch_on = lambda: True
        task._free_cocktails_short = False
        ok = PVPTask._verify_free_cost(task, multiplier, count)
        return ok, task._free_cocktails_short, warnings

    def test_four_left_at_18x_is_the_end_of_the_day_not_a_failure(self):
        ok, short, warnings = self._verify(cost=18, free=4, battles=2)
        self.assertFalse(ok)
        self.assertTrue(short)
        self.assertEqual([], warnings)

    def test_enough_for_one_battle_is_still_a_mismatch_warning(self):
        # 20 free covers one 18x battle; the count guard owns that case.
        ok, short, warnings = self._verify(cost=18, free=20, battles=2)
        self.assertFalse(ok)
        self.assertFalse(short)
        self.assertEqual(1, len(warnings))

    def test_disagreeing_free_reads_never_fight_nor_end_the_day(self):
        # One frame dropped a digit (40 -> 4): no fight, but not "day done".
        from src.tasks.PVPTask import PVPTask

        task = object.__new__(PVPTask)
        task.info_set = lambda *a: None
        task.log_info = lambda *a, **k: None
        task.log_warning = lambda *a, **k: None
        task.sleep = lambda *a: None
        values = iter((18, 4, 2, 40))
        task._read_until = lambda _reader: next(values)
        task._free_ap_switch_on = lambda: True
        task._free_cocktails_short = False
        self.assertFalse(PVPTask._verify_free_cost(task, 18, 2))
        self.assertFalse(task._free_cocktails_short)

    def test_switch_off_is_never_short(self):
        from src.tasks.PVPTask import PVPTask

        task = object.__new__(PVPTask)
        task.info_set = lambda *a: None
        task.log_info = lambda *a, **k: None
        task.log_warning = lambda *a, **k: None
        task.sleep = lambda *a: None
        values = iter((18, 4, 2, 4))
        task._read_until = lambda _reader: next(values)
        task._free_ap_switch_on = lambda: False
        task._free_cocktails_short = False
        self.assertFalse(PVPTask._verify_free_cost(task, 18, 2))
        self.assertFalse(task._free_cocktails_short)


class FreeShortFallbackTest(unittest.TestCase):
    """Leo 2026-09-29: cocktails short of 18x -> one battle at 1x."""

    def _run(self, states):
        from src.tasks.PVPTask import PVPTask

        task = object.__new__(PVPTask)
        task.config = {"启用": True, "竞技场战斗倍数": 18}
        task.info_set = lambda *a: None
        task.log_info = lambda *a, **k: None
        task.log_completion = lambda *a, **k: None
        task._ensure_pvp_hub = lambda: True
        seen = []
        results = iter(states)

        def start(multiplier):
            seen.append((multiplier, task._battle_count_override))
            return next(results)

        task._start_auto_battle = start
        task._wait_result_and_leave = lambda *_a: True
        task._click_reference = lambda *a, **k: seen.append("back")
        task._ensure_pvp_hub_after_leave = lambda: seen.append("rank page or hub") or True
        task._return_home_from_pvp_hub = lambda: seen.append("home") or True
        return PVPTask.run(task), seen

    def test_short_at_18x_fights_one_battle_at_1x(self):
        ok, seen = self._run(["free_short", "started"])
        self.assertTrue(ok)
        self.assertEqual([(18, None), (1, 1)], [s for s in seen if isinstance(s, tuple)])

    def test_short_even_at_1x_goes_home_done(self):
        ok, seen = self._run(["free_short", "free_short"])
        self.assertTrue(ok)
        # Leo 2026-10-05: going back can show the rank-down page; it is
        # confirmed (as after a battle) before heading home.
        self.assertEqual(
            [(18, None), (1, 1), "back", "rank page or hub", "home"], seen
        )


if __name__ == "__main__":
    unittest.main()
