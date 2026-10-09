"""问题摘要 records: what a run looked like when it went wrong (Leo 2026-10-09)."""

import json
import logging
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from ok.task.exceptions import FinishedException, TaskDisabledException

from src.tasks import problem_report


def executor(width=1920, height=1080):
    method = SimpleNamespace(width=width, height=height, connected=lambda: True)
    window = SimpleNamespace(exists=True, width=width, height=height, hwnd=0, scaling=1.25)
    manager = SimpleNamespace(capture_method=method, hwnd_window=window)
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    return SimpleNamespace(device_manager=manager, _frame=frame)


class Task:
    def __init__(self, name="每周跑图", found=None, stage=""):
        self.name = name
        self.executor = found or executor()
        self.info = {"当前阶段": stage} if stage else {}


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        problem_report.set_root(self.folder.name)
        problem_report.install_log_ring()
        self.log = logging.getLogger("ok")
        self.log.setLevel(logging.DEBUG)

    def tearDown(self):
        self.log.removeHandler(problem_report._ring)
        problem_report._ring = None
        problem_report._current = None
        problem_report._last_written.clear()
        problem_report.set_root(None)
        self.folder.cleanup()

    def saved(self):
        return problem_report.records()

    def test_failure_keeps_the_moment_it_failed(self):
        task = Task(stage="切换卡带找第 12 章", found=executor(1467, 824))
        with problem_report.run_scope(task) as scope:
            self.log.info("BaseBD2Task:每周跑图：开始第 12 章")
            for _ in range(5):
                self.log.info("MapCollectionTask:找卡带编号 12：这页没有，往右滑")
                self.log.info("MapCollectionTask:找卡带编号 12：这页没有，往左滑")
            self.log.warning("MapCollectionTask:认不到卡带编号（相似度 0.81，要 0.95）")
            problem_report.note_problem(task, "fail")
            task.executor._frame = None  # the screen after going home
            scope.result = False
        [record] = self.saved()
        self.assertEqual("failed", record["ended"])
        problem = record["problem"]
        self.assertEqual("每周跑图", problem["task"])
        self.assertEqual("切换卡带找第 12 章", problem["stage"])
        self.assertEqual([1467, 824], problem["env"]["game_size"])
        self.assertEqual(125, problem["env"]["scaling"])
        self.assertTrue(Path(record["frame_path"]).is_file())
        texts = [(line["text"], line["count"]) for line in problem["logs"]]
        self.assertEqual(
            [
                ("每周跑图：开始第 12 章", 1),
                ("找卡带编号 12：这页没有，往右滑", 5),
                ("找卡带编号 12：这页没有，往左滑", 5),
                ("认不到卡带编号（相似度 0.81，要 0.95）", 1),
            ],
            texts,
        )

    def test_stop_keeps_where_it_stopped(self):
        task = Task(stage="找第 12 章卡带")
        with self.assertRaises(TaskDisabledException):
            with problem_report.run_scope(task):
                problem_report.note_problem(task, "stop")
                raise TaskDisabledException()
        [record] = self.saved()
        self.assertEqual("stopped", record["ended"])
        self.assertEqual("stop", record["problem"]["how"])
        self.assertEqual("找第 12 章卡带", record["problem"]["stage"])

    def test_error_without_a_note_is_captured_at_the_end(self):
        task = Task()
        with self.assertRaises(RuntimeError):
            with problem_report.run_scope(task):
                raise RuntimeError("磁盘满了")
        [record] = self.saved()
        self.assertEqual("error", record["ended"])
        self.assertEqual("磁盘满了", record["problem"]["note"])

    def test_a_good_run_keeps_facts_but_no_frame(self):
        task = Task()
        with problem_report.run_scope(task) as scope:
            self.log.info("FreeGachaTask:抽完了")
            scope.result = True
        [record] = self.saved()
        self.assertEqual("done", record["ended"])
        self.assertIsNone(record["problem"])
        self.assertNotIn("frame_path", record)
        self.assertEqual([1920, 1080], record["env"]["game_size"])
        self.assertEqual(["抽完了"], [line["text"] for line in record["logs"]])

    def test_the_first_problem_of_a_batch_wins(self):
        batch, first, second = Task("一键完成日常"), Task("烂装强化分解"), Task("每周跑图")
        with problem_report.run_scope(batch):
            with problem_report.run_scope(first):
                problem_report.note_problem(first, "fail")
            with problem_report.run_scope(second):
                problem_report.note_problem(second, "fail")
        [record] = self.saved()
        self.assertEqual("一键完成日常", record["label"])
        self.assertEqual("烂装强化分解", record["problem"]["task"])

    def test_trigger_tasks_and_app_exit_keep_nothing(self):
        task = Task()
        with problem_report.run_scope(task, keep=False):
            problem_report.note_problem(task, "fail")
        with self.assertRaises(FinishedException):
            with problem_report.run_scope(task):
                raise FinishedException()
        self.assertEqual([], self.saved())

    def test_auto_login_is_a_trigger_task(self):
        # Leo's 4K test (10-09): 自动登录游戏 runs every second and returns
        # False while it waits, which filled the page with 「失败」.
        class AutoLoginTask(Task):
            runs_by_itself = True

        self.assertTrue(problem_report.is_trigger(AutoLoginTask("自动登录游戏")))
        polled = Task("别的检查")
        polled.executor.trigger_tasks = [polled]
        self.assertTrue(problem_report.is_trigger(polled))
        self.assertFalse(problem_report.is_trigger(Task()))
        day = Path(self.folder.name) / "2026-10-09"
        day.mkdir()
        old = {"label": "自动登录游戏", "finished": 1_791_520_000.0, "ended": "failed"}
        (day / "143100-000.json").write_text(json.dumps(old), encoding="utf-8")
        self.assertEqual([], self.saved())

    def test_lines_are_kept_after_ok_resets_the_logger(self):
        # ok-script's config_logger replaces the "ok" handlers at start-up.
        self.log.removeHandler(problem_report._ring)
        task = Task(stage="关闭创造新纪录")
        with problem_report.run_scope(task) as scope:
            self.log.warning("DoomBookTask:战斗失败，已回主页")
            scope.result = False
        lines = [line["text"] for line in problem_report.logs_of(self.saved()[0])]
        self.assertIn("战斗失败，已回主页", lines)

    def test_a_quick_repeat_updates_the_last_record(self):
        task = Task(stage="找卡带")
        for _ in range(3):
            with problem_report.run_scope(task) as scope:
                problem_report.note_problem(task, "fail")
                scope.result = False
        saved = self.saved()
        self.assertEqual(1, len(saved))
        self.assertEqual(3, saved[0]["repeats"])
        self.assertEqual(1, len(list(Path(self.folder.name).glob("*/*.jpg"))))
        with problem_report.run_scope(Task("一键完成日常")) as scope:
            scope.result = True
        self.assertEqual(2, len(self.saved()))

    def test_nothing_is_kept_outside_the_app(self):
        self.log.removeHandler(problem_report._ring)
        problem_report._ring = None
        task = Task()
        with problem_report.run_scope(task):
            problem_report.note_problem(task, "fail")
        self.assertEqual([], self.saved())

    def test_other_threads_lines_stay_out(self):
        task = Task()
        with problem_report.run_scope(task):
            self.log.info("X:这次的")
            other = threading.Thread(target=lambda: self.log.info("Y:别的线程"))
            other.start()
            other.join()
            problem_report.note_problem(task, "fail")
        [record] = self.saved()
        self.assertEqual(["这次的"], [line["text"] for line in record["problem"]["logs"]])

    def test_find_matches_a_batch_summary(self):
        task = Task("一键完成日常")
        with problem_report.run_scope(task):
            pass
        [record] = self.saved()
        found = problem_report.find("一键完成日常", record["finished"] + 2)
        self.assertEqual(record["path"], found["path"])
        self.assertIsNone(problem_report.find("一键完成周常", record["finished"]))
        data = json.loads(Path(record["path"]).read_text(encoding="utf-8"))
        self.assertNotIn("path", data)


class FoldTest(unittest.TestCase):
    def test_numbers_do_not_split_a_repeat(self):
        lines = [(1, 20, "相似度 0.81"), (2, 20, "相似度 0.79"), (3, 30, "相似度 0.80")]
        [entry] = problem_report.fold(lines)
        self.assertEqual(3, entry["count"])
        self.assertEqual("相似度 0.80", entry["text"])
        self.assertEqual(30, entry["level"])

    def test_module_prefix_is_dropped(self):
        self.assertEqual("每周跑图：开始", problem_report._clean("BaseBD2Task:每周跑图：开始"))
        self.assertEqual("12:30 开始", problem_report._clean("12:30 开始"))


if __name__ == "__main__":
    unittest.main()
