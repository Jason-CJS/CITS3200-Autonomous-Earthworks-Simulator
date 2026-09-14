from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

import pychrono as chrono

from vehicles.excavator.articulation.excavator_model import ASSET_DIR, ExcavatorModel


class ExcavatorAcceptanceTest(unittest.TestCase):
    def test_assets_load_vehicle_moves_and_all_joints_articulate(self) -> None:
        system = chrono.ChSystemNSC()
        system.SetGravitationalAcceleration(chrono.ChVector3d(0.0, 0.0, -9.81))
        system.Add(chrono.ChBody())
        excavator = ExcavatorModel(system)
        self.assertEqual(excavator.body_count, 8)
        self.assertGreaterEqual(excavator.imported_vertex_count, 1000)

        start = excavator.get_chassis_position()
        targets = (0.20, 0.30, -0.40, 0.50)
        excavator.set_drive_speeds(0.60, 0.90)
        excavator.set_articulation_targets(*targets)
        for _ in range(1000):
            excavator.advance(0.001)

        displacement = (excavator.get_chassis_position() - start).Length()
        self.assertGreater(displacement, 0.5)
        self.assertGreater(abs(excavator.get_chassis_heading()), 0.05)
        self.assertGreater(abs(excavator.get_chassis_position().y - start.y), 0.02)
        for actual, expected in zip(excavator.get_joint_angles(), targets, strict=True):
            self.assertAlmostEqual(actual, expected, delta=1e-3)
        tracks = excavator.get_track_angles()
        self.assertGreater(abs(tracks[0] - tracks[1]), 0.1)

        before_stop = excavator.get_chassis_position()
        heading_before_stop = excavator.get_chassis_heading()
        excavator.set_drive_speeds(0.0, 0.0)
        excavator.advance(0.001)
        self.assertLess((excavator.get_chassis_position() - before_stop).Length(), 1e-3)
        self.assertAlmostEqual(excavator.get_chassis_heading(), heading_before_stop, delta=1e-3)
        print(
            f"PASS: Python excavator loaded {excavator.imported_vertex_count} vertices, "
            f"moved {displacement:.6f} m, and reached all four joint targets."
        )

    def test_imported_asset_hashes_match_manifest(self) -> None:
        manifest = ASSET_DIR / "SHA256SUMS"
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, filename = line.split(maxsplit=1)
            asset = ASSET_DIR / filename.lstrip("* ")
            actual = hashlib.sha256(asset.read_bytes()).hexdigest()
            self.assertEqual(actual, expected, asset.name)


if __name__ == "__main__":
    unittest.main()
