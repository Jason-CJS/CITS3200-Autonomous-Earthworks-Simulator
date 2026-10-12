"""Fast tests for experimental manual tree-avoidance decisions."""

import unittest
from types import SimpleNamespace

from scenarios.goose_navigation.run_demo import _manual_tree_collision


TRUNK_RADIUS = 0.20


class FakeBody:
    def __init__(self, x, y):
        self.position = SimpleNamespace(x=x, y=y)

    def GetPos(self):
        return self.position


class FakeDrive:
    def __init__(self, dx=0.0, dy=0.0, turn=0.0):
        self.dx = dx
        self.dy = dy
        self.turn = turn

    def evaluate(self, time):
        fraction = time / 0.15
        return SimpleNamespace(
            x=self.dx * fraction,
            y=self.dy * fraction,
            heading=self.turn * fraction,
        )


class FakeSystem:
    def GetChTime(self):
        return 0.0


class FakeVehicle:
    def __init__(self, key, dx=0.0, dy=0.0, turn=0.0):
        self.system = FakeSystem()
        self.drive = FakeDrive(dx, dy, turn)
        self.chassis = FakeBody(0.0, 0.0)

        if key == "bulldozer":
            self.blade = FakeBody(-1.3, 0.0)
        else:
            self.boom = FakeBody(0.5, 0.0)
            self.arm = FakeBody(1.4, 0.0)
            self.bucket = FakeBody(2.0, 0.0)

    def get_chassis_position(self):
        return self.chassis.GetPos()

    def get_chassis_heading(self):
        return 0.0


def tree(x, y):
    return [{"tree_id": 1, "x": x, "y": y, "z": 0.0}]


def detect(key, trees, dx=0.0, dy=0.0, turn=0.0):
    vehicle = FakeVehicle(key, dx=dx, dy=dy, turn=turn)
    return _manual_tree_collision(vehicle, key, trees, TRUNK_RADIUS)


class ManualTreeAvoidanceTests(unittest.TestCase):

    def test_bulldozer_forward_toward_tree_is_blocked(self):
        result = detect("bulldozer", tree(-1.7, 0.0), dx=-0.15)
        self.assertIsNotNone(result)

    def test_bulldozer_reverse_away_is_allowed(self):
        result = detect("bulldozer", tree(-1.7, 0.0), dx=0.15)
        self.assertIsNone(result)

    def test_bulldozer_reverse_into_rear_tree_is_blocked(self):
        result = detect("bulldozer", tree(1.5, 0.0), dx=0.15)
        self.assertIsNotNone(result)

    def test_bulldozer_forward_away_from_rear_tree_is_allowed(self):
        result = detect("bulldozer", tree(1.5, 0.0), dx=-0.15)
        self.assertIsNone(result)

    def test_bulldozer_turn_toward_tree_is_blocked(self):
        result = detect("bulldozer", tree(-1.3, -1.4), turn=0.20)
        self.assertIsNotNone(result)

    def test_bulldozer_turn_away_is_allowed(self):
        result = detect("bulldozer", tree(-1.3, -1.4), turn=-0.20)
        self.assertIsNone(result)

    def test_excavator_bucket_approach_is_blocked(self):
        result = detect("excavator", tree(3.15, 0.0), dx=0.15)
        self.assertIsNotNone(result)

    def test_excavator_bucket_escape_is_allowed(self):
        result = detect("excavator", tree(3.15, 0.0), dx=-0.15)
        self.assertIsNone(result)

    def test_either_vehicle_moves_without_nearby_trees(self):
        for key in ("bulldozer", "excavator"):
            with self.subTest(vehicle=key):
                result = detect(key, tree(50.0, 50.0), dx=0.15)
                self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
