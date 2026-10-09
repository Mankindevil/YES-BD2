import hashlib
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from ok.task.exceptions import TaskDisabledException
from PIL import Image

from src.tasks import TradeFavoritesTask as task_module
from src.tasks.map_trade.data import SHOP_CARTRIDGE_ORDER, SHOP_FAVORITE_POINTS
from src.tasks.map_trade.favorite_guide import (
    GUIDE_DIR,
    GUIDE_SHOPS,
    INCLUDE_ZERO,
    PROFILE_KEY,
    PROFILES,
    PROFIT_ONLY,
    TASK_NAME,
    favorite_count,
)
from src.tasks.map_trade.models import NavigationResult, ScreenState
from src.tasks.map_trade.trader import Trader
from src.tasks.map_trade.vision import Vision


class GuideArchiveTest(unittest.TestCase):
    def test_counts_coverage_and_zero_profit_slots(self):
        self.assertEqual(tuple(GUIDE_SHOPS), SHOP_CARTRIDGE_ORDER)
        self.assertEqual([favorite_count(p) for p in PROFILES], [195, 205])
        self.assertEqual(sum(len(s.zero_profit_slots) for s in GUIDE_SHOPS.values()), 10)
        for shop in GUIDE_SHOPS.values():
            self.assertTrue(set(shop.gray_slots) <= shop.present_slots)
            self.assertTrue(set(shop.zero_profit_slots) <= shop.favorite_slots(INCLUDE_ZERO))
        self.assertIn(4, GUIDE_SHOPS["R7"].favorite_slots(PROFIT_ONLY))
        self.assertNotIn(4, GUIDE_SHOPS["E1"].favorite_slots(INCLUDE_ZERO))
        with self.assertRaises(ValueError):
            favorite_count("invalid")

    def test_all_images_have_source_hash_and_local_markdown_link(self):
        manifest = json.loads((GUIDE_DIR / "source.json").read_text(encoding="utf-8"))
        markdown = (GUIDE_DIR / "README.md").read_text(encoding="utf-8")
        self.assertEqual(len(manifest["images"]), 33)
        self.assertEqual(
            {entry["id"] for entry in manifest["images"]},
            set(GUIDE_SHOPS) | {"buy-profit", "buy-achievement"},
        )
        for entry in manifest["images"]:
            path = GUIDE_DIR / entry["file"]
            self.assertIn(f'({entry["file"]})', markdown)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
            with Image.open(path) as image:
                self.assertEqual(image.size, (1600, 900))

    def test_real_recognizer_matches_every_archived_star(self):
        trader = object.__new__(Trader)
        trader.task = SimpleNamespace(config={}, info_set=lambda *_: None)
        trader.favorite_guide_profile = INCLUDE_ZERO
        trader.vision = Vision(trader.task)
        for shop_id, shop in GUIDE_SHOPS.items():
            with Image.open(GUIDE_DIR / "images" / f"{shop_id}.png") as image:
                frame = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
            for width, height in ((1600, 900), (1920, 1080), (2560, 1440)):
                scaled = cv2.resize(frame, (width, height))
                states = {
                    slot: trader._star_state(scaled, slot, point)
                    for slot, point in SHOP_FAVORITE_POINTS.items()
                }
                with self.subTest(shop=shop_id, size=(width, height)):
                    self.assertEqual(
                        {slot for slot, state in states.items() if state is not None},
                        shop.present_slots,
                    )
                    self.assertEqual(
                        {slot for slot, state in states.items() if state == "yellow"},
                        shop.favorite_slots(INCLUDE_ZERO),
                    )


class FavoriteAlignmentTest(unittest.TestCase):
    def trader(self, shop_id="R1", profile=PROFIT_ONLY):
        trader = object.__new__(Trader)
        states = {slot: "gray" for slot in GUIDE_SHOPS[shop_id].present_slots}
        clicked = []

        def click(x, y, **_kwargs):
            slot = next(slot for slot, point in SHOP_FAVORITE_POINTS.items() if point == (x, y))
            clicked.append(slot)
            states[slot] = "gray" if states[slot] == "yellow" else "yellow"

        trader.task = SimpleNamespace(
            info_set=lambda *_: None, log_warning=Mock(), sleep=lambda *_: None,
            operate_click=click,
        )
        trader.vision = SimpleNamespace(capture=lambda: None)
        trader._star_state = lambda _frame, slot, _point: states.get(slot)
        trader._wait_for_gray_star = lambda slot, _point: states.get(slot) == "gray"
        trader._wait_for_yellow_star = lambda slot, _point: states.get(slot) == "yellow"
        trader.favorite_guide_profile = profile
        return trader, states, clicked

    def test_every_profile_is_idempotent_and_switching_removes_zero_profit(self):
        for shop_id in GUIDE_SHOPS:
            trader, states, clicked = self.trader(shop_id, INCLUDE_ZERO)
            for profile in (INCLUDE_ZERO, PROFIT_ONLY, INCLUDE_ZERO):
                with self.subTest(shop=shop_id, profile=profile):
                    trader.favorite_guide_profile = profile
                    self.assertTrue(trader._align_unfavorited_points(shop_id))
                    self.assertEqual(
                        {s for s, value in states.items() if value == "yellow"},
                        GUIDE_SHOPS[shop_id].favorite_slots(profile),
                    )
                    clicked.clear()
                    self.assertTrue(trader._align_unfavorited_points(shop_id))
                    self.assertEqual(clicked, [])

    def test_missing_or_extra_product_stops_before_any_click(self):
        for mismatch in ("missing", "extra"):
            trader, states, clicked = self.trader()
            if mismatch == "missing":
                del states[3]
            else:
                states[8] = "gray"
            self.assertFalse(trader._align_unfavorited_points("R1"))
            self.assertEqual(clicked, [])
            trader.task.log_warning.assert_called_once()

    def test_disappearing_star_and_false_positive_toast_cannot_mark_success(self):
        trader, states, _ = self.trader()
        trader.task.operate_click = lambda *_args, **_kwargs: states.pop(1, None)
        trader._wait_for_yellow_star = lambda *_: True
        self.assertFalse(trader._align_unfavorited_points("R1"))


class FavoritesTaskTest(unittest.TestCase):
    def run_task(self, profile=PROFIT_ONLY, *, entered=True, rebuilt=True, stopped=False):
        task = object.__new__(task_module.TradeFavoritesTask)
        task.config = {PROFILE_KEY: profile}
        task.info_set = Mock()
        task.log_completion = Mock()
        task.log_warning = Mock()
        task._save_diagnostic = Mock()
        navigator = Mock()
        navigator.enter_q_sp6_buy_flow.return_value = NavigationResult(entered, ScreenState.SHOP)
        navigator.return_home.return_value = NavigationResult(True, ScreenState.HOME)
        progress = Mock()
        trader = Mock(spec=["rebuild_favorites", "favorite_guide_profile"])
        trader.rebuild_favorites.return_value = rebuilt
        if stopped:
            trader.rebuild_favorites.side_effect = TaskDisabledException()
        with (
            patch.object(task_module, "Vision"),
            patch.object(task_module, "Navigator", return_value=navigator),
            patch.object(task_module, "ProgressStore", return_value=progress) as store,
            patch.object(task_module, "Trader", return_value=trader),
        ):
            if stopped:
                with self.assertRaises(TaskDisabledException):
                    task.run()
                result = None
            else:
                result = task.run()
        navigator.enter_q_sp6_buy_flow.assert_called_once_with(bargain=False)
        store.assert_called_once_with(Path("configs") / "trade_favorites_progress.json")
        progress.clear_favorite_cards.assert_called_once_with()
        return result, navigator, trader, task

    def test_setup_never_calls_purchase_and_honors_both_profiles(self):
        for profile in PROFILES:
            result, navigator, trader, task = self.run_task(profile)
            self.assertTrue(result)
            self.assertEqual(trader.favorite_guide_profile, profile)
            trader.rebuild_favorites.assert_called_once_with()
            navigator.return_home.assert_called_once_with()
            task.log_completion.assert_called_once()

    def test_failed_entry_does_not_touch_favorites(self):
        result, _, trader, _ = self.run_task(entered=False)
        self.assertFalse(result)
        trader.rebuild_favorites.assert_not_called()

    def test_partial_failure_is_not_reported_complete(self):
        result, _, _, task = self.run_task(rebuilt=False)
        self.assertFalse(result)
        task.log_completion.assert_not_called()

    def test_stop_does_not_return_home_or_report_complete(self):
        _, navigator, _, task = self.run_task(stopped=True)
        navigator.return_home.assert_not_called()
        task.log_completion.assert_not_called()


class FavoritePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_lazy_loaded_form_changes_setup_task_and_start_uses_that_task(self):
        from src.ui.shell import trade

        task = task_module.TradeFavoritesTask(SimpleNamespace(scene=None), SimpleNamespace())
        task.config = dict(task.default_config)
        with patch.object(trade.data, "task_by_name", return_value=None):
            page = trade.TradePage()
            page._refresh_favorites()
            self.assertFalse(page.favorites_button.isEnabled())
        self.addCleanup(page.deleteLater)
        with (
            patch.object(
                trade.data, "task_by_name",
                side_effect=lambda name: task if name == TASK_NAME else None,
            ),
            patch.object(trade.actions, "can_start", return_value=True),
            patch.object(trade.actions, "start", return_value=True) as start,
        ):
            page._refresh_favorites()
            self.assertTrue(page.favorites_button.isEnabled())
            self.assertIs(page.favorites_form.task, task)
            from src.ui.shell.widgets import Segmented

            control = page.favorites_form._rows[PROFILE_KEY][1]
            self.assertIsInstance(control, Segmented)
            control._buttons[INCLUDE_ZERO].click()
            self.assertEqual(task.config[PROFILE_KEY], INCLUDE_ZERO)
            page._start_favorites()
            start.assert_called_once_with(task, page.window())
        with (
            patch.object(trade.data, "task_by_name", return_value=task),
            patch.object(trade.data, "current_task", return_value=task),
            patch.object(trade.actions, "can_start", return_value=False),
        ):
            page._refresh_favorites()
            self.assertFalse(page.favorites_button.isEnabled())
            self.assertFalse(page.favorites_form.isEnabled())


if __name__ == "__main__":
    unittest.main()
