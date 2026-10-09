"""Task lifecycle: readiness, pause, bounded runs, verified stop and process fencing."""

from __future__ import annotations

import time

import psutil

from src.fishing.bridge import BridgeError, FishingBridge

DEFAULTS = {
    "最长运行分钟": 30,
    "收获数量上限": 0,
    "等待进入钓场秒数": 180,
    "下一竿间隔毫秒": 1000,
    "抛竿蓄力百分比": 90,
    "优先弱点": True,
    "自动靠近钓区": True,
    "自动使用已有鱼饵": True,
    "到期往返原钓场": True,
    "背包满自动出售": False,
    "保留全部传说鱼": True,
}
LIMITS = {
    "最长运行分钟": (1, 360),
    "收获数量上限": (0, 10000),
    "等待进入钓场秒数": (10, 600),
    "下一竿间隔毫秒": (0, 60000),
    "抛竿蓄力百分比": (5, 95),
}
_uncertain_game: tuple[int, float] | None = None


def validate(config):
    for key, default in DEFAULTS.items():
        value = config.get(key, default)
        if key in LIMITS:
            low, high = LIMITS[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{key} 必须为 {low}–{high} 的整数。")
        elif type(value) is not bool:
            raise ValueError(f"{key} 必须为开关值。")


def backend_settings(config):
    validate(config)
    config = DEFAULTS | dict(config)
    return {
        "NextCastMilliseconds": config["下一竿间隔毫秒"],
        "CastGauge": config["抛竿蓄力百分比"] / 100,
        "PreferWeak": config["优先弱点"],
        "AutoApproach": config["自动靠近钓区"],
        "AutoBait": config["自动使用已有鱼饵"],
        "AutoMapRenewal": config["到期往返原钓场"],
        "AutoSell": config["背包满自动出售"],
        "Retention": {
            "KeepLegendary": config["保留全部传说鱼"],
            "KeepLocked": True,
            "KeepUnknown": True,
        },
    }


def block_reason():
    """Never hand an unconfirmed, still-live game to another task."""
    global _uncertain_game
    if _uncertain_game:
        pid, started = _uncertain_game
        try:
            if abs(psutil.Process(pid).create_time() - started) < 0.01:
                return "上次钓鱼停止未确认，请先重启游戏，再执行任务。"
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            return "无法确认上次钓鱼是否停止，请重启游戏后重试。"
        _uncertain_game = None
    return ""


def select_game():
    from src.utils.clone_desktop import _session_of

    own_session = _session_of(psutil.Process().pid)
    if own_session is None:
        raise BridgeError("无法识别当前 Windows 会话。")
    games = []
    for proc in psutil.process_iter(["pid", "name", "create_time"]):
        if (proc.info.get("name") or "").lower() != "browndust ii.exe":
            continue
        if _session_of(proc.pid) == own_session:
            games.append((proc.pid, proc.info["create_time"]))
    if len(games) != 1:
        raise BridgeError("请在当前桌面中只打开一个 BrownDust II，并进入已解锁的钓场。")
    return games[0]


def fresh(snapshot, pid):
    if (
        not snapshot
        or snapshot.get("ProcessId") != pid
        or snapshot.get("Schema") != 1
        or snapshot.get("Runtime") != "BD2Fishing.Runtime11"
    ):
        return False
    stamp = snapshot.get("CapturedUtcTicks", 0) / 10_000_000 - 62135596800
    return -2 <= time.time() - stamp <= 3


def settled(snapshot):
    return not any(
        snapshot.get(key, False)
        for key in (
            "Enabled",
            "CastRunning",
            "HoldTracking",
            "SalePending",
            "SaleActive",
            "BaitPending",
            "NetworkPending",
            "MapTravelBusy",
            "HoldActive",
        )
    )


class FishingRunner:
    def __init__(
        self,
        config,
        state,
        update,
        *,
        factory=FishingBridge,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        self.config = DEFAULTS | dict(config)
        self.state, self.update = state, update
        self.factory, self.clock, self.sleep = factory, clock, sleep
        self.bridge = None

    def check(self):
        self.state()  # Stop/exit raises the executor's normal cancellation exception.

    def status(self, pid):
        reply = self.bridge.request("status")
        if reply.get("error"):
            raise BridgeError(reply["error"])
        snapshot = reply.get("snapshot")
        if snapshot and snapshot.get("Error"):
            raise BridgeError(snapshot["Error"])
        return snapshot if fresh(snapshot, pid) else None

    def run(self, pid, started):
        global _uncertain_game
        settings = backend_settings(self.config)
        self.bridge = self.factory(
            check=self.check, progress=lambda text: self.update({"状态": text})
        )
        connected = False
        try:
            self.bridge.request("connect", pid=pid, started=started, timeout=90)
            connected = True
            self.bridge.request("configure", settings=settings)
            waiting_until = self.clock() + self.config["等待进入钓场秒数"]
            owner = None
            running = False
            baseline = None
            elapsed = 0.0
            count = 0
            armed_at = 0.0
            previous = self.clock()
            transition_until = None
            while True:
                mode = self.state()
                now = self.clock()
                if running:
                    elapsed += now - previous
                previous = now
                if elapsed >= self.config["最长运行分钟"] * 60:
                    return count
                if mode == "pause":
                    if running:
                        self.bridge.request("stop")
                        running = False
                    self.update({"状态": "已暂停钓鱼"})
                    self.bridge.pulse()
                    self.sleep(0.1)
                    continue
                snapshot = self.status(pid)
                if snapshot is None:
                    if owner:
                        raise BridgeError("钓鱼状态已过期，已停止任务。")
                    if now > waiting_until:
                        raise BridgeError("等待钓场超时，请进入钓场后重新开始。")
                elif not snapshot.get("Ready") or snapshot.get("State") == "Auto":
                    if owner:
                        if snapshot.get("State") == "Auto":
                            raise BridgeError("检测到游戏内自动钓鱼，请关闭后重新开始。")
                        transition_until = transition_until or now + 90
                        self.update({"状态": "等待钓场切换完成"})
                        if now > transition_until:
                            raise BridgeError("钓场切换等待超时，已停止任务。")
                        self.bridge.pulse()
                        self.sleep(0.25)
                        continue
                    self.update({"状态": "请在游戏中进入钓场，关闭游戏内自动钓鱼"})
                    if now > waiting_until:
                        raise BridgeError("等待钓场超时。")
                else:
                    transition_until = None
                    catches = snapshot.get("Catches", 0)
                    if baseline is None:
                        baseline = catches
                    count = max(0, catches - baseline)
                    if running and snapshot.get("OwnerId") not in (owner, ""):
                        raise BridgeError("钓鱼控制权已被其他工具接管。")
                    if running and now - armed_at > 3 and not snapshot.get("Enabled"):
                        raise BridgeError("钓鱼控制已停止或未生效，请查看诊断。")
                    self.update(
                        {
                            "状态": snapshot.get("Reason", "钓鱼中"),
                            "本次收获": count,
                            "已运行秒数": int(elapsed),
                            "鱼背包": (
                                f"{snapshot.get('BagCount', 0)}/{snapshot.get('BagCapacity', 0)}"
                            ),
                            "鱼饵": snapshot.get("BaitStatus", ""),
                            "出售": snapshot.get("SaleStatus", ""),
                        }
                    )
                    limit = self.config["收获数量上限"]
                    if elapsed >= self.config["最长运行分钟"] * 60 or (limit and count >= limit):
                        return count
                    if snapshot.get("BagFull") and not settings["AutoSell"]:
                        raise BridgeError("鱼背包已满，自动出售未开启，请先手动整理。")
                    if not running:
                        result = self.bridge.request("start")
                        owner = result["owner"]
                        running = True
                        armed_at = self.clock()
                        self.update({"自动操作中": True})
                self.bridge.pulse()
                self.sleep(0.25)
        finally:
            # Cleanup must run even when the task is disabled/paused.
            self.bridge.check = lambda: None
            confirmed = not connected
            try:
                if connected:
                    stopped_at = int((time.time() + 62135596800) * 10_000_000)
                    self.bridge.request("stop", timeout=4)
                    until = self.clock() + 15
                    while self.clock() < until:
                        reply = self.bridge.request("status", timeout=3)
                        snapshot = reply.get("snapshot")
                        if (
                            fresh(snapshot, pid)
                            and settled(snapshot)
                            and snapshot.get("CapturedUtcTicks", 0) >= stopped_at
                        ):
                            confirmed = True
                            break
                        self.sleep(0.2)
            except (BridgeError, OSError):
                pass
            finally:
                if not confirmed:
                    _uncertain_game = (pid, started)
                    self.update({"状态": "停止未确认，请先重启游戏再执行其他任务"})
                self.bridge.close()
