"""Viewer regressions using a real #22 export and small synthetic edge cases."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import numpy as np
from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
from scenarios.goose_label_viewer import viewer
from scenarios.goose_label_viewer.view_scene import main

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/goose_label_viewer"
REAL_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/goose_label_viewer_real"


class GooseLabelViewerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.scene_dir = self.root / "fixture"
        shutil.copytree(FIXTURE_ROOT, self.scene_dir)
        self.scene_path = self.scene_dir / "scene.json"
        self.output_dir = self.root / "previews"

    def invoke(self, *options):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main([
                "--scene", str(self.scene_path), "--output-dir", str(self.output_dir),
                *options,
            ])
        return status, stdout.getvalue(), stderr.getvalue()

    def update_scene(self, operation):
        value = json.loads(self.scene_path.read_text())
        operation(value)
        self.scene_path.write_text(json.dumps(value), encoding="utf-8")

    def test_saved_maps_use_exact_legend_colours_and_preserve_orientation(self):
        scene = viewer.load_scene(self.scene_path)
        fine, coarse = scene.maps
        self.assertEqual(fine.values.shape, (6, 8))
        self.assertEqual(coarse.values.shape, (6, 8))
        rgb, entries, messages = viewer.colourise(fine)
        np.testing.assert_array_equal(rgb[0, 0], [210, 210, 210])
        np.testing.assert_array_equal(rgb[0, 1], [36, 115, 70])
        np.testing.assert_array_equal(rgb[5, 7], [91, 100, 112])
        np.testing.assert_array_equal(rgb[fine.values == 31][0], [170, 119, 68])
        self.assertEqual({item.class_id for item in entries}, {0, 16, 31, 38, 50, 65535})
        self.assertEqual(messages, [])

    def test_cli_writes_both_previews_without_modifying_any_input(self):
        before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.scene_dir.iterdir() if path.is_file()
        }
        status, stdout, stderr = self.invoke()
        self.assertEqual(status, 0, stderr)
        self.assertEqual(stderr, "")
        for kind in ("fine", "coarse"):
            output = self.output_dir / f"fixture_{kind}_labels.png"
            self.assertIn(str(output), stdout)
            with Image.open(output) as image:
                self.assertGreater(image.width, 1000)
                self.assertGreater(image.height, 500)
                self.assertIn(f"{kind} labels", image.info["Description"])
        after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.scene_dir.iterdir() if path.is_file()
        }
        self.assertEqual(before, after)

    def test_overlay_blends_pixel_values_and_leaves_nodata_transparent(self):
        scene = viewer.load_scene(self.scene_path, overlay=True)
        item = scene.maps[0]
        rgb, _, _ = viewer.colourise(item)
        result = viewer.composite(rgb, item, scene.heightmap, 0.5)
        expected = np.rint(0.5 * rgb[0, 1] + 0.5 * scene.heightmap[0, 1] * 255)
        np.testing.assert_array_equal(result[0, 1], expected.astype(np.uint8))
        np.testing.assert_array_equal(
            result[0, 0], np.full(3, round(scene.heightmap[0, 0] * 255), dtype=np.uint8)
        )
        status, _, stderr = self.invoke("--map", "coarse", "--overlay", "--alpha", "0.5")
        self.assertEqual(status, 0, stderr)
        self.assertTrue((self.output_dir / "fixture_coarse_overlay.png").is_file())
        self.assertFalse((self.output_dir / "fixture_fine_overlay.png").exists())

    def test_old_heightmap_only_manifest_returns_clear_error_without_traceback(self):
        self.update_scene(lambda value: value.pop("label_maps"))
        status, _, stderr = self.invoke()
        self.assertEqual(status, 2)
        self.assertIn("No requested semantic label maps", stderr)
        self.assertIn("#22", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertFalse(self.output_dir.exists())

    def test_explicit_files_can_view_a_manifest_without_label_fields(self):
        self.update_scene(lambda value: value.pop("label_maps"))
        status, _, stderr = self.invoke(
            "--fine-map", str(self.scene_dir / "labels_fine.npy"),
            "--coarse-map", str(self.scene_dir / "labels_coarse.npy"),
            "--legend", str(self.scene_dir / "label_legend.json"),
        )
        self.assertEqual(status, 0, stderr)
        # Overrides have no nodata declaration; unknown IDs must remain visible.
        self.assertIn("65535", stderr)

    def test_missing_map_file_and_missing_legend_are_clear_errors(self):
        for name in ("labels_coarse.npy", "label_legend.json"):
            with self.subTest(name=name):
                path = self.scene_dir / name
                backup = path.with_suffix(path.suffix + ".saved")
                path.rename(backup)
                try:
                    status, _, stderr = self.invoke()
                    self.assertEqual(status, 2)
                    self.assertIn(name, stderr)
                    self.assertNotIn("Traceback", stderr)
                finally:
                    backup.rename(path)

    def test_absent_coarse_map_warns_in_both_mode_and_errors_when_requested(self):
        self.update_scene(lambda value: value["label_maps"].pop("coarse"))
        status, _, stderr = self.invoke()
        self.assertEqual(status, 0)
        self.assertIn("No coarse label map", stderr)
        self.assertTrue((self.output_dir / "fixture_fine_labels.png").is_file())
        status, _, stderr = self.invoke("--map", "coarse")
        self.assertEqual(status, 2)
        self.assertIn("No requested semantic label maps", stderr)

    def test_unknown_ids_are_magenta_and_get_an_explicit_legend_entry(self):
        path = self.scene_dir / "labels_fine.npy"
        values = np.load(path)
        values[1, 1] = 777
        np.save(path, values)
        item = viewer.load_scene(self.scene_path, selection="fine").maps[0]
        rgb, entries, warnings = viewer.colourise(item)
        np.testing.assert_array_equal(rgb[1, 1], [255, 0, 255])
        self.assertIn("Unknown ID 777", [item.name for item in entries])
        self.assertIn("777", warnings[0])

    def test_overlay_refuses_shape_mismatch(self):
        np.save(self.scene_dir / "height_grid.npy", np.ones((3, 4)))
        status, _, stderr = self.invoke("--overlay")
        self.assertEqual(status, 2)
        self.assertIn("differs from label-map shape", stderr)
        self.assertFalse(self.output_dir.exists())

    def test_per_point_float_and_rgb_arrays_are_not_accepted_as_label_maps(self):
        for values in (np.arange(48), np.zeros((6, 8), dtype=float), np.zeros((6, 8, 3), dtype=np.uint8)):
            with self.subTest(shape=values.shape, dtype=values.dtype):
                np.save(self.scene_dir / "labels_fine.npy", values)
                status, _, stderr = self.invoke("--map", "fine")
                self.assertEqual(status, 2)
                self.assertNotIn("Traceback", stderr)

    def test_palette_png_retains_ids_instead_of_converting_colours(self):
        values = np.array([[31, 50], [16, 38]], dtype=np.uint8)
        image = Image.fromarray(values).convert("P")
        path = self.scene_dir / "palette.png"
        image.save(path)
        np.testing.assert_array_equal(viewer.read_label_map(path), values)

    def test_archive_named_as_npy_returns_a_clear_error(self):
        with (self.scene_dir / "labels_fine.npy").open("wb") as stream:
            np.savez(stream, labels=np.zeros((6, 8), dtype=np.uint8))
        status, _, stderr = self.invoke("--map", "fine")
        self.assertEqual(status, 2)
        self.assertIn("archives are not supported", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_bad_legend_entries_return_clear_errors(self):
        path = self.scene_dir / "label_legend.json"
        original = path.read_text()
        for mutation in (
            lambda value: value.update(format_version=99),
            lambda value: value["fine"].append(value["fine"][0]),
            lambda value: value["fine"][0].update(color=[0.5, 0.5, 0.5]),
        ):
            value = json.loads(original)
            mutation(value)
            path.write_text(json.dumps(value))
            status, _, stderr = self.invoke()
            self.assertEqual(status, 2)
            self.assertNotIn("Traceback", stderr)

    def test_output_cannot_overwrite_a_label_input(self):
        source = self.scene_dir / "fixture_fine_labels.png"
        Image.fromarray(np.full((6, 8), 31, dtype=np.uint8)).save(source)
        self.update_scene(lambda value: value["label_maps"].update(fine=source.name))
        before = source.read_bytes()
        scene = viewer.load_scene(self.scene_path, selection="fine")
        with self.assertRaisesRegex(viewer.ViewerError, "overwrite an input"):
            viewer.render_previews(scene, self.scene_dir)
        self.assertEqual(before, source.read_bytes())

    def test_output_protects_unselected_map_and_non_overlay_heightmap(self):
        source = self.scene_dir / "fixture_fine_labels.png"
        Image.fromarray(np.full((6, 8), 31, dtype=np.uint8)).save(source)
        before = source.read_bytes()
        for field in ("coarse", "heightmap"):
            with self.subTest(field=field):
                shutil.copy(FIXTURE_ROOT / "scene.json", self.scene_path)
                if field == "coarse":
                    self.update_scene(lambda value: value["label_maps"].update(coarse=source.name))
                else:
                    self.update_scene(lambda value: value.update(heightmap=source.name))
                scene = viewer.load_scene(self.scene_path, selection="fine")
                with self.assertRaisesRegex(viewer.ViewerError, "overwrite an input"):
                    viewer.render_previews(scene, self.scene_dir)
                self.assertEqual(before, source.read_bytes())

    def test_module_command_resolves_manifest_paths_from_another_directory(self):
        result = subprocess.run(
            [sys.executable, "-m", "scenarios.goose_label_viewer.view_scene",
             "--scene", str(self.scene_path), "--map", "fine",
             "--output-dir", str(self.output_dir)],
            cwd=self.root, env=dict(os.environ, PYTHONPATH=str(REPOSITORY_ROOT)),
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output_dir / "fixture_fine_labels.png").is_file())

    def test_real_saved_export(self):
        path = Path(os.environ.get("GOOSE_LABEL_SCENE", REAL_FIXTURE_ROOT / "scene.json"))
        before = {p: hashlib.sha256(p.read_bytes()).digest() for p in path.parent.iterdir() if p.is_file()}
        for overlay in (False, True):
            with self.subTest(overlay=overlay):
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    status = main([
                        "--scene", str(path), "--output-dir", str(self.output_dir),
                        *(["--overlay"] if overlay else []),
                    ])
                self.assertEqual(status, 0, stderr.getvalue())
                self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(list(self.output_dir.glob("*.png"))), 4)
        for image in self.output_dir.glob("*.png"):
            with Image.open(image) as preview:
                preview.verify()
        for file, digest in before.items():
            self.assertEqual(hashlib.sha256(file.read_bytes()).digest(), digest)

    def test_real_export_distribution_rollup_and_unobserved_cells(self):
        path = REAL_FIXTURE_ROOT / "scene.json"
        scene = viewer.load_scene(path, overlay=True)
        fine, coarse = scene.maps
        self.assertEqual(fine.values.shape, (268, 268))
        self.assertEqual(fine.values.dtype, np.dtype("uint16"))
        self.assertEqual(coarse.values.dtype, np.dtype("uint8"))
        self.assertEqual((fine.nodata, coarse.nodata), (65535, 255))
        self.assertEqual(len(fine.legend), 64)
        self.assertEqual(len(coarse.legend), 12)
        metadata = json.loads(path.read_text())["semantics"]
        for item in scene.maps:
            values, counts = np.unique(item.values, return_counts=True)
            actual = {int(value): int(count) for value, count in zip(values, counts) if value != item.nodata}
            expected = {entry["id"]: entry["count"] for entry in metadata[f"{item.kind}_distribution"]}
            self.assertEqual(actual, expected)
            self.assertEqual(sum(actual.values()), 26364)
        np.testing.assert_array_equal(fine.values == fine.nodata, coarse.values == coarse.nodata)
        legend = json.loads((REAL_FIXTURE_ROOT / "semantic_legend.json").read_text())
        for row in legend["classes"]:
            self.assertTrue(np.all(coarse.values[fine.values == row["id"]] == row["coarse_id"]))
        rgb, _, warnings = viewer.colourise(coarse)
        self.assertEqual(warnings, [])
        blended = viewer.composite(rgb, coarse, scene.heightmap, 0.55)
        missing = coarse.values == coarse.nodata
        expected = np.repeat(np.rint(scene.heightmap[missing, None] * 255), 3, axis=1).astype(np.uint8)
        np.testing.assert_array_equal(blended[missing], expected)
        # Ignored is an observed class, distinct from unobserved cells.
        self.assertEqual(np.count_nonzero(coarse.values == 0), 627)
        self.assertEqual(np.count_nonzero(missing), 45460)

    def test_real_legend_colours_are_stable_and_explicit_colours_take_precedence(self):
        path = self.root / "legend.json"
        original = json.loads((REAL_FIXTURE_ROOT / "semantic_legend.json").read_text())
        path.write_text(json.dumps(original))
        entries = viewer.load_legend(path, ("fine", "coarse"))
        original["classes"].reverse()
        original["coarse_taxonomy"]["categories"].reverse()
        path.write_text(json.dumps(original))
        reversed_entries = viewer.load_legend(path, ("fine", "coarse"))
        self.assertEqual(entries, reversed_entries)
        self.assertEqual(entries["coarse"][1].color, (38, 139, 74))
        original["classes"] = [row for row in original["classes"] if row["id"] == 31]
        path.write_text(json.dumps(original))
        self.assertEqual(viewer.load_legend(path, ("fine",))["fine"][31], entries["fine"][31])
        original["classes"][0]["color"] = "#123456"
        path.write_text(json.dumps(original))
        self.assertEqual(viewer.load_legend(path, ("fine",))["fine"][31].color, (18, 52, 86))

    def test_real_manifest_rejects_outdated_versions_shapes_and_conflicting_nodata(self):
        scene_dir = self.root / "real"
        shutil.copytree(REAL_FIXTURE_ROOT, scene_dir)
        path = scene_dir / "scene.json"
        original = json.loads(path.read_text())
        for mutation, message in (
            (lambda value: value.update(format_version=99), "Unsupported scene"),
            (lambda value: value["semantics"].update(format_version=99), "Unsupported semantics"),
            (lambda value: value["outputs"]["semantic_fine"].update(shape=[1, 1]), "manifest shape"),
            (lambda value: value["outputs"]["semantic_fine"].update(dtype="uint8"), "manifest dtype"),
            (lambda value: value["semantics"]["coarse_taxonomy"].update(unobserved_id=0), "Conflicting coarse"),
            (lambda value: value["grid"].update(row_zero="ymin"), "Unsupported scene grid"),
        ):
            with self.subTest(message=message):
                value = json.loads(json.dumps(original))
                mutation(value)
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(viewer.ViewerError, message):
                    viewer.load_scene(path)

    def test_real_manifest_missing_map_and_heightmap_fallback(self):
        scene_dir = self.root / "real"
        shutil.copytree(REAL_FIXTURE_ROOT, scene_dir)
        path = scene_dir / "scene.json"
        (scene_dir / "height_grid.npy").unlink()
        scene = viewer.load_scene(path, overlay=True)
        self.assertEqual(scene.heightmap_path.name, "heightmap.bmp")
        self.assertEqual(scene.heightmap.shape, (268, 268))
        (scene_dir / "semantic_fine.npy").unlink()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            status = main(["--scene", str(path)])
        self.assertEqual(status, 2)
        self.assertIn("semantic_fine.npy", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
