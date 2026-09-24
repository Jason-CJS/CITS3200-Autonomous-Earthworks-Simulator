"""Tests for reading and classifying previously-generated output files."""

import json
import tempfile
import unittest
from pathlib import Path

from deformation.output_inspector import (
    DEFORMATION_SUMMARY,
    GOOSE_SCENE,
    HOLE_FILL_SUMMARY,
    UNKNOWN,
    detect_output_kind,
    discover_output_files,
    format_report,
    load_output_directory,
    load_output_file,
)


HOLE_FILL_SUMMARY_DATA = {
    "acceptance_thresholds": {
        "minimum_average_height_increase_m": 0.001,
        "minimum_modified_nodes_in_hole": 10,
    },
    "format_version": 1,
    "hole_metrics": {
        "average_height_increase_m": 0.002085541491011589,
        "final_average_height_m": -0.03382949118872698,
        "hole_node_count": 48,
        "initial_average_height_m": -0.03591503267973857,
        "modified_node_count_in_hole": 14,
    },
    "modified_node_count": 1287,
    "passed": True,
    "scenario": "scripted_bulldozer_hole_filling",
    "simulation_settings": {"step_size_s": 0.002},
}

DEFORMATION_SUMMARY_DATA = {
    "format_version": 1,
    "maximum_sinkage_m": 0.22052693684576805,
    "mean_sinkage_m": 0.029238569463623867,
    "modified_node_count": 1287,
    "simulation_settings": {"step_size_s": 0.002},
}

GOOSE_SCENE_DATA = {
    "format_version": 1,
    "quality": {"preset": "high", "resolved": {}, "overrides": {}},
    "source": {"scenario": "alice_scenario02"},
    "heightmap": "heightmap.bmp",
    "size_x": 40.0,
    "size_y": 40.0,
    "grid": {"width": 401, "height": 401},
}


class OutputKindDetectionTests(unittest.TestCase):
    def test_detects_hole_fill_summary(self):
        self.assertEqual(detect_output_kind(HOLE_FILL_SUMMARY_DATA), HOLE_FILL_SUMMARY)

    def test_detects_deformation_summary(self):
        self.assertEqual(detect_output_kind(DEFORMATION_SUMMARY_DATA), DEFORMATION_SUMMARY)

    def test_detects_goose_scene(self):
        self.assertEqual(detect_output_kind(GOOSE_SCENE_DATA), GOOSE_SCENE)

    def test_unrecognised_shape_returns_unknown(self):
        self.assertEqual(detect_output_kind({"unrelated": True}), UNKNOWN)


class LoadOutputFileTests(unittest.TestCase):
    def test_loads_and_summarises_hole_fill_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hole_fill_summary.json"
            path.write_text(json.dumps(HOLE_FILL_SUMMARY_DATA))

            record = load_output_file(path)

            self.assertTrue(record.ok)
            self.assertEqual(record.kind, HOLE_FILL_SUMMARY)
            self.assertEqual(record.format_version, 1)
            self.assertIn("PASSED", record.summary)

    def test_missing_file_reports_error_without_raising(self):
        record = load_output_file(Path("/nonexistent/does_not_exist.json"))

        self.assertFalse(record.ok)
        self.assertIsNotNone(record.error)

    def test_malformed_json_reports_error_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("{not valid json")

            record = load_output_file(path)

            self.assertFalse(record.ok)
            self.assertIn("invalid JSON", record.error)

    def test_non_object_json_reports_error_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "list.json"
            path.write_text("[1, 2, 3]")

            record = load_output_file(path)

            self.assertFalse(record.ok)

    def test_non_utf8_file_reports_error_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.json"
            path.write_bytes(bytes([0xFF, 0xD5, 0x00, 0x10, 0x20]))

            record = load_output_file(path)

            self.assertFalse(record.ok)
            self.assertIn("could not read file", record.error)

    def test_directory_path_reports_error_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = load_output_file(Path(tmp))

            self.assertFalse(record.ok)


class FormatReportTests(unittest.TestCase):
    def test_hole_fill_report_converts_metres_to_millimetres(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hole_fill_summary.json"
            path.write_text(json.dumps(HOLE_FILL_SUMMARY_DATA))
            record = load_output_file(path)

            report = format_report(record)

            self.assertIn("PASSED", report)
            self.assertIn("2.09 mm", report)
            self.assertIn("14 / 48", report)
            self.assertNotIn("average_height_increase_m", report)

    def test_deformation_report_converts_metres_to_millimetres(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deformation_summary.json"
            path.write_text(json.dumps(DEFORMATION_SUMMARY_DATA))
            record = load_output_file(path)

            report = format_report(record)

            self.assertIn("1287", report)
            self.assertIn("29.24 mm", report)

    def test_goose_scene_report_includes_quality_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.json"
            path.write_text(json.dumps(GOOSE_SCENE_DATA))
            record = load_output_file(path)

            report = format_report(record)

            self.assertIn("alice_scenario02", report)
            self.assertIn("high", report)

    def test_unreadable_file_report_shows_error_without_raising(self):
        record = load_output_file(Path("/nonexistent/missing.json"))

        report = format_report(record)

        self.assertIn("Could not read", report)


class DiscoverOutputFilesTests(unittest.TestCase):
    def test_finds_known_filenames_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run_a").mkdir()
            (root / "run_b" / "nested").mkdir(parents=True)
            (root / "run_a" / "hole_fill_summary.json").write_text(
                json.dumps(HOLE_FILL_SUMMARY_DATA)
            )
            (root / "run_b" / "nested" / "scene.json").write_text(
                json.dumps(GOOSE_SCENE_DATA)
            )
            (root / "run_a" / "ignored.txt").write_text("not an output file")

            found = discover_output_files(root)

            self.assertEqual(len(found), 2)

    def test_missing_root_returns_empty_list(self):
        self.assertEqual(discover_output_files(Path("/nonexistent/root")), [])

    def test_load_output_directory_skips_malformed_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deformation_summary.json").write_text(
                json.dumps(DEFORMATION_SUMMARY_DATA)
            )
            (root / "hole_fill_summary.json").write_text("{not valid")

            records = load_output_directory(root)

            self.assertEqual(len(records), 2)
            self.assertTrue(any(r.ok for r in records))
            self.assertTrue(any(not r.ok for r in records))


if __name__ == "__main__":
    unittest.main()
