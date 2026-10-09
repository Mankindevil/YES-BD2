import tempfile
import unittest
from pathlib import Path

from src.tasks import weekly_ticks
from src.tasks.run_history import week_start_ts

WEEK = 7 * 86400


class WeeklyTicksTest(unittest.TestCase):
    # Leo 2026-10-09: done this week = tick taken away; next week it comes back.

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "weekly_ticks.json"
        self.now = week_start_ts() + 3 * 86400
        self.runs = {}

    def sync(self, config, now=None):
        return weekly_ticks.sync(
            config,
            [("街机", "浏览街机菜单"), ("书", "末日之书")],
            self.runs.get,
            now=self.now if now is None else now,
            path=self.path,
        )

    def done(self, name, at, ok=True):
        self.runs[name] = {"finished": at, "ok": ok}

    def test_done_this_week_loses_its_tick(self):
        config = {"街机": True, "书": True}
        self.done("浏览街机菜单", self.now - 60)
        self.assertEqual(["街机"], self.sync(config))
        self.assertEqual({"街机": False, "书": True}, config)

    def test_failed_or_last_weeks_run_keeps_the_tick(self):
        config = {"街机": True, "书": True}
        self.done("浏览街机菜单", self.now - 60, ok=False)
        self.done("末日之书", week_start_ts(self.now) - 60)
        self.assertEqual([], self.sync(config))
        self.assertEqual({"街机": True, "书": True}, config)

    def test_comes_back_next_week(self):
        config = {"街机": True, "书": True}
        self.done("浏览街机菜单", self.now - 60)
        self.sync(config)
        self.assertEqual(["街机"], self.sync(config, now=self.now + WEEK))
        self.assertEqual({"街机": True, "书": True}, config)

    def test_ticked_again_by_the_player_stays_until_it_runs_again(self):
        config = {"街机": True, "书": True}
        self.done("浏览街机菜单", self.now - 60)
        self.sync(config)
        config["街机"] = True  # the player wants it once more
        self.assertEqual([], self.sync(config))
        self.assertIs(True, config["街机"])
        self.done("浏览街机菜单", self.now + 600)
        self.assertEqual(["街机"], self.sync(config, now=self.now + 700))
        self.assertIs(False, config["街机"])

    def test_the_players_own_untick_is_not_given_back(self):
        config = {"街机": True, "书": False}
        self.sync(config)
        self.assertEqual([], self.sync(config, now=self.now + WEEK))
        self.assertIs(False, config["书"])

    def test_mark_done_during_a_run(self):
        config = {"街机": True, "书": True}
        weekly_ticks.mark_done(config, "书", self.now, now=self.now, path=self.path)
        self.assertIs(False, config["书"])
        # run_history stamps the same run a moment later: not a new completion.
        self.done("末日之书", self.now + 1)
        config["书"] = True
        self.assertEqual([], self.sync(config))
        self.assertEqual(["书"], self.sync({"街机": True, "书": False}, now=self.now + WEEK))


if __name__ == "__main__":
    unittest.main()
