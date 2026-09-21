import math
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TERRAIN_ROOT = REPOSITORY_ROOT / "environments" / "terrain"
sys.path.insert(0, str(TERRAIN_ROOT))

from goose_quality import resolve_quality
from goose_quality import scm_grid_spacing_from_scene

class GooseQualityTests(unittest.TestCase):
    def test_default_is_balanced(self):
        quality = resolve_quality()

        self.assertEqual(quality.preset, "balanced")
        self.assertEqual(quality.terrain_resolution, 0.15)
        self.assertEqual(quality.scm_grid_spacing, 0.15)
        self.assertEqual(quality.overrides, ())

    def test_named_presets_resolve_to_benchmarked_values(self):
        expected = {
            "low": (0.30, 0.30),
            "balanced": (0.15, 0.15),
            "high": (0.10, 0.10),
        }

        for preset, values in expected.items():
            with self.subTest(preset=preset):
                quality = resolve_quality(preset)

                self.assertEqual(
                    quality.terrain_resolution, values[0]
                )
                self.assertEqual(
                    quality.scm_grid_spacing, values[1]
                )

    def test_resolution_override_changes_only_resolution(self):
        quality = resolve_quality("high", resolution=0.20)

        self.assertEqual(quality.terrain_resolution, 0.20)
        self.assertEqual(quality.scm_grid_spacing, 0.10)
        self.assertEqual(
            quality.overrides, ("terrain_resolution",)
        )

    def test_grid_spacing_override_changes_only_grid_spacing(self):
        quality = resolve_quality("low", grid_spacing=0.12)

        self.assertEqual(quality.terrain_resolution, 0.30)
        self.assertEqual(quality.scm_grid_spacing, 0.12)
        self.assertEqual(
            quality.overrides, ("scm_grid_spacing",)
        )

    def test_both_values_can_be_overridden(self):
        quality = resolve_quality(
            "balanced",
            resolution=0.25,
            grid_spacing=0.20,
        )

        self.assertEqual(quality.terrain_resolution, 0.25)
        self.assertEqual(quality.scm_grid_spacing, 0.20)
        self.assertEqual(
            quality.overrides,
            ("terrain_resolution", "scm_grid_spacing"),
        )

    def test_manifest_records_resolved_values_and_overrides(self):
        quality = resolve_quality("high", grid_spacing=0.12)

        self.assertEqual(
            quality.to_manifest(),
            {
                "preset": "high",
                "resolved": {
                    "terrain_resolution": 0.10,
                    "scm_grid_spacing": 0.12,
                },
                "overrides": {
                    "scm_grid_spacing": 0.12,
                },
            },
        )

    def test_unknown_preset_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError, "Unknown quality preset"
        ):
            resolve_quality("ultra")

    def test_invalid_numeric_values_are_rejected(self):
        invalid_values = (
            0,
            -0.1,
            math.nan,
            math.inf,
            -math.inf,
        )

        for value in invalid_values:
            with self.subTest(option="resolution", value=value):
                with self.assertRaises(ValueError):
                    resolve_quality(resolution=value)

            with self.subTest(option="grid_spacing", value=value):
                with self.assertRaises(ValueError):
                    resolve_quality(grid_spacing=value)
    def test_scene_grid_spacing_uses_resolved_quality(self):
        scene = {
            "quality": resolve_quality("high").to_manifest(),
        }

        self.assertEqual(
            scm_grid_spacing_from_scene(scene, fallback=0.15),
            0.10,
        )

    def test_legacy_scene_grid_spacing_uses_fallback(self):
        self.assertEqual(
            scm_grid_spacing_from_scene({}, fallback=0.15),
            0.15,
        )

    def test_malformed_scene_quality_is_rejected(self):
        scene = {
            "quality": {
                "preset": "high",
            },
        }

        with self.assertRaisesRegex(
            ValueError,
            "resolved SCM grid spacing",
        ):
            scm_grid_spacing_from_scene(scene, fallback=0.15)

if __name__ == "__main__":
    unittest.main()
