"""Regression for 2026-10-12: 19/21 was persisted as fully depleted."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.tasks.map_trade.collector import Collector
from src.tasks.map_trade.models import CARD_BY_ID
from src.tasks.map_trade.progress import UTC_PLUS_8, ProgressStore


class QuotaDeferralTest(unittest.TestCase):
    def store(self, directory):
        store = ProgressStore(Path(directory) / "progress.json",
                              lambda: datetime(2026, 10, 12, 13, tzinfo=UTC_PLUS_8))
        store.load()
        state = store.state
        state.daily_submaps = 18
        state.daily_summons = state.daily_suppressions = 12
        state.observed_counts = {"吸收": (19, 21), "召集": (11, 21), "压制": (12, 55)}
        state.observed_limits = {"吸收": 21, "召集": 21, "压制": 55}
        state.depleted_today = True
        state.cards = {"Q_sp1": ["battle_area_1", "battle_area_2", "main_area"]}
        state.verified_cards = ["Q_sp1"]
        store.save()
        return store

    def test_old_flag_is_repaired_without_resetting_any_other_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            before = json.loads(store.path.read_text(encoding="utf-8"))
            state = store.load()
            self.assertFalse(state.depleted_today)
            after = json.loads(store.path.read_text(encoding="utf-8"))
            before["depleted_today"] = False
            self.assertEqual(before, after)

    def test_real_full_or_unknown_counts_keep_depletion(self):
        for action in ("吸收", "召集", "压制", "unknown", "local"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                store = self.store(directory)
                if action == "unknown":
                    del store.state.observed_counts["压制"]
                elif action == "local":
                    store.state.daily_submaps = 21
                else:
                    limit = store.limit_of(action)
                    store.state.observed_counts[action] = (limit, limit)
                store.save()
                self.assertTrue(store.load().depleted_today)

    def test_repeated_runs_report_two_remaining_without_persisting_exhaustion(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            task = SimpleNamespace(config={}, info_set=Mock(), log_warning=Mock())
            navigator = SimpleNamespace(select_collection_card=Mock(
                side_effect=AssertionError("must not enter a card that needs three absorbs")))
            collector = Collector(task, object(), navigator, store)
            with patch("src.tasks.map_trade.collector.COLLECTABLE_CARDS", (CARD_BY_ID["Q_sp7"],)):
                for _ in range(2):
                    result = collector.run()
                    self.assertTrue(result.success)
                    self.assertTrue(result.deferred)
                    self.assertFalse(result.depleted)
                    self.assertIn("吸收还剩2次", result.message)
                    self.assertFalse(store.load().depleted_today)

    def test_two_remaining_maps_of_a_partial_card_still_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            store.load()
            collector = Collector(SimpleNamespace(), object(), object(), store)
            self.assertTrue(collector._can_finish_card_today(CARD_BY_ID["Q_sp7"], {"main_area"}))
            self.assertFalse(collector._can_finish_card_today(CARD_BY_ID["Q_sp7"], set()))
