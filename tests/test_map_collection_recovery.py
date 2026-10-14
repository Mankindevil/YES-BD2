"""Regression coverage for the 2026-10-10 beginner teleport-page failure."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np

from src.tasks.map_trade.models import CollectionResult, MapPageMode, NavigationResult, ScreenState
from src.tasks.map_trade.navigator import Navigator
from src.tasks.map_trade.navigator_constants import MapPageDetection
from src.tasks.map_trade.vision import Vision
from src.tasks.MapCollectionTask import MapCollectionTask


class BeginnerMapTest(unittest.TestCase):
    def test_chapter18_transit_map_reaches_structural_checks_and_can_be_closed(self):
        # Live 2026-10-14: this exact OCR header was rejected before any
        # footer/template checks because it is not a collection target.
        from src.tasks.map_trade.models import STORY_NAVIGATION_ONLY_MAP_TITLES

        frame = np.zeros((1440, 2560, 3), np.uint8)
        text = {"地图页面左上标题": "安全 科库托斯暗黑神殿 普通 ?",
                "箱庭大地图底部控件": "在战场中查看 探索 世界地图"}
        task = SimpleNamespace(info_set=Mock(), operate_click=Mock())
        nav = Navigator(task, SimpleNamespace(
            capture=lambda: frame, simplify=lambda s: s,
            match=lambda *_: None, passes=lambda *_: False,
            ocr_text=lambda _frame, label, **kw: text[label]))
        nav._map_page_template_signal = lambda _f, spec: (True, spec.name)
        nav._wait_for_current_sandbox = lambda **kw: NavigationResult(True, ScreenState.SANDBOX)
        for title in STORY_NAVIGATION_ONLY_MAP_TITLES:
            text["地图页面左上标题"] = f"安全 {title} 普通 ?"
            with self.subTest(title=title):
                self.assertEqual(MapPageMode.SANDBOX_LARGE_MAP,
                                 nav._detect_map_page_mode(frame).mode)
                self.assertIsNone(nav._collection_location_from_header(text["地图页面左上标题"]))
        text["地图页面左上标题"] = "安全 科库托斯暗黑神殿 普通 ?"
        self.assertTrue(nav._restore_field_after_map_failure().success)
        task.operate_click.assert_called_once()

        # A title alone still cannot authorize a map-close click.
        task.operate_click.reset_mock()
        text["箱庭大地图底部控件"] = "探索"
        result = nav._close_confirmed_map_page({MapPageMode.SANDBOX_LARGE_MAP})
        self.assertFalse(result.success)
        task.operate_click.assert_not_called()
        text["箱庭大地图底部控件"] = "在战场中查看 探索 世界地图"
        nav._map_page_template_signal = lambda _f, spec: (False, spec.name)
        self.assertEqual(MapPageMode.UNKNOWN, nav._detect_map_page_mode(frame).mode)

    def test_childroom_failure_frame_uses_physical_portal_route(self):
        path = Path(__file__).parent / "fixtures/map_trade/map_pages/generate_childroom.png"
        frame = cv2.imread(str(path))
        self.assertIsNotNone(frame)
        events = []
        task = SimpleNamespace(config={}, info_set=lambda *_: None)
        vision = Vision(task)
        vision.capture = lambda: frame
        vision.ocr_text = lambda _frame, label, **_kwargs: (
            "移动魔法阵 初级" if label == "地图页面左上标题" else "安全儿童房"
        )
        navigator = Navigator(task, vision)
        detected = navigator._detect_map_page_mode(frame)
        navigator.open_teleport_map_from_sandbox = lambda: NavigationResult(
            True,
            ScreenState.AREA_MAP,
            map_page_mode=detected.mode,
        )
        navigator._close_confirmed_map_page = lambda _modes: (
            events.append("close") or NavigationResult(True, ScreenState.SANDBOX)
        )
        navigator._walk_to_sandbox_teleport_interaction = lambda: (
            events.append("walk")
            or NavigationResult(
                True,
                ScreenState.AREA_MAP,
                map_page_mode=MapPageMode.DIRECT_TELEPORT,
            )
        )
        result = navigator._open_teleport_map_anywhere()
        self.assertTrue(result.success)
        self.assertEqual(MapPageMode.DIRECT_TELEPORT, result.map_page_mode)
        self.assertEqual(["close", "walk"], events)

    def test_unpageable_skill_map_is_closed_before_physical_portal_fallback(self):
        navigator = self.navigator_on_page(MapPageDetection(MapPageMode.GENERATE_TELEPORT))
        events = []
        navigator.open_teleport_map_from_sandbox = lambda: NavigationResult(
            True,
            ScreenState.AREA_MAP,
            map_page_mode=MapPageMode.GENERATE_TELEPORT,
        )
        navigator._optional_match = lambda *_: None
        navigator._close_confirmed_map_page = lambda _modes: (
            events.append("close") or NavigationResult(True, ScreenState.SANDBOX)
        )
        navigator._walk_to_sandbox_teleport_interaction = lambda: (
            events.append("walk")
            or NavigationResult(
                True,
                ScreenState.AREA_MAP,
                map_page_mode=MapPageMode.DIRECT_TELEPORT,
            )
        )
        result = navigator._open_teleport_map_anywhere()
        self.assertTrue(result.success)
        self.assertEqual(MapPageMode.DIRECT_TELEPORT, result.map_page_mode)
        self.assertEqual(["close", "walk"], events)

    def test_failure_frame_has_generate_identity_even_without_arrow_matches(self):
        path = Path(__file__).parent / "fixtures/map_trade/map_pages/generate_beginner.png"
        frame = cv2.imread(str(path))
        self.assertIsNotNone(frame)
        for height in (720, 1080, 1440, 2160):
            with self.subTest(height=height):
                replay = cv2.resize(frame, (height * 16 // 9, height))
                task = SimpleNamespace(config={}, info_set=lambda *_: None)
                vision = Vision(task)
                # OCR text was read from this exact frame in the live log;
                # image template matching remains real at every resolution.
                vision.ocr_text = lambda _frame, label, **_kw: (
                    "移动魔法阵 初级" if label == "地图页面左上标题" else "安全 阿尔卡迪亚居住区域"
                )
                detection = Navigator(task, vision)._detect_map_page_mode(replay)
                self.assertEqual(MapPageMode.GENERATE_TELEPORT, detection.mode)

    def test_skill_rank_is_not_a_requirement_but_page_evidence_is(self):
        frame = np.zeros((1080, 1920, 3), np.uint8)
        text = {
            "地图页面左上标题": "移动魔法阵 初级",
            "传送阵页面底部标签": "安全 阿尔卡迪亚居住区域",
        }
        navigator = Navigator(
            SimpleNamespace(info_set=lambda *_: None),
            SimpleNamespace(simplify=lambda s: s, ocr_text=lambda _f, label, **_kw: text[label]),
        )
        signals = {"技能生成页图标"}
        navigator._map_page_template_signal = lambda _f, spec: (spec.name in signals, spec.name)
        for rank in ("初级", "中级", "高级", "传说", ""):
            text["地图页面左上标题"] = f"移动魔法阵 {rank}"
            self.assertEqual(
                MapPageMode.GENERATE_TELEPORT, navigator._detect_map_page_mode(frame).mode
            )
        signals.add("交互直传页图标")
        self.assertEqual(MapPageMode.UNKNOWN, navigator._detect_map_page_mode(frame).mode)
        signals.remove("交互直传页图标")
        text["传送阵页面底部标签"] = ""
        self.assertEqual(MapPageMode.UNKNOWN, navigator._detect_map_page_mode(frame).mode)
        text["地图页面左上标题"] = "技能说明 初级"
        self.assertEqual(MapPageMode.UNKNOWN, navigator._detect_map_page_mode(frame).mode)

    def navigator_on_page(self, detection):
        navigator = Navigator(SimpleNamespace(), SimpleNamespace(capture=lambda: None))
        navigator._detect_map_page_mode = lambda _: detection
        navigator._status = lambda *_: None
        return navigator

    def test_retry_closes_existing_map_before_looking_for_field_navigation(self):
        navigator = self.navigator_on_page(MapPageDetection(MapPageMode.GENERATE_TELEPORT))
        events = []
        navigator.open_teleport_map_from_sandbox = lambda: NavigationResult(
            False, ScreenState.UNKNOWN
        )
        navigator._close_confirmed_map_page = lambda modes: (
            events.append(("close", modes)) or NavigationResult(True, ScreenState.SANDBOX)
        )
        navigator._walk_to_sandbox_teleport_interaction = lambda: (
            events.append("walk") or NavigationResult(True, ScreenState.AREA_MAP)
        )
        self.assertTrue(navigator._open_teleport_map_anywhere().success)
        self.assertEqual([("close", {MapPageMode.GENERATE_TELEPORT}), "walk"], events)

    def test_retry_stops_if_map_cannot_be_closed_or_identified(self):
        for mode in (MapPageMode.GENERATE_TELEPORT, MapPageMode.UNKNOWN):
            with self.subTest(mode=mode):
                navigator = self.navigator_on_page(
                    MapPageDetection(mode, header_text="移动魔法阵 初级")
                )
                navigator.open_teleport_map_from_sandbox = lambda: NavigationResult(
                    False, ScreenState.UNKNOWN
                )
                navigator._close_confirmed_map_page = lambda _: NavigationResult(
                    False, ScreenState.AREA_MAP
                )
                navigator._walk_to_sandbox_teleport_interaction = Mock()
                navigator._travel_to_hunting_ground = Mock()
                self.assertFalse(navigator._open_teleport_map_anywhere().success)
                navigator._walk_to_sandbox_teleport_interaction.assert_not_called()
                navigator._travel_to_hunting_ground.assert_not_called()

    def test_restart_closes_map_before_minimap_and_stops_if_close_fails(self):
        for success in (True, False):
            navigator = self.navigator_on_page(MapPageDetection(MapPageMode.GENERATE_TELEPORT))
            events = []
            navigator._close_confirmed_map_page = lambda _: (
                events.append("close") or NavigationResult(success, ScreenState.SANDBOX)
            )
            navigator.ensure_small_minimap = lambda: events.append("minimap") or False
            self.assertFalse(
                navigator.prepare_collection_main_area("Q_sp14", via_hunting_ground=True).success
            )
            self.assertEqual(["close", "minimap"] if success else ["close"], events)

    def test_unrecognized_screen_must_confirm_field_before_retry(self):
        navigator = self.navigator_on_page(MapPageDetection(MapPageMode.UNKNOWN))
        navigator._wait_for_current_sandbox = Mock(
            return_value=NavigationResult(False, ScreenState.UNKNOWN)
        )
        self.assertFalse(navigator._restore_field_after_map_failure().success)
        navigator._wait_for_current_sandbox.assert_called_once()


class CollectionOutcomeTest(unittest.TestCase):
    def test_insufficient_card_budget_keeps_specific_reason_in_final_status(self):
        task = object.__new__(MapCollectionTask)
        task.config = {"执行地图采集": True}
        statuses = {}
        task.info_set = statuses.__setitem__
        task.log_info = Mock()
        task.log_completion = Mock()
        navigator = SimpleNamespace(return_home=lambda: NavigationResult(True, ScreenState.HOME))
        reason = "吸收还剩2次，Q_sp7剩余3张地图需要3次；未达到每日上限"
        result = CollectionResult(True, deferred=True, message=reason)
        self.assertTrue(task._run_phases(
            navigator, (("地图采集", "执行地图采集", lambda: result),)))
        self.assertEqual("-", statuses["完成"])
        self.assertEqual("地图采集", statuses["待次日继续"])
        self.assertIn(reason, statuses["状态"])
        self.assertNotIn("已用尽", statuses["状态"])

    def test_depleted_run_is_daily_success_with_deferred_maps_not_full_completion(self):
        for depleted in (True, False):
            with self.subTest(depleted=depleted):
                task = object.__new__(MapCollectionTask)
                task.config = {"执行地图采集": True}
                statuses = {}
                task.info_set = statuses.__setitem__
                task.log_info = Mock()
                task.log_completion = Mock()
                navigator = SimpleNamespace(
                    return_home=lambda: NavigationResult(True, ScreenState.HOME)
                )
                result = CollectionResult(True, depleted=depleted)
                self.assertTrue(
                    task._run_phases(navigator, (("地图采集", "执行地图采集", lambda: result),))
                )
                if depleted:
                    self.assertEqual("-", statuses["完成"])
                    self.assertEqual("地图采集", statuses["待次日继续"])
                    self.assertIn("待次日继续", statuses["状态"])
                    self.assertNotIn("所有已开启流程完成", task.log_completion.call_args.args[0])
                else:
                    self.assertEqual("地图采集", statuses["完成"])
                    self.assertEqual("-", statuses["待次日继续"])
                    self.assertEqual("跑图完成。", statuses["状态"])

    def test_return_home_failure_is_still_failure_when_quota_is_exhausted(self):
        task = object.__new__(MapCollectionTask)
        task.config = {"执行地图采集": True}
        statuses = {}
        task.info_set = statuses.__setitem__
        task.log_info = Mock()
        task.log_warning = Mock()
        task.log_completion = Mock()
        task._save_diagnostic = Mock()
        task._recover_home_after_trade = lambda: False
        navigator = SimpleNamespace(
            return_home=lambda: NavigationResult(False, ScreenState.UNKNOWN)
        )
        self.assertFalse(
            task._run_phases(
                navigator,
                (("地图采集", "执行地图采集", lambda: CollectionResult(True, depleted=True)),),
            )
        )
        self.assertEqual("返回章节主页", statuses["失败"])
        task.log_completion.assert_not_called()


if __name__ == "__main__":
    unittest.main()
