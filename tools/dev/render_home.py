"""Draw the idle home page to a PNG and print how tall it needs to be (layout
check for the first-open window size, no game, no executor).

    python tools/dev/render_home.py <out.png> [page width] [page height]

The page width is the window width minus the sidebar (1335 - 224 by default).
"""

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from src.tasks.DailyBatchTask import DAILY_BATCH_CHILDREN  # noqa: E402
from src.ui.shell import data  # noqa: E402

batch = SimpleNamespace(
    name=data.DAILY_BATCH, child_tasks=DAILY_BATCH_CHILDREN, config={}, info={}
)
data.task_by_name = lambda name: batch if name == data.DAILY_BATCH else None
data.busy = lambda: False
data.executor = lambda: None

from src.ui.shell.home import HomePage  # noqa: E402

out = sys.argv[1]
width = int(sys.argv[2]) if len(sys.argv) > 2 else 1335 - 224
height = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
page = HomePage(lambda *_a: None, lambda *_a: None)
page.resize(width, height)
page.show()
for _ in range(5):
    app.processEvents()
page._refresh_idle()
for _ in range(5):
    app.processEvents()
needed = page.view.heightForWidth(width)
if needed <= 0:
    needed = page.view.sizeHint().height()
print(f"page {width}x{height}: content needs {needed} px")
page.resize(width, max(height, needed))
for _ in range(3):
    app.processEvents()
page.grab().save(out)
print("saved", out)
