import unittest
from types import SimpleNamespace
from unittest import mock

from src.tasks import RestaurantTask as restaurant_module
from src.tasks.RestaurantTask import RestaurantStoneTask


def _box(name):
    return SimpleNamespace(name=name, x=1100, y=270, width=100, height=30)


class GoButtonTest(unittest.TestCase):
    """Live 2026-09-28 at 1080p: 立刻前往 was not read exactly."""

    def _task(self, reads):
        clock = [0.0]
        task = object.__new__(RestaurantStoneTask)
        reads = iter(reads)
        task.capture_frame = lambda: None
        task._roi_boxes = lambda *_a: next(reads)
        task.info_set = lambda *_a: None
        task.sleep = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
        patcher = mock.patch.object(restaurant_module, "monotonic", lambda: clock[0])
        patcher.start()
        self.addCleanup(patcher.stop)
        return task

    def test_partial_read_still_finds_the_button(self):
        task = self._task([[_box("立到前往")]])
        self.assertEqual("立到前往", task._find_go_button().name)

    def test_button_that_appears_late_is_found(self):
        task = self._task([[], [], [_box("立刻前往")]])
        self.assertIsNotNone(task._find_go_button())

    def test_gives_up_when_nothing_shows(self):
        task = self._task([[]] * 20)
        self.assertIsNone(task._find_go_button())


class StoneToastTest(unittest.TestCase):
    _task = GoButtonTest._task

    def test_late_toast_is_still_seen(self):
        task = self._task([[], [], [_box("火圣石×30")]])
        self.assertEqual("火圣石×30", task._wait_stone_toast())

    def test_no_toast_gives_up_after_the_wait(self):
        task = self._task([[]] * 50)
        self.assertEqual("", task._wait_stone_toast())


if __name__ == "__main__":
    unittest.main()
