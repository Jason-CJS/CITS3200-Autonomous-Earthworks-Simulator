import csv
import json
import tempfile
import unittest
from pathlib import Path

from deformation.scm_deformation_export import (
    CSV_FIELDS,
    CSV_FILENAME,
    SUMMARY_FILENAME,
    calculate_scm_grid_geometry,
    calculate_deformation_summary,
    collect_deformation_records,
    write_deformation_export,
)


class AttributeVector:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class MethodVector:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class PairNodeLevel:
    def __init__(self, position, level):
        self.first = position
        self.second = level


class DeformationExportTests(unittest.TestCase):
    def test_collects_pair_and_sequence_node_levels(self):
        modified_nodes = [
            PairNodeLevel(MethodVector(2, -1), -0.08),
            (AttributeVector(-1, 3), 0.04),
        ]

        records = collect_deformation_records(
            modified_nodes,
            grid_spacing_m=0.15,
            initial_height_at=lambda _x, _y: 0.02,
            world_position_at=lambda x, y: (x + 10, y - 4),
        )

        self.assertEqual(
            [(record.grid_x, record.grid_y) for record in records],
            [(-1, 3), (2, -1)],
        )

        raised_node, sunk_node = records
        self.assertAlmostEqual(raised_node.world_x_m, 9.85)
        self.assertAlmostEqual(raised_node.world_y_m, -3.55)
        self.assertAlmostEqual(raised_node.height_change_m, 0.02)
        self.assertAlmostEqual(raised_node.sinkage_m, 0.0)

        self.assertAlmostEqual(sunk_node.world_x_m, 10.3)
        self.assertAlmostEqual(sunk_node.world_y_m, -4.15)
        self.assertAlmostEqual(sunk_node.height_change_m, -0.1)
        self.assertAlmostEqual(sunk_node.sinkage_m, 0.1)

    def test_rejects_non_positive_grid_spacing(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            collect_deformation_records([], grid_spacing_m=0)

    def test_calculates_chrono_adjusted_grid_geometry(self):
        geometry = calculate_scm_grid_geometry(20.0, 10.0, 0.15)

        self.assertAlmostEqual(geometry.actual_spacing_m, 20.0 / 134)
        self.assertEqual(geometry.node_count_x, 135)
        self.assertEqual(geometry.node_count_y, 69)

    def test_rejects_invalid_grid_geometry(self):
        with self.assertRaisesRegex(ValueError, "dimensions"):
            calculate_scm_grid_geometry(0, 10.0, 0.15)
        with self.assertRaisesRegex(ValueError, "requested_spacing_m"):
            calculate_scm_grid_geometry(20.0, 10.0, -0.15)

    def test_calculates_summary_metrics(self):
        records = collect_deformation_records(
            [
                (AttributeVector(0, 0), -0.1),
                (AttributeVector(1, 0), -0.05),
                (AttributeVector(2, 0), 0.02),
            ],
            grid_spacing_m=0.15,
        )

        summary = calculate_deformation_summary(records)

        self.assertEqual(summary["modified_node_count"], 3)
        self.assertAlmostEqual(summary["maximum_sinkage_m"], 0.1)
        self.assertAlmostEqual(summary["mean_sinkage_m"], 0.05)

    def test_writes_csv_and_json(self):
        records = collect_deformation_records(
            [(AttributeVector(1, -2), -0.03)],
            grid_spacing_m=0.15,
        )
        settings = {
            "simulation_duration_s": 6.0,
            "terrain": {"grid_spacing_m": 0.15},
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path, summary_path = write_deformation_export(
                records,
                temporary_directory,
                settings,
            )

            self.assertEqual(csv_path.name, CSV_FILENAME)
            self.assertEqual(summary_path.name, SUMMARY_FILENAME)

            with csv_path.open(encoding="utf-8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))
            self.assertEqual(tuple(rows[0].keys()), CSV_FIELDS)
            self.assertEqual(rows[0]["grid_x"], "1")
            self.assertEqual(rows[0]["grid_y"], "-2")
            self.assertAlmostEqual(float(rows[0]["sinkage_m"]), 0.03)

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["format_version"], 1)
            self.assertEqual(summary["modified_node_count"], 1)
            self.assertEqual(summary["simulation_settings"], settings)

    def test_writes_valid_empty_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path, summary_path = write_deformation_export(
                [],
                temporary_directory,
                {"simulation_duration_s": 0.0},
            )

            with csv_path.open(encoding="utf-8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))
            self.assertEqual(rows, [])

            summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
            self.assertEqual(summary["modified_node_count"], 0)
            self.assertEqual(summary["maximum_sinkage_m"], 0.0)
            self.assertEqual(summary["mean_sinkage_m"], 0.0)


if __name__ == "__main__":
    unittest.main()
