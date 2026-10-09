"""Unit tests for semantic-derived GOOSE vegetation placement."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VEGETATION_ROOT = REPOSITORY_ROOT / "environments" / "vegetation"
sys.path.insert(0, str(VEGETATION_ROOT))

import goose_vegetation as vegetation


class GooseVegetationTests(unittest.TestCase):

    def test_finds_only_vegetation_labelled_cells(self):
        semantic_map = np.array(
            [
                [1, 1, 2],
                [2, 1, 2],
                [2, 2, 1],
            ],
            dtype=np.uint8,
        )

        cells = vegetation.find_vegetation_cells(
            semantic_map,
            vegetation_class=1,
        )

        actual_cells = {
            tuple(map(int, cell))
            for cell in cells
        }

        self.assertEqual(
            actual_cells,
            {(0, 0), (0, 1), (1, 1), (2, 2)},
        )

    def test_vegetation_class_is_read_from_legend(self):
        legend = {
            "coarse_taxonomy": {
                "categories": [
                    {"id": 4, "name": "vehicle"},
                    {"id": 7, "name": "vegetation"},
                    {"id": 2, "name": "terrain"},
                ]
            }
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "semantic_legend.json"
            path.write_text(
                json.dumps(legend),
                encoding="utf-8",
            )

            vegetation_class = vegetation.load_semantic_legend(path)

        self.assertEqual(vegetation_class, 7)

    def test_world_coordinates_and_terrain_height(self):
        height_grid = np.array(
            [
                [1.0, 2.0, 3.0],
                [4.0, 5.0, 6.0],
                [7.0, 8.0, 9.0],
            ],
            dtype=float,
        )

        cells = np.array(
            [
                [0, 0],
                [1, 2],
            ],
            dtype=int,
        )

        positions = vegetation.cells_to_world_positions(
            cells,
            height_grid,
            x_spacing=0.5,
            y_spacing=0.25,
            xmin=-10.0,
            ymax=20.0,
        )

        self.assertEqual(len(positions), 2)

        first = positions[0]
        second = positions[1]

        self.assertEqual((first["row"], first["column"]), (0, 0))
        self.assertAlmostEqual(first["x"], -10.0)
        self.assertAlmostEqual(first["y"], 20.0)
        self.assertAlmostEqual(first["z"], 1.0)

        self.assertEqual((second["row"], second["column"]), (1, 2))
        self.assertAlmostEqual(second["x"], -9.0)
        self.assertAlmostEqual(second["y"], 19.75)
        self.assertAlmostEqual(second["z"], 6.0)

    def test_generated_positions_are_deterministic(self):
        semantic_map = np.array(
            [
                [1, 0, 1],
                [0, 1, 0],
            ],
            dtype=np.uint8,
        )

        height_grid = np.array(
            [
                [0.2, 0.3, 0.4],
                [0.5, 0.6, 0.7],
            ],
            dtype=float,
        )

        cells = vegetation.find_vegetation_cells(semantic_map, 1)

        first_run = vegetation.cells_to_world_positions(
            cells, height_grid, 1.0, 1.0,
        )

        second_run = vegetation.cells_to_world_positions(
            cells, height_grid, 1.0, 1.0,
        )

        self.assertEqual(first_run, second_run)

    def test_load_goose_scene_uses_manifest_and_semantic_legend(self):
        with tempfile.TemporaryDirectory() as directory:
            scene_directory = Path(directory)
            scene_path = scene_directory / "scene.json"

            semantic_map = np.array(
                [
                    [7, 2],
                    [2, 7],
                ],
                dtype=np.uint8,
            )

            height_grid = np.array(
                [
                    [0.1, 0.2],
                    [0.3, 0.4],
                ],
                dtype=float,
            )

            legend = {
                "coarse_taxonomy": {
                    "categories": [
                        {"id": 2, "name": "terrain"},
                        {"id": 7, "name": "vegetation"},
                    ]
                }
            }

            scene = {
                "bounds_xy": {
                    "xmin": -5.0,
                    "ymax": 5.0,
                },
                "grid": {
                    "x_spacing": 0.5,
                    "y_spacing": 0.25,
                },
                "outputs": {
                    "semantic_coarse": {
                        "path": "semantic_coarse.npy",
                    },
                    "semantic_legend": {
                        "path": "semantic_legend.json",
                    },
                    "height_grid": {
                        "path": "height_grid.npy",
                    },
                },
            }

            np.save(
                scene_directory / "semantic_coarse.npy",
                semantic_map,
            )
            np.save(
                scene_directory / "height_grid.npy",
                height_grid,
            )

            (scene_directory / "semantic_legend.json").write_text(
                json.dumps(legend),
                encoding="utf-8",
            )

            scene_path.write_text(
                json.dumps(scene),
                encoding="utf-8",
            )

            loaded = vegetation.load_goose_scene(scene_path)

            self.assertEqual(loaded["vegetation_class"], 7)
            self.assertEqual(loaded["xmin"], -5.0)
            self.assertEqual(loaded["ymax"], 5.0)
            self.assertEqual(loaded["x_spacing"], 0.5)
            self.assertEqual(loaded["y_spacing"], 0.25)

            np.testing.assert_array_equal(
                loaded["semantic_map"],
                semantic_map,
            )

            np.testing.assert_array_equal(
                loaded["height_grid"],
                height_grid,
            )

    def test_mismatched_semantic_and_height_grids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            scene_directory = Path(directory)
            scene_path = scene_directory / "scene.json"

            np.save(
                scene_directory / "semantic_coarse.npy",
                np.zeros((2, 2), dtype=np.uint8),
            )

            np.save(
                scene_directory / "height_grid.npy",
                np.zeros((3, 3), dtype=float),
            )

            legend = {
                "coarse_taxonomy": {
                    "categories": [
                        {"id": 1, "name": "vegetation"},
                    ]
                }
            }

            (scene_directory / "semantic_legend.json").write_text(
                json.dumps(legend),
                encoding="utf-8",
            )

            scene = {
                "outputs": {
                    "semantic_coarse": {
                        "path": "semantic_coarse.npy",
                    },
                    "semantic_legend": {
                        "path": "semantic_legend.json",
                    },
                    "height_grid": {
                        "path": "height_grid.npy",
                    },
                }
            }

            scene_path.write_text(
                json.dumps(scene),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "not aligned"):
                vegetation.load_goose_scene(scene_path)


if __name__ == "__main__":
    unittest.main()
