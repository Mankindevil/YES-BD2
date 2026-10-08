import unittest
from datetime import datetime

from src.tasks import run_report
from src.utils.game_day import GAME_TZ


def _ts(text: str) -> float:
    return datetime.fromisoformat(text).replace(tzinfo=GAME_TZ).timestamp()


def _report(ended, finished, rows):
    return {"label": "一键完成日常", "ended": ended, "finished": finished, "rows": rows}


DONE = {"key": "a", "state": run_report.DONE, "started": 1.0, "note": ""}
CUT = {"key": "b", "state": run_report.SKIP, "started": 2.0, "note": "手动停止"}
WAITING = {"key": "c", "state": run_report.WAIT, "started": None, "note": ""}


class StoppedRowTest(unittest.TestCase):
    """Leo 2026-10-06: 继续 after a manual Stop, same game day only."""

    def test_continues_from_the_item_stop_cut_short(self):
        report = _report(run_report.ENDED_STOPPED, _ts("2026-10-06 10:00"), [DONE, CUT, WAITING])
        self.assertIs(CUT, run_report.stopped_row(report, now=_ts("2026-10-06 12:00")))

    def test_stop_between_items_continues_from_the_next_one(self):
        report = _report(run_report.ENDED_STOPPED, _ts("2026-10-06 10:00"), [DONE, WAITING])
        self.assertIs(WAITING, run_report.stopped_row(report, now=_ts("2026-10-06 12:00")))

    def test_after_the_08_00_reset_there_is_nothing_to_continue(self):
        report = _report(run_report.ENDED_STOPPED, _ts("2026-10-06 07:50"), [DONE, CUT])
        self.assertIsNone(run_report.stopped_row(report, now=_ts("2026-10-06 08:10")))
        # Still the same game day after midnight.
        late = _report(run_report.ENDED_STOPPED, _ts("2026-10-06 23:50"), [DONE, CUT])
        self.assertIs(CUT, run_report.stopped_row(late, now=_ts("2026-10-07 01:00")))

    def test_only_a_manual_stop_offers_continue(self):
        for ended in (run_report.ENDED_DONE, run_report.ENDED_ABORTED, run_report.ENDED_ERROR):
            report = _report(ended, _ts("2026-10-06 10:00"), [DONE, CUT])
            self.assertIsNone(run_report.stopped_row(report, now=_ts("2026-10-06 12:00")))
        self.assertIsNone(run_report.stopped_row(None))
