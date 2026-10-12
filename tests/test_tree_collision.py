"""Tests for rigid GOOSE tree collision in Project Chrono."""

import sys
import unittest
from pathlib import Path

import pychrono as chrono


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from environments.vegetation.goose_vegetation_objects import create_tree


class GooseTreeCollisionTests(unittest.TestCase):

    def test_tree_is_fixed_and_has_collision_geometry(self):
        system = chrono.ChSystemSMC()

        tree = create_tree(
            system,
            {
                "tree_id": 1,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
            },
        )

        self.assertTrue(tree.IsFixed())
        self.assertTrue(tree.IsCollisionEnabled())
        self.assertGreater(
            tree.GetCollisionModel().GetNumShapes(),
            0,
        )

    def test_moving_sphere_collides_with_rigid_tree(self):
        system = chrono.ChSystemSMC()
        system.SetGravitationalAcceleration(
            chrono.ChVector3d(0, 0, 0)
        )
        system.SetCollisionSystemType(
            chrono.ChCollisionSystem.Type_BULLET
        )

        tree = create_tree(
            system,
            {
                "tree_id": 1,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
            },
        )

        material = chrono.ChContactMaterialSMC()

        sphere = chrono.ChBodyEasySphere(
            0.3,
            1000.0,
            True,
            True,
            material,
        )

        sphere.SetPos(
            chrono.ChVector3d(-2.0, 0.0, 1.0)
        )
        sphere.SetPosDt(
            chrono.ChVector3d(2.0, 0.0, 0.0)
        )
        system.Add(sphere)

        maximum_contacts = 0

        for _ in range(1500):
            system.DoStepDynamics(0.001)
            maximum_contacts = max(
                maximum_contacts,
                system.GetNumContacts(),
            )

        self.assertGreater(maximum_contacts, 0)

        # The sphere should rebound rather than pass through
        # the fixed trunk.
        self.assertLess(sphere.GetPos().x, -0.5)
        self.assertTrue(tree.IsFixed())


if __name__ == "__main__":
    unittest.main()
