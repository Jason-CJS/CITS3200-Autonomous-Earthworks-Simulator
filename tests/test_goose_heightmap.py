import json
import struct
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import numpy as np

from environments.goose.terrain import build_heightmap as converter


class GooseHeightmapTests(unittest.TestCase):
    def test_label_bit_fields_are_decoded(self):
        with tempfile.TemporaryDirectory() as directory:
            label_path = Path(directory) / "frame_goose.label"
            encoded = np.array([(7 << 16) | 31, (2 << 16) | 23], dtype=np.uint32)
            encoded.tofile(label_path)

            semantic, instance = converter.read_labels(label_path, 2)

            np.testing.assert_array_equal(semantic, [31, 23])
            np.testing.assert_array_equal(instance, [7, 2])

    def test_rasterizer_uses_ground_labels_not_vegetation(self):
        axis = np.linspace(-2, 2, 21, dtype=np.float32)
        xx, yy = np.meshgrid(axis, axis)
        ground_z = 0.1 * xx + 0.05 * yy
        ground = np.column_stack(
            (xx.ravel(), yy.ravel(), ground_z.ravel(), np.ones(xx.size))
        ).astype(np.float32)
        vegetation = ground.copy()
        vegetation[:, 2] += 5.0
        points = np.vstack((ground, vegetation))
        semantic = np.concatenate(
            (
                np.full(len(ground), 31, dtype=np.uint32),
                np.full(len(vegetation), 16, dtype=np.uint32),
            )
        )

        grid, observed, count = converter.rasterize_ground(
            points,
            semantic,
            ground_ids=[31],
            bounds=(-2, 2, -2, 2),
            resolution=0.2,
            height_percentile=20,
            smooth_passes=0,
        )

        self.assertEqual(count, len(ground))
        self.assertTrue(observed.all())
        self.assertLess(float(grid.max()), 1.0)
        self.assertAlmostEqual(float(grid[10, 10]), 0.0, places=5)

    def test_bmp_header_contains_expected_dimensions(self):
        pixels = np.arange(35, dtype=np.uint8).reshape((5, 7))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "heightmap.bmp"
            converter.write_grayscale_bmp(path, pixels)
            contents = path.read_bytes()

        self.assertEqual(contents[:2], b"BM")
        width, height = struct.unpack_from("<ii", contents, 18)
        bits_per_pixel = struct.unpack_from("<H", contents, 28)[0]
        self.assertEqual((width, height), (7, 5))
        self.assertEqual(bits_per_pixel, 8)

    def test_build_scene_selects_real_goose_ex_naming_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "gooseEx_3d_val"
            lidar = root / "lidar" / "val" / "alice_scenario02"
            labels = root / "labels" / "val" / "alice_scenario02"
            lidar.mkdir(parents=True)
            labels.mkdir(parents=True)
            prefix = "alice_scenario02_sequence07_0000_123"
            pointcloud_path = lidar / f"{prefix}_pcl.bin"
            label_path = labels / f"{prefix}_goose.label"
            pointcloud_path.touch()
            label_path.touch()

            selected_cloud, selected_label = converter.find_frame_pair(
                root, "val", "alice_scenario02", "07", 0
            )

            self.assertEqual(selected_cloud, pointcloud_path)
            self.assertEqual(selected_label, label_path)

    def test_end_to_end_scene_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "gooseEx_3d_val"
            lidar = root / "lidar" / "val" / "alice_scenario02"
            labels = root / "labels" / "val" / "alice_scenario02"
            lidar.mkdir(parents=True)
            labels.mkdir(parents=True)
            prefix = "alice_scenario02_sequence07_0000_123"

            axis = np.linspace(-2, 2, 21, dtype=np.float32)
            xx, yy = np.meshgrid(axis, axis)
            points = np.column_stack(
                (xx.ravel(), yy.ravel(), (0.1 * xx).ravel(), np.ones(xx.size))
            ).astype(np.float32)
            semantic = np.full(len(points), 31, dtype=np.uint32)
            points.tofile(lidar / f"{prefix}_pcl.bin")
            semantic.tofile(labels / f"{prefix}_goose.label")

            args = Namespace(
                dataset=root,
                split="val",
                scenario="alice_scenario02",
                sequence="07",
                frame_index=0,
                bounds=(-2.0, 2.0, -2.0, 2.0),
                resolution=0.2,
                height_percentile=20.0,
                smooth_passes=1,
                ground_classes=["soil"],
                output=temporary / "generated",
            )
            scene_path = converter.build_scene(args)
            scene = json.loads(scene_path.read_text(encoding="utf-8"))

            self.assertEqual(scene["source"]["platform"], "ALICE")
            self.assertEqual(scene["conversion"]["ground_class_ids"], [31])
            self.assertEqual(scene["conversion"]["ground_points_used"], len(points))
            self.assertTrue((scene_path.parent / scene["heightmap"]).is_file())
            self.assertEqual(
                np.load(scene_path.parent / scene["height_grid"]).shape, (21, 21)
            )


if __name__ == "__main__":
    unittest.main()
