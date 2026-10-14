import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np
import win32api
import win32con

from src.capture.letterbox import client_point, content_bounds, patch_capture_class
from src.interaction.BD2Interaction import BD2Interaction
from src.utils.cartridge_quick_switch import (
    BATTLE_GAMEPLAY_CATEGORY_HIGHLIGHT_REGION,
    GAMEPLAY_CATEGORY_HIGHLIGHT_MIN_RATIO,
    category_highlight_ratio,
)


def padded_frame(width=2560, height=1600):
    frame = np.zeros((height, width, 3), np.uint8)
    content_height = round(width * 9 / 16)
    top = (height - content_height) // 2
    frame[top : top + content_height] = 90
    return frame


def capture_for(frame):
    class Capture:
        def get_frame(self):
            return self.frame

        def get_abs_cords(self, x, y):
            return (100 + x, 200 + y)

    patch_capture_class(Capture)
    patch_capture_class(Capture)  # installation must be idempotent
    capture = Capture()
    capture.frame = frame
    return capture


class LetterboxCaptureTest(unittest.TestCase):
    def test_framework_resolution_check_and_task_guard_use_content_size(self):
        import threading

        from ok.device.capture_methods.base import BaseWindowsCaptureMethod
        from ok.task.TaskExecutor import TaskExecutor

        from src.utils import game_size

        class Capture(BaseWindowsCaptureMethod):
            def do_get_frame(self):
                return padded_frame()

        patch_capture_class(Capture)
        capture = Capture(SimpleNamespace(exists=True, hwnd=1))
        capture.exit_event = threading.Event()
        manager = SimpleNamespace(
            capture_method=capture, update_resolution_for_hwnd=Mock()
        )
        executor = SimpleNamespace(device_manager=manager, method=capture)
        with patch("ok.task.TaskExecutor.time.sleep"):
            self.assertEqual(
                (True, "2560x1440"),
                TaskExecutor.check_frame_and_resolution(executor, "16:9", (1280, 720)),
            )
        resize = Mock()
        self.assertFalse(game_size.fix_or_warn(SimpleNamespace(executor=executor), resize=resize))
        resize.assert_not_called()

    def test_content_dimensions_and_screen_coordinates_share_offset(self):
        capture = capture_for(padded_frame())
        cropped = capture.get_frame()
        self.assertEqual((1440, 2560, 3), cropped.shape)
        self.assertEqual((2560, 1440), capture._size)
        self.assertEqual((1000, 980), client_point(capture, 1000, 900))
        self.assertEqual((1100, 1180), capture.get_abs_cords(1000, 900))

    def test_supported_content_sizes_on_16_10_clients(self):
        for width, height in ((1920, 1200), (2560, 1600), (3840, 2400)):
            with self.subTest(size=(width, height)):
                content_height = round(width * 9 / 16)
                self.assertEqual(
                    (0, (height - content_height) // 2, width, content_height),
                    content_bounds(padded_frame(width, height)),
                )

    def test_native_16_10_and_16_9_are_not_cropped(self):
        for width, height in ((2560, 1600), (1920, 1080), (3840, 2160)):
            frame = np.full((height, width, 3), 100, np.uint8)
            self.assertEqual((0, 0, width, height), content_bounds(frame))
        frame = padded_frame()
        frame[0, 0] = 255
        self.assertEqual((0, 0, 2560, 1600), content_bounds(frame))

    def test_black_loading_frames_and_resize_do_not_reuse_wrong_offset(self):
        capture = capture_for(np.zeros((1600, 2560, 3), np.uint8))
        self.assertEqual((1600, 2560, 3), capture.get_frame().shape)
        capture.frame = padded_frame()
        capture.get_frame()
        capture.frame[:] = 0
        self.assertEqual((1440, 2560, 3), capture.get_frame().shape)
        capture.frame[600:900] = 90  # loading spinner / dark scene
        self.assertEqual((1440, 2560, 3), capture.get_frame().shape)
        capture.frame = np.zeros((2160, 3840, 3), np.uint8)
        self.assertEqual((2160, 3840, 3), capture.get_frame().shape)
        self.assertEqual((0, 0), capture._bd2_content_offset)
        capture.frame = padded_frame()
        capture.get_frame()
        capture.frame[:] = 100
        self.assertEqual((1600, 2560, 3), capture.get_frame().shape)
        self.assertEqual((0, 0), capture._bd2_content_offset)

    def test_category_recognition_preserved_at_letterboxed_resolution(self):
        root = Path(__file__).parent / "fixtures" / "quick_switch"
        for selected in ("battle", "life"):
            with self.subTest(selected=selected):
                source = cv2.imread(str(root / f"{selected}_gameplay_selected_fhd.png"))
                scaled = cv2.resize(source, (2560, 1440))
                # Fixture masks the rest of the screenshot. Provide content
                # at the upper edge, as the real saved client frames do.
                scaled[:3] = 90
                frame = np.pad(scaled, ((80, 80), (0, 0), (0, 0)))
                cropped = capture_for(frame).get_frame()
                ratio = category_highlight_ratio(cropped, BATTLE_GAMEPLAY_CATEGORY_HIGHLIGHT_REGION)
                self.assertEqual(
                    selected == "battle", ratio >= GAMEPLAY_CATEGORY_HIGHLIGHT_MIN_RATIO
                )


class LetterboxInputTest(unittest.TestCase):
    def make_interaction(self):
        import threading

        interaction = object.__new__(BD2Interaction)
        interaction.capture = capture_for(padded_frame())
        interaction.capture.get_frame()
        interaction._input_lock = threading.RLock()
        interaction._operating = False
        interaction.try_activate = Mock()
        interaction.post = Mock()
        interaction.hwnd_window = SimpleNamespace(
            top_hwnd=1, hwnd=1, get_top_window_cords=lambda x, y: (x, y), hwnds=[]
        )
        return interaction

    def test_click_moves_cursor_and_posts_to_same_adjusted_point(self):
        interaction = self.make_interaction()
        with (
            patch("src.interaction.BD2Interaction.SetCursorPos") as cursor,
            patch("src.interaction.BD2Interaction.time.sleep"),
            patch("src.interaction.BD2Interaction._in_clone", return_value=False),
        ):
            interaction.click(1000, 900)
        cursor.assert_called_once_with((1100, 1180))
        expected = win32api.MAKELONG(1000, 980)
        self.assertEqual([expected, expected], [c.args[2] for c in interaction.post.call_args_list])

    def test_drag_offsets_each_message_and_cursor_once(self):
        interaction = self.make_interaction()
        with (
            patch("src.interaction.BD2Interaction.SetCursorPos") as cursor,
            patch("src.interaction.BD2Interaction.GetCursorPos", return_value=(2, 3)),
            patch("src.interaction.BD2Interaction.time.sleep"),
        ):
            interaction.post_swipe(100, 200, 300, 400, steps=2)
        self.assertEqual((200, 480), cursor.call_args_list[0].args[0])
        self.assertEqual((400, 680), cursor.call_args_list[-2].args[0])
        self.assertEqual(win32api.MAKELONG(300, 480), interaction.post.call_args_list[-1].args[2])

    def test_scroll_offsets_before_screen_conversion(self):
        interaction = self.make_interaction()
        with patch(
            "src.interaction.BD2Interaction.win32gui.ClientToScreen", return_value=(1100, 1180)
        ) as screen:
            interaction.scroll(1000, 900, 1)
        screen.assert_called_once_with(1, (1000, 980))
        self.assertEqual(win32con.WM_MOUSEWHEEL, interaction.post.call_args.args[0])
        self.assertEqual(win32api.MAKELONG(1100, 1180), interaction.post.call_args.args[2])

    def test_move_and_release_keep_offset_once(self):
        interaction = self.make_interaction()
        with (
            patch(
                "ok.device.interaction_methods.post_message.win32gui.ClientToScreen",
                side_effect=lambda hwnd, pos: pos,
            ),
            patch(
                "ok.device.interaction_methods.post_message.win32gui.ScreenToClient",
                side_effect=lambda hwnd, pos: pos,
            ),
        ):
            interaction.move(1000, 900)
            interaction.mouse_down()
            interaction.mouse_up()
        expected = win32api.MAKELONG(1000, 980)
        self.assertEqual([expected] * 3, [c.args[2] for c in interaction.post.call_args_list])


if __name__ == "__main__":
    unittest.main()
