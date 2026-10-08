import unittest

import numpy as np

from src.tasks.claim_page import SETTLED_BRIGHTNESS_RATIO, ClaimPageMixin


def frame(title_level: int, body_level: int, height: int = 2160, width: int = 3840):
    image = np.full((height, width, 3), body_level, dtype=np.uint8)
    image[: round(110 / 1080 * height), : round(760 / 1920 * width)] = title_level
    return image


class SettleBrightnessTest(unittest.TestCase):
    def test_emptied_page_content_does_not_count_as_an_overlay(self):
        # Claiming all mail darkens the list area but not the title bar.
        before = ClaimPageMixin._frame_brightness(frame(title_level=36, body_level=60))
        after = ClaimPageMixin._frame_brightness(frame(title_level=36, body_level=20))
        self.assertGreaterEqual(after, before * SETTLED_BRIGHTNESS_RATIO)

    def test_overlay_dimming_the_title_bar_is_detected(self):
        before = ClaimPageMixin._frame_brightness(frame(title_level=74, body_level=56))
        dimmed = ClaimPageMixin._frame_brightness(frame(title_level=15, body_level=25))
        self.assertLess(dimmed, before * SETTLED_BRIGHTNESS_RATIO)

    def test_works_at_1080p_too(self):
        self.assertAlmostEqual(
            ClaimPageMixin._frame_brightness(frame(40, 90, 1080, 1920)),
            ClaimPageMixin._frame_brightness(frame(40, 10, 2160, 3840)),
            delta=1.0,
        )


class TitleWaitTest(unittest.TestCase):
    """Live 2026-09-27: 17 s of an unchanged 消耗品 page looked like a freeze."""

    def _task(self, titles):
        from types import SimpleNamespace
        from unittest.mock import patch

        clock = [0.0]
        reads = iter(titles)
        task = object.__new__(ClaimPageMixin)
        task.config = {}
        task.claim_log_name = "test"
        task.capture_frame = lambda: None
        task._page_title_text = lambda _f, _l: next(reads)
        task._match = lambda *_a: SimpleNamespace(score=-1.0)
        task.info_set = lambda *_a: None
        task.log_info = lambda *_a, **_k: None
        task._save_flow_diagnostic = lambda *_a: None
        task.sleep = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
        patcher = patch("src.tasks.claim_page.monotonic", lambda: clock[0])
        patcher.start()
        self.addCleanup(patcher.stop)
        return task, clock

    def test_unchanged_other_title_stops_the_wait_early(self):
        task, clock = self._task(["消耗品149/320"] * 40)
        self.assertFalse(task._wait_for_title("装备", ("装备",)))
        self.assertLessEqual(clock[0], 4.0)

    def test_loading_without_a_title_waits_for_the_page(self):
        task, _clock = self._task([""] * 12 + ["装备450/800"])
        self.assertTrue(task._wait_for_title("装备", ("装备",)))

    def test_title_changing_during_a_transition_is_not_cut_short(self):
        task, _clock = self._task(["消耗品"] * 5 + [""] * 4 + ["装备"])
        self.assertTrue(task._wait_for_title("装备", ("装备",)))


if __name__ == "__main__":
    unittest.main()


class OverrideSignatureTest(unittest.TestCase):
    """Live 2026-09-28: a shared helper added to ClaimPageMixin had the name
    of CraftGearTask's own method, and craft gear crashed on the bag page."""

    def test_task_overrides_keep_the_mixin_signatures(self):
        import importlib
        import inspect
        import pkgutil

        import src.tasks as tasks_pkg

        for module_info in pkgutil.iter_modules(tasks_pkg.__path__):
            importlib.import_module(f"src.tasks.{module_info.name}")

        def subclasses(cls):
            for sub in cls.__subclasses__():
                yield sub
                yield from subclasses(sub)

        shared = {
            name: member
            for name, member in vars(ClaimPageMixin).items()
            if inspect.isfunction(member)
        }
        for cls in set(subclasses(ClaimPageMixin)):
            for name, base in shared.items():
                override = vars(cls).get(name)
                if override is None or not inspect.isfunction(override):
                    continue
                with self.subTest(cls=cls.__name__, method=name):
                    self.assertEqual(
                        list(inspect.signature(base).parameters),
                        list(inspect.signature(override).parameters),
                    )
