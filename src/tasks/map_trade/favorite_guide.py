"""Verified transcription of the locally archived Tencent low-price guide.

Slots run left to right, four per row. Gray stars are never selected; red
boxes mark the additional zero-profit items. This snapshot is independent of
the legacy purchase table and is never downloaded during a game task.
"""

from dataclasses import dataclass
from pathlib import Path

GUIDE_DATE = "2026-10-09"
GUIDE_URL = "https://docs.qq.com/aio/DQ2hEVUJxb2N3TG5u?no_promotion=1&p=vtUoQTm6eZgmT38JHgrXma"
GUIDE_DIR = Path(__file__).resolve().parents[3] / "docs/guides/trade-buy"
TASK_NAME = "按攻略设置收藏"
PROFILE_KEY = "收藏方案"
PROFIT_ONLY = "只买有利润商品"
INCLUDE_ZERO = "包含零利润商品刷成就"
PROFILES = (PROFIT_ONLY, INCLUDE_ZERO)


@dataclass(frozen=True)
class FavoriteGuideShop:
    product_count: int
    gray_slots: tuple[int, ...] = ()
    zero_profit_slots: tuple[int, ...] = ()

    @property
    def present_slots(self) -> frozenset[int]:
        return frozenset(range(1, self.product_count + 1))

    def favorite_slots(self, profile: str) -> frozenset[int]:
        if profile not in PROFILES:
            raise ValueError(f"未知收藏方案：{profile}")
        excluded = set(self.gray_slots)
        if profile == PROFIT_ONLY:
            excluded.update(self.zero_profit_slots)
        return self.present_slots - excluded


# Each row can be audited against images/<shop_id>.png and source.json.
GUIDE_SHOPS = {
    "S1": FavoriteGuideShop(7, (6,)),
    "S2": FavoriteGuideShop(8, (1,)),
    "S3": FavoriteGuideShop(13, (8, 9, 12, 13)),
    "S4": FavoriteGuideShop(13, (3, 4, 11, 12, 13)),
    "S5": FavoriteGuideShop(8, (2, 4, 8)),
    "S6": FavoriteGuideShop(9, (8, 9)),
    "S7": FavoriteGuideShop(9, (5, 9)),
    "S8": FavoriteGuideShop(13, (3, 4, 9, 10, 11, 12)),
    "S9": FavoriteGuideShop(8, (1, 2, 3, 4, 5, 6, 7, 8)),
    "S10": FavoriteGuideShop(12, (2, 3, 4, 5, 9, 12)),
    "S11": FavoriteGuideShop(10, (9,)),
    "S12": FavoriteGuideShop(15, (3, 4, 6, 11, 12, 13)),
    "S13": FavoriteGuideShop(13, (7, 8, 9, 11, 12, 13)),
    "S14": FavoriteGuideShop(12, (2, 3, 4, 5, 9, 11, 12)),
    "S15": FavoriteGuideShop(9, (1, 8, 9)),
    "S16": FavoriteGuideShop(10, (7, 9, 10)),
    "S17": FavoriteGuideShop(10, (2, 8, 9, 10)),
    "S18": FavoriteGuideShop(9, (2, 9)),
    "S19": FavoriteGuideShop(9, (3, 8, 9)),
    "R1": FavoriteGuideShop(7, (), (2,)),
    "R2": FavoriteGuideShop(8, (4,), (5,)),
    "R3": FavoriteGuideShop(10, (3, 10), (1,)),
    "R4": FavoriteGuideShop(8),
    "R5": FavoriteGuideShop(11, (3, 7, 8, 9, 11)),
    "R6": FavoriteGuideShop(11, (3, 7, 8, 9, 11)),
    "R7": FavoriteGuideShop(7, (), (2,)),
    "E1": FavoriteGuideShop(7, (4,), (2,)),
    "E2": FavoriteGuideShop(7, (4,), (5,)),
    "E3": FavoriteGuideShop(10, (3, 8, 10), (1,)),
    "E5": FavoriteGuideShop(7, (4,), (5,)),
    "E7": FavoriteGuideShop(8, (5,), (1, 7)),
}


def favorite_count(profile: str) -> int:
    return sum(len(shop.favorite_slots(profile)) for shop in GUIDE_SHOPS.values())
