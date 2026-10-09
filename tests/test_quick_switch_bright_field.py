"""The field quick-switch (P) button and the key caps that prove the field
are found over bright backgrounds.

A player's 跑图 (2026-10-09) stopped at 「寻找快速切换按钮」 in front of white
fog.  Fifteen bright event-cartridge scenes from Leo's 4K PC (sand glare,
pool water, fairy lights; tests/fixtures/field/bright_4k) all pass the P
template at 4K, 2K and 1080p: its disc is opaque enough.  This keeps it so.

The C cap found nothing over white sand and pool water (beach_safe_*,
splash_safe_pool), so the field check takes any 2 of the C/H/M/Q caps (#111);
every scene keeps at least 2 even without M, which these crops leave out.
"""

import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from src.tasks.map_trade.navigator_constants import (
    FIELD_ALL_KEYCAP_TEMPLATES,
    FIELD_KEYCAP_MIN_PASSES,
    QUICK_SWITCH_TEMPLATE,
)
from src.tasks.map_trade.vision import TEMPLATE_DIR, Vision
from src.utils import task_vision

FIXTURES = Path(__file__).parent / "fixtures" / "field" / "bright_4k"
OTHER_PAGES = (
    "quick_switch/home_bottom_strip_1600x901.png",
    "quick_switch/battle_gameplay_selected_fhd.png",
    "quick_switch/life_gameplay_selected_fhd.png",
    "pvp/recent_pvp_home_fhd.png",
    "map_trade/map_pages/sandbox_large.png",
    "map_trade/home_return/update_notice.png",
)
SIZES = ((3840, 2160), (2560, 1440), (1920, 1080))
# Where the README says each crop was cut from the 4K frame.
BOTTOM_ORIGIN = (1400, 1800)
TOPRIGHT_ORIGIN = (3040, 0)
# The P button's place in 1080 reference pixels (FIELD_QUICK_SWITCH_POINT).
P_POINT = (851, 997)


def scenes() -> list[str]:
    return sorted(path.name[: -len("_bottom.png")] for path in FIXTURES.glob("*_bottom.png"))


def frame_4k(scene: str) -> np.ndarray:
    """The scene's crops placed where they were cut, on a black 4K frame."""
    frame = np.zeros((2160, 3840, 3), np.uint8)
    for suffix, (x, y) in (("bottom", BOTTOM_ORIGIN), ("topright", TOPRIGHT_ORIGIN)):
        crop = cv2.imread(str(FIXTURES / f"{scene}_{suffix}.png"), cv2.IMREAD_COLOR)
        frame[y : y + crop.shape[0], x : x + crop.shape[1]] = crop
    return frame


def sized(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    if frame.shape[1] == width:
        return frame
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def keycaps_passing(frame: np.ndarray) -> int:
    """How many field key caps pass, with the navigator's own matcher."""
    vision = Vision(SimpleNamespace(config={}, info_set=lambda *_args, **_kwargs: None))
    return sum(
        bool(vision.passes(vision.match(frame, spec), spec)) for spec in FIELD_ALL_KEYCAP_TEMPLATES
    )


class QuickSwitchBrightFieldTest(unittest.TestCase):
    def test_fixtures_are_there(self):
        self.assertGreaterEqual(len(scenes()), 15)

    def test_quick_switch_button_passes_on_every_bright_scene(self):
        for scene in scenes():
            source = frame_4k(scene)
            for width, height in SIZES:
                frame = sized(source, width, height)
                with self.subTest(scene=scene, size=f"{width}x{height}"):
                    result = task_vision.match_template(
                        frame, QUICK_SWITCH_TEMPLATE, {}, TEMPLATE_DIR, cache={}, min_size=4
                    )
                    self.assertTrue(
                        task_vision.passes_match(result, QUICK_SWITCH_TEMPLATE, {}), str(result)
                    )
                    # ...and on the P disc, not on the run or Q disc next to it.
                    center_x = (result.position[0] + result.size[0] / 2) * 1920 / width
                    center_y = (result.position[1] + result.size[1] / 2) * 1080 / height
                    self.assertLess(abs(center_x - P_POINT[0]), 25)
                    self.assertLess(abs(center_y - P_POINT[1]), 25)

    def test_enough_key_caps_on_every_bright_scene(self):
        for scene in scenes():
            source = frame_4k(scene)
            for width, height in SIZES:
                with self.subTest(scene=scene, size=f"{width}x{height}"):
                    self.assertGreaterEqual(
                        keycaps_passing(sized(source, width, height)), FIELD_KEYCAP_MIN_PASSES
                    )

    def test_no_key_caps_off_the_field(self):
        for name in OTHER_PAGES:
            frame = cv2.imread(str(Path(__file__).parent / "fixtures" / name), cv2.IMREAD_COLOR)
            with self.subTest(page=name):
                self.assertIsNotNone(frame)
                self.assertLess(keycaps_passing(frame), FIELD_KEYCAP_MIN_PASSES)


if __name__ == "__main__":
    unittest.main()
