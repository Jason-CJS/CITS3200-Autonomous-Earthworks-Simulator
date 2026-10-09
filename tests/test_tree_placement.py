"""Unit tests for semantic-derived GOOSE tree placement."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VEGETATION_ROOT = REPOSITORY_ROOT / "environments" / "vegetation"
sys.path.insert(0, str(VEGETATION_ROOT))

import goose_tree_placement as trees


class GooseTreePlacementTests(unittest.TestCase):

    def test_finds_tree_trunk_class_by_name(self):
        legend = {
            "classes": [
                {"id": 27, "name": "tree_crown"},
                {"id": 28, "name": "tree_trunk"},
                {"id": 50, "name": "low_grass"},
            ]
        }

        self.assertEqual(trees.find_class_id(legend, "tree_trunk"), 28)
        self.assertEqual(trees.find_class_id(legend, "TREE_TRUNK"), 28)

    def test_missing_tree_trunk_class_raises_error(self):
        legend = {
            "classes": [
                {"id": 27, "name": "tree_crown"},
                {"id": 50, "name": "low_grass"},
            ]
        }

        with self.assertRaises(ValueError):
            trees.find_class_id(legend, "tree_trunk")

    def test_connected_regions_use_four_neighbours(self):
        mask = np.array(
            [
                [True, True, False, False],
                [False, True, False, False],
                [False, False, True, True],
                [False, False, False, True],
            ],
            dtype=bool,
        )

        regions = trees.find_connected_regions(mask)

        self.assertEqual(len(regions), 2)
        self.assertEqual(sorted(len(region) for region in regions), [3, 3])

        actual_cells = {
            cell
            for region in regions
            for cell in region
        }

        expected_cells = {
            (0, 0), (0, 1), (1, 1),
            (2, 2), (2, 3), (3, 3),
        }

        self.assertEqual(actual_cells, expected_cells)

    def test_diagonal_cells_are_separate_regions(self):
        mask = np.array(
            [
                [True, False],
                [False, True],
            ],
            dtype=bool,
        )

        regions = trees.find_connected_regions(mask)

        self.assertEqual(len(regions), 2)

    def test_anchor_is_an_actual_trunk_cell(self):
        region = [
            (0, 0),
            (0, 1),
            (1, 0),
        ]

        anchor = trees.choose_anchor_cell(region)

        self.assertIn(anchor, region)
        self.assertEqual(anchor, (0, 0))

    def test_grid_to_world_uses_correct_coordinates_and_height(self):
        height_grid = np.array(
            [
                [1.0, 2.0, 3.0],
                [4.0, 5.0, 6.0],
            ],
            dtype=float,
        )

        x, y, z = trees.grid_to_world(
            row=1,
            column=2,
            height_grid=height_grid,
            xmin=-10.0,
            ymax=20.0,
            x_spacing=0.5,
            y_spacing=0.25,
        )

        self.assertAlmostEqual(x, -9.0)
        self.assertAlmostEqual(y, 19.75)
        self.assertAlmostEqual(z, 6.0)

    def test_generated_placements_match_semantics_and_terrain(self):
        with tempfile.TemporaryDirectory() as directory:
            scene_directory = Path(directory)
            scene_path = scene_directory / "scene.json"

            fine_map = np.array(
                [
                    [28, 28, 50, 50],
                    [50, 28, 50, 50],
                    [50, 50, 50, 28],
                    [50, 50, 50, 28],
                ],
                dtype=np.uint16,
            )

            height_grid = np.array(
                [
                    [0.1, 0.2, 0.3, 0.4],
                    [0.5, 0.6, 0.7, 0.8],
                    [0.9, 1.0, 1.1, 1.2],
                    [1.3, 1.4, 1.5, 1.6],
                ],
                dtype=float,
            )

            legend = {
                "classes": [
                    {"id": 27, "name": "tree_crown"},
                    {"id": 28, "name": "tree_trunk"},
                    {"id": 50, "name": "low_grass"},
                ]
            }

            scene = {
                "bounds_xy": {
                    "xmin": -10.0,
                    "ymax": 20.0,
                },
                "grid": {
                    "x_spacing": 0.5,
                    "y_spacing": 0.25,
                },
            }

            np.save(scene_directory / "semantic_fine.npy", fine_map)
            np.save(scene_directory / "height_grid.npy", height_grid)

            (scene_directory / "semantic_legend.json").write_text(
                json.dumps(legend),
                encoding="utf-8",
            )

            scene_path.write_text(
                json.dumps(scene),
                encoding="utf-8",
            )

            first_run = trees.generate_tree_placements(scene_path)
            second_run = trees.generate_tree_placements(scene_path)

            self.assertEqual(first_run, second_run)
            self.assertEqual(len(first_run), 2)
            self.assertEqual(
                [placement["region_size"] for placement in first_run],
                [3, 2],
            )

            for placement in first_run:
                row = placement["row"]
                column = placement["column"]

                self.assertEqual(int(fine_map[row, column]), 28)
                self.assertEqual(placement["source"], "tree_trunk")

                self.assertAlmostEqual(
                    placement["x"],
                    -10.0 + column * 0.5,
                )

                self.assertAlmostEqual(
                    placement["y"],
                    20.0 - row * 0.25,
                )

                self.assertAlmostEqual(
                    placement["z"],
                    float(height_grid[row, column]),
                )

    def test_mismatched_semantic_and_height_grids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            scene_directory = Path(directory)
            scene_path = scene_directory / "scene.json"

            np.save(
                scene_directory / "semantic_fine.npy",
                np.zeros((2, 2), dtype=np.uint16),
            )

            np.save(
                scene_directory / "height_grid.npy",
                np.zeros((3, 3), dtype=float),
            )

            scene_path.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "matching shapes"):
                trees.generate_tree_placements(scene_path)


if __name__ == "__main__":
    unittest.main()
