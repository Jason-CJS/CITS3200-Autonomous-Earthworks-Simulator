"""Portable checks for the GOOSE-Ex bulldozer route and saved outputs."""

from __future__ import annotations

import csv
from argparse import Namespace
import json
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np

from environments import terrain as terrain_package
from vehicles.bulldozer import articulation as bulldozer_package
from scenarios.goose_navigation.traversal import (
    SceneGrid,
    TrajectorySample,
    exact_steps,
    write_route_overlay,
    write_trajectory,
)
from scenarios.goose_navigation.run_demo import run_demo


def make_scene(root: Path) -> Path:
    heights = np.array([[10 * row + col for col in range(7)] for row in range(5)])
    np.save(root / "height_grid.npy", heights)
    (root / "heightmap.bmp").write_bytes(b"fixture")
    path = root / "scene.json"
    path.write_text(
        json.dumps({
            "format_version": 1,
            "heightmap": "heightmap.bmp",
            "height_grid": "height_grid.npy",
            "size_x": 12.0,
            "size_y": 8.0,
            "bounds_xy": {"xmin": -6, "xmax": 6, "ymin": -4, "ymax": 4},
            "grid": {
                "width": 7, "height": 5, "x_spacing": 2, "y_spacing": 2,
                "row_zero": "ymax", "column_zero": "xmin",
            },
        }),
        encoding="utf-8",
    )
    return path


class SceneGridTests(unittest.TestCase):
    def test_chrono_coordinates_follow_manifest_grid_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = SceneGrid.load(make_scene(Path(tmp)))
            self.assertEqual(scene.height_at(-6, 4), 0)
            self.assertEqual(scene.height_at(0, 0), 23)
            self.assertEqual(scene.height_at(6, -4), 46)
            self.assertAlmostEqual(scene.height_at(1, 1), 18.5)

    def test_route_checks_the_blade_footprint_and_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = SceneGrid.load(make_scene(Path(tmp)))
            scene.validate_route(0, 0, 0.6, 6)
            with self.assertRaisesRegex(ValueError, "leaves the generated terrain"):
                scene.validate_route(0, 0, 0.6, 10)
            with self.assertRaisesRegex(ValueError, "leaves the generated terrain"):
                scene.validate_route(0, 3, 0.6, 6)
            with self.assertRaisesRegex(ValueError, "must be finite"):
                scene.validate_route(0, 0, float("nan"), 6)

    def test_rejects_missing_or_misaligned_grid_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = make_scene(root)
            metadata = json.loads(path.read_text(encoding="utf-8"))
            metadata["grid"]["row_zero"] = "ymin"
            path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "orientation"):
                SceneGrid.load(path)

            metadata["grid"]["row_zero"] = "ymax"
            path.write_text(json.dumps(metadata), encoding="utf-8")
            np.save(root / "height_grid.npy", np.ones((3, 3)))
            with self.assertRaisesRegex(ValueError, "wrong shape"):
                SceneGrid.load(path)

    def test_fixed_step_sampling_requires_exact_multiples(self) -> None:
        self.assertEqual(exact_steps(6.0, 0.002, "duration"), 3000)
        self.assertEqual(exact_steps(0.1, 0.002, "sample period"), 50)
        with self.assertRaisesRegex(ValueError, "multiple"):
            exact_steps(0.101, 0.002, "sample period")

    def test_exports_trajectory_and_route_on_heightmap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene = SceneGrid.load(make_scene(root))
            samples = [
                TrajectorySample(0.0, 0.0, 0.0, 23.0, 0.0),
                TrajectorySample(1.0, -0.6, 0.0, 23.0, 0.0),
            ]
            csv_path, png_path = root / "trajectory.csv", root / "route_overlay.png"
            write_trajectory(samples, csv_path)
            write_route_overlay(scene, samples, png_path)
            with csv_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["time_s"] for row in rows], ["0.000000", "1.000000"])
            self.assertEqual(rows[1]["x_m"], "-0.600000")
            self.assertEqual(rows[1]["coarse_semantic_class"], "")
            self.assertEqual(png_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_scripted_run_records_chassis_motion_and_status(self) -> None:
        """Exercise CLI orchestration with the Chrono boundary replaced."""
        class FakeSystem:
            time = 0.0

            def GetChTime(self):
                return self.time

        class FakeTerrain:
            def Synchronize(self, time):
                pass

            def Advance(self, step):
                pass

        class FakeBulldozer:
            def __init__(self, system, show_rigid_ground, initial_z_offset, initial_xy):
                self.system = system
                self.x, self.y = initial_xy
                self.z = 1.0 + initial_z_offset
                self.speed = 0.0

            def set_blade_targets(self, lift, tilt):
                pass

            def set_drive_speeds(self, left, right):
                self.speed = left

            def advance(self, step):
                self.x -= self.speed * step
                self.system.time += step

            def get_chassis_position(self):
                return SimpleNamespace(x=self.x, y=self.y, z=self.z)

            def get_chassis_heading(self):
                return 0.0

        chrono = ModuleType("pychrono")
        chrono.ChVector3d = lambda *values: values
        terrain_module = ModuleType("environments.terrain.goose_environment")
        terrain_module.create_system = FakeSystem
        terrain_module.create_terrain = lambda *args: FakeTerrain()
        dozer_module = ModuleType("vehicles.bulldozer.articulation.bulldozer_model")
        dozer_module.BulldozerModel = FakeBulldozer
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene_path = make_scene(root)
            config_path = root / "scm.json"
            config_path.write_text(json.dumps({"step_size": 0.1}), encoding="utf-8")
            args = Namespace(
                scene=scene_path, config=config_path, output_dir=root / "out",
                start_x=0.0, start_y=0.0, speed=0.5, duration=2.0,
                sample_period=0.5, headless=True,
            )
            with patch.dict(sys.modules, {
                "pychrono": chrono,
                "environments.terrain.goose_environment": terrain_module,
                "vehicles.bulldozer.articulation.bulldozer_model": dozer_module,
            }), patch.object(
                terrain_package, "goose_environment", terrain_module, create=True
            ), patch.object(
                bulldozer_package, "bulldozer_model", dozer_module, create=True
            ):
                self.assertEqual(run_demo(args), 0)
            manifest = json.loads((root / "out/run_manifest.json").read_text(encoding="utf-8"))
            with (root / "out/trajectory.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(manifest["status"], "completed")
            self.assertAlmostEqual(manifest["displacement_m"], 1.0)
            self.assertEqual(len(rows), 5)  # Initial state and four half-second samples.
            self.assertEqual(rows[-1]["x_m"], "-1.000000")


if __name__ == "__main__":
    unittest.main()
