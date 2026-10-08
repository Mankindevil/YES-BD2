import unittest
from pathlib import Path

import cv2
import numpy as np

from src.utils.stage_walk import STAGE_TARGET, WalkStep, find_stage, plan_step


def synthetic_frame(stage_center, occluder=None):
    frame = np.full((1080, 1920, 3), (60, 20, 40), dtype=np.uint8)  # purple floor
    cv2.ellipse(frame, stage_center, (140, 70), 0, 0, 360, (30, 20, 200), -1)
    cv2.rectangle(frame, (1500, 20), (1900, 250), (30, 20, 200), -1)  # red bar carpet
    if occluder:
        x, y = occluder
        cv2.rectangle(frame, (x - 30, y - 80), (x + 30, y + 20), (200, 200, 200), -1)
    return frame


class StageDetectionTest(unittest.TestCase):
    def test_finds_the_stage_and_ignores_the_carpet(self):
        center = find_stage(synthetic_frame((790, 650)))
        self.assertIsNotNone(center)
        self.assertLess(abs(center[0] - 790), 8)
        self.assertLess(abs(center[1] - 650), 8)

    def test_no_stage_in_view(self):
        frame = np.full((1080, 1920, 3), (60, 20, 40), dtype=np.uint8)
        self.assertIsNone(find_stage(frame))

    def test_live_spawn_frame_if_available(self):
        # Spawn frame from 2026-09-26: stage down-left of the character.
        path = Path(".local-dev/shots/pvp_fail.png")
        if not path.exists():
            self.skipTest("live calibration frame not present")
        center = find_stage(cv2.imread(str(path)))
        self.assertIsNotNone(center)
        self.assertLess(center[0], STAGE_TARGET[0])
        self.assertGreater(center[1], STAGE_TARGET[1])


class WalkPlanTest(unittest.TestCase):
    def test_spawn_offset_walks_the_longer_axis_first(self):
        # From spawn the stage is 135 px left (0.25 s) and 115 px down (0.29 s).
        step = plan_step((790, 650))
        self.assertEqual("s", step.key)
        self.assertGreater(step.seconds, 0.25)

    def test_directions(self):
        self.assertEqual("d", plan_step((STAGE_TARGET[0] + 200, STAGE_TARGET[1])).key)
        self.assertEqual("w", plan_step((STAGE_TARGET[0], STAGE_TARGET[1] - 200)).key)
        self.assertEqual("s", plan_step((STAGE_TARGET[0], STAGE_TARGET[1] + 200)).key)

    def test_steps_are_bounded_and_arrival_stops(self):
        far = plan_step((STAGE_TARGET[0] - 900, STAGE_TARGET[1]))
        self.assertEqual(WalkStep("a", 0.35), far)
        self.assertIsNone(plan_step((STAGE_TARGET[0] + 10, STAGE_TARGET[1] - 10)))


if __name__ == "__main__":
    unittest.main()
