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
        heightmap.touch()
        height_grid.touch()

        scene_path = scene_dir / "scene.json"
        scene = {
            "source": {
                "dataset_root": str(root),
                "pointcloud": str(frame.pointcloud.relative_to(root)),
                "labels": str(frame.label.relative_to(root)),
                "mapping": None,
            },
            "quality": quality.to_manifest(),
            "heightmap": heightmap.name,
            "height_grid": height_grid.name,
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


if __name__ == "__main__":
    unittest.main()