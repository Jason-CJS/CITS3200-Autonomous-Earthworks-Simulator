"""Tests for GOOSE bulldozer tree obstacle detection."""

import unittest
from types import SimpleNamespace

from scenarios.goose_navigation.run_demo import (
    _tree_ahead_of_blade,
)


class TestTreeNavigation(unittest.TestCase):

    def setUp(self):
        # Simulate a bulldozer blade at X=3.0, Y=0.0.
        # No Chrono simulation is required.
        position = SimpleNamespace(x=3.0, y=0.0)

        blade = SimpleNamespace(
            GetPos=lambda: position
        )

        self.bulldozer = SimpleNamespace(blade=blade)
        self.trunk_radius = 0.20

    def make_tree(self, tree_id, x, y):
        return {
            "tree_id": tree_id,
            "x": x,
            "y": y,
            "z": 0.0,
        }

    def test_tree_directly_ahead(self):
        tree = self.make_tree(10, 2.65, 0.0)

        result = _tree_ahead_of_blade(
            self.bulldozer,
            [tree],
            self.trunk_radius,
        )

        self.assertEqual(result, tree)

    def test_tree_outside_blade_width(self):
        tree = self.make_tree(11, 2.65, 3.0)

        result = _tree_ahead_of_blade(
            self.bulldozer,
            [tree],
            self.trunk_radius,
        )

        self.assertIsNone(result)

    def test_tree_behind_blade(self):
        tree = self.make_tree(12, 3.50, 0.0)

        result = _tree_ahead_of_blade(
            self.bulldozer,
            [tree],
            self.trunk_radius,
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
