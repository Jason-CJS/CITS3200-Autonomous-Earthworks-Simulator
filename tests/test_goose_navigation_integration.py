"""Real PyChrono acceptance checks for both vehicles on generated GOOSE terrain."""

from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pychrono as chrono

from environments.terrain import build_heightmap as converter, goose_environment
from scenarios.goose_navigation.run_demo import DEFAULT_CONFIG, parse_args, run_demo
from scenarios.goose_navigation.traversal import SceneGrid
from scenarios.goose_navigation.vehicles import EXCAVATOR_TARGETS, NavigationVehicle, select_vehicle
from src.demo_common import KeyboardState


REPO_ROOT = Path(__file__).resolve().parents[1]


class NavigationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.addClassCleanup(cls.temporary.cleanup)
        dataset = cls.root / "data"
        lidar = dataset / "lidar" / "val" / "alice_scenario02"
        labels = dataset / "labels" / "val" / "alice_scenario02"
        lidar.mkdir(parents=True)
        labels.mkdir(parents=True)
        axis_x, axis_y = np.linspace(-12, 12, 97), np.linspace(-8, 8, 65)
        xx, yy = np.meshgrid(axis_x, axis_y)
        points = np.column_stack((xx.ravel(), yy.ravel(), np.zeros(xx.size),
                                  np.ones(xx.size))).astype(np.float32)
        prefix = "alice_scenario02_sequence07_0000_123"
        points.tofile(lidar / f"{prefix}_pcl.bin")
        np.full(len(points), 31, dtype=np.uint32).tofile(labels / f"{prefix}_goose.label")
        with redirect_stdout(io.StringIO()):
            cls.scene_path = converter.build_scene(Namespace(
                dataset=dataset, split="val", scenario="alice_scenario02", sequence="07",
                frame_index=0, bounds=(-12, 12, -8, 8), quality="balanced", resolution=0.25,
                grid_spacing=0.25, height_percentile=20.0, smooth_passes=0,
                ground_classes=["soil"], output=cls.root / "generated",
            ))

    def arguments(self, vehicle: str, output: str):
        return parse_args([
            "--scene", str(self.scene_path), "--vehicle", vehicle,
            "--start-x", "-4", "--start-y", "1", "--duration", "0.4", "--speed", "0.5",
            "--headless", "--output-dir", str(self.root / output),
        ])

    def test_both_scripted_paths_share_the_terrain_system_and_export_motion(self) -> None:
        original = NavigationVehicle.create_model
        for name, direction in (("bulldozer", -1), ("excavator", 1)):
            with self.subTest(vehicle=name):
                models = []

                def create_model(selected, system, initial_xy, terrain_height):
                    model = original(selected, system, initial_xy, terrain_height)
                    models.append(model)
                    return model

                args = self.arguments(name, name)
                with patch.object(NavigationVehicle, "create_model", create_model), \
                        patch.object(goose_environment, "create_terrain",
                                     wraps=goose_environment.create_terrain) as terrain_call, \
                        redirect_stdout(io.StringIO()):
                    self.assertEqual(run_demo(args), 0)
                self.assertIs(models[0].system, terrain_call.call_args.args[0])
                self.assertFalse(models[0].ground.IsCollisionEnabled())
                self.assertIsInstance(models[0].system, chrono.ChSystemSMC)
                self.assertAlmostEqual(models[0].system.GetChTime(), 0.4)
                manifest = json.loads((args.output_dir / "run_manifest.json").read_text())
                self.assertEqual(manifest["vehicle_key"], name)
                self.assertEqual(manifest["vehicle"], select_vehicle(name).label)
                self.assertEqual(manifest["status"], "completed")
                self.assertGreater(manifest["scm_modified_nodes"], 0)
                self.assertAlmostEqual(manifest["displacement_m"], 0.2, delta=0.003)
                with (args.output_dir / "trajectory.csv").open(newline="") as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(len(rows), 5)
                self.assertAlmostEqual(float(rows[0]["x_m"]), -4.0)
                self.assertAlmostEqual(float(rows[0]["y_m"]), 1.0)
                self.assertAlmostEqual(float(rows[-1]["x_m"]), -4.0 + direction * 0.2,
                                       delta=0.003)
                self.assertTrue(all(row["coarse_semantic_class"] == "terrain" for row in rows))
                self.assertTrue((args.output_dir / "route_overlay.png").is_file())

    def test_excavator_repeated_headless_runs_have_identical_trajectories(self) -> None:
        for output in ("repeat1", "repeat2"):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(run_demo(self.arguments("excavator", output)), 0)
        for filename in ("trajectory.csv", "run_manifest.json", "route_overlay.png"):
            self.assertEqual((self.root / "repeat1" / filename).read_bytes(),
                             (self.root / "repeat2" / filename).read_bytes(), filename)

    def test_manual_excavator_keys_drive_stop_articulate_and_reset(self) -> None:
        system = goose_environment.create_system()
        scene = SceneGrid.load(self.scene_path)
        config = json.loads(DEFAULT_CONFIG.read_text())
        terrain = goose_environment.create_terrain(system, scene.path, scene.metadata, config)
        selected = select_vehicle("excavator")
        model = selected.create_model(system, (-4.0, 1.0), scene.height_at(-4, 1))
        text = "\n".join(selected.controls)
        for label in ("W / S", "A / D", "SPACE", "Q / E", "R / F", "T / G", "Y / H", "X"):
            self.assertIn(label, text)
        self.assertNotIn("blade", text)

        def command(keys):
            controller = selected.create_controller(model, KeyboardState(keys))
            controller.update(0.2)
            for _ in range(500):
                terrain.Synchronize(system.GetChTime())
                model.advance(0.002)
                terrain.Advance(0.002)
            return controller

        start = model.get_chassis_position().x
        command(("w",))
        self.assertGreater(model.get_chassis_position().x, start + 0.1)
        start = model.get_chassis_position().x
        command(("s",))
        self.assertLess(model.get_chassis_position().x, start - 0.1)
        for key, sign in (("a", 1), ("d", -1)):
            before = model.get_chassis_heading()
            command((key,))
            self.assertGreater(sign * (model.get_chassis_heading() - before), 0.03)
        before = model.get_chassis_position()
        command(("w", "space"))
        self.assertLess((model.get_chassis_position() - before).Length(), 0.002)
        for keys, sign in ((("q", "r", "t", "y"), 1),
                           (("e", "f", "g", "h"), -1), (("x",), 0)):
            controller = command(keys)
            expected = [target + sign * rate * 0.2 for target, rate in
                        zip(EXCAVATOR_TARGETS, (0.70, 0.55, 0.65, 0.85), strict=True)]
            np.testing.assert_allclose(controller.targets, expected, atol=1e-12)
            for actual, target in zip(model.get_joint_angles(), expected, strict=True):
                self.assertAlmostEqual(actual, target, delta=0.003)
        self.assertEqual(controller.targets, list(EXCAVATOR_TARGETS))
        self.assertGreater(len(terrain.GetModifiedNodes(True)), 0)

    def test_navigation_graphics_smoke_reuses_each_manual_controller(self) -> None:
        for name in ("bulldozer", "excavator"):
            with self.subTest(vehicle=name):
                result = subprocess.run([
                    sys.executable, "-m", "scenarios.goose_navigation.run_demo",
                    "--scene", str(self.scene_path), "--vehicle", name, "--mode", "manual",
                    "--start-x", "-4", "--start-y", "1", "--duration", "0.2",
                    "--smoke-test", "--output-dir", str(self.root / f"graphics_{name}"),
                ], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                manifest = json.loads((self.root / f"graphics_{name}" / "run_manifest.json").read_text())
                self.assertEqual(manifest["mode"], "manual_keyboard")
                self.assertGreater(manifest["displacement_m"], 0.1)
                self.assertGreater(manifest["scm_modified_nodes"], 0)

    def test_optional_tree_and_rural_placements_load_in_main_demo(self) -> None:
        """Load available scene objects without requiring them in older scenes."""
        scene_dir = self.scene_path.parent
        tree_path = scene_dir / "tree_placements.json"
        rural_path = scene_dir / "rural_placements.json"

        self.assertFalse(tree_path.exists())
        self.assertFalse(rural_path.exists())

        from environments.vegetation import (
            goose_vegetation_objects,
            goose_rural_objects,
        )

        try:
            # Existing scenes without optional vegetation must still run.
            with patch.object(
                goose_vegetation_objects, "create_trees"
            ) as tree_loader, patch.object(
                goose_rural_objects, "create_rural_objects"
            ) as rural_loader, redirect_stdout(io.StringIO()):
                args = self.arguments("bulldozer", "without_rural")
                self.assertEqual(run_demo(args), 0)
                tree_loader.assert_not_called()
                rural_loader.assert_not_called()

            # The main demo should call both loaders when files exist.
            tree_path.write_text('{"trees": []}', encoding="utf-8")
            rural_path.write_text('{"placements": []}', encoding="utf-8")

            with patch.object(
                goose_vegetation_objects,
                "create_trees",
                return_value=[],
            ) as tree_loader, patch.object(
                goose_rural_objects,
                "create_rural_objects",
                return_value=[],
            ) as rural_loader, redirect_stdout(io.StringIO()):
                args = self.arguments("bulldozer", "with_rural")
                self.assertEqual(run_demo(args), 0)

                tree_loader.assert_called_once()
                rural_loader.assert_called_once()

                self.assertEqual(tree_loader.call_args.args[1], tree_path)
                self.assertEqual(rural_loader.call_args.args[1], rural_path)

                self.assertIs(
                    tree_loader.call_args.args[0],
                    rural_loader.call_args.args[0],
                )
        finally:
            tree_path.unlink(missing_ok=True)
            rural_path.unlink(missing_ok=True)

    def test_imports_do_not_load_chrono_open_windows_or_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code = (
                "import sys\n"
                f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
                "from pathlib import Path\n"
                "import scenarios.goose_navigation.run_demo\n"
                "import scenarios.goose_navigation.vehicles\n"
                "assert 'pychrono' not in sys.modules\n"
                "assert list(Path('.').iterdir()) == []\n"
            )
            result = subprocess.run([sys.executable, "-B", "-c", code], cwd=directory,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
