from pathlib import Path

from qfluentwidgets import FluentIcon

from src.tasks.map_trade.favorite_guide import (
    GUIDE_DATE,
    PROFILE_KEY,
    PROFILES,
    PROFIT_ONLY,
    TASK_NAME,
    favorite_count,
)
from src.tasks.map_trade.models import ScreenState
from src.tasks.map_trade.navigator import Navigator
from src.tasks.map_trade.progress import ProgressStore
from src.tasks.map_trade.trader import Trader
from src.tasks.map_trade.vision import Vision
from src.tasks.MapTradeTask import (
    TRADE_OCR_THRESHOLD_KEY,
    TRADE_VISION_THRESHOLD_KEY,
    MapAutomationTaskBase,
)


class TradeFavoritesTask(MapAutomationTaskBase):
    """Explicit one-shot setup; never buys or participates in daily batches."""

    start_from_home = True
    recover_home_on_failure = True
    vision_threshold_key = TRADE_VISION_THRESHOLD_KEY
    ocr_threshold_key = TRADE_OCR_THRESHOLD_KEY
    task_log_name = "攻略收藏"
    diagnostic_prefix = "trade_favorites"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = TASK_NAME
        self.description = "按本地攻略替换 31 个商店的收藏；只设置星标，不砍价、不购买。"
        self.icon = FluentIcon.SHOPPING_CART
        self.group_name = "跑商"
        self.visible = True
        self.default_config.update({
            PROFILE_KEY: PROFIT_ONLY,
            TRADE_VISION_THRESHOLD_KEY: 0.72,
            TRADE_OCR_THRESHOLD_KEY: 0.20,
            "加载页面等待秒数": 45.0,
        })
        self.config_type[PROFILE_KEY] = {"type": "drop_down", "options": list(PROFILES)}
        self.config_description[PROFILE_KEY] = (
            "默认排除攻略红框内的零利润商品；刷成就方案包含这些商品。"
            "会替换已有收藏；更换方案或中途停止后可重新运行，逐项核对星标。"
        )

    def validate_config(self, key, value):
        if key == PROFILE_KEY and value not in PROFILES:
            return "请选择有效的收藏方案。"
        return super().validate_config(key, value)

    def run(self):
        # Snapshot the selection: a UI change cannot switch policy halfway through.
        profile = self.config.get(PROFILE_KEY, PROFIT_ONLY)
        count = favorite_count(profile)
        self.info_set("收藏方案", profile)
        self.info_set("状态", f"按 {GUIDE_DATE} 攻略设置 {count} 组收藏。")
        vision = Vision(self)
        navigator = Navigator(self, vision)
        # Isolate this setup task from purchase/cooking/collection progress.
        progress = ProgressStore(Path("configs") / "trade_favorites_progress.json")
        progress.load()
        progress.clear_favorite_cards()
        trader = Trader(self, vision, navigator, progress)
        trader.favorite_guide_profile = profile
        entered = navigator.enter_q_sp6_buy_flow(bargain=False)
        if not entered.success or entered.state != ScreenState.SHOP:
            self.log_warning(f"收藏：未确认购买商店页面。{entered.message}")
            return False
        if not trader.rebuild_favorites():
            self._save_diagnostic("trade_favorites_incomplete")
            self.info_set("状态", "收藏未全部完成；已改星标保留，修正问题后可重新运行。")
            return False
        # No finally: cancellation must propagate without further game input.
        returned = navigator.return_home()
        if not returned.success:
            self.log_warning(f"收藏已设置，但返回主页失败：{returned.message}")
            return False
        self.info_set("状态", f"已按攻略设置 {count} 组收藏，未购买。")
        self.log_completion(f"{profile}：{count} 组收藏设置完成，购买请运行每日跑商。")
        return True
