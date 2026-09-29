import json
import sys
import unittest
from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TERRAIN_ROOT = REPOSITORY_ROOT / "environments" / "terrain"
sys.path.insert(0, str(TERRAIN_ROOT))

import goose_dataset as dataset
import goose_semantics as semantics


class GooseSemanticTests(unittest.TestCase):
    def test_taxonomy_has_a_complete_stable_rollup(self):
        legend = semantics.semantic_legend()

        self.assertEqual(len(legend["classes"]), 64)
        self.assertEqual(
            [entry["id"] for entry in legend["classes"]],
            list(range(64)),
        )
        self.assertEqual(
            {entry["id"] for entry in legend["coarse_taxonomy"]["categories"]},
            set(range(12)),
        )
        self.assertEqual(legend["classes"][16]["coarse_name"], "vegetation")
        self.assertEqual(legend["classes"][31]["coarse_name"], "terrain")
        self.assertEqual(legend["classes"][38]["coarse_name"], "structure")
        self.assertEqual(legend["classes"][57]["coarse_name"], "vehicle")
        self.assertEqual(
            json.dumps(legend, sort_keys=True),
            json.dumps(semantics.semantic_legend(), sort_keys=True),
        )

    def test_raster_alignment_majority_and_tie_break_are_deterministic(self):
        points = np.array(
            [
                [0.0, 2.0, 0.0, 1.0],  # top-left: terrain majority
                [0.1, 1.9, 1.0, 1.0],
                [0.0, 2.0, 2.0, 1.0],
                [1.0, 1.0, 0.0, 1.0],  # centre: 16 wins tie over 31
                [1.0, 1.0, 0.0, 1.0],
                [2.0, 0.0, 0.0, 1.0],  # bottom-right
                [3.0, 3.0, 0.0, 1.0],  # out of bounds
            ],
            dtype=np.float32,
        )
        labels = np.array([31, 31, 16, 31, 16, 57, 38], dtype=np.uint32)

        fine, coarse, count = semantics.rasterize_semantics(
            points, labels, bounds=(0, 2, 0, 2), resolution=1.0
        )

        self.assertEqual(fine.shape, (3, 3))
        self.assertEqual(count, 6)
        self.assertEqual(int(fine[0, 0]), 31)
        self.assertEqual(int(coarse[0, 0]), 2)
        self.assertEqual(int(fine[1, 1]), 16)
        self.assertEqual(int(coarse[1, 1]), 1)
        self.assertEqual(int(fine[2, 2]), 57)
        self.assertEqual(int(coarse[2, 2]), 4)
        self.assertEqual(int(fine[0, 2]), 65535)
        self.assertEqual(int(coarse[0, 2]), 255)

    def test_unknown_class_id_is_rejected(self):
        points = np.array([[0, 0, 0, 1]], dtype=np.float32)
        with self.assertRaisesRegex(ValueError, "Unknown GOOSE semantic class IDs"):
            semantics.rasterize_semantics(
                points,
                np.array([64], dtype=np.uint32),
                bounds=(-1, 1, -1, 1),
                resolution=1.0,
            )

    def test_incomplete_or_changed_mapping_is_rejected(self):
        incomplete = {
            identifier: name
            for identifier, name in enumerate(semantics.FINE_CLASS_NAMES[:-1])
        }
        with self.assertRaisesRegex(ValueError, "IDs 0 through 63"):
            semantics.validate_class_names(incomplete)

        renamed = dict(enumerate(semantics.FINE_CLASS_NAMES))
        renamed[31] = "dirt"
        with self.assertRaisesRegex(ValueError, "original GOOSE-64 taxonomy"):
            semantics.validate_class_names(renamed)

    def test_documented_frame_name_fields_are_parsed(self):
        metadata = dataset.parse_frame_metadata(
            Path("2022-08-30_alice_scenario02_sequence07_000042_1661840000123_vls128.bin")
        )

        self.assertEqual(metadata.sequence, "07")
        self.assertEqual(metadata.frame_number, 42)
        self.assertEqual(metadata.timestamp, 1661840000123)
        self.assertEqual(
            metadata.name,
            "2022-08-30_alice_scenario02_sequence07_000042_1661840000123",
        )


if __name__ == "__main__":
    unittest.main()
