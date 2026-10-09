import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import psutil

from src.fishing import runner
from src.fishing.bridge import BridgeError

PID = 4242


def snapshot(**values):
    return {
        "Schema": 1,
        "Runtime": "BD2Fishing.Runtime11",
        "ProcessId": PID,
        "CapturedUtcTicks": int((time.time() + 62135596800) * 10_000_000),
        "Ready": True,
        "State": "None",
        "Catches": 0,
        "Enabled": False,
        "OwnerId": "",
        "BagCount": 0,
        "BagCapacity": 50,
    } | values


class Clock:
    value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeBridge:
    def __init__(self, frames=(), *, stuck=False, failure=None):
        self.frames = iter(frames)
        self.last = snapshot()
        self.stuck, self.failure = stuck, failure
        self.calls = []
        self.closed = self.stopped = False

    def factory(self, **kwargs):
        self.check = kwargs["check"]
        return self

    def request(self, op, **values):
        self.check()
        self.calls.append(op)
        if self.failure == op:
            raise BridgeError("simulated failure")
        if op == "status":
            if self.stopped:
                return {"snapshot": snapshot(Enabled=self.stuck), "error": ""}
            self.last = next(self.frames, self.last)
            return {"snapshot": self.last, "error": ""}
        if op == "start":
            self.stopped = False
            return {"owner": "owner"}
        if op == "stop":
            self.stopped = True

    def pulse(self):
        self.calls.append("heartbeat")

    def close(self):
        self.closed = True


class Cancelled(Exception):
    pass


class FishingRunnerTest(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(runner, "_uncertain_game", None)
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.clock = Clock()
        self.updates = []

    def run_with(self, bridge, config=None, state=lambda: "run"):
        return runner.FishingRunner(
            config or {},
            state,
            self.updates.append,
            factory=bridge.factory,
            clock=self.clock,
            sleep=self.clock.sleep,
        ).run(PID, 123.0)

    def test_defaults_do_not_sell_and_preserve_protected_fish(self):
        settings = runner.backend_settings({})
        self.assertFalse(settings["AutoSell"])
        self.assertEqual(
            settings["Retention"],
            {
                "KeepLocked": True,
                "KeepUnknown": True,
                "KeepLegendary": True,
            },
        )

    def test_invalid_limits_and_bool_as_integer_are_rejected(self):
        for value in (0, 361, True, "30"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runner.backend_settings({"最长运行分钟": value})
        with self.assertRaises(ValueError):
            runner.backend_settings({"背包满自动出售": "false"})

    def test_fresh_requires_matching_process_runtime_and_time(self):
        self.assertTrue(runner.fresh(snapshot(), PID))
        for change in (
            {"ProcessId": PID + 1},
            {"Schema": 2},
            {"Runtime": "old"},
            {"CapturedUtcTicks": 0},
            {"CapturedUtcTicks": 9999999999999999999},
        ):
            self.assertFalse(runner.fresh(snapshot(**change), PID))

    def test_count_limit_is_relative_to_session_baseline_and_stops(self):
        bridge = FakeBridge(
            [snapshot(Catches=20), snapshot(Catches=22, Enabled=True, OwnerId="owner")]
        )
        self.assertEqual(2, self.run_with(bridge, {"收获数量上限": 2}))
        self.assertEqual(1, bridge.calls.count("start"))
        self.assertEqual("stop", bridge.calls[-2])
        self.assertTrue(bridge.closed)
        self.assertIsNone(runner._uncertain_game)

    def test_full_bag_never_starts_with_default_settings(self):
        bridge = FakeBridge([snapshot(BagFull=True)])
        with self.assertRaisesRegex(BridgeError, "背包已满"):
            self.run_with(bridge)
        self.assertNotIn("start", bridge.calls)
        self.assertTrue(bridge.closed)

    def test_cancellation_still_stops_and_closes(self):
        bridge = FakeBridge([snapshot()])

        def state():
            if self.clock() >= 0.25:
                raise Cancelled()
            return "run"

        with self.assertRaises(Cancelled):
            self.run_with(bridge, state=state)
        self.assertIn("stop", bridge.calls)
        self.assertTrue(bridge.closed)
        self.assertIsNone(runner._uncertain_game)

    def test_paused_time_does_not_count_and_resume_rearms(self):
        # The real runtime reports a stopped snapshot before resuming.
        bridge = FakeBridge([snapshot(), snapshot(Enabled=True, OwnerId="owner")])
        bridge.last = snapshot(Enabled=True, OwnerId="owner")

        def state():
            return "pause" if 0.25 <= self.clock() < 120 else "run"

        self.run_with(bridge, {"最长运行分钟": 1}, state=state)
        self.assertGreaterEqual(self.clock(), 179)
        self.assertEqual(2, bridge.calls.count("start"))
        self.assertEqual(2, bridge.calls.count("stop"))

    def test_waiting_for_manual_entry_does_not_start(self):
        for frame in (snapshot(Ready=False), snapshot(State="Auto")):
            bridge = FakeBridge([frame])
            self.clock.value = 0
            with self.assertRaisesRegex(BridgeError, "超时"):
                self.run_with(bridge, {"等待进入钓场秒数": 10})
            self.assertNotIn("start", bridge.calls)

    def test_runtime_failure_stale_state_and_ownership_loss_stop(self):
        for frame in (
            snapshot(Error="hook failed"),
            snapshot(CapturedUtcTicks=0),
            snapshot(Enabled=True, OwnerId="another"),
        ):
            bridge = FakeBridge([snapshot(), frame])
            with self.subTest(frame=frame), self.assertRaises(BridgeError):
                self.run_with(bridge)
            self.assertTrue(bridge.closed)
            self.assertIn("stop", bridge.calls)

    def test_start_that_never_becomes_enabled_is_rejected(self):
        bridge = FakeBridge([snapshot()])
        with self.assertRaisesRegex(BridgeError, "未生效"):
            self.run_with(bridge)
        self.assertTrue(bridge.closed)

    def test_map_transition_has_bounded_wait_and_remains_cancellable(self):
        bridge = FakeBridge([snapshot(), snapshot(Ready=False, Enabled=True, OwnerId="owner")])
        with self.assertRaisesRegex(BridgeError, "钓场切换等待超时"):
            self.run_with(bridge)
        self.assertLess(self.clock(), 92)
        self.assertIn("stop", bridge.calls)

    def test_stop_failure_fences_same_process_until_restart(self):
        bridge = FakeBridge([snapshot(BagFull=True)], stuck=True)
        with self.assertRaises(BridgeError):
            self.run_with(bridge)
        self.assertEqual((PID, 123.0), runner._uncertain_game)
        with patch.object(psutil, "Process", return_value=Mock(create_time=lambda: 123.0)):
            self.assertIn("重启游戏", runner.block_reason())
        with patch.object(psutil, "Process", return_value=Mock(create_time=lambda: 124.0)):
            self.assertEqual("", runner.block_reason())
        self.assertIsNone(runner._uncertain_game)

    def test_stop_needs_snapshot_captured_after_stop(self):
        bridge = FakeBridge([snapshot(BagFull=True)])
        old = snapshot()
        old["CapturedUtcTicks"] -= 10_000_000
        original = bridge.request

        def request(op, **values):
            result = original(op, **values)
            if op == "status" and bridge.stopped:
                return {"snapshot": old}
            return result

        bridge.request = request
        with self.assertRaises(BridgeError):
            self.run_with(bridge)
        self.assertIsNotNone(runner._uncertain_game)

    def test_pending_operations_cannot_be_declared_stopped(self):
        for flag in (
            "Enabled",
            "HoldActive",
            "HoldTracking",
            "SalePending",
            "SaleActive",
            "BaitPending",
            "NetworkPending",
            "MapTravelBusy",
            "CastRunning",
        ):
            self.assertFalse(runner.settled(snapshot(**{flag: True})))

    def test_connection_failure_never_starts_or_sets_false_fence(self):
        bridge = FakeBridge(failure="connect")
        with self.assertRaises(BridgeError):
            self.run_with(bridge)
        self.assertNotIn("start", bridge.calls)
        self.assertTrue(bridge.closed)
        self.assertIsNone(runner._uncertain_game)

    def test_scheduled_task_is_blocked_before_running(self):
        from src.tasks.BaseBD2Task import BaseBD2Task

        called = []

        class DummyTask(BaseBD2Task):
            def run(self):
                called.append(True)

        with patch.object(runner, "block_reason", return_value="请重启游戏"):
            with self.assertRaisesRegex(RuntimeError, "重启游戏"):
                object.__new__(DummyTask).run()
        self.assertEqual([], called)


class ProcessSelectionTest(unittest.TestCase):
    def test_filters_child_session_and_rejects_ambiguous_targets(self):
        from src.utils import clone_desktop

        games = [
            SimpleNamespace(pid=2, info={"name": "BrownDust II.exe", "create_time": 12.0}),
            SimpleNamespace(pid=3, info={"name": "BrownDust II.exe", "create_time": 13.0}),
        ]
        with (
            patch.object(psutil, "Process", return_value=SimpleNamespace(pid=1)),
            patch.object(psutil, "process_iter", return_value=games),
            patch.object(
                clone_desktop, "_session_of", side_effect=lambda pid: 9 if pid == 3 else 1
            ),
        ):
            self.assertEqual((2, 12.0), runner.select_game())
        with (
            patch.object(psutil, "Process", return_value=SimpleNamespace(pid=1)),
            patch.object(psutil, "process_iter", return_value=games),
            patch.object(clone_desktop, "_session_of", return_value=1),
        ):
            with self.assertRaises(BridgeError):
                runner.select_game()


class TaskStatusTest(unittest.TestCase):
    def test_stop_and_error_replace_running_status(self):
        from ok.task.exceptions import TaskDisabledException

        from src.tasks.FishingTask import FishingTask

        for error, label in (
            (TaskDisabledException(), "已停止"),
            (BridgeError("test"), "已停止，需处理后重新开始"),
        ):
            task = object.__new__(FishingTask)
            task.info = {}
            task.info_set = Mock()
            task._fish = Mock(side_effect=error)
            with self.assertRaises(type(error)):
                task.run()
            self.assertEqual(label, task.fishing_status["状态"])


if __name__ == "__main__":
    unittest.main()
