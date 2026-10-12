"""Tests for GOOSE bulldozer tree obstacle detection."""

import unittest
from types import SimpleNamespace

from scenarios.goose_navigation.run_demo import _tree_ahead_of_blade
from src.bulldozer_main import BulldozerController


class TestTreeNavigation(unittest.TestCase):

    def setUp(self):
        # Chassis at X=4 and blade at X=3 means the bulldozer faces -X.
        self.bulldozer = self.make_bulldozer(
            chassis=(4.0, 0.0),
            blade=(3.0, 0.0),
        )
        self.trunk_radius = 0.20

    @staticmethod
    def make_bulldozer(*, chassis, blade):
        chassis_position = SimpleNamespace(x=chassis[0], y=chassis[1])
        blade_position = SimpleNamespace(x=blade[0], y=blade[1])

        return SimpleNamespace(
            chassis=SimpleNamespace(GetPos=lambda: chassis_position),
            blade=SimpleNamespace(GetPos=lambda: blade_position),
        )

    @staticmethod
    def make_tree(tree_id, x, y):
        return {
            "tree_id": tree_id,
            "x": x,
            "y": y,
            "z": 0.0,
        }

    def test_tree_directly_ahead(self):
        tree = self.make_tree(10, 2.65, 0.0)

        result = _tree_ahead_of_blade(
            self.bulldozer,
            [tree],
            self.trunk_radius,
        )

        self.assertEqual(result, tree)

    def test_tree_outside_blade_width(self):
        tree = self.make_tree(11, 2.65, 3.0)

        result = _tree_ahead_of_blade(
            self.bulldozer,
            [tree],
            self.trunk_radius,
        )

        self.assertIsNone(result)

    def test_tree_behind_blade(self):
        tree = self.make_tree(12, 3.50, 0.0)

        result = _tree_ahead_of_blade(
            self.bulldozer,
            [tree],
            self.trunk_radius,
        )

        self.assertIsNone(result)

    def test_tree_detection_follows_bulldozer_orientation(self):
        # Rotate the vehicle 90 degrees so its blade faces +Y.
        bulldozer = self.make_bulldozer(
            chassis=(0.0, 0.0),
            blade=(0.0, 1.0),
        )
        tree = self.make_tree(13, 0.0, 1.35)

        result = _tree_ahead_of_blade(
            bulldozer,
            [tree],
            self.trunk_radius,
        )

        self.assertEqual(result, tree)

    def test_rotated_vehicle_ignores_tree_behind_blade(self):
        bulldozer = self.make_bulldozer(
            chassis=(0.0, 0.0),
            blade=(0.0, 1.0),
        )
        tree = self.make_tree(14, 0.0, 0.65)

        result = _tree_ahead_of_blade(
            bulldozer,
            [tree],
            self.trunk_radius,
        )

        self.assertIsNone(result)



class TestManualTreeBlocking(unittest.TestCase):

    class FakeKeyboard:
        def __init__(self, *pressed):
            self.pressed = set(pressed)

        def is_down(self, key):
            return key in self.pressed

    class FakeBulldozer:
        def __init__(self):
            self.drive_speeds = None
            self.blade_targets = None

        def set_drive_speeds(self, left, right):
            self.drive_speeds = (left, right)

        def set_blade_targets(self, lift, tilt):
            self.blade_targets = (lift, tilt)

    def make_controller(self, *pressed):
        bulldozer = self.FakeBulldozer()
        keyboard = self.FakeKeyboard(*pressed)
        return bulldozer, BulldozerController(bulldozer, keyboard)

    def test_forward_input_is_blocked_at_tree(self):
        bulldozer, controller = self.make_controller("w")

        controller.update(0.1, block_forward=True)

        self.assertEqual(bulldozer.drive_speeds, (0.0, 0.0))

    def test_reverse_remains_available_at_tree(self):
        bulldozer, controller = self.make_controller("s")

        controller.update(0.1, block_forward=True)

        self.assertEqual(bulldozer.drive_speeds, (-0.70, -0.70))

    def test_steering_remains_available_at_tree(self):
        bulldozer, controller = self.make_controller("a")

        controller.update(0.1, block_forward=True)

        self.assertEqual(bulldozer.drive_speeds, (0.48, -0.48))

    def test_forward_behaves_normally_without_tree(self):
        bulldozer, controller = self.make_controller("w")

        controller.update(0.1, block_forward=False)

        self.assertEqual(bulldozer.drive_speeds, (0.70, 0.70))

if __name__ == "__main__":
    unittest.main()
