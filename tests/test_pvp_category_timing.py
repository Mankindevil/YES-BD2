import unittest
from unittest.mock import Mock, patch

import numpy as np

from src.tasks.PVPTask import PVP_CARTRIDGE_SLOT_POINT, PVPTask
from src.utils.cartridge_quick_switch import BATTLE_GAMEPLAY_CATEGORY_LABEL


class PvpCategoryTimingTest(unittest.TestCase):
    def test_late_highlight_is_confirmed_without_clicking_category_again(self):
        task = object.__new__(PVPTask)
        task.config = {}
        task.info_set = Mock()
        task.log_info = Mock()
        task.sleep = Mock()
        task.operate_click = Mock()
        task.open_cartridge_quick_switcher = Mock(return_value=True)
        task._wait_for_battle_gameplay_category = Mock(return_value=False)
        # Unlit guard sees selection change; lit guard confirms two stable
        # selected frames; after the slot click the page disappears.
        task._quick_switch_still_shows = Mock(side_effect=[False, True, False])
        task._wait_for_pvp_hub_after_cart = Mock(return_value=True)
        task._clear_pvp_hub_notice_if_present = Mock()
        self.assertTrue(task._enter_pvp_from_home())
        self.assertEqual(2, task.operate_click.call_count)
        task.operate_click.assert_called_with(*PVP_CARTRIDGE_SLOT_POINT, after_sleep=0.0)

    def test_timeout_saves_the_frame_used_for_highlight_not_a_later_frame(self):
        task = object.__new__(PVPTask)
        task.config = {"玩法类别高亮确认秒数": 1.0}
        task.info_set = Mock()
        task.log_info = Mock()
        task.sleep = Mock()
        task.save_frame = Mock()
        failed_frame = np.zeros((1080, 1920, 3), np.uint8)
        task.capture_frame = Mock(return_value=failed_frame)
        task._ocr_text = Mock(return_value=BATTLE_GAMEPLAY_CATEGORY_LABEL)
        with patch("src.tasks.PVPTask.monotonic", side_effect=[0, 0, 2]):
            self.assertFalse(task._wait_for_battle_gameplay_category())
        task.capture_frame.assert_called_once()
        self.assertEqual("pvp_battle_category_failed", task.save_frame.call_args.args[0])
        self.assertIs(failed_frame, task.save_frame.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
