import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from src.tasks.EventRewardTask import (
    BADGE_STRIP,
    CURRENCY_ROI,
    DIALOG_ROI,
    DIAMOND_TEMPLATE,
    PANEL_ROI,
    button_lit,
    diamond_icon,
    find_badges,
    list_view,
    views_match,
    parse_token_count,
    red_share,
)


def _frame(width=1920, height=1080, color=(40, 40, 40)):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = color
    return frame


class FindBadgesTest(unittest.TestCase):
    def test_red_square_in_the_strip_is_a_badge(self):
        frame = _frame()
        x = BADGE_STRIP[0] + 8
        frame[400:418, x : x + 18] = (0, 0, 230)  # BGR red, 18 px like the live badge
        self.assertEqual(find_badges(frame), [409])

    def test_scales_with_the_frame(self):
        frame = _frame(3840, 2160)
        x = (BADGE_STRIP[0] + 8) * 2
        frame[800:836, x : x + 36] = (0, 0, 230)
        self.assertEqual(find_badges(frame), [409])

    def test_large_red_art_is_not_a_badge(self):
        frame = _frame()
        frame[300:500, BADGE_STRIP[0] : BADGE_STRIP[0] + 30] = (0, 0, 230)
        self.assertEqual(find_badges(frame), [])


class ButtonLitTest(unittest.TestCase):
    def _box(self):
        return SimpleNamespace(x=100, y=100, width=80, height=30)

    def test_white_pill_is_lit_and_grey_is_not(self):
        self.assertTrue(button_lit(_frame(color=(255, 255, 255)), self._box()))
        self.assertFalse(button_lit(_frame(color=(128, 128, 128)), self._box()))

    def test_blue_claim_all_lit_and_dim(self):
        # 全部领取 live 4K 2026-10-04: lit BGR (231,134,107), dim (137,82,63).
        self.assertTrue(button_lit(_frame(color=(231, 134, 107)), self._box()))
        self.assertFalse(button_lit(_frame(color=(137, 82, 63)), self._box()))


class RedShareTest(unittest.TestCase):
    def test_red_cost_digits(self):
        frame = _frame()
        frame[10:20, 10:30] = (0, 0, 230)
        self.assertGreater(red_share(frame, (0, 0, 40, 40)), 0.08)
        self.assertEqual(red_share(_frame(), (0, 0, 40, 40)), 0.0)


class DiamondIconTest(unittest.TestCase):
    def test_gem_in_the_currency_bar_is_found(self):
        gem = cv2.imread(str(DIAMOND_TEMPLATE))
        frame = _frame()
        gh, gw = gem.shape[:2]
        frame[41 : 41 + gh, 1461 : 1461 + gw] = gem  # where 满月 shows it
        self.assertTrue(diamond_icon(frame, (CURRENCY_ROI,)))
        self.assertFalse(diamond_icon(frame, (DIALOG_ROI,)))

    def test_plain_frame_has_no_gem(self):
        self.assertFalse(diamond_icon(_frame(), (PANEL_ROI, CURRENCY_ROI, DIALOG_ROI)))


if __name__ == "__main__":
    unittest.main()


class TokenCountTest(unittest.TestCase):
    def test_narrow_ones_read_as_letters(self):
        self.assertEqual(parse_token_count("ll0"), 110)
        self.assertEqual(parse_token_count("I|O"), 110)

    def test_plain_digits_and_nothing(self):
        self.assertEqual(parse_token_count("210"), 210)
        self.assertEqual(parse_token_count("1,000"), 1000)
        self.assertIsNone(parse_token_count(""))


class DiamondRecheckTest(unittest.TestCase):
    """The 钻石 check runs again on the frame of every press."""

    def _task(self, diamond_checks):
        from src.tasks.EventRewardTask import EventRewardTask

        task = object.__new__(EventRewardTask)
        task.capture_frame = lambda: _frame()
        task.info_set = lambda *a, **k: None
        task.log_info = lambda *a, **k: None
        task._reference_boxes = lambda *a: []
        task._diamonds_now = lambda *_a: diamond_checks.pop(0)
        task._click_reference_box = lambda *a, **k: self.fail("pressed on a paid page")
        return task

    def test_paid_page_presses_nothing(self):
        self.assertFalse(self._task([True])._press_what_is_lit("钻石"))


class ListBottomTest(unittest.TestCase):
    def test_same_list_picture_is_the_bottom(self):
        frame = np.random.default_rng(3).integers(0, 255, (1440, 2560, 3), dtype=np.uint8)
        self.assertTrue(views_match(list_view(frame), list_view(frame.copy())))

    def test_moved_list_is_not(self):
        frame = np.random.default_rng(3).integers(0, 255, (1440, 2560, 3), dtype=np.uint8)
        moved = np.roll(frame, 120, axis=0)
        self.assertFalse(views_match(list_view(frame), list_view(moved)))


class LastCardTest(unittest.TestCase):
    def test_login_event_is_the_last_card(self):
        from src.tasks.EventRewardTask import LAST_CARD_TEXT
        from src.utils.ocr_utils import normalize_ocr_text

        self.assertIn(LAST_CARD_TEXT, normalize_ocr_text("丰饶之月 登录活动 D-5"))
        self.assertNotIn(LAST_CARD_TEXT, normalize_ocr_text("每日登录 1/5"))


def _box(name, x, y, w=90, h=30):
    return SimpleNamespace(name=name, x=x, y=y, width=w, height=h)


class PressWhatIsLitTest(unittest.TestCase):
    """Leo 2026-10-08: every event page — press what is lit, 即刻刷新 first."""

    def _task(self, frames, boxes, pressed, confirm=True):
        from src.tasks.EventRewardTask import EventRewardTask

        task = object.__new__(EventRewardTask)
        task.capture_frame = lambda: frames[0]
        task.info_set = lambda *a, **k: None
        task.log_info = lambda *a, **k: None
        task._diamonds_now = lambda *_a: False
        task._reference_boxes = lambda *a: boxes
        task._hand_points = lambda *_a: []

        def press(box, **_k):
            pressed.append(box.name)
            if len(frames) > 1:
                frames.pop(0)

        task._click_reference_box = press
        task._confirm_dialog = lambda *_a: confirm
        task._settle = lambda *_a: None
        return task

    @staticmethod
    def _lit(frame, *boxes):
        frame = frame.copy()
        for box in boxes:
            frame[box.y : box.y + box.height, box.x : box.x + box.width] = 255
        return frame

    def test_refresh_first_then_unlock(self):
        refresh, unlock = _box("即刻刷新", 1290, 760), _box("全部解锁", 1500, 750)
        grey = _frame(color=(128, 128, 128))
        frames = [self._lit(grey, refresh, unlock), self._lit(grey, unlock), grey]
        pressed = []
        self.assertTrue(self._task(frames, [refresh, unlock], pressed)._press_what_is_lit("拼图"))
        self.assertEqual(pressed, ["即刻刷新", "全部解锁"])

    def test_grey_page_presses_nothing(self):
        boxes = [_box("即刻刷新", 1290, 760), _box("全部解锁", 1500, 750), _box("旋转1次", 1100, 740)]
        pressed = []
        self._task([_frame(color=(128, 128, 128))], boxes, pressed)._press_what_is_lit("x")
        self.assertEqual(pressed, [])

    def test_task_line_is_not_a_button(self):
        # A white task row that only mentions a button word is never pressed.
        rows = [_box("转盘旋转1次", 1100, 400, 300), _box("获得拼图用触控笔", 600, 700, 200)]
        frame = self._lit(_frame(), *rows)
        pressed = []
        self._task([frame], rows, pressed)._press_what_is_lit("任务")
        self.assertEqual(pressed, [])

    def test_claim_all_on_the_puzzle_task_page(self):
        claim = _box("全部领取", 1450, 760)
        boxes = [_box("获得拼图用触控笔", 600, 700, 200), _box("活动任务", 600, 740), claim]
        frames = [self._lit(_frame(), claim), _frame()]
        pressed = []
        self._task(frames, boxes, pressed)._press_what_is_lit("活动任务")
        self.assertEqual(pressed, ["全部领取"])

    def test_exchange_without_confirm_stops_exchanging(self):
        exchange = _box("兑换100次", 1300, 720)
        frame = self._lit(_frame(), exchange)
        pressed = []
        self._task([frame], [exchange], pressed, confirm=False)._press_what_is_lit("兑换所")
        self.assertEqual(pressed, ["兑换100次"])

    def test_traditional_ocr_reads_as_the_button(self):
        unlock = _box("全部解鎖", 1500, 750)
        frames = [self._lit(_frame(), unlock), _frame()]
        pressed = []
        self._task(frames, [unlock], pressed)._press_what_is_lit("拼图")
        self.assertEqual(pressed, ["全部解鎖"])


class SecondSweepTest(unittest.TestCase):
    def test_second_pass_closes_and_reopens_the_page(self):
        from src.tasks.EventRewardTask import EventRewardTask

        steps = []
        task = object.__new__(EventRewardTask)
        task.info_set = lambda *a, **k: None
        task._open_page_from_home = lambda *a: steps.append("open") or True
        task._leave_to_home = lambda *a: steps.append("home") or True
        sweeps = iter([1, 0])
        task._sweep_list = lambda _skipped: steps.append("sweep") or next(sweeps)
        self.assertTrue(task.run_claim())
        self.assertEqual(steps, ["open", "sweep", "home", "open", "sweep", "home"])

    def test_nothing_claimed_means_no_second_pass(self):
        from src.tasks.EventRewardTask import EventRewardTask

        steps = []
        task = object.__new__(EventRewardTask)
        task.info_set = lambda *a, **k: None
        task._open_page_from_home = lambda *a: steps.append("open") or True
        task._leave_to_home = lambda *a: steps.append("home") or True
        task._sweep_list = lambda _skipped: steps.append("sweep") or 0
        self.assertTrue(task.run_claim())
        self.assertEqual(steps, ["open", "sweep", "home"])
