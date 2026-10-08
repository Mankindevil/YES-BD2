"""Save a 960x540 frame of the game window every 3 s (developer helper).

    .venv\\Scripts\\python.exe tools\\recorder.py

Frames go to .local-dev/rec/<MMDD_HHMM>/HHMMSS.jpg; look back through them when
a run stalls.  Stop it with Ctrl+C (or end the python process).
"""

import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bd2dev  # noqa: E402

out = Path(__file__).resolve().parents[1] / ".local-dev" / "rec" / time.strftime("%m%d_%H%M")
out.mkdir(parents=True, exist_ok=True)
print(out, flush=True)
while True:
    try:
        frame = bd2dev.capture(bd2dev.find_hwnd())
        small = cv2.resize(frame, (960, 540), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out / f"{time.strftime('%H%M%S')}.jpg"), small, [cv2.IMWRITE_JPEG_QUALITY, 80])
    except BaseException as exc:  # keep recording through transient failures
        if isinstance(exc, KeyboardInterrupt):
            raise
        print("capture failed:", exc, flush=True)
    time.sleep(3)
