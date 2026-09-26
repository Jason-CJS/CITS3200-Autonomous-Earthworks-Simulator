"""Scene coordinates, route validation, and portable traversal outputs.

This module deliberately does not import PyChrono, so scene and export checks
can run on machines that cannot render the simulation.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import math
from pathlib import Path

import numpy as np


VEHICLE_MARGIN_M = 1.8


@dataclass(frozen=True)
class SceneGrid:
    path: Path
    metadata: dict
    heights: np.ndarray
    size_x: float
    size_y: float

    @classmethod
    def load(cls, path: Path) -> "SceneGrid":
        path = path.expanduser().resolve()
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict) or metadata.get("format_version") != 1:
            raise ValueError(f"{path}: expected a version 1 GOOSE scene manifest")

        try:
            size_x, size_y = float(metadata["size_x"]), float(metadata["size_y"])
            grid = metadata["grid"]
            bounds = metadata["bounds_xy"]
            width, height = int(grid["width"]), int(grid["height"])
            heightmap = path.parent / metadata["heightmap"]
            height_grid = path.parent / metadata["height_grid"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path}: incomplete GOOSE scene manifest: {exc}") from exc

        if not math.isfinite(size_x) or not math.isfinite(size_y) or min(size_x, size_y) <= 0:
            raise ValueError(f"{path}: scene dimensions must be positive and finite")
        if width < 2 or height < 2:
            raise ValueError(f"{path}: height grid must have at least two rows and columns")
        if grid.get("row_zero") != "ymax" or grid.get("column_zero") != "xmin":
            raise ValueError(f"{path}: unsupported height-grid orientation")
        try:
            xmin, xmax = float(bounds["xmin"]), float(bounds["xmax"])
            ymin, ymax = float(bounds["ymin"]), float(bounds["ymax"])
            x_spacing = float(grid["x_spacing"])
            y_spacing = float(grid["y_spacing"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path}: incomplete grid coordinates: {exc}") from exc
        if not all(map(math.isfinite, (xmin, xmax, ymin, ymax, x_spacing, y_spacing))):
            raise ValueError(f"{path}: grid coordinates must be finite")
        if not (
            math.isclose(xmax - xmin, size_x, abs_tol=1e-6)
            and math.isclose(ymax - ymin, size_y, abs_tol=1e-6)
            and math.isclose(x_spacing * (width - 1), size_x, abs_tol=1e-5)
            and math.isclose(y_spacing * (height - 1), size_y, abs_tol=1e-5)
        ):
            raise ValueError(f"{path}: grid spacing and bounds disagree with scene dimensions")
        if not heightmap.is_file() or not height_grid.is_file():
            raise FileNotFoundError(f"{path}: heightmap.bmp or height_grid.npy is missing")

        heights = np.load(height_grid, allow_pickle=False)
        if heights.shape != (height, width) or not np.isfinite(heights).all():
            raise ValueError(f"{path}: height_grid.npy has the wrong shape or non-finite heights")
        return cls(path, metadata, heights, size_x, size_y)

    def height_at(self, x: float, y: float) -> float:
        """Bilinear terrain height in Chrono's centred XY coordinates."""
        if not all(map(math.isfinite, (x, y))):
            raise ValueError("start position must be finite")
        if abs(x) > self.size_x / 2 or abs(y) > self.size_y / 2:
            raise ValueError("start position is outside the generated terrain")
        col = (x + self.size_x / 2) * (self.heights.shape[1] - 1) / self.size_x
        row = (self.size_y / 2 - y) * (self.heights.shape[0] - 1) / self.size_y
        c0, r0 = int(math.floor(col)), int(math.floor(row))
        c1 = min(c0 + 1, self.heights.shape[1] - 1)
        r1 = min(r0 + 1, self.heights.shape[0] - 1)
        dc, dr = col - c0, row - r0
        return float(
            (1 - dr) * ((1 - dc) * self.heights[r0, c0] + dc * self.heights[r0, c1])
            + dr * ((1 - dc) * self.heights[r1, c0] + dc * self.heights[r1, c1])
        )

    def validate_route(self, start_x: float, start_y: float, speed: float, duration: float) -> None:
        """Keep the bulldozer and its blade within the rectangular terrain."""
        if not all(map(math.isfinite, (start_x, start_y, speed, duration))):
            raise ValueError("start coordinates, speed, and duration must be finite")
        if speed <= 0 or duration <= 0:
            raise ValueError("speed and duration must be greater than zero")
        end_x = start_x - speed * duration  # Positive B10 track speeds face negative X.
        if not (
            -self.size_x / 2 + VEHICLE_MARGIN_M <= min(start_x, end_x)
            and max(start_x, end_x) <= self.size_x / 2 - VEHICLE_MARGIN_M
            and abs(start_y) <= self.size_y / 2 - VEHICLE_MARGIN_M
        ):
            raise ValueError(
                "scripted route or bulldozer footprint leaves the generated terrain; "
                "adjust --start-x, --start-y, --speed, or --duration"
            )


def exact_steps(duration: float, step: float, name: str) -> int:
    """Require fixed-step durations, so exported sample times are repeatable."""
    if not math.isfinite(duration) or not math.isfinite(step) or duration <= 0 or step <= 0:
        raise ValueError(f"{name} and time step must be positive and finite")
    steps = round(duration / step)
    if steps < 1 or not math.isclose(steps * step, duration, abs_tol=1e-8):
        raise ValueError(f"{name} must be a positive multiple of the simulation time step")
    return steps


@dataclass(frozen=True)
class TrajectorySample:
    time_s: float
    x_m: float
    y_m: float
    z_m: float
    yaw_rad: float


def write_trajectory(samples: list[TrajectorySample], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("time_s", "x_m", "y_m", "z_m", "yaw_rad", "coarse_semantic_class"))
        for sample in samples:
            writer.writerow((
                f"{sample.time_s:.6f}",
                f"{sample.x_m:.6f}",
                f"{sample.y_m:.6f}",
                f"{sample.z_m:.6f}",
                f"{sample.yaw_rad:.6f}",
                "",  # Populated when Issue #22 defines the coarse label-map format.
            ))


def write_route_overlay(scene: SceneGrid, samples: list[TrajectorySample], path: Path) -> None:
    """Show the measured route over the existing terrain height grid."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(8, 7))
    image = axes.imshow(
        scene.heights,
        extent=(-scene.size_x / 2, scene.size_x / 2, -scene.size_y / 2, scene.size_y / 2),
        origin="upper",
        cmap="terrain",
    )
    axes.plot([sample.x_m for sample in samples], [sample.y_m for sample in samples],
              color="crimson", linewidth=2, label="Bulldozer route")
    axes.scatter(samples[0].x_m, samples[0].y_m, color="lime", edgecolors="black",
                 s=75, zorder=3, label="Start")
    axes.scatter(samples[-1].x_m, samples[-1].y_m, color="dodgerblue", edgecolors="black",
                 s=75, zorder=3, label="End")
    axes.set(xlabel="Chrono X (m)", ylabel="Chrono Y (m)", title="GOOSE-Ex bulldozer traversal")
    axes.set_aspect("equal")
    axes.legend(loc="best")
    figure.colorbar(image, ax=axes, label="Initial terrain height (m)")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
