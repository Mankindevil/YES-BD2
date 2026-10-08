import unittest
from pathlib import Path

import cv2
import numpy as np

from src.utils.junk_gear import (
    GearItem,
    agreed_rarity,
    classify,
    colour_rarity,
    leading_new_cells,
    load_exclusive_stars,
    new_marker_ratio,
    ocr_rarity,
)


def label(hues):
    """A label image whose coloured pixels use the given OpenCV hues."""
    hsv = np.zeros((40, 40, 3), dtype=np.uint8)
    hsv[:, :, 1] = 200
    hsv[:, :, 2] = 220
    for index, hue in enumerate(hues):
        hsv[:, index * 40 // len(hues) : (index + 1) * 40 // len(hues), 0] = hue
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


class JunkRulesTest(unittest.TestCase):
    STARS = {"掠夺之手": 4, "卢戈制衬衫": 3, "噬血者": 5, "恋的头饰": 5}

    def item(self, name, rarity, **flags):
        return GearItem(name, rarity, flags.get("equipped", False),
                        flags.get("locked", False), flags.get("enhanced", False))

    def test_live_items_from_2026_09_26(self):
        self.assertTrue(classify(self.item("掠夺之手", "R"), self.STARS)[0])
        self.assertTrue(classify(self.item("飞翅骷髅", "R"), self.STARS)[0])
        self.assertTrue(classify(self.item("卢戈制衬衫", "UR"), self.STARS)[0])
        self.assertFalse(classify(self.item("噬血者", "UR"), self.STARS)[0])

    def test_uncertain_items_are_kept(self):
        self.assertFalse(classify(self.item("未知装备", "UR"), self.STARS)[0])
        self.assertFalse(classify(self.item("掠夺之手", None), self.STARS)[0])
        self.assertFalse(classify(self.item("某装备", "N"), self.STARS)[0])

    def test_equipped_locked_or_enhanced_are_never_junk(self):
        for flag in ("equipped", "locked", "enhanced"):
            self.assertFalse(classify(self.item("掠夺之手", "R", **{flag: True}), self.STARS)[0])

    def test_toggles(self):
        self.assertFalse(
            classify(self.item("掠夺之手", "SR"), self.STARS, dismantle_r_sr=False)[0]
        )
        self.assertFalse(
            classify(self.item("卢戈制衬衫", "UR"), self.STARS, dismantle_low_star_ur=False)[0]
        )


class RarityReadingTest(unittest.TestCase):
    def test_ocr_tokens(self):
        self.assertEqual("UR", ocr_rarity("JR"))
        self.assertEqual("UR", ocr_rarity("UR"))
        self.assertEqual("R", ocr_rarity("R"))
        self.assertEqual("SR", ocr_rarity("SR"))
        self.assertIsNone(ocr_rarity("掠夺之手"))

    def test_label_colours(self):
        self.assertEqual("R", colour_rarity(label([106])))
        self.assertEqual("SR", colour_rarity(label([140])))
        self.assertEqual("UR", colour_rarity(label([30, 60, 100, 140, 160])))

    def test_text_and_colour_must_agree(self):
        # A UR whose "U" was dropped by OCR must not become an R.
        self.assertIsNone(agreed_rarity("R", label([30, 60, 100, 140, 160])))
        self.assertEqual("R", agreed_rarity("R", label([106])))

    def test_live_label_crops_if_available(self):
        shots = Path(".local-dev/shots")
        cases = {"label_it0.png": "R", "label_it_904.png": "UR", "label_it_lock.png": "UR"}
        if not all((shots / name).exists() for name in cases):
            self.skipTest("live label crops not present")
        for name, expected in cases.items():
            self.assertEqual(expected, colour_rarity(cv2.imread(str(shots / name))), name)


class NewMarkerTest(unittest.TestCase):
    COLUMNS = (778, 904, 1030, 1156, 1282, 1408, 1534, 1660)
    ROWS = (207, 333, 459, 585, 711, 837)

    def frame_with_markers(self, cells):
        frame = np.full((1080, 1920, 3), (60, 40, 40), dtype=np.uint8)
        for row, column in cells:
            x, y = self.COLUMNS[column] + 42, self.ROWS[row] - 68
            cv2.rectangle(frame, (x + 4, y + 4), (x + 22, y + 22), (0, 150, 255), -1)
        return frame

    def test_contiguous_new_items_from_the_top_left(self):
        frame = self.frame_with_markers([(0, 0), (0, 1), (0, 2), (0, 3)])
        self.assertEqual(
            [(0, 0), (0, 1), (0, 2), (0, 3)],
            leading_new_cells(frame, self.COLUMNS, self.ROWS, cap=10),
        )

    def test_scan_stops_at_the_first_unmarked_cell_and_at_the_cap(self):
        frame = self.frame_with_markers([(0, 0), (0, 2)])
        self.assertEqual([(0, 0)], leading_new_cells(frame, self.COLUMNS, self.ROWS, cap=10))
        frame = self.frame_with_markers([(0, c) for c in range(8)] + [(1, 0)])
        self.assertEqual(9, len(leading_new_cells(frame, self.COLUMNS, self.ROWS, cap=10)))
        self.assertEqual(3, len(leading_new_cells(frame, self.COLUMNS, self.ROWS, cap=3)))

    def test_no_marker_means_nothing(self):
        frame = self.frame_with_markers([])
        self.assertEqual([], leading_new_cells(frame, self.COLUMNS, self.ROWS, cap=10))

    def test_live_bag_frames_if_available(self):
        # Both frames (star sort and newest-first sort) had one new item.
        for name in ("bn2.png", "so4.png"):
            path = Path(".local-dev/shots") / name
            if not path.exists():
                self.skipTest("live bag frames not present")
            frame = cv2.imread(str(path))
            self.assertGreater(new_marker_ratio(frame, (778, 207)), 0.2, name)
            self.assertEqual(
                [(0, 0)], leading_new_cells(frame, self.COLUMNS, self.ROWS, cap=10), name
            )

    def test_table_covers_the_live_items(self):
        stars = load_exclusive_stars()
        for name, star in (("掠夺之手", 4), ("卢戈制衬衫", 3), ("飞翅骷髅", 4),
                           ("J收藏品", 4), ("噬血者", 5), ("恋的头饰", 5)):
            self.assertEqual(star, stars.get(name), name)


if __name__ == "__main__":
    unittest.main()


class JunkTaskParsingTest(unittest.TestCase):
    def test_sort_labels(self):
        from types import SimpleNamespace as Box

        from src.tasks.JunkGearTask import active_sort_label

        self.assertEqual(
            "按星级从高到低排序",
            active_sort_label([Box(name="按星级从高到低排序↓"), Box(name="按获得时间排序")]),
        )
        self.assertEqual(
            "按获得时间从晚到早排序",
            active_sort_label([Box(name="按星级排序"), Box(name="按获得时间从晚到早排序▼")]),
        )


class JunkSafetyTest(unittest.TestCase):
    """Guards added after the 2026-09-26 stability review."""

    @staticmethod
    def _task():
        from types import SimpleNamespace

        from src.tasks.JunkGearTask import JunkGearTask

        task = object.__new__(JunkGearTask)
        task.name = "爛装强化分解"
        task.config = {}
        task.info = {}
        task.info_set = lambda key, value: task.info.__setitem__(key, value)
        task.log_info = lambda *a, **k: None
        task.log_warning = lambda *a, **k: task.info.setdefault("warnings", []).append(a[0])
        task.sleep = lambda *_a: None
        task._executor = SimpleNamespace()
        return task

    def test_cell_similarity_separates_same_and_other_items(self):
        from src.tasks.JunkGearTask import SELECTION_MATCH_MIN, cell_similarity

        rng = np.random.default_rng(7)
        first = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
        other = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
        self.assertGreater(cell_similarity(first, first.copy(), (0, 0)), 0.99)
        self.assertLess(cell_similarity(first, other, (0, 0)), SELECTION_MATCH_MIN)

    def test_wait_detail_needs_the_requested_state(self):
        task = self._task()
        states = iter([True, True, False])
        task._detail_open = lambda: next(states)
        self.assertTrue(task._wait_detail(False, timeout=60))
        task._detail_open = lambda: True
        self.assertFalse(task._wait_detail(False, timeout=0))

    def test_a_stale_popup_keeps_every_item(self):
        # The detail popup never closes: nothing is classified as junk.
        task = self._task()
        clicks = []
        task._click_reference = lambda x, y, after_sleep=0: clicks.append((x, y))
        task._wait_detail = lambda open_, timeout=0: open_
        self.assertEqual([], task._classify_cells([(0, 0), (0, 1)], {}))
        self.assertEqual([], clicks)

    def test_selection_is_cancelled_when_cells_moved(self):
        from src.tasks import JunkGearTask as module

        task = self._task()
        clicks = []
        task._click_reference = lambda x, y, after_sleep=0: clicks.append((x, y))
        task._selection_count = lambda: 0
        rng = np.random.default_rng(3)
        classified = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
        moved = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
        task.capture_frame = lambda: moved
        self.assertFalse(task._enhance_and_dismantle([(0, 0)], classified))
        # Only 一键强化 and 取消: no cell was selected.
        self.assertEqual(
            [module.ONE_CLICK_ENHANCE_POINT, module.SELECTION_CANCEL_POINT], clicks
        )

    def test_saved_sort_round_trip(self):
        import tempfile
        from unittest import mock

        from src.tasks import JunkGearTask as module

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "configs" / "junk_gear_sort.json"
            with mock.patch.object(module, "SORT_STATE_FILE", path):
                self.assertIsNone(module.JunkGearTask._saved_sort())
                module.JunkGearTask._save_sort("按星级从高到低排序")
                self.assertEqual("按星级从高到低排序", module.JunkGearTask._saved_sort())
                module.JunkGearTask._clear_saved_sort()
                self.assertIsNone(module.JunkGearTask._saved_sort())

    def test_unrestorable_saved_sort_stops_before_switching(self):
        from unittest import mock

        task = self._task()
        task._open_equipment_bag = lambda: True
        task._saved_sort = lambda: "按星级从高到低排序"
        task._restore_sort = lambda original: False
        task._switch_to_newest_first = mock.Mock()
        with mock.patch("src.tasks.JunkGearTask.load_exclusive_stars", return_value={}):
            self.assertFalse(task.run_claim())
        task._switch_to_newest_first.assert_not_called()

    def test_stop_mid_run_clicks_nothing_more(self):
        from unittest import mock

        from ok.task.exceptions import TaskDisabledException

        task = self._task()
        task._open_equipment_bag = lambda: True
        task._saved_sort = lambda: None
        task._clear_saved_sort = mock.Mock()
        task._switch_to_newest_first = lambda: "按星级从高到低排序"
        task._restore_sort = mock.Mock()

        def stop():
            raise TaskDisabledException()

        task.capture_frame = stop
        with mock.patch("src.tasks.JunkGearTask.load_exclusive_stars", return_value={}):
            with self.assertRaises(TaskDisabledException):
                task.run_claim()
        # The sort is restored on the next run from the saved file instead.
        task._restore_sort.assert_not_called()


class TitleParsingTest(unittest.TestCase):
    """Live 2026-09-27: 拉菲娜's SR E.P.G was kept as unreadable."""

    @staticmethod
    def _box(name, x):
        from types import SimpleNamespace

        return SimpleNamespace(name=name, x=x, y=340, width=60, height=24)

    def _parse(self, *boxes):
        from src.tasks.JunkGearTask import JunkGearTask

        name, rarity = JunkGearTask._name_and_rarity(list(boxes))
        return (name.name if name else None, rarity.name if rarity else None)

    def test_separate_boxes(self):
        parsed = self._parse(self._box("E.P.G", 500), self._box("SR", 580))
        self.assertEqual(("E.P.G", "SR"), parsed)

    def test_rarity_glued_to_the_name(self):
        self.assertEqual(("E.P.G", "SR"), self._parse(self._box("E.P.G SR", 500)))

    def test_rarity_touching_a_chinese_name(self):
        # Live 2K 2026-09-29: no space between the name and the italic R.
        self.assertEqual(("冰雪红宝石", "R"), self._parse(self._box("冰雪红宝石R X", 500)))
        self.assertEqual(("冰雪红宝石", "UR"), self._parse(self._box("冰雪红宝石UR", 500)))

    def test_stray_mark_after_the_rarity(self):
        parsed = self._parse(self._box("E.P.G", 500), self._box("SR X", 580))
        self.assertEqual(("E.P.G", "SR"), parsed)

    def test_no_rarity_stays_unreadable(self):
        self.assertEqual(("E.P.G", None), self._parse(self._box("E.P.G", 500)))


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "junk_gear"


class GridShortcutTest(unittest.TestCase):
    """User 2026-09-27: R/SR off the grid label; locked cells never touched."""

    def _placed(self, crop, box, cell=(0, 0)):
        from src.tasks.GearTasks import GRID_COLUMNS, GRID_ROWS

        frame = np.zeros((1080, 1920, 3), np.uint8)
        dx, dy, _w, _h = box
        x, y = GRID_COLUMNS[cell[1]] + dx, GRID_ROWS[cell[0]] + dy
        frame[y : y + crop.shape[0], x : x + crop.shape[1]] = crop
        return frame

    def test_live_labels(self):
        from src.utils.junk_gear import grid_label_rarity

        sr = cv2.imread(str(FIXTURES / "grid_label_sr.png"))
        ur = cv2.imread(str(FIXTURES / "grid_label_ur.png"))
        self.assertEqual("SR", grid_label_rarity(sr))  # beside golden gauntlet art
        self.assertEqual("UR", grid_label_rarity(ur))

    def test_live_padlock(self):
        from src.tasks.JunkGearTask import GRID_LOCK_SEARCH_BOX, grid_cell_locked

        on = cv2.imread(str(FIXTURES / "grid_lock_on.png"))
        off = cv2.imread(str(FIXTURES / "grid_lock_off.png"))
        self.assertTrue(grid_cell_locked(self._placed(on, GRID_LOCK_SEARCH_BOX), (0, 0)))
        self.assertFalse(grid_cell_locked(self._placed(off, GRID_LOCK_SEARCH_BOX), (0, 0)))

    def _task(self):
        from src.tasks.JunkGearTask import JunkGearTask

        task = object.__new__(JunkGearTask)
        task.config = {}
        task.info_set = lambda *a: None
        task.log_info = lambda *a, **k: None
        task.log_warning = lambda *a, **k: None
        task.clicks = []
        task._click_reference = lambda x, y, after_sleep=0: task.clicks.append((x, y))
        return task

    def test_locked_cell_is_never_clicked_or_dismantled(self):
        from unittest import mock

        task = self._task()
        with mock.patch("src.tasks.JunkGearTask.grid_cell_locked", return_value=True):
            self.assertEqual([], task._classify_cells([(0, 0)], {}, np.zeros((1080, 1920, 3))))
        self.assertEqual([], task.clicks)

    def test_grid_sr_is_junk_without_opening_it(self):
        from unittest import mock

        task = self._task()
        task._grid_rarity = lambda frame, cell: "SR"
        with mock.patch("src.tasks.JunkGearTask.grid_cell_locked", return_value=False):
            junk = task._classify_cells([(0, 0)], {}, np.zeros((1080, 1920, 3)))
        self.assertEqual([(0, 0)], junk)
        self.assertEqual([], task.clicks)

    def test_ur_or_unsure_is_opened_as_before(self):
        from unittest import mock

        task = self._task()
        task._grid_rarity = lambda frame, cell: None
        task._wait_detail = lambda open_, timeout=0: open_ is False or True
        opened = []
        task._read_detail = lambda: opened.append(1) or (None, "")
        task.sleep = lambda *a: None
        with mock.patch("src.tasks.JunkGearTask.grid_cell_locked", return_value=False):
            task._classify_cells([(0, 0)], {}, np.zeros((1080, 1920, 3)))
        self.assertTrue(opened)


class NewBadgeLabelTest(unittest.TestCase):
    """Live 2026-09-27: the yellow "!" beside a new item's label hid its R."""

    def test_labels_next_to_the_new_badge(self):
        from src.utils.junk_gear import grid_label_rarity

        r_new = cv2.imread(str(FIXTURES / "grid_label_r_new.png"))
        ur_new = cv2.imread(str(FIXTURES / "grid_label_ur_new.png"))
        self.assertEqual("R", grid_label_rarity(r_new))
        self.assertEqual("UR", grid_label_rarity(ur_new))

    def test_ocr_with_the_badge_glued_on(self):
        from src.tasks.JunkGearTask import grid_label_text_matches

        self.assertTrue(grid_label_text_matches("R!", "R"))
        self.assertTrue(grid_label_text_matches("RI", "R"))
        self.assertTrue(grid_label_text_matches("SR 1", "SR"))
        self.assertFalse(grid_label_text_matches("UR", "R"))
        self.assertFalse(grid_label_text_matches("UR", "SR"))
        self.assertFalse(grid_label_text_matches("", "R"))


class SortMenuSearchTest(unittest.TestCase):
    """Live 2026-09-28 at 1080p: 6-notch jumps skipped the middle option."""

    def test_small_steps_find_an_option_in_the_middle(self):
        from types import SimpleNamespace

        from src.tasks.JunkGearTask import JunkGearTask

        pages = [["按获得时间"], ["按星级"], ["按强化从高到低排序"], ["按套装"], ["按套装"]]
        position = [0]
        task = object.__new__(JunkGearTask)
        task._sort_menu_boxes = lambda: [SimpleNamespace(name=n) for n in pages[position[0]]]
        task._boxes_text = lambda boxes: " ".join(b.name for b in boxes)

        def scroll(_point, notches, **_kwargs):
            step = 1 if notches > 0 else -1
            position[0] = max(0, min(len(pages) - 1, position[0] + step))

        task.scroll_client = scroll
        boxes = task._find_sort_option("按强化从")
        self.assertEqual("按强化从高到低排序", boxes[0].name)


class GridLabelCertaintyTest(unittest.TestCase):
    """Leo 2026-09-30: R/SR are judged on the grid without opening them."""

    @staticmethod
    def _label(*hues):
        import cv2
        import numpy as np

        # One vertical stripe per hue (OpenCV hue 0-179), full saturation/value.
        stripes = [np.full((32, 12, 3), (h, 255, 255), np.uint8) for h in hues]
        return cv2.cvtColor(np.hstack(stripes), cv2.COLOR_HSV2BGR)

    def test_pure_blue_is_certainly_r(self):
        from src.utils.junk_gear import grid_label_colour_certain

        self.assertTrue(grid_label_colour_certain(self._label(110, 112, 108), "R"))
        self.assertFalse(grid_label_colour_certain(self._label(110, 112, 108), "SR"))

    def test_pure_purple_is_certainly_sr(self):
        from src.utils.junk_gear import grid_label_colour_certain

        self.assertTrue(grid_label_colour_certain(self._label(140, 145, 150), "SR"))

    def test_any_green_is_never_certain(self):
        from src.utils.junk_gear import grid_label_colour_certain

        # A UR gradient: green, blue and purple bands.
        self.assertFalse(grid_label_colour_certain(self._label(60, 110, 140), "R"))
        self.assertFalse(grid_label_colour_certain(self._label(110, 110, 110, 110, 110, 60), "R"))

    def test_cyan_tinted_r_at_2k(self):
        from src.utils.junk_gear import grid_label_colour_certain, grid_label_rarity

        # Live 2K: R letters span hue 90-109 (the old 35-95 green band made
        # every R unsure).
        cyan_r = self._label(92, 97, 102, 106, 106, 106)
        self.assertEqual("R", grid_label_rarity(cyan_r))
        self.assertTrue(grid_label_colour_certain(cyan_r, "R"))

    def test_ur_gradient_or_green_n_is_never_r(self):
        from src.utils.junk_gear import grid_label_colour_certain, grid_label_rarity

        gradient = self._label(40, 70, 90, 100, 105, 110, 130, 150)
        self.assertNotIn(grid_label_rarity(gradient), ("R", "SR"))
        self.assertFalse(grid_label_colour_certain(gradient, "R"))
        green_n = self._label(60, 62, 65)
        self.assertNotIn(grid_label_rarity(green_n), ("R", "SR"))
        self.assertFalse(grid_label_colour_certain(green_n, "R"))

    def test_live_2k_labels(self):
        from src.utils.junk_gear import grid_label_colour_certain, grid_label_rarity

        # 珍藏集 at 2560x1440 resized to 1080 like the bag frame (2026-09-30).
        r = cv2.imread(str(FIXTURES / "grid_label_r_2k.png"))
        sr = cv2.imread(str(FIXTURES / "grid_label_sr_2k.png"))
        ur = cv2.imread(str(FIXTURES / "grid_label_ur_2k.png"))
        self.assertEqual("R", grid_label_rarity(r))
        self.assertTrue(grid_label_colour_certain(r, "R"))
        self.assertEqual("SR", grid_label_rarity(sr))
        self.assertTrue(grid_label_colour_certain(sr, "SR"))
        self.assertEqual("UR", grid_label_rarity(ur))
        self.assertFalse(grid_label_colour_certain(ur, "R"))
        self.assertFalse(grid_label_colour_certain(ur, "SR"))

    def test_u_in_the_read_blocks_the_colour_shortcut(self):
        from src.utils.junk_gear import label_text_looks_ur

        self.assertTrue(label_text_looks_ur("UR"))
        self.assertTrue(label_text_looks_ur("JR!"))
        self.assertFalse(label_text_looks_ur(""))
        self.assertFalse(label_text_looks_ur("R!"))
        self.assertFalse(label_text_looks_ur("SR"))


class LoneDigitsTest(unittest.TestCase):
    def test_letters_read_for_a_lone_digit(self):
        from src.tasks.enhance_dialog import lone_digits

        # Live 2K 2026-09-30: 已选择装备 "4" read as "a".
        self.assertEqual("4", lone_digits("a"))
        self.assertEqual("10", lone_digits("lO"))
        self.assertEqual("7", lone_digits("7"))
        self.assertEqual("强化", lone_digits("强化"))
        self.assertEqual("abcd", lone_digits("abcd"))
