"""Keep recognition in BD2's 16:9 content coordinates on a 16:10 client.

Eight saved 2560x1600 captures have exactly 80 black rows above and below
the 2560x1440 game. Never stretch that picture or change the window size.
The capture and the input layer must use the same confirmed offset.
"""

from __future__ import annotations

import numpy as np


def content_bounds(frame: np.ndarray) -> tuple[int, int, int, int]:
    height, width = frame.shape[:2]
    full = (0, 0, width, height)
    if abs(width / height - 1.6) > 0.005:
        return full
    content_height = round(width * 9 / 16)
    top = (height - content_height) // 2
    bottom = top + content_height
    if top <= 0 or bottom >= height:
        return full
    pixels = frame[..., :3] if frame.ndim == 3 else frame
    # Alpha is ignored. Both complete bars must be black; a native 16:10
    # scene or an overlay in a bar must not be silently cut off.
    if np.max(pixels[:top]) > 8 or np.max(pixels[bottom:]) > 8:
        return full
    # A black loading frame alone cannot establish where the content is.
    if not np.any(pixels[top : top + 3] > 16) or not np.any(pixels[bottom - 3 : bottom] > 16):
        return full
    return (0, top, width, content_height)


def client_point(capture, x, y):
    """Recognition coordinates -> uncropped game client coordinates."""
    left, top = getattr(capture, "_bd2_content_offset", (0, 0))
    return round(x + left), round(y + top)


def patch_capture_class(capture_class: type) -> None:
    """Patch the Windows capture boundary, including WGC and its fallback."""
    if getattr(capture_class, "_bd2_letterbox_enabled", False):
        return
    original_frame = capture_class.get_frame
    original_abs = capture_class.get_abs_cords

    def get_frame(self):
        frame = original_frame(self)
        if frame is None:
            return None
        height, width = frame.shape[:2]
        bounds = content_bounds(frame)
        previous = getattr(self, "_bd2_content_bounds", None)
        # Dark scenes and loading animations can hide a content edge. Keep
        # an established viewport while both bars remain black at the same
        # client size. Resize and nonblack bars reset it immediately.
        pixels = frame[..., :3] if frame.ndim == 3 else frame
        if (
            previous is not None
            and getattr(self, "_bd2_client_size", None) == (width, height)
            and previous[1] > 0
            and not np.any(pixels[: previous[1]] > 8)
            and not np.any(pixels[previous[1] + previous[3] :] > 8)
        ):
            bounds = previous
        left, top, content_width, content_height = bounds
        self._bd2_client_size = (width, height)
        self._bd2_content_bounds = bounds
        self._bd2_content_offset = (left, top)
        self._size = (content_width, content_height)
        return frame[top : top + content_height, left : left + content_width]

    def get_abs_cords(self, x, y):
        return original_abs(self, *client_point(self, x, y))

    capture_class.get_frame = get_frame
    capture_class.get_abs_cords = get_abs_cords
    capture_class._bd2_letterbox_enabled = True


def install() -> None:
    from ok.device.capture_methods.base import BaseWindowsCaptureMethod

    patch_capture_class(BaseWindowsCaptureMethod)
