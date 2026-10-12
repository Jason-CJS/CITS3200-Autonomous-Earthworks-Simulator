"""Test manual driving commands without opening the graphics window."""

import unittest
from unittest.mock import Mock

from src.demo_common import KeyboardState
from src.bulldozer_main import BulldozerController
from src.excavator_main import ExcavatorController


class ManualTreeControllerTests(unittest.TestCase):

    def test_bulldozer_w_s_and_w_again(self):
        vehicle = Mock()
        keyboard = KeyboardState(("w",))
        controller = BulldozerController(vehicle, keyboard)

        controller.update(0.0)
        vehicle.set_drive_speeds.assert_called_with(0.70, 0.70)

        keyboard._pressed = {"s"}
        controller.update(0.0)
        vehicle.set_drive_speeds.assert_called_with(-0.70, -0.70)

        keyboard._pressed = {"w"}
        controller.update(0.0)
        vehicle.set_drive_speeds.assert_called_with(0.70, 0.70)

    def test_excavator_w_s_and_w_again(self):
        vehicle = Mock()
        keyboard = KeyboardState(("w",))
        controller = ExcavatorController(vehicle, keyboard, calibration=False)

        controller.update(0.0)
        vehicle.set_drive_speeds.assert_called_with(0.75, 0.75)

        keyboard._pressed = {"s"}
        controller.update(0.0)
        vehicle.set_drive_speeds.assert_called_with(-0.75, -0.75)

        keyboard._pressed = {"w"}
        controller.update(0.0)
        vehicle.set_drive_speeds.assert_called_with(0.75, 0.75)

    def test_space_stops_both_vehicles(self):
        for vehicle_type in ("bulldozer", "excavator"):
            with self.subTest(vehicle=vehicle_type):
                vehicle = Mock()
                keyboard = KeyboardState(("w", "space"))

                if vehicle_type == "bulldozer":
                    controller = BulldozerController(vehicle, keyboard)
                else:
                    controller = ExcavatorController(
                        vehicle, keyboard, calibration=False
                    )

                controller.update(0.0)
                vehicle.set_drive_speeds.assert_called_with(0.0, 0.0)


if __name__ == "__main__":
    unittest.main()
