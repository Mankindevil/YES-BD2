"""Leaving the refine page (live 2K 2026-09-29: the first back press was swallowed)."""

import unittest
from types import SimpleNamespace


class BackToBagTest(unittest.TestCase):
    def _task(self, pages):
        """``pages`` = the page after each back press: "refine", "bag" or "loading"."""
        from src.tasks.GearTasks import DailyRefineTask

        task = object.__new__(DailyRefineTask)
        task.log_info = lambda *a, **k: None
        task.capture_frame = lambda: None
        presses = []
        current = ["refine"]
        shown = iter(pages)

        def press(*_a, **_k):
            presses.append(1)
            current[0] = next(shown)

        task._click_reference = press
        task._wait_for_title = lambda _l, _keys, **_k: current[0] == "bag"
        task._roi_boxes = lambda *_a: [
            SimpleNamespace(name="精炼80" if current[0] == "refine" else "一键分解")
        ]
        return task, presses

    def test_swallowed_press_is_repeated_while_still_on_the_refine_page(self):
        task, presses = self._task(["refine", "bag"])
        self.assertEqual("refined", task._back_to_bag("refined"))
        self.assertEqual(2, len(presses))

    def test_no_second_press_once_the_refine_page_is_gone(self):
        # A slow bag (still loading) must not get a press that leaves it.
        task, presses = self._task(["loading"])
        self.assertEqual("failed", task._back_to_bag("refined"))
        self.assertEqual(1, len(presses))


if __name__ == "__main__":
    unittest.main()
