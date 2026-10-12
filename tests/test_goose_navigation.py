"""Portable checks for the GOOSE-Ex bulldozer route and saved outputs."""

from __future__ import annotations

import csv
from argparse import Namespace
import dataclasses
import json
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np
# The fake runs below wrap sys.modules in patch.dict, which also removes any
# module first imported inside it. SciPy and Matplotlib have C extensions that
# cannot be loaded twice in one process, so load the ones the exports use first.
import matplotlib.pyplot  # noqa: F401
import scipy.ndimage  # noqa: F401

from environments import terrain as terrain_package
from environments.terrain.goose_semantics import semantic_legend
from vehicles.bulldozer import articulation as bulldozer_package
from scenarios.goose_navigation.traversal import (
    SceneGrid,
    TrajectorySample,
    exact_steps,
    footprint_corners,
    write_route_overlay,
    write_terrain_texture,
    write_trajectory,
)
from scenarios.goose_navigation.run_demo import (
    _scm_active_domain_geometry,
    parse_args,
    run_demo,
)
from scenarios.goose_navigation.vehicles import select_vehicle


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_scene(root: Path, version: int = 2) -> Path:
    heights = np.array([[10 * row + col for col in range(7)] for row in range(5)])
    np.save(root / "height_grid.npy", heights)
    (root / "heightmap.bmp").write_bytes(b"fixture")
    path = root / "scene.json"
    metadata = {
            "format_version": version,
            "heightmap": "heightmap.bmp",
            "height_grid": "height_grid.npy",
            "size_x": 12.0,
            "size_y": 8.0,
            "bounds_xy": {"xmin": -6, "xmax": 6, "ymin": -4, "ymax": 4},
            "grid": {
                "width": 7, "height": 5, "x_spacing": 2, "y_spacing": 2,
                "row_zero": "ymax", "column_zero": "xmin",
            },
        }
    if version == 2:
        coarse = np.full(heights.shape, 2, dtype=np.uint8)
        coarse[2, 3] = 1  # Vegetation at the centre of the terrain.
        coarse[2, 4] = 255  # No semantic observation at (2, 0).
        np.save(root / "semantic_coarse.npy", coarse)
        (root / "semantic_legend.json").write_text(json.dumps(semantic_legend()), encoding="utf-8")
        metadata["outputs"] = {
            "semantic_coarse": {
                "path": "semantic_coarse.npy", "dtype": "uint8", "shape": list(heights.shape),
            },
            "semantic_legend": {"path": "semantic_legend.json"},
        }
        metadata["semantics"] = {"coarse_taxonomy": {"unobserved_id": 255}}
    path.write_text(json.dumps(metadata), encoding="utf-8")
    return path


class SceneGridTests(unittest.TestCase):
    def test_vehicle_selection_defaults_to_bulldozer_and_rejects_unknown_names(self) -> None:
        self.assertEqual(parse_args(["--scene", "scene.json"]).vehicle, "bulldozer")
        self.assertEqual(parse_args(["--scene", "scene.json", "--vehicle", "excavator"]).vehicle,
                         "excavator")
        with self.assertRaisesRegex(ValueError, "vehicle must be bulldozer or excavator"):
            select_vehicle("truck")
        with patch("sys.stderr"), self.assertRaises(SystemExit) as error:
            parse_args(["--scene", "scene.json", "--vehicle", "truck"])
        self.assertEqual(error.exception.code, 2)

    def test_excavator_route_uses_positive_x_and_its_extended_footprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = SceneGrid.load(make_scene(Path(tmp)))
            selected = select_vehicle("excavator")
            scene.validate_route(-3, 1, 0.5, 2, footprint=selected.footprint,
                                 direction=selected.direction)
            # The rear fits here, but the extended boom would leave +X.
            with self.assertRaisesRegex(ValueError, "excavator starting footprint"):
                scene.validate_start(1, 0, footprint=selected.footprint)
            # Both endpoints need the full boom/bucket clearance.
            with self.assertRaisesRegex(ValueError, "scripted route or excavator footprint"):
                scene.validate_route(-3, 0, 0.5, 10, footprint=selected.footprint,
                                     direction=selected.direction)
            with self.assertRaisesRegex(ValueError, "excavator starting footprint"):
                scene.validate_start(-3, 3, footprint=selected.footprint)

    def test_footprint_corners_follow_the_chassis_heading(self) -> None:
        footprint = select_vehicle("excavator").footprint
        corners = footprint_corners(footprint, 1.0, 2.0, 0.0)
        np.testing.assert_allclose(corners, [(-1.0, 0.3), (6.5, 0.3), (6.5, 3.7), (-1.0, 3.7)])
        # A quarter turn left puts the boom clearance along +Y.
        turned = footprint_corners(footprint, 1.0, 2.0, np.pi / 2)
        np.testing.assert_allclose(turned, [(2.7, 0.0), (2.7, 7.5), (-0.7, 7.5), (-0.7, 0.0)],
                                   atol=1e-12)

    def test_terrain_texture_keeps_grid_orientation_and_is_repeatable(self) -> None:
        import matplotlib.image

        scene = SceneGrid.load(REPO_ROOT / "tests/fixtures/goose_label_viewer_real/scene.json")
        rows, cols = scene.heights.shape
        # Vegetation only in the (xmin, ymax) corner: the image's top-left.
        labels = np.full((rows, cols), scene.unobserved_id, dtype=np.uint8)
        labels[: rows // 2, : cols // 2] = 1
        scene = dataclasses.replace(scene, coarse_labels=labels)
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a.png", Path(tmp) / "b.png"
            write_terrain_texture(scene, first, size=256)
            write_terrain_texture(scene, second, size=256)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            image = matplotlib.image.imread(first)
        self.assertEqual(image.shape[:2], (256, 256))
        top_left, bottom_right = image[:96, :96, :3].mean((0, 1)), image[160:, 160:, :3].mean((0, 1))
        self.assertGreater(top_left[1], top_left[0])  # green vegetation
        self.assertGreater(bottom_right[0], bottom_right[1])  # brown soil

    def test_scm_active_domain_matches_vehicle_footprint(self) -> None:
        bulldozer = select_vehicle("bulldozer")
        excavator = select_vehicle("excavator")

        bulldozer_center, bulldozer_dimensions = _scm_active_domain_geometry(
            bulldozer.footprint
        )
        excavator_center, excavator_dimensions = _scm_active_domain_geometry(
            excavator.footprint
        )

        np.testing.assert_allclose(bulldozer_center, (0.0, 0.0, 0.0))
        np.testing.assert_allclose(bulldozer_dimensions, (6.0, 6.0, 4.0))

        np.testing.assert_allclose(excavator_center, (1.75, 0.0, 0.0))
        np.testing.assert_allclose(excavator_dimensions, (9.9, 5.8, 4.0))

    def test_each_vehicle_has_its_own_camera_framing(self) -> None:
        bulldozer, excavator = select_vehicle("bulldozer"), select_vehicle("excavator")
        # The bulldozer keeps the original Issue #26 view.
        self.assertEqual(bulldozer.camera_offset, (4.0, -10.0, 7.0))
        self.assertEqual(bulldozer.camera_target_offset, (-1.0, 0.0, 0.0))
        # The excavator aims ahead of the start, where its boom and bucket are.
        self.assertGreater(excavator.camera_target_offset[0], 0)

    def test_chrono_coordinates_follow_manifest_grid_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = SceneGrid.load(make_scene(Path(tmp)))
            self.assertEqual(scene.height_at(-6, 4), 0)
            self.assertEqual(scene.height_at(0, 0), 23)
            self.assertEqual(scene.height_at(6, -4), 46)
            self.assertAlmostEqual(scene.height_at(1, 1), 18.5)

    def test_coarse_classes_follow_grid_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = SceneGrid.load(make_scene(Path(tmp)))
            self.assertEqual(scene.coarse_class_at(0, 0), "vegetation")
            self.assertEqual(scene.coarse_class_at(-2, 0), "terrain")
            self.assertEqual(scene.coarse_class_at(2, 0), "unobserved")
            self.assertEqual(scene.coarse_class_at(0, 4), "terrain")
            self.assertEqual(scene.coarse_class_at(7, 0), "unobserved")

    def test_version1_scene_still_works_without_semantic_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = SceneGrid.load(make_scene(Path(tmp), version=1))
            self.assertIsNone(scene.coarse_labels)
            self.assertEqual(scene.coarse_class_at(0, 0), "")
            samples = [TrajectorySample(0, 0, 0, 0, 0)]
            csv_path, png_path = Path(tmp) / "trajectory.csv", Path(tmp) / "route.png"
            write_trajectory(samples, csv_path, scene)
            write_route_overlay(scene, samples, png_path)
            with csv_path.open(newline="", encoding="utf-8") as stream:
                self.assertEqual(list(csv.DictReader(stream))[0]["coarse_semantic_class"], "")
            self.assertTrue(png_path.is_file())

    def test_route_checks_the_blade_footprint_and_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = SceneGrid.load(make_scene(Path(tmp)))
            scene.validate_route(0, 0, 0.6, 6)
            scene.validate_start(0, 0)
            with self.assertRaisesRegex(ValueError, "leaves the generated terrain"):
                scene.validate_route(0, 0, 0.6, 10)
            with self.assertRaisesRegex(ValueError, "leaves the generated terrain"):
                scene.validate_route(0, 3, 0.6, 6)
            with self.assertRaisesRegex(ValueError, "starting footprint"):
                scene.validate_start(5, 0)
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

    def test_rejects_missing_or_misaligned_semantic_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = make_scene(root)
            (root / "semantic_coarse.npy").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "semantic_coarse.npy"):
                SceneGrid.load(path)

            np.save(root / "semantic_coarse.npy", np.zeros((3, 3), dtype=np.uint8))
            with self.assertRaisesRegex(ValueError, "wrong shape or dtype"):
                SceneGrid.load(path)

            np.save(root / "semantic_coarse.npy", np.full((5, 7), 42, dtype=np.uint8))
            with self.assertRaisesRegex(ValueError, "map and legend disagree"):
                SceneGrid.load(path)

    def test_fullscreen_needs_a_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = Namespace(scene=make_scene(Path(tmp)), mode="scripted", headless=True,
                             fullscreen=True, duration=None)
            with self.assertRaisesRegex(ValueError, "--fullscreen needs a window"):
                run_demo(args)

    def test_fixed_step_sampling_requires_exact_multiples(self) -> None:
        self.assertEqual(exact_steps(6.0, 0.002, "duration"), 3000)
        self.assertEqual(exact_steps(0.1, 0.002, "sample period"), 50)
        with self.assertRaisesRegex(ValueError, "multiple"):
            exact_steps(0.101, 0.002, "sample period")

    def test_exports_trajectory_and_route_on_semantic_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene = SceneGrid.load(make_scene(root))
            samples = [
                TrajectorySample(0.0, 0.0, 0.0, 23.0, 0.0),
                TrajectorySample(1.0, -0.6, 0.0, 23.0, 0.0),
            ]
            csv_path, png_path = root / "trajectory.csv", root / "route_overlay.png"
            write_trajectory(samples, csv_path, scene)
            write_route_overlay(scene, samples, png_path)
            with csv_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["time_s"] for row in rows], ["0.000000", "1.000000"])
            self.assertEqual(rows[1]["x_m"], "-0.600000")
            self.assertEqual(rows[1]["coarse_semantic_class"], "vegetation")
            self.assertEqual(png_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_scripted_run_records_chassis_motion_and_status(self) -> None:
        """Exercise CLI orchestration with the Chrono boundary replaced."""
        class FakeSystem:
            time = 0.0

            def GetChTime(self):
                return self.time

        class FakeTerrain:
            def SetMeshWireframe(self, wireframe):
                pass

            def Synchronize(self, time):
                pass

            def Advance(self, step):
                pass

            def AddActiveDomain(self, body, center, dimensions):
                pass

        class FakeBulldozer:
            def __init__(self, system, show_rigid_ground, initial_z_offset, initial_xy):
                self.system = system
                self.x, self.y = initial_xy
                self.z = 1.0 + initial_z_offset
                self.speed = 0.0
                self.chassis = object()

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
            self.assertEqual(manifest["source_scene_format_version"], 2)
            self.assertEqual(Path(manifest["semantic_labels"]["coarse_map"]).resolve(),
            (root / "semantic_coarse.npy").resolve(),)
            self.assertEqual(manifest["semantic_labels"]["taxonomy"], "project-coarse-v1")
            self.assertAlmostEqual(manifest["displacement_m"], 1.0)
            self.assertEqual(len(rows), 5)  # Initial state and four half-second samples.
            self.assertEqual(rows[-1]["x_m"], "-1.000000")
            self.assertTrue(all(row["coarse_semantic_class"] == "vegetation" for row in rows))

    def test_manual_mode_records_keyboard_driving_until_window_closes(self) -> None:
        """Manual mode reuses a keyboard controller and saves the final partial sample."""
        class Vec:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

            def __add__(self, other):
                return Vec(self.x + other.x, self.y + other.y, self.z + other.z)

        class FakeSystem:
            def __init__(self):
                self.time = 0.0

            def GetChTime(self):
                return self.time

        class FakeTerrain:
            textures = []

            def SetMeshWireframe(self, wireframe):
                pass

            def SetTexture(self, path, scale_x, scale_y):
                # The semantic texture must exist when the visual system binds it.
                self.textures.append((Path(path).is_file(), scale_x, scale_y))

            def SetColor(self, color):
                pass

            def Synchronize(self, time):
                pass

            def Advance(self, step):
                pass

            def AddActiveDomain(self, body, center, dimensions):
                pass

        class FakeBulldozer:
            def __init__(self, system, show_rigid_ground, initial_z_offset, initial_xy):
                self.system = system
                self.x, self.y = initial_xy
                self.z = 1.0 + initial_z_offset
                self.speed = 0.0
                self.chassis = object()

            def set_blade_targets(self, lift, tilt):
                pass

            def set_drive_speeds(self, left, right):
                self.speed = left

            def advance(self, step):
                self.x -= self.speed * step
                self.system.time += step

            def get_chassis_position(self):
                return Vec(self.x, self.y, self.z)

            def get_chassis_heading(self):
                return 0.0

        class FakeKeyboard:
            stopped = False

            def start(self):
                pass

            def stop(self):
                FakeKeyboard.stopped = True

        class FakeController:
            def __init__(self, bulldozer, keyboard):
                self.bulldozer = bulldozer
                self.blade = [0.0, 0.0]

            def update(self, frame_time, block_forward=False):
                self.bulldozer.set_drive_speeds(
                    0.0 if block_forward else 0.6,
                    0.0 if block_forward else 0.6,
                )

        class FakeVisual:
            calls = 0

            def Run(self):
                self.calls += 1
                return self.calls <= 3

            def SetCameraPosition(self, position):
                pass

            def SetCameraTarget(self, position):
                pass

            def BeginScene(self):
                pass

            def Render(self):
                pass

            def EndScene(self):
                pass

        chrono = ModuleType("pychrono")
        chrono.ChVector3d = Vec
        chrono.ChColor = lambda r, g, b: (r, g, b)
        chrono.ChRealtimeStepTimer = lambda: SimpleNamespace(Spin=lambda time: None)
        terrain_module = ModuleType("environments.terrain.goose_environment")
        terrain_module.create_system = FakeSystem
        terrain_module.create_terrain = lambda *args: FakeTerrain()
        dozer_module = ModuleType("vehicles.bulldozer.articulation.bulldozer_model")
        dozer_module.BulldozerModel = FakeBulldozer
        demo_module = ModuleType("src.demo_common")
        demo_module.KeyboardState = FakeKeyboard
        demo_module.create_visual_system = lambda *args, **kwargs: FakeVisual()
        controls_module = ModuleType("src.bulldozer_main")
        controls_module.BulldozerController = FakeController

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene_path = make_scene(root)
            config_path = root / "scm.json"
            config_path.write_text(json.dumps({"step_size": 0.1}), encoding="utf-8")
            args = Namespace(
                scene=scene_path, config=config_path, output_dir=root / "out",
                mode="manual", start_x=0.0, start_y=0.0, speed=0.6,
                duration=None, sample_period=0.2, headless=False,
            )
            with patch.dict(sys.modules, {
                "pychrono": chrono,
                "environments.terrain.goose_environment": terrain_module,
                "vehicles.bulldozer.articulation.bulldozer_model": dozer_module,
                "src.demo_common": demo_module,
                "src.bulldozer_main": controls_module,
            }), patch.object(
                terrain_package, "goose_environment", terrain_module, create=True
            ), patch.object(
                bulldozer_package, "bulldozer_model", dozer_module, create=True
            ):
                self.assertEqual(run_demo(args), 0)
            manifest = json.loads((root / "out/run_manifest.json").read_text(encoding="utf-8"))
            with (root / "out/trajectory.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(manifest["mode"], "manual_keyboard")
            self.assertEqual(FakeTerrain.textures, [(True, 1.0, 1.0)])
            self.assertEqual(manifest["status"], "completed")
            self.assertIsNone(manifest["requested_duration_s"])
            self.assertEqual([row["time_s"] for row in rows],
                             ["0.000000", "0.200000", "0.300000"])
            self.assertEqual(rows[-1]["x_m"], "-0.180000")
            self.assertEqual(rows[-1]["coarse_semantic_class"], "vegetation")
            self.assertTrue(FakeKeyboard.stopped)

            args.headless = True
            with self.assertRaisesRegex(ValueError, "manual mode needs a window"):
                run_demo(args)


if __name__ == "__main__":
    unittest.main()
