"""Tests for semantic-guided GOOSE rural vegetation placement and objects."""

import math
import unittest

import numpy as np

from environments.vegetation.goose_rural_placement import (
    MIN_SPACING,
    PLACEMENT_CLASSES,
    TREE_EXCLUSION_RADIUS,
    generate_placements,
)


class TestRuralPlacement(unittest.TestCase):
    """Test semantic-guided rural object placement."""

    def setUp(self):
        # Create a small synthetic GOOSE scene.
        self.labels = np.full((20, 20), 50, dtype=np.uint16)

        # High grass.
        self.labels[0:5, :] = 51

        # Soil and cobble for rocks.
        self.labels[15:19, :] = 31
        self.labels[19, :] = 3

        self.heights = np.full((20, 20), 0.25)

        self.grid = {
            "xmin": -10.0,
            "ymax": 10.0,
            "x_spacing": 1.0,
            "y_spacing": 1.0,
        }

    def test_deterministic_placement(self):
        """The same seed should generate identical placements."""

        counts = {
            "low_grass_patch": 10,
            "tall_wild_grass": 5,
            "rock": 5,
        }

        first = generate_placements(
            self.labels,
            self.heights,
            self.grid,
            counts=counts,
            seed=38,
        )

        second = generate_placements(
            self.labels,
            self.heights,
            self.grid,
            counts=counts,
            seed=38,
        )

        self.assertEqual(first, second)
        self.assertGreater(len(first), 0)

    def test_semantic_labels(self):
        """Objects must be placed on permitted semantic classes."""

        placements = generate_placements(
            self.labels,
            self.heights,
            self.grid,
            counts={
                "low_grass_patch": 5,
                "tall_wild_grass": 5,
                "rock": 5,
            },
        )

        for placement in placements:
            asset = placement["asset_type"]
            row = placement["row"]
            column = placement["column"]

            label = int(self.labels[row, column])
            preferred, fallback = PLACEMENT_CLASSES[asset]

            self.assertIn(label, preferred + fallback)

            self.assertEqual(
                placement["z"],
                float(self.heights[row, column]),
            )

    def test_minimum_spacing(self):
        """Objects must satisfy minimum horizontal spacing."""

        placements = generate_placements(
            self.labels,
            self.heights,
            self.grid,
            counts={
                "low_grass_patch": 12,
                "tall_wild_grass": 5,
                "scrub_bush": 4,
                "broadleaf_sapling": 2,
                "rock": 8,
            },
        )

        for index, first in enumerate(placements):
            for second in placements[index + 1:]:
                distance = math.hypot(
                    first["x"] - second["x"],
                    first["y"] - second["y"],
                )

                required = max(
                    MIN_SPACING[first["asset_type"]],
                    MIN_SPACING[second["asset_type"]],
                )

                self.assertGreaterEqual(
                    distance + 1e-9,
                    required,
                )

    def test_tree_avoidance(self):
        """Bushes and saplings must avoid existing trees."""

        tree = {
            "x": 0.0,
            "y": 0.0,
        }

        placements = generate_placements(
            self.labels,
            self.heights,
            self.grid,
            counts={
                "scrub_bush": 10,
                "broadleaf_sapling": 5,
            },
            trees=[tree],
        )

        self.assertGreater(len(placements), 0)

        for placement in placements:
            exclusion = TREE_EXCLUSION_RADIUS.get(
                placement["asset_type"],
                0.0,
            )

            if exclusion:
                distance = math.hypot(
                    placement["x"] - tree["x"],
                    placement["y"] - tree["y"],
                )

                self.assertGreaterEqual(
                    distance + 1e-9,
                    exclusion,
                )

    def test_invalid_grid_shapes(self):
        """Mismatched semantic and height grids must be rejected."""

        with self.assertRaises(ValueError):
            generate_placements(
                self.labels,
                np.zeros((10, 10)),
                self.grid,
            )


class TestRuralChronoObjects(unittest.TestCase):
    """Test rural vegetation and rock visual assets."""

    def test_asset_mesh_loading(self):
        """All five rural meshes and six rocks should load."""

        from environments.vegetation.goose_rural_objects import (
            ASSET_PATHS,
            ROCK_PATHS,
            _load_visual_shape,
        )

        paths = list(ASSET_PATHS.values()) + ROCK_PATHS

        self.assertEqual(len(paths), 11)

        for path in paths:
            with self.subTest(asset=path.name):
                self.assertTrue(path.is_file())

                shape = _load_visual_shape(path, 1.0)

                self.assertIsNotNone(shape.GetMesh())

    def test_rock_width_and_ground_alignment(self):
        """Rocks should have the expected width and touch the ground."""

        import pychrono as chrono

        from environments.vegetation.goose_rural_objects import (
            ROCK_PATHS,
            ROCK_SIZE_RANGES,
            _get_mesh_bounds,
            _rock_size_category,
            create_rural_object,
        )

        # Test all six rock models.
        for index, path in enumerate(ROCK_PATHS):
            with self.subTest(rock=path.name):
                mesh_width, min_z = _get_mesh_bounds(path)

                self.assertGreater(mesh_width, 0)

                placement = {
                    "asset_type": "rock",
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.5,
                    "scale": 1.0,
                    "rotation_z": 0.0,
                }

                system = chrono.ChSystemSMC()

                body = create_rural_object(
                    system,
                    placement,
                    rock_index=index,
                    rock_total=len(ROCK_PATHS),
                    seed=38,
                )

                # Read the scale applied by the rock loader.
                shape_instances = (
                    body.GetVisualModel().GetShapeInstances()
                )

                self.assertEqual(len(shape_instances), 1)

                shape = chrono.CastToChVisualShapeTriangleMesh(
                    shape_instances[0].shape
                )
                self.assertIsNotNone(shape)
                scale = shape.GetScale().x

                actual_width = mesh_width * scale

                # Determine the correct size category for this rock.
                category = _rock_size_category(
                    index,
                    len(ROCK_PATHS),
                )

                lower, upper = ROCK_SIZE_RANGES[category]

                self.assertGreaterEqual(
                    actual_width + 1e-9,
                    lower,
                )

                self.assertLessEqual(
                    actual_width,
                    upper + 1e-9,
                )

                # The lowest mesh vertex should touch terrain Z = 0.5.
                bottom_z = body.GetPos().z + min_z * scale

                self.assertAlmostEqual(
                    bottom_z,
                    0.5,
                    places=5,
                )

    def test_rural_objects_are_fixed_and_noncolliding(self):
        """Rural objects should be visual-only for performance."""

        import pychrono as chrono

        from environments.vegetation.goose_rural_objects import (
            create_rural_object,
        )

        system = chrono.ChSystemSMC()

        placement = {
            "asset_type": "low_grass_patch",
            "x": 2.0,
            "y": 3.0,
            "z": 0.25,
            "scale": 1.0,
            "rotation_z": 45.0,
        }

        body = create_rural_object(
            system,
            placement,
        )

        self.assertTrue(body.IsFixed())
        self.assertFalse(body.IsCollisionEnabled())
        self.assertIsNotNone(body.GetVisualModel())


if __name__ == "__main__":
    unittest.main()
