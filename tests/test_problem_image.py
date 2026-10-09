"""The 问题摘要 picture, its four lines of text and the 回报问题 page (Leo 2026-10-09)."""

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from src.tasks import problem_report
from src.ui.shell import problem_image

FINISHED = 1_791_520_000.0


def record(**changes):
    found = {
        "label": "一键完成日常",
        "started": FINISHED - 600,
        "finished": FINISHED,
        "ended": "stopped",
        "counts": {"done": 13, "skip": 1, "fail": 0},
        "problem": {
            "at": FINISHED,
            "how": "stop",
            "task": "每周跑图",
            "stage": "切换卡带找第 12 章",
            "note": "手动停止",
            "env": {
                "version": "0.1.11",
                "game_size": [1467, 824],
                "window_mode": "窗口化",
                "monitor": [1920, 1080],
                "scaling": 125,
                "hdr": False,
                "clone": False,
                "ui_language": "简体中文",
            },
            "logs": [
                {"at": FINISHED - 9, "level": 20, "text": "每周跑图：开始第 12 章", "count": 1},
                {"at": FINISHED - 5, "level": 30, "text": "认不到卡带编号（相似度 0.81，要 0.95）",
                 "count": 36},
                {"at": FINISHED - 1, "level": 20, "text": "回到主页", "count": 1},
            ],
        },
    }
    found.update(changes)
    return found


class SummaryTextTest(unittest.TestCase):
    def test_four_short_lines(self):
        lines = problem_image.summary_text(record()).splitlines()
        self.assertEqual(
            [
                "【YES-BD2 v0.1.11】一键完成日常 · 手动停止",
                "停在：每周跑图 · 切换卡带找第 12 章 · 手动停止",
                "画面：1467×824 窗口化 · 缩放 125% · HDR 关 · 简体中文 · 没用分身",
                "最后：认不到卡带编号（相似度 0.81，要 0.95），重复 36 次",
            ],
            lines,
        )

    def test_a_good_run(self):
        good = record(ended="done", problem=None, env={"game_size": [1920, 1080]}, logs=[])
        lines = problem_image.summary_text(good).splitlines()
        self.assertEqual("【YES-BD2】一键完成日常 · 全部完成", lines[0])
        self.assertEqual("没有失败，也没有中途停下", lines[1])
        self.assertEqual("画面：1920×1080", lines[2])
        self.assertEqual(3, len(lines))

    def test_version_has_one_v(self):
        # The installed tool saves its version as 「v0.1.11」 (Leo's 4K test, 10-09).
        lines = problem_image.summary_text(record(problem={**record()["problem"], "env": {
            **record()["problem"]["env"], "version": "v0.1.11"}})).splitlines()
        self.assertTrue(lines[0].startswith("【YES-BD2 v0.1.11】"))
        self.assertEqual("", problem_image.version_text({}))

    def test_file_name_has_the_time(self):
        name = problem_image.file_name(record())
        self.assertTrue(name.startswith("YES-BD2-问题-"))
        self.assertTrue(name.endswith(".png"))


class PictureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_picture_with_and_without_the_game_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            frame = Path(folder) / "frame.jpg"
            cv2.imwrite(str(frame), np.full((864, 1536, 3), 40, dtype=np.uint8))
            plain = problem_image.render(record())
            framed = problem_image.render(record(frame_path=str(frame)))
            saved = problem_image.save_image(record(), Path(folder))
            self.assertTrue(saved is not None and saved.is_file())
        self.assertEqual(problem_image.WIDTH * problem_image.SCALE, plain.width())
        # The frame adds a picture as wide as the card, in the game's shape.
        self.assertGreater(framed.height() - plain.height(), 400 * problem_image.SCALE)

    def test_page_lists_the_runs_newest_first(self):
        from src.ui.shell.problem_page import ProblemPage

        with tempfile.TemporaryDirectory() as folder:
            problem_report.set_root(folder)
            self.addCleanup(problem_report.set_root, None)
            for index, ended in enumerate(("done", "stopped")):
                day = Path(folder) / "2026-10-09"
                day.mkdir(exist_ok=True)
                body = record(ended=ended, finished=FINISHED + index)
                (day / f"0{index}.json").write_text(json.dumps(body), encoding="utf-8")
            page = ProblemPage()
            page.refresh()
            self.assertEqual(2, len(page._rows))
            self.assertTrue(page._rows[0].path.endswith("01.json"))
            self.assertTrue(page._rows[0]._selected)
            self.assertTrue(page.actions.copy_image.isEnabled())


class ScrubTest(unittest.TestCase):
    def test_no_user_name_in_a_record(self):
        # D: here: the public-copy check flags any C: user folder in the source.
        self.assertEqual(
            r"打不开 D:\Users\<用户>\AppData\x.png",
            problem_report.scrub(r"打不开 D:\Users\李 小明\AppData\x.png"),
        )
        self.assertEqual("e:/users/<用户>/x", problem_report.scrub("e:/users/bob/x"))


if __name__ == "__main__":
    unittest.main()
