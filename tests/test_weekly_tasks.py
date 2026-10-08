"""HomePopularityTask only clicks its fixed points on a confirmed visit page."""

import unittest
from unittest import mock

from src.tasks.WeeklyTasks import (
    LIKE_BUTTON_POINT,
    NEXT_HOME_POINT,
    HomePopularityTask,
)


def _task(on_page):
    task = object.__new__(HomePopularityTask)
    task.name = "小屋增加人气"
    task.config = {"点赞次数": 3, "最多翻看小屋数": 8}
    task.info_set = lambda *a: None
    task.log_info = lambda *a, **k: None
    task._open_page_from_home = lambda *a: True
    task._wait_for_title = lambda *a, **k: True
    task._leave_to_home = mock.Mock(return_value=True)
    task.clicks = []
    task._click_reference = lambda x, y, after_sleep=0: task.clicks.append((x, y))
    task._on_visited_home = on_page
    task.log_warning = lambda *a, **k: None
    task._click_until_changed = lambda _label, click, _rois, **_k: click() or True
    return task


class HomePopularityTest(unittest.TestCase):
    def test_no_like_or_next_click_off_the_visit_page(self):
        task = _task(lambda: False)
        self.assertFalse(task.run_claim())
        self.assertNotIn(LIKE_BUTTON_POINT, task.clicks)
        self.assertNotIn(NEXT_HOME_POINT, task.clicks)
        task._leave_to_home.assert_called_once()

    def test_likes_until_the_goal_on_the_visit_page(self):
        task = _task(lambda: True)
        task._like_current_home = lambda visit: True
        self.assertTrue(task.run_claim())

    def test_like_counter_that_updates_late_still_counts(self):
        task = _task(lambda: True)
        reads = iter([10, 10, 10, 11, 11])
        task._like_count = lambda: next(reads)
        task.sleep = lambda _s: None
        clicks = []
        task._click_reference = lambda x, y, after_sleep=0: clicks.append((x, y))
        self.assertTrue(task._like_current_home(1))
        # Pressed once only: a second press could take the like back.
        self.assertEqual([LIKE_BUTTON_POINT], clicks)

    def test_like_without_counter_change_is_not_pressed_again(self):
        task = _task(lambda: True)
        task._like_count = lambda: 10
        task.sleep = lambda _s: None
        clicks = []
        task._click_reference = lambda x, y, after_sleep=0: clicks.append((x, y))
        with mock.patch("src.tasks.WeeklyTasks.monotonic", side_effect=[0, 1, 2, 5]):
            self.assertFalse(task._like_current_home(1))
        self.assertEqual([LIKE_BUTTON_POINT], clicks)


if __name__ == "__main__":
    unittest.main()
