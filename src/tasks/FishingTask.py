import time

from ok.task.exceptions import TaskDisabledException
from qfluentwidgets import FluentIcon

from src.fishing.runner import DEFAULTS, LIMITS, FishingRunner, block_reason, select_game, validate
from src.tasks.BaseBD2Task import BaseBD2Task


class FishingTask(BaseBD2Task):
    """Optional injection task; never part of the default daily batch."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自动钓鱼"
        self.description = "手动进入钓场后自动钓鱼。基于 MadestSamurai/bd2-fishing（MIT）。"
        self.icon = FluentIcon.GAME
        self.group_name = "钓鱼"
        self.visible = True
        self.default_config.update(DEFAULTS)
        self.config_type.update({key: {"min": lo, "max": hi} for key, (lo, hi) in LIMITS.items()})
        self.config_description.update(
            {
                "最长运行分钟": "达到时长后停止；暂停时间不计入。",
                "收获数量上限": "0 表示仅按时长停止；其他值表示达到该鱼数就停止。",
                "等待进入钓场秒数": "开始后允许你手动进入钓场，超时退出。",
                "自动使用已有鱼饵": "使用背包现有鱼饵，不购买补给。",
                "背包满自动出售": "默认关闭。开启后按保留规则出售；始终保留锁定及资料不明的鱼。",
                "保留全部传说鱼": "自动出售开启时仍保留全部传说鱼，建议保持开启。",
            }
        )
        self.fishing_status = {}
        self.player_plays_along = True  # Allows manual entry into the fishing map.

    def validate_config(self, key, value):
        try:
            validate(DEFAULTS | dict(self.config or {}) | {key: value})
        except ValueError as exc:
            return str(exc)

    def _state(self):
        if not self._enabled or self.executor.exit_event.is_set():
            raise TaskDisabledException()
        return "pause" if self.paused or self.executor.paused else "run"

    def _update(self, values):
        if values.get("自动操作中"):
            self.player_plays_along = False
        values = {key: value for key, value in values.items() if key != "自动操作中"}
        self.fishing_status = self.fishing_status | values
        for key, value in values.items():
            self.info_set(key, value)

    def run(self):
        reason = block_reason()
        if reason:
            raise RuntimeError(reason)
        self.fishing_status = {}
        self.player_plays_along = True
        try:
            return self._fish()
        except TaskDisabledException:
            if not block_reason():
                self._update({"状态": "已停止"})
            raise
        except Exception as exc:
            if not block_reason():
                self._update({"状态": "已停止，需处理后重新开始", "原因": str(exc)})
            raise

    def _fish(self):
        self._update({"状态": "等待游戏；请进入钓场"})
        # The clone may just have launched its game. Wait without capturing or clicking.
        until = time.monotonic() + self.config.get("等待进入钓场秒数", 180)
        while True:
            self._state()
            try:
                pid, started = select_game()
                break
            except RuntimeError:
                if time.monotonic() >= until:
                    raise
                time.sleep(0.25)
        count = FishingRunner(dict(self.config), self._state, self._update).run(pid, started)
        if block_reason():
            raise RuntimeError(block_reason())
        self._update({"状态": "已完成并停止", "本次收获": count})
        self.log_completion(f"钓鱼完成，本次收获 {count} 条。")
        return True
