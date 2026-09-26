import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

import goose_to_heightmaps as launcher


class GooseLauncherTests(unittest.TestCase):
    def make_frame(self, root: Path) -> Namespace:
        pointcloud = root / "frame_pcl.bin"
        labels = root / "frame_goose.label"
        pointcloud.touch()
        labels.touch()

        return Namespace(
            scenario=Namespace(
                split="val",
                name="alice_scenario02",
            ),
            pointcloud=pointcloud.resolve(),
            label=labels.resolve(),
            mapping=None,
            changelog=None,
            selection_index=0,
        )

    def write_scene(
        self,
        root: Path,
        frame: Namespace,
        quality,
    ) -> Path:
        scene_dir = root / "generated"
        scene_dir.mkdir()

        heightmap = scene_dir / "heightmap.bmp"
        height_grid = scene_dir / "height_grid.npy"
        semantic_fine = scene_dir / "semantic_fine.npy"
        semantic_coarse = scene_dir / "semantic_coarse.npy"
        semantic_legend = scene_dir / "semantic_legend.json"
        heightmap.touch()
        height_grid.touch()
        semantic_fine.touch()
        semantic_coarse.touch()
        semantic_legend.touch()

        scene_path = scene_dir / "scene.json"
        scene = {
            "format_version": launcher.SCENE_FORMAT_VERSION,
            "source": {
                "dataset_root": str(root),
                "pointcloud": str(frame.pointcloud.relative_to(root)),
                "labels": str(frame.label.relative_to(root)),
                "mapping": None,
                "changelog": None,
                "fingerprints": launcher.frame_source_fingerprints(frame),
            },
            "quality": quality.to_manifest(),
            "heightmap": heightmap.name,
            "height_grid": height_grid.name,
            "outputs": {
                "semantic_fine": {"path": semantic_fine.name},
                "semantic_coarse": {"path": semantic_coarse.name},
                "semantic_legend": {"path": semantic_legend.name},
            },
            "semantics": {
                "format_version": launcher.SEMANTIC_FORMAT_VERSION,
                "fine_taxonomy": {
                    "name": launcher.FINE_TAXONOMY_NAME,
                    "mapping_sha256": launcher.FINE_MAPPING_SHA256,
                    "unobserved_id": 65535,
                },
                "coarse_taxonomy": {
                    "name": launcher.COARSE_TAXONOMY_NAME,
                    "unobserved_id": 255,
                },
                "aligned_to": height_grid.name,
            },
        }
        scene_path.write_text(
            json.dumps(scene),
            encoding="utf-8",
        )
        return scene_path

    def test_cli_defaults_to_balanced(self):
        with patch.object(
            sys,
            "argv",
            ["goose_to_heightmaps.py"],
        ):
            args = launcher.parse_args()

        self.assertEqual(args.quality, "balanced")
        self.assertIsNone(args.resolution)
        self.assertIsNone(args.grid_spacing)

    def test_cli_accepts_quality_and_overrides(self):
        with patch.object(
            sys,
            "argv",
            [
                "goose_to_heightmaps.py",
                "--quality",
                "high",
                "--resolution",
                "0.20",
                "--grid-spacing",
                "0.12",
            ],
        ):
            args = launcher.parse_args()

        self.assertEqual(args.quality, "high")
        self.assertEqual(args.resolution, 0.20)
        self.assertEqual(args.grid_spacing, 0.12)

    def test_converter_command_forwards_only_explicit_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            args = Namespace(
                frame_index=3,
                sequence="07",
                mapping=None,
                resolution=0.20,
                grid_spacing=None,
            )
            quality = launcher.resolve_quality(
                "high",
                resolution=0.20,
            )

            command = launcher.build_converter_command(
                args,
                root,
                frame,
                quality,
            )

        self.assertEqual(
            command[command.index("--quality") + 1],
            "high",
        )
        self.assertEqual(
            command[command.index("--resolution") + 1],
            "0.2",
        )
        self.assertEqual(
            command[command.index("--sequence") + 1],
            "07",
        )
        self.assertNotIn("--grid-spacing", command)
        self.assertNotIn("--mapping", command)

    def test_matching_quality_scene_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            quality = launcher.resolve_quality("balanced")
            scene_path = self.write_scene(
                root,
                frame,
                quality,
            )

            self.assertTrue(
                launcher.scene_matches_source(
                    scene_path,
                    frame,
                    quality,
                )
            )

    def test_different_quality_invalidates_cached_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            balanced = launcher.resolve_quality("balanced")
            high = launcher.resolve_quality("high")
            scene_path = self.write_scene(
                root,
                frame,
                balanced,
            )

            self.assertFalse(
                launcher.scene_matches_source(
                    scene_path,
                    frame,
                    high,
                )
            )

    def test_legacy_scene_without_quality_is_invalidated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            quality = launcher.resolve_quality("balanced")
            scene_path = self.write_scene(
                root,
                frame,
                quality,
            )

            scene = json.loads(
                scene_path.read_text(encoding="utf-8")
            )
            scene.pop("quality")
            scene_path.write_text(
                json.dumps(scene),
                encoding="utf-8",
            )

            self.assertFalse(
                launcher.scene_matches_source(
                    scene_path,
                    frame,
                    quality,
                )
            )

    def test_missing_semantic_output_invalidates_cached_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            quality = launcher.resolve_quality("balanced")
            scene_path = self.write_scene(root, frame, quality)
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            (
                scene_path.parent
                / scene["outputs"]["semantic_coarse"]["path"]
            ).unlink()

            self.assertFalse(
                launcher.scene_matches_source(scene_path, frame, quality)
            )

    def test_changed_source_invalidates_cached_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            quality = launcher.resolve_quality("balanced")
            scene_path = self.write_scene(root, frame, quality)
            frame.label.write_bytes(b"new labels")

            self.assertFalse(
                launcher.scene_matches_source(scene_path, frame, quality)
            )

    def test_old_semantic_taxonomy_invalidates_cached_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            quality = launcher.resolve_quality("balanced")
            scene_path = self.write_scene(root, frame, quality)
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["semantics"]["coarse_taxonomy"]["name"] = "old-taxonomy"
            scene_path.write_text(json.dumps(scene), encoding="utf-8")

            self.assertFalse(
                launcher.scene_matches_source(scene_path, frame, quality)
            )

    def test_old_scene_format_invalidates_cached_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            quality = launcher.resolve_quality("balanced")
            scene_path = self.write_scene(root, frame, quality)
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["format_version"] = 1
            scene_path.write_text(json.dumps(scene), encoding="utf-8")

            self.assertFalse(
                launcher.scene_matches_source(scene_path, frame, quality)
            )

    def test_main_runs_converter_when_cache_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            frame = self.make_frame(root)
            args = Namespace(
                dataset=root,
                split="auto",
                scenario=None,
                list_scenarios=False,
                mapping=None,
                sequence=None,
                frame_index=0,
                quality="balanced",
                resolution=None,
                grid_spacing=None,
                rebuild=False,
                headless=True,
                duration=0.01,
            )

            with (
                patch.object(launcher, "GENERATED_ROOT", root / "outputs"),
                patch.object(launcher, "parse_args", return_value=args),
                patch.object(launcher, "select_frame", return_value=frame),
                patch.object(launcher, "ensure_pychrono"),
                patch.object(launcher, "run") as run,
            ):
                result = launcher.main()

            self.assertEqual(result, 0)
            self.assertEqual(run.call_count, 2)
            converter_command = run.call_args_list[0].args[0]
            environment_command = run.call_args_list[1].args[0]
            self.assertEqual(Path(converter_command[1]), launcher.CONVERTER)
            self.assertEqual(Path(environment_command[1]), launcher.ENVIRONMENT)
            self.assertIn("--headless", environment_command)


if __name__ == "__main__":
    unittest.main()
