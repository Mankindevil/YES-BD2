"""Developer helper: capture the BD2 window and send single clicks.

Used while calibrating new tasks (templates, OCR ROIs, click points).
All coordinates on the command line are 1920x1080 reference coordinates,
scaled to the real client size, matching ``TaskVisionMixin._click_reference``.

    python tools/bd2dev.py info
    python tools/bd2dev.py shot [name] [--full]
    python tools/bd2dev.py click X Y [--shot name]
    python tools/bd2dev.py crop name X Y W H     # cut a template from a shot
    python tools/bd2dev.py ocr name [X Y W H]    # OCR a saved shot (optional ROI)

Background-input probes (never move the real cursor, never raise the game;
they print where the real cursor was and which window was in front, so a
result can be read against them).  --focus also posts fake activate/focus
messages first, the way some ok-script games need:
    python tools/bd2dev.py bgclick X Y [--focus] [--shot name]
    python tools/bd2dev.py bgscroll X Y NOTCHES [--focus] [--shot name]
    python tools/bd2dev.py bgdrag X1 Y1 X2 Y2 [SECONDS] [--focus] [--shot name]
"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import win32api
import win32con
import win32gui
import win32process
import win32ui

REF_W, REF_H = 1920, 1080
OUT_DIR = Path(__file__).resolve().parents[1] / ".local-dev" / "shots"
GAME_EXE = "BrownDust II.exe"
HWND_CLASS = "UnityWndClass"

# Per-monitor aware (as ok-script is): with only system awareness a game on
# a second monitor with another scale factor was captured shrunken
# (1080p monitor beside a 4K one, 2026-09-28).
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    ctypes.windll.user32.SetProcessDPIAware()


def find_hwnd() -> int:
    import psutil

    found: list[int] = []

    def visit(hwnd, _):
        if win32gui.GetClassName(hwnd) != HWND_CLASS or not win32gui.IsWindowVisible(hwnd):
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            if psutil.Process(pid).name().lower() == GAME_EXE.lower():
                found.append(hwnd)
        except psutil.Error:
            pass

    win32gui.EnumWindows(visit, None)
    if not found:
        raise SystemExit("找不到 BrownDust II 視窗")
    return found[0]


def client_size(hwnd: int) -> tuple[int, int]:
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    return right - left, bottom - top


def capture(hwnd: int) -> np.ndarray:
    """PrintWindow(PW_RENDERFULLCONTENT) capture of the client area as BGR."""
    width, height = client_size(hwnd)
    window_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(window_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)
    try:
        ok = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        raw = bitmap.GetBitmapBits(True)
        image = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
        frame = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)
    if not ok or frame.max() == 0:
        frame = capture_screen(hwnd)
    return frame


def capture_screen(hwnd: int) -> np.ndarray:
    """Fallback: grab the visible client area from the desktop."""
    from PIL import ImageGrab

    width, height = client_size(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    image = ImageGrab.grab(bbox=(left, top, left + width, top + height), all_screens=True)
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def to_client(hwnd: int, x: float, y: float) -> tuple[int, int]:
    width, height = client_size(hwnd)
    return round(x / REF_W * width), round(y / REF_H * height)


def click(hwnd: int, x: float, y: float) -> None:
    """Same scheme as BD2Interaction standard mode: move cursor, post button."""
    cx, cy = to_client(hwnd, x, y)
    old = win32api.GetCursorPos()
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.05)
    win32api.SetCursorPos(win32gui.ClientToScreen(hwnd, (cx, cy)))
    time.sleep(0.05)
    pos = win32api.MAKELONG(cx, cy)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
    time.sleep(0.03)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, pos)
    time.sleep(0.05)
    win32api.SetCursorPos(old)
    print(f"click ref=({x:.0f},{y:.0f}) client=({cx},{cy})")


def hold(hwnd: int, x: float, y: float, seconds: float) -> None:
    """Press and hold the left button at a reference point (on-screen D-pad)."""
    cx, cy = to_client(hwnd, x, y)
    old = win32api.GetCursorPos()
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.05)
    win32api.SetCursorPos(win32gui.ClientToScreen(hwnd, (cx, cy)))
    time.sleep(0.05)
    pos = win32api.MAKELONG(cx, cy)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
    time.sleep(seconds)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, pos)
    time.sleep(0.05)
    win32api.SetCursorPos(old)
    print(f"hold ref=({x:.0f},{y:.0f}) for {seconds:.2f}s")


def scroll(hwnd: int, x: float, y: float, notches: int) -> None:
    """Wheel at a reference point; negative notches scroll the list down."""
    cx, cy = to_client(hwnd, x, y)
    old = win32api.GetCursorPos()
    abs_x, abs_y = win32gui.ClientToScreen(hwnd, (cx, cy))
    win32api.SetCursorPos((abs_x, abs_y))
    time.sleep(0.05)
    step = 1 if notches > 0 else -1
    for _ in range(abs(notches)):
        w_param = win32api.MAKELONG(0, win32con.WHEEL_DELTA * step)
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, w_param, win32api.MAKELONG(abs_x, abs_y))
        time.sleep(0.08)
    time.sleep(0.3)
    win32api.SetCursorPos(old)
    print(f"scroll ref=({x:.0f},{y:.0f}) notches={notches}")


def _bg_context(hwnd: int) -> str:
    """Where the real cursor is and which window is in front (for the log)."""
    cursor = win32api.GetCursorPos()
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    width, height = client_size(hwnd)
    over_game = left <= cursor[0] < left + width and top <= cursor[1] < top + height
    front = win32gui.GetForegroundWindow()
    return (
        f"cursor={cursor} over_game={over_game} "
        f"game_in_front={front == hwnd} front_title={win32gui.GetWindowText(front)!r}"
    )


def _bg_focus(hwnd: int) -> None:
    """Tell the game it is active without raising it (no real focus change)."""
    win32gui.PostMessage(hwnd, win32con.WM_ACTIVATEAPP, 1, 0)
    win32gui.PostMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
    win32gui.PostMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
    time.sleep(0.05)


def bg_click(hwnd: int, x: float, y: float, focus: bool) -> None:
    """Posted move + press + release only; the real cursor stays put."""
    before = win32api.GetCursorPos()
    print("before", _bg_context(hwnd))
    if focus:
        _bg_focus(hwnd)
    cx, cy = to_client(hwnd, x, y)
    pos = win32api.MAKELONG(cx, cy)
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, pos)
    time.sleep(0.03)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, pos)
    time.sleep(0.03)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, pos)
    time.sleep(0.05)
    print(f"bgclick ref=({x:.0f},{y:.0f}) client=({cx},{cy}) focus={focus}")
    print("after ", _bg_context(hwnd), f"cursor_moved={win32api.GetCursorPos() != before}")


def bg_scroll(hwnd: int, x: float, y: float, notches: int, focus: bool) -> None:
    """Posted move + wheel; WM_MOUSEWHEEL carries screen coordinates."""
    before = win32api.GetCursorPos()
    print("before", _bg_context(hwnd))
    if focus:
        _bg_focus(hwnd)
    cx, cy = to_client(hwnd, x, y)
    abs_x, abs_y = win32gui.ClientToScreen(hwnd, (cx, cy))
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, win32api.MAKELONG(cx, cy))
    time.sleep(0.03)
    step = 1 if notches > 0 else -1
    for _ in range(abs(notches)):
        w_param = win32api.MAKELONG(0, win32con.WHEEL_DELTA * step)
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, w_param, win32api.MAKELONG(abs_x, abs_y))
        time.sleep(0.08)
    time.sleep(0.3)
    print(f"bgscroll ref=({x:.0f},{y:.0f}) notches={notches} focus={focus}")
    print("after ", _bg_context(hwnd), f"cursor_moved={win32api.GetCursorPos() != before}")


def bg_drag(
    hwnd: int, x1: float, y1: float, x2: float, y2: float, seconds: float, focus: bool
) -> None:
    """Posted press, posted moves with the button flag, posted release."""
    before = win32api.GetCursorPos()
    print("before", _bg_context(hwnd))
    if focus:
        _bg_focus(hwnd)
    sx, sy = to_client(hwnd, x1, y1)
    ex, ey = to_client(hwnd, x2, y2)
    start = win32api.MAKELONG(sx, sy)
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, start)
    time.sleep(0.03)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, start)
    time.sleep(0.05)
    steps = max(6, round(seconds / 0.03))
    for index in range(1, steps + 1):
        x = round(sx + (ex - sx) * index / steps)
        y = round(sy + (ey - sy) * index / steps)
        point = win32api.MAKELONG(x, y)
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, point)
        time.sleep(seconds / steps)
    time.sleep(0.05)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, win32api.MAKELONG(ex, ey))
    time.sleep(0.05)
    print(f"bgdrag ref=({x1:.0f},{y1:.0f})->({x2:.0f},{y2:.0f}) {seconds:.2f}s focus={focus}")
    print("after ", _bg_context(hwnd), f"cursor_moved={win32api.GetCursorPos() != before}")


def save_shot(hwnd: int, name: str, full: bool = False) -> Path:
    frame = capture(hwnd)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    full_path = OUT_DIR / f"{name}_full.png"
    cv2.imwrite(str(full_path), frame)
    ref = cv2.resize(frame, (REF_W, REF_H), interpolation=cv2.INTER_AREA)
    ref_path = OUT_DIR / f"{name}.png"
    cv2.imwrite(str(ref_path), ref)
    print(f"saved {ref_path} (1920x1080 ref) and {full_path} ({frame.shape[1]}x{frame.shape[0]})")
    return full_path if full else ref_path


def ocr(name: str, roi: tuple[int, int, int, int] | None) -> None:
    from onnxocr.onnx_paddleocr import ONNXPaddleOcr

    image = cv2.imread(str(OUT_DIR / f"{name}.png"))
    offset = (0, 0)
    if roi:
        x, y, w, h = roi
        image = image[y : y + h, x : x + w]
        offset = (x, y)
    engine = ONNXPaddleOcr(use_angle_cls=False, use_openvino=True)
    for box, (text, score) in engine.ocr(image)[0] or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        cx = offset[0] + (min(xs) + max(xs)) / 2
        cy = offset[1] + (min(ys) + max(ys)) / 2
        print(f"({cx:6.0f},{cy:5.0f}) {score:.2f} {text}")


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    command, args = argv[0], argv[1:]
    if command == "crop":
        name, *numbers = args
        x, y, w, h = map(int, numbers)
        image = cv2.imread(str(OUT_DIR / f"{name}.png"))
        out = OUT_DIR / f"{name}_crop_{x}_{y}_{w}_{h}.png"
        cv2.imwrite(str(out), image[y : y + h, x : x + w])
        print(f"saved {out}")
        return
    if command == "ocr":
        name, *numbers = args
        ocr(name, tuple(map(int, numbers)) if numbers else None)
        return

    hwnd = find_hwnd()
    if command == "info":
        rect = win32gui.GetWindowRect(hwnd)
        print(f"hwnd={hwnd} client={client_size(hwnd)} window={rect}")
    elif command == "shot":
        name = args[0] if args and not args[0].startswith("--") else time.strftime("%H%M%S")
        save_shot(hwnd, name, full="--full" in args)
    elif command in ("click", "scroll", "hold"):
        if command == "click":
            click(hwnd, float(args[0]), float(args[1]))
        elif command == "hold":
            hold(hwnd, float(args[0]), float(args[1]), float(args[2]))
        else:
            scroll(hwnd, float(args[0]), float(args[1]), int(args[2]))
        if "--shot" in args:
            time.sleep(1.5)
            save_shot(hwnd, args[args.index("--shot") + 1])
    elif command in ("bgclick", "bgscroll", "bgdrag"):
        focus = "--focus" in args
        head = args[: args.index("--shot")] if "--shot" in args else args
        numbers = [float(a) for a in head if not a.startswith("--")]
        if command == "bgclick":
            bg_click(hwnd, numbers[0], numbers[1], focus)
        elif command == "bgscroll":
            bg_scroll(hwnd, numbers[0], numbers[1], int(numbers[2]), focus)
        else:
            seconds = numbers[4] if len(numbers) > 4 else 0.6
            bg_drag(hwnd, numbers[0], numbers[1], numbers[2], numbers[3], seconds, focus)
        if "--shot" in args:
            time.sleep(1.5)
            save_shot(hwnd, args[args.index("--shot") + 1])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
