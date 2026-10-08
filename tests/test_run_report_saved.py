import json
import tempfile
import unittest
from pathlib import Path

from src.tasks import run_report
from src.ui.shell.home import summary_switch_text


class SavedReportsTest(unittest.TestCase):
    def tearDown(self):
        run_report.set_report_file(None)

    def test_every_finished_run_newest_first(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "reports.json"
            path.write_text(
                json.dumps(
                    {
                        "一键完成日常": {"label": "一键完成日常", "finished": 100},
                        "一键完成周常": {"label": "一键完成周常", "finished": 200},
                        "半截": {"label": "半截", "finished": None},
                    }
                ),
                encoding="utf-8",
            )
            run_report.set_report_file(str(path))
            labels = [report["label"] for report in run_report.saved()]
        self.assertEqual(["一键完成周常", "一键完成日常"], labels)

    def test_switch_text(self):
        self.assertEqual("日常的结果", summary_switch_text("一键完成日常"))
