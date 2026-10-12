"""Bucket digging on SCM terrain: volume bookkeeping, the dig cycle and the runner."""

from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scenarios.goose_navigation.run_demo import DEFAULT_CONFIG, run_demo
from vehicles.excavator.articulation.bucket_soil import (
    _cavity_x_limits,
    box_bottom_heights,
    push_aside,
    _mound_vertices,
    _side_plate_top,
    cut_below,
    deposit_cone,
    relax_loose,
    scm_node_spacing,
)
from vehicles.excavator.articulation.dig_cycle import (
    DUMP_DURATION_S,
    SCOOP_DURATION_S,
    CYCLE_S,
    DEEPEN_BOOM_RAD,
    KEYFRAMES,
    TRAVEL_POSE,
    dig_cycle_targets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_SCENE = REPO_ROOT / "tests/fixtures/goose_label_viewer_real/scene.json"
SPACING = 0.15
CELL = SPACING * SPACING


class SoilVolumeTests(unittest.TestCase):
    def test_scm_spacing_fits_a_whole_number_of_cells(self) -> None:
        self.assertAlmostEqual(scm_node_spacing(40.0, 0.15), 40.0 / 268)
        self.assertAlmostEqual(scm_node_spacing(12.0, 0.15), 0.15)

    def test_cut_takes_loose_soil_first_and_respects_the_bucket_capacity(self) -> None:
        levels = np.full((3, 3), 1.0)
        loose = np.zeros((3, 3))
        loose[1, 1] = 0.2
        mask = np.zeros((3, 3), dtype=bool)
        mask[1, 1] = mask[1, 2] = True
        removed = cut_below(levels, loose, mask, 0.5, max_volume=1.0, cell_area=CELL)
        self.assertAlmostEqual(removed, 2 * 0.5 * CELL)
        self.assertEqual(levels[1, 1], 0.5)
        self.assertEqual(levels[0, 0], 1.0)
        self.assertEqual(loose[1, 1], 0.0)
        # A nearly full bucket only takes what still fits, spread evenly.
        levels, loose = np.full((3, 3), 1.0), np.zeros((3, 3))
        removed = cut_below(levels, loose, mask, 0.5, max_volume=0.5 * CELL, cell_area=CELL)
        self.assertAlmostEqual(removed, 0.5 * CELL)
        self.assertAlmostEqual(levels[1, 1], 0.75)

    def test_deposit_and_slump_conserve_volume_and_reach_the_angle_of_repose(self) -> None:
        levels = np.zeros((31, 31))
        levels[:, :3] = 2.0  # a steep natural bank that has no loose soil on it
        loose = np.zeros_like(levels)
        bank = levels[:, :3].copy()
        deposit_cone(levels, loose, (15.0, 18.0), 0.2, SPACING, radius=0.3)
        self.assertAlmostEqual((levels.sum() - bank.sum()) * CELL, 0.2)
        repose = np.tan(np.radians(34.0))
        relax_loose(levels, loose, SPACING, repose, iterations=2000)
        self.assertAlmostEqual((levels.sum() - bank.sum()) * CELL, 0.2)
        self.assertAlmostEqual(loose.sum() * CELL, 0.2)
        np.testing.assert_array_equal(levels[:, :3], bank)
        pile = levels[:, 4:]
        slopes = np.abs(np.diff(pile, axis=0)).max(), np.abs(np.diff(pile, axis=1)).max()
        self.assertLessEqual(max(slopes), repose * SPACING * 1.05)
        self.assertGreater(pile.max(), 0.1)  # still a pile, not a smear


class BucketLoadDisplayTests(unittest.TestCase):
    def test_soil_surface_reaches_the_bucket_walls_at_every_fill(self) -> None:
        for fill in (0.3, 0.6, 1.0):
            with self.subTest(fill=fill):
                points = _mound_vertices(fill, 11, 7).reshape(11, 7, 3)
                self.assertAlmostEqual(points[..., 1].min(), -0.235)
                self.assertAlmostEqual(points[..., 1].max(), 0.235)
                back, front = _cavity_x_limits(points[..., 2])
                np.testing.assert_allclose(points[0, :, 0], back[0], atol=0.01)
                np.testing.assert_allclose(points[-1, :, 0], front[-1], atol=0.01)
        # The edges stay below the side plates, so nothing shows underneath the soil.
        full = _mound_vertices(1.0, 11, 7).reshape(11, 7, 3)
        for edge in (full[:, 0], full[:, -1]):
            self.assertTrue(np.all(edge[:, 2] < _side_plate_top(edge[:, 0])))


class BucketBoxSoilTests(unittest.TestCase):
    def test_box_bottom_follows_the_tilted_bucket(self) -> None:
        xs, ys = np.array([-1.0, 0.0, 0.3, 2.0]), np.array([0.0])
        level = box_bottom_heights(xs, ys, np.array([0.0, 0.0, 1.0]), np.eye(3), np.array([0.5, 0.5, 0.25]))
        self.assertEqual(level[0, 0], np.inf)        # outside the footprint
        self.assertAlmostEqual(level[1, 0], 0.75)    # flat box: bottom face everywhere
        self.assertAlmostEqual(level[2, 0], 0.75)
        self.assertEqual(level[3, 0], np.inf)
        tilt = np.radians(30.0)  # rotate about y: the bottom slopes along x
        axes = np.array([[np.cos(tilt), 0, np.sin(tilt)], [0, 1, 0], [-np.sin(tilt), 0, np.cos(tilt)]])
        sloped = box_bottom_heights(np.array([-0.2, 0.0, 0.2]), ys, np.zeros(3), axes, np.full(3, 0.5))
        self.assertTrue(np.all(np.diff(sloped[:, 0]) < 0))  # lower towards +x

    def test_a_full_bucket_pushes_soil_aside_without_losing_any(self) -> None:
        levels = np.zeros((9, 9))
        loose = np.zeros_like(levels)
        inside = np.zeros_like(levels, dtype=bool)
        inside[3:6, 3:6] = True
        push_aside(levels, loose, inside, 0.05, CELL)
        self.assertAlmostEqual(levels.sum() * CELL, 0.05)
        self.assertEqual(levels[inside].sum(), 0.0)  # the ridge forms around the bucket
        self.assertGreater(levels[2, 4], 0.0)


class AutoScoopKeyTests(unittest.TestCase):
    class FakeExcavator:
        def set_drive_speeds(self, left, right):
            pass

        def set_articulation_targets(self, *targets):
            self.targets = targets

    def run_keys(self, controller, keys, seconds):
        from src.demo_common import KeyboardState

        controller.keyboard = KeyboardState(keys)
        for _ in range(round(seconds / 0.1)):
            controller.update(0.1)

    def test_z_scoops_and_c_dumps_at_the_current_swing(self) -> None:
        from src.demo_common import KeyboardState
        from src.excavator_main import ExcavatorController
        from vehicles.excavator.articulation.dig_cycle import CARRY, DUMP

        excavator = self.FakeExcavator()
        controller = ExcavatorController(excavator, KeyboardState(), calibration=False)
        controller.targets[0] = 0.8  # cab already swung left
        self.run_keys(controller, ("z",), SCOOP_DURATION_S + 0.5)
        np.testing.assert_allclose(excavator.targets, (0.8, *CARRY[1:]), atol=1e-9)
        self.run_keys(controller, (), 0.2)   # key released
        self.run_keys(controller, ("c",), DUMP_DURATION_S + 0.5)
        np.testing.assert_allclose(excavator.targets, (0.8, *DUMP[1:]), atol=1e-9)

    def test_any_arm_key_takes_back_control(self) -> None:
        from src.demo_common import KeyboardState
        from src.excavator_main import ExcavatorController

        excavator = self.FakeExcavator()
        controller = ExcavatorController(excavator, KeyboardState(), calibration=False)
        self.run_keys(controller, ("z",), 0.3)
        self.assertIsNotNone(controller.motion)
        boom = controller.targets[1]
        self.run_keys(controller, ("r",), 0.5)
        self.assertIsNone(controller.motion)
        self.assertGreater(controller.targets[1], boom)  # R raises the boom by hand again


class DigCycleTests(unittest.TestCase):
    def test_cycle_starts_from_travel_pose_and_repeats_smoothly(self) -> None:
        self.assertEqual(dig_cycle_targets(0.0), TRAVEL_POSE)
        end = KEYFRAMES[-1][0]
        np.testing.assert_allclose(dig_cycle_targets(end - 1e-6), dig_cycle_targets(end), atol=1e-6)
        for time in np.arange(0.0, end + 3 * CYCLE_S, 0.05):
            swing, boom, arm, bucket = dig_cycle_targets(time)
            self.assertTrue(-1.5 <= swing <= 1.5 and -1.3 <= bucket <= 1.3, time)

    def test_each_repeat_digs_deeper(self) -> None:
        drag_time = KEYFRAMES[3][0]
        first = dig_cycle_targets(drag_time)
        second = dig_cycle_targets(drag_time + CYCLE_S)
        self.assertAlmostEqual(second[1], first[1] - DEEPEN_BOOM_RAD)
        self.assertEqual(second[3], first[3])


class DigModeRunTests(unittest.TestCase):
    def arguments(self, root: Path, **overrides) -> Namespace:
        values = dict(scene=REAL_SCENE, config=DEFAULT_CONFIG, output_dir=root / "out",
                      mode="dig", vehicle="excavator", start_x=-4.0, start_y=0.0, speed=0.6,
                      duration=KEYFRAMES[-1][0], sample_period=0.1, headless=True, capture=None,
                      smoke_test=False, fullscreen=False)
        values.update(overrides)
        return Namespace(**values)

    def test_headless_dig_moves_soil_from_the_trench_to_a_pile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(run_demo(self.arguments(root)), 0)
            manifest = json.loads((root / "out/run_manifest.json").read_text())
            # Same deformation export as the bulldozer hole-filling demo, plus a map.
            for key, name in (("deformation_nodes", "deformation_nodes.csv"),
                              ("deformation_summary", "deformation_summary.json"),
                              ("soil_change_map", "soil_change.png")):
                self.assertEqual(manifest["outputs"][key], name)
                self.assertTrue((root / "out" / name).is_file(), name)
            deformation = json.loads((root / "out/deformation_summary.json").read_text())
            self.assertGreater(deformation["modified_node_count"], 0)
        soil = manifest["soil"]
        self.assertEqual(manifest["mode"], "scripted_dig_and_dump")
        self.assertEqual(manifest["status"], "completed")
        self.assertGreater(soil["excavated_m3"], 0.1)
        # Whatever was scooped is either dumped (as looser soil) or still in the bucket.
        poured = soil["excavated_m3"] - soil["carried_in_bucket_m3"]
        self.assertLess(soil["carried_in_bucket_m3"], 0.05 * soil["excavated_m3"])
        self.assertAlmostEqual(soil["deposited_m3"], soil["bulking_factor"] * poured)
        self.assertGreater(manifest["scm_modified_nodes"], 0)
        self.assertLess(manifest["displacement_m"], 0.01)  # it digs in place

    def test_pit_and_pile_match_the_counted_volumes(self) -> None:
        import pychrono as chrono

        from environments.terrain import goose_environment
        from scenarios.goose_navigation.traversal import SceneGrid
        from scenarios.goose_navigation.vehicles import select_vehicle

        scene = SceneGrid.load(REAL_SCENE)
        config = json.loads(DEFAULT_CONFIG.read_text())
        system = goose_environment.create_system()
        terrain = goose_environment.create_terrain(system, scene.path, scene.metadata, config)
        selected = select_vehicle("excavator")
        excavator = selected.create_model(system, (-4.0, 0.0), scene.height_at(-4.0, 0.0))
        soil = selected.create_soil(terrain, excavator, scene, config)
        xs, ys = np.arange(-10.0, 3.0, 0.1), np.arange(-6.0, 6.01, 0.1)

        def heights():
            return np.array([[terrain.GetHeight(chrono.ChVector3d(x, y, 0.0)) for y in ys] for x in xs])

        before = heights()
        for step in range(round(KEYFRAMES[-1][0] / 0.002)):
            if step % 10 == 0:
                excavator.set_articulation_targets(*dig_cycle_targets(step * 0.002))
            terrain.Synchronize(system.GetChTime())
            excavator.advance(0.002)
            soil.advance(0.002)
            terrain.Advance(0.002)
        change = heights() - before
        x, y = np.meshgrid(xs + 4.0, ys, indexing="ij")
        away_from_tracks = ~((np.abs(x) < 2.3) & (np.abs(np.abs(y) - 1.35) < 0.45))
        lost = -change[(change < -1e-4) & away_from_tracks].sum() * 0.01
        net = change[away_from_tracks].sum() * 0.01
        # No soil appears or vanishes: the terrain only gains the loose soil's extra
        # bulk. Squashing soil under the bucket would show up as a large net loss.
        poured = soil.excavated_m3 - soil.load_m3
        self.assertAlmostEqual(net, soil.deposited_m3 - poured, delta=0.05)
        self.assertGreaterEqual(lost, 0.9 * soil.excavated_m3)

    def test_bulldozer_runs_have_no_bucket_soil(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self.arguments(root, mode="scripted", vehicle="bulldozer", start_x=4.0, duration=1.0)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(run_demo(args), 0)
            manifest = json.loads((root / "out/run_manifest.json").read_text())
        self.assertIsNone(manifest["soil"])
        self.assertEqual(manifest["vehicle_key"], "bulldozer")
        self.assertEqual(set(manifest["outputs"]), {"trajectory", "route_overlay"})

    def test_dig_mode_needs_the_excavator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "--mode dig needs --vehicle excavator"):
                run_demo(self.arguments(Path(tmp), vehicle="bulldozer"))


if __name__ == "__main__":
    unittest.main()
