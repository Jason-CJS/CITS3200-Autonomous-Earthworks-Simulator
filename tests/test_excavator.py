from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

import numpy as np
import pychrono as chrono

from vehicles.excavator.articulation.excavator_model import ASSET_DIR, ExcavatorModel
from vehicles.excavator.articulation.excavator_visuals import HydraulicCylinder, shoe_poses


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

    def test_initial_z_offset_moves_all_motor_frames(self) -> None:
        offset = -0.15

        baseline = ExcavatorModel(
            chrono.ChSystemSMC(),
            show_rigid_ground=False,
        )
        shifted = ExcavatorModel(
            chrono.ChSystemSMC(),
            show_rigid_ground=False,
            initial_z_offset=offset,
        )

        baseline_motors = (
            *baseline.joints,
            baseline.left_track_drive,
            baseline.right_track_drive,
        )
        shifted_motors = (
            *shifted.joints,
            shifted.left_track_drive,
            shifted.right_track_drive,
        )

        for index, (baseline_motor, shifted_motor) in enumerate(
            zip(baseline_motors, shifted_motors, strict=True)
        ):
            for frame_getter in ("GetFrame1Abs", "GetFrame2Abs"):
                with self.subTest(motor=index, frame=frame_getter):
                    baseline_z = getattr(baseline_motor, frame_getter)().GetPos().z
                    shifted_z = getattr(shifted_motor, frame_getter)().GetPos().z
                    self.assertAlmostEqual(shifted_z, baseline_z + offset)

    def test_initial_xy_moves_every_vehicle_body_and_joint_together(self) -> None:
        baseline = ExcavatorModel(chrono.ChSystemSMC(), show_rigid_ground=False)
        shifted = ExcavatorModel(
            chrono.ChSystemSMC(), show_rigid_ground=False,
            initial_xy=(-4.0, 2.0), initial_z_offset=0.3,
        )
        for name in ("chassis", "cabin", "left_track", "right_track", "boom", "arm", "bucket"):
            with self.subTest(body=name):
                before = getattr(baseline, name).GetPos()
                after = getattr(shifted, name).GetPos()
                for axis, offset in (("x", -4.0), ("y", 2.0), ("z", 0.3)):
                    self.assertAlmostEqual(getattr(after, axis), getattr(before, axis) + offset)
        baseline_links = (*baseline.joints, baseline.left_track_drive, baseline.right_track_drive)
        shifted_links = (*shifted.joints, shifted.left_track_drive, shifted.right_track_drive)
        for before, after in zip(baseline_links, shifted_links, strict=True):
            for frame in ("GetFrame1Abs", "GetFrame2Abs"):
                # Keep the owning frames alive while using SWIG's position references.
                f0, f1 = getattr(before, frame)(), getattr(after, frame)()
                p0, p1 = f0.GetPos(), f1.GetPos()
                for axis, offset in (("x", -4.0), ("y", 2.0), ("z", 0.3)):
                    self.assertAlmostEqual(getattr(p1, axis), getattr(p0, axis) + offset)
        shifted.set_drive_speeds(0.5, 0.5)
        for _ in range(100):
            shifted.advance(0.002)
        self.assertAlmostEqual(shifted.get_chassis_position().x, -3.9, delta=1e-3)
        self.assertAlmostEqual(shifted.get_chassis_position().y, 2.0, delta=1e-3)
        self.assertFalse(shifted.ground.IsCollisionEnabled())

    def test_initial_position_rejects_non_finite_coordinates(self) -> None:
        for xy in ((float("nan"), 0), (0, float("inf")), (0,)):
            with self.subTest(xy=xy), self.assertRaisesRegex(ValueError, "finite coordinates"):
                ExcavatorModel(chrono.ChSystemSMC(), initial_xy=xy)

    def test_imported_asset_hashes_match_manifest(self) -> None:
        manifest = ASSET_DIR / "SHA256SUMS"
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, filename = line.split(maxsplit=1)
            asset = ASSET_DIR / filename.lstrip("* ")
            actual = hashlib.sha256(asset.read_bytes()).hexdigest()
            self.assertEqual(actual, expected, asset.name)


    def test_hydraulic_cylinders_follow_the_moving_arm_without_adding_bodies(self) -> None:
        excavator = ExcavatorModel(chrono.ChSystemSMC(), show_rigid_ground=False)
        self.assertEqual(excavator.body_count, 8)
        self.assertEqual(len(excavator.cylinders), 4)
        excavator.set_articulation_targets(0.0, 0.3, -0.8, 0.6)
        for _ in range(300):
            excavator.advance(0.002)  # advance() refreshes the cylinders itself
        rod_end = 2 * HydraulicCylinder.SIDES + 1  # centre of the rod's far cap
        for cylinder in excavator.cylinders:
            with self.subTest(rod_body=cylinder.rod_body.GetName()):
                vertex = cylinder.rod.mesh.GetCoordsVertices()[rod_end]
                drawn = cylinder.base_body.TransformPointLocalToParent(vertex)
                anchor = cylinder.rod_body.TransformPointLocalToParent(cylinder.rod_local)
                self.assertLess((drawn - anchor).Length(), 0.05)

    def test_track_shoes_travel_round_the_loop_as_the_tracks_turn(self) -> None:
        centres, normals = shoe_poses(0.0)
        moved, _ = shoe_poses(0.1)
        bottom = (np.abs(centres[:, 1] + 0.36) < 1e-9) & (centres[:, 0] > -1.4)
        np.testing.assert_allclose(moved[bottom, 0], centres[bottom, 0] - 0.1)  # bottom run moves back
        np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1.0)
        perimeter = 2 * (2 * 1.575 + np.pi * 0.36)
        np.testing.assert_allclose(shoe_poses(perimeter)[0], centres, atol=1e-9)  # one full lap
        excavator = ExcavatorModel(chrono.ChSystemSMC(), show_rigid_ground=False)
        left = excavator.track_shoes[0].mesh.mesh.GetCoordsVertices()
        before = (left[0].x, left[0].z)
        excavator.set_drive_speeds(0.5, 0.5)
        for _ in range(100):
            excavator.advance(0.002)  # advance() refreshes the shoes itself
        self.assertNotEqual(before, (left[0].x, left[0].z))


if __name__ == "__main__":
    unittest.main()
