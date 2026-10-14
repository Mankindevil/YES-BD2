"""Reuse only a freshly confirmed field location and preserve navigation fallback."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.tasks.BaseBD2Task import BaseBD2Task
from src.tasks.MapCollectionTask import MapCollectionTask
from src.tasks.map_trade.card_status import (
    CollectionCardSelectionOutcome,
    CollectionCardSelectionResult,
)
from src.tasks.map_trade.collector import Collector
from src.tasks.map_trade.models import CARD_BY_ID, NavigationResult, ScreenState
from src.tasks.map_trade.navigator import Navigator
from src.tasks.map_trade.progress import UTC_PLUS_8, ProgressStore


class CurrentScreenStartTest(unittest.TestCase):
    def test_home_guard_reuses_only_opted_in_screen(self):
        for usable in (True, False):
            task = SimpleNamespace(
                can_start_from_current_screen=lambda: usable,
                info_set=Mock(), log_warning=Mock(),
            )
            with patch("src.tasks.recovery.recover_to_home", return_value=True) as home:
                self.assertTrue(BaseBD2Task._go_home_before_run(task))
                self.assertEqual(0 if usable else 1, home.call_count)

    def test_start_check_never_swallows_stop(self):
        from ok.task.exceptions import TaskDisabledException

        task = SimpleNamespace(
            can_start_from_current_screen=Mock(side_effect=TaskDisabledException()),
        )
        with self.assertRaises(TaskDisabledException):
            BaseBD2Task._go_home_before_run(task)

    def test_collection_accepts_only_navigation_pages(self):
        accepted = {ScreenState.SANDBOX, ScreenState.CARD_MENU,
                    ScreenState.AREA_MAP, ScreenState.SANDBOX_MAP}
        for state in ScreenState:
            with self.subTest(state=state), patch(
                "src.tasks.MapCollectionTask.Vision"
            ), patch("src.tasks.MapCollectionTask.Navigator") as navigator:
                navigator.return_value.classify.return_value = state
                task = SimpleNamespace(info_set=Mock())
                self.assertEqual(state in accepted,
                                 MapCollectionTask.can_start_from_current_screen(task))


class CurrentLocationTest(unittest.TestCase):
    def navigator(self, state=ScreenState.SANDBOX):
        nav = Navigator(SimpleNamespace(info_set=Mock()), SimpleNamespace(capture=Mock()))
        nav.classify = Mock(return_value=state)
        nav.ensure_small_minimap = Mock(return_value=True)
        nav._walk_flags = Mock(return_value=(False, False))
        nav._open_field_map = Mock(return_value="战斗Ⅱ 卢戈森林深处")
        nav._field_map_header = Mock(return_value="战斗Ⅱ 卢戈森林深处")
        nav._close_confirmed_map_page = Mock(
            return_value=NavigationResult(True, ScreenState.SANDBOX))
        nav._restore_field_after_map_failure = Mock(
            return_value=NavigationResult(True, ScreenState.SANDBOX))
        return nav

    def test_header_needs_known_unique_map_and_area_prefix(self):
        for header, expected in (
            ("战斗Ⅱ 卢戈森林深处", ("Q_sp1", "battle_area_2")),
            ("安全 阿尔卡迪亚居住区域", ("Q_sp14", "main_area")),
            ("卢戈森林深处", None), ("安全 未知地图", None),
        ):
            with self.subTest(header=header):
                self.assertEqual(expected, Navigator._collection_location_from_header(header))

    def test_current_map_requires_two_matching_reads_and_return_to_field(self):
        nav = self.navigator()
        self.assertEqual(("Q_sp1", "battle_area_2"), nav.current_collection_location())
        nav._field_map_header.return_value = "安全 卢戈镇"
        self.assertIsNone(nav.current_collection_location())
        nav._field_map_header.return_value = "战斗Ⅱ 卢戈森林深处"
        nav._close_confirmed_map_page.return_value = NavigationResult(False, ScreenState.AREA_MAP)
        self.assertIsNone(nav.current_collection_location())

    def test_open_map_preview_is_closed_before_reading_actual_location(self):
        nav = self.navigator(ScreenState.AREA_MAP)
        events = Mock()
        events.attach_mock(nav._restore_field_after_map_failure, "restore")
        events.attach_mock(nav._open_field_map, "open")
        self.assertEqual(("Q_sp1", "battle_area_2"), nav.current_collection_location())
        self.assertEqual(["restore", "open"], [call[0] for call in events.mock_calls])
        nav._restore_field_after_map_failure.return_value = NavigationResult(False, ScreenState.AREA_MAP)
        nav._open_field_map.reset_mock()
        self.assertIsNone(nav.current_collection_location())
        nav._open_field_map.assert_not_called()

    def test_moving_or_unknown_screen_is_not_reused(self):
        for state, flags in ((ScreenState.UNKNOWN, (False, False)),
                             (ScreenState.SANDBOX, (True, False)),
                             (ScreenState.SANDBOX, (False, True))):
            nav = self.navigator(state)
            nav._walk_flags.return_value = flags
            self.assertIsNone(nav.current_collection_location())
            nav._open_field_map.assert_not_called()

    def test_same_card_is_reused_but_other_card_uses_selection(self):
        nav = self.navigator()
        nav._locate_story_card = Mock(return_value=NavigationResult(False, ScreenState.CARD_MENU))
        self.assertTrue(nav.select_collection_card("Q_sp1").success)
        nav._locate_story_card.assert_not_called()
        self.assertFalse(nav.select_collection_card("Q_sp2").success)
        nav._locate_story_card.assert_called_once_with("Q_sp2")

    def test_field_card_switch_uses_quick_switch_before_home_fallback(self):
        for succeeds in (True, False):
            nav = self.navigator()
            nav._menu_still_confirmed = Mock(return_value=False)
            nav.open_story_quick_switcher_from_sandbox = Mock(
                return_value=NavigationResult(succeeds, ScreenState.CARD_MENU))
            nav.return_home = Mock(return_value=NavigationResult(True, ScreenState.HOME))
            nav._open_story_quick_switcher = Mock(
                return_value=NavigationResult(True, ScreenState.CARD_MENU))
            nav._wait_for_story_badge_with_scroll = Mock(return_value=None)
            nav._locate_story_card("Q_sp1")
            nav.open_story_quick_switcher_from_sandbox.assert_called_once_with(category="story")
            self.assertEqual(0 if succeeds else 1, nav.return_home.call_count)
            self.assertEqual(0 if succeeds else 1, nav._open_story_quick_switcher.call_count)


class CurrentCardPriorityTest(unittest.TestCase):
    def run_from_current(self, *, allowed="全部", done=False):
        from src.tasks.map_trade.collector_constants import SkillExecutionResult

        events = []
        with tempfile.TemporaryDirectory() as temp_dir:
            progress = ProgressStore(Path(temp_dir) / "progress.json",
                                     lambda: datetime(2026, 10, 12, 12, tzinfo=UTC_PLUS_8))
            progress.load()
            if done:
                progress.mark_card_complete_from_badge("Q_sp2")
            task = SimpleNamespace(config={"跑图章节": allowed}, info_set=Mock(), log_warning=Mock())
            nav = SimpleNamespace(
                current_collection_location=lambda: ("Q_sp2", "battle_area_1"),
                select_collection_card=lambda card_id, **kw: (
                    events.append(("select", card_id)) or CollectionCardSelectionResult(
                        CollectionCardSelectionOutcome.ENTERED,
                        NavigationResult(True, ScreenState.SANDBOX))),
                current_collection_target=lambda card: "main_area",
            )
            collector = Collector(task, object(), nav, progress)
            # Returning a failure here stops before skills and further navigation.
            collector._go_to_collection_target = lambda card, current, target: (
                events.append(("arrive", card.card_id, current.key, target.key)) or None)
            collector._absorb_used_up = lambda **kw: SkillExecutionResult(False, message="stop fixture")
            with patch("src.tasks.map_trade.collector.COLLECTABLE_CARDS",
                       (CARD_BY_ID["Q_sp1"], CARD_BY_ID["Q_sp2"])):
                collector.run()
        return events

    def test_enabled_unfinished_current_card_runs_first_without_reentry(self):
        self.assertEqual([("arrive", "Q_sp2", "battle_area_1", "battle_area_1")],
                         self.run_from_current())

    def test_excluded_or_completed_current_card_is_not_prioritized(self):
        for kwargs in ({"allowed": "1"}, {"done": True}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(("select", "Q_sp1"), self.run_from_current(**kwargs)[0])
