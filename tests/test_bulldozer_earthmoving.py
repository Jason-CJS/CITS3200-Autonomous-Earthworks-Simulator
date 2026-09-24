"""Tests for the pure-Python parts of the bulldozer scenario."""

import math
from pathlib import Path
import struct
import tempfile
import unittest

from scenarios.bulldozer_earthmoving.terrain_profile import (
    TerrainProfile,
    calculate_hole_metrics,
    height_to_grayscale,
    write_profile_heightmap,
)

from scenarios.bulldozer_earthmoving.run_scenario import (
    meets_success_criteria,
)

class BulldozerEarthmovingTests(unittest.TestCase):
    def setUp(self):
        self.profile = TerrainProfile()

    def test_profile_contains_shallow_hole_and_raised_mound(self):
        hole_height = self.profile.initial_height_at(
            self.profile.hole_center_x_m,
            self.profile.hole_center_y_m,
        )
        mound_height = self.profile.initial_height_at(
            self.profile.mound_center_x_m,
            self.profile.mound_center_y_m,
        )

        self.assertLess(hole_height, -0.06)
        self.assertGreater(mound_height, 0.08)
        self.assertGreater(mound_height, hole_height)

    def test_initial_grid_matches_expected_geometry(self):
        grid = self.profile.initial_grid()
        geometry = self.profile.geometry

        self.assertEqual(
            len(grid),
            geometry.node_count_x * geometry.node_count_y,
        )
        self.assertIn((0, 0), grid)

    def test_hole_metric_measures_average_height_increase(self):
        initial_grid = self.profile.initial_grid()
        final_grid = dict(initial_grid)
        spacing = self.profile.geometry.actual_spacing_m

        for point in initial_grid:
            distance = math.hypot(
                point[0] * spacing - self.profile.hole_center_x_m,
                point[1] * spacing - self.profile.hole_center_y_m,
            )
            if distance <= self.profile.hole_radius_m:
                final_grid[point] += 0.02

        metrics = calculate_hole_metrics(
            self.profile,
            initial_grid,
            final_grid,
        )

        self.assertGreater(metrics["hole_node_count"], 0)
        self.assertEqual(
            metrics["modified_node_count_in_hole"],
            metrics["hole_node_count"],
        )
        self.assertAlmostEqual(
            metrics["average_height_increase_m"],
            0.02,
            places=12,
        )

    def test_heightmap_is_valid_bmp_with_expected_dimensions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = (
                Path(temporary_directory) / "purpose_built_heightmap.bmp"
            )
            write_profile_heightmap(self.profile, output_path)
            contents = output_path.read_bytes()

        self.assertEqual(contents[:2], b"BM")
        self.assertEqual(
            struct.unpack_from("<I", contents, 18)[0],
            self.profile.geometry.node_count_x,
        )
        self.assertEqual(
            struct.unpack_from("<I", contents, 22)[0],
            self.profile.geometry.node_count_y,
        )

    def test_rejects_invalid_height_range(self):
        with self.assertRaises(ValueError):
            height_to_grayscale(0.0, 1.0, 1.0)

    def test_acceptance_criteria_reject_noise_and_sparse_changes(self):
        self.assertTrue(
            meets_success_criteria(1295, 0.00209, 14)
        )
        self.assertFalse(
            meets_success_criteria(1230, 0.00007, 3)
        )
        self.assertFalse(
            meets_success_criteria(1295, 0.00209, 9)
        )
        self.assertFalse(
            meets_success_criteria(0, 0.00209, 14)
        )


if __name__ == "__main__":
    unittest.main()