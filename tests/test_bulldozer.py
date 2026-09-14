from __future__ import annotations

import unittest

import pychrono as chrono

from vehicles.bulldozer.articulation.bulldozer_model import BulldozerModel


class BulldozerAcceptanceTest(unittest.TestCase):
    def test_b10_loads_moves_toward_blade_and_articulates(self) -> None:
        system = chrono.ChSystemNSC()
        system.SetGravitationalAcceleration(chrono.ChVector3d(0.0, 0.0, -9.81))
        system.Add(chrono.ChBody())
        bulldozer = BulldozerModel(system)
        self.assertEqual(bulldozer.body_count, 6)
        self.assertGreaterEqual(bulldozer.imported_vertex_count, 1000)

        start = bulldozer.get_chassis_position()
        targets = (0.30, -0.20)
        bulldozer.set_drive_speeds(0.55, 0.85)
        bulldozer.set_blade_targets(*targets)
        for _ in range(1000):
            bulldozer.advance(0.001)

        travel = bulldozer.get_chassis_position() - start
        displacement = travel.Length()
        self.assertGreater(displacement, 0.5)
        self.assertLess(travel.x, -0.5, "positive track commands must move toward the negative-X blade")
        self.assertGreater(abs(bulldozer.get_chassis_heading()), 0.05)
        self.assertGreater(abs(travel.y), 0.02)
        for actual, expected in zip(bulldozer.get_blade_state(), targets, strict=True):
            self.assertAlmostEqual(actual, expected, delta=1e-3)
        tracks = bulldozer.get_track_angles()
        self.assertGreater(abs(tracks[0] - tracks[1]), 0.1)

        before_stop = bulldozer.get_chassis_position()
        heading_before_stop = bulldozer.get_chassis_heading()
        bulldozer.set_drive_speeds(0.0, 0.0)
        bulldozer.advance(0.001)
        self.assertLess((bulldozer.get_chassis_position() - before_stop).Length(), 1e-3)
        self.assertAlmostEqual(bulldozer.get_chassis_heading(), heading_before_stop, delta=1e-3)
        print(
            f"PASS: Python bulldozer loaded {bulldozer.imported_vertex_count} B10 vertices, "
            f"moved {displacement:.6f} m toward its blade, and articulated lift/tilt."
        )


if __name__ == "__main__":
    unittest.main()
