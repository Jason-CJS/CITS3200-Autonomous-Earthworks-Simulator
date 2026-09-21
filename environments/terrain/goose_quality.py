"""Resolve reproducible performance and quality settings for GOOSE terrain."""

from __future__ import annotations

import math
from dataclasses import dataclass


DEFAULT_QUALITY_PRESET = "balanced"

QUALITY_PRESETS = {
    "low": {
        "terrain_resolution": 0.30,
        "scm_grid_spacing": 0.30,
    },
    "balanced": {
        "terrain_resolution": 0.15,
        "scm_grid_spacing": 0.15,
    },
    "high": {
        "terrain_resolution": 0.10,
        "scm_grid_spacing": 0.10,
    },
}

QUALITY_PRESET_NAMES = tuple(QUALITY_PRESETS)


@dataclass(frozen=True)
class ResolvedQuality:
    """A selected preset after applying and validating explicit overrides."""

    preset: str
    terrain_resolution: float
    scm_grid_spacing: float
    overrides: tuple[str, ...] = ()

    def to_manifest(self) -> dict:
        resolved = {
            "terrain_resolution": self.terrain_resolution,
            "scm_grid_spacing": self.scm_grid_spacing,
        }
        return {
            "preset": self.preset,
            "resolved": resolved,
            "overrides": {
                name: resolved[name]
                for name in self.overrides
            },
        }


def _positive_finite(value: float, option_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{option_name} must be a finite number greater than zero"
        ) from None

    if not math.isfinite(number) or number <= 0:
        raise ValueError(
            f"{option_name} must be a finite number greater than zero"
        )
    return number


def resolve_quality(
    preset: str = DEFAULT_QUALITY_PRESET,
    resolution: float | None = None,
    grid_spacing: float | None = None,
) -> ResolvedQuality:
    """Resolve one preset with optional per-setting overrides."""

    if preset not in QUALITY_PRESETS:
        choices = ", ".join(QUALITY_PRESET_NAMES)
        raise ValueError(
            f"Unknown quality preset {preset!r}; choose one of: {choices}"
        )

    preset_values = QUALITY_PRESETS[preset]
    terrain_resolution = float(preset_values["terrain_resolution"])
    scm_grid_spacing = float(preset_values["scm_grid_spacing"])
    overrides: list[str] = []

    if resolution is not None:
        terrain_resolution = _positive_finite(resolution, "--resolution")
        overrides.append("terrain_resolution")

    if grid_spacing is not None:
        scm_grid_spacing = _positive_finite(
            grid_spacing, "--grid-spacing"
        )
        overrides.append("scm_grid_spacing")

    return ResolvedQuality(
        preset=preset,
        terrain_resolution=terrain_resolution,
        scm_grid_spacing=scm_grid_spacing,
        overrides=tuple(overrides),
    )
