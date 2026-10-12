"""Test interaction between manual controls and tree avoidance."""

import unittest
from unittest.mock import Mock

from src.demo_common import KeyboardState
from src.bulldozer_main import BulldozerController
from src.excavator_main import ExcavatorController

from test_manual_tree_avoidance import FakeVehicle, tree
from scenarios.goose_navigation.run_demo import _manual_tree_collision


class ManualTreeRecoveryTests(unittest.TestCase):

    def test_forward_blocked_then_reverse_allowed(self):
        for name in ("bulldozer", "excavator"):
            with self.subTest(vehicle=name):
                vehicle = Mock()
                keyboard = KeyboardState(("w",))

                if name == "bulldozer":
                    controller = BulldozerController(vehicle, keyboard)
                    forward_speed = 0.70
                    obstacle = tree(-1.7, 0.0)
                    forward_dx = -0.15
                else:
                    controller = ExcavatorController(vehicle, keyboard, calibration=False)
                    forward_speed = 0.75
                    obstacle = tree(3.15, 0.0)
                    forward_dx = 0.15

                # The real controller requests forward movement.
                controller.update(0.0)
                vehicle.set_drive_speeds.assert_called_with(
                    forward_speed, forward_speed
                )

                # Collision detection identifies the unsafe approach.
                simulation = FakeVehicle(name, dx=forward_dx)
                hit = _manual_tree_collision(
                    simulation, name, obstacle, 0.20
                )
                self.assertIsNotNone(hit)

                # The experimental simulation loop cancels the command.
                vehicle.set_drive_speeds(0.0, 0.0)

                # Pressing S should request movement away from the tree.
                keyboard._pressed = {"s"}
                controller.update(0.0)
                vehicle.set_drive_speeds.assert_called_with(
                    -forward_speed, -forward_speed
                )

                simulation.drive.dx = -forward_dx
                hit = _manual_tree_collision(
                    simulation, name, obstacle, 0.20
                )
                self.assertIsNone(hit)


if __name__ == "__main__":
    unittest.main()
