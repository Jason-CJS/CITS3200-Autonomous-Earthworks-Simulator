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
    coarse_labels: np.ndarray | None = None
    coarse_names: dict[int, str] | None = None
    unobserved_id: int | None = None
    coarse_map_path: Path | None = None
    legend_path: Path | None = None
    coarse_taxonomy: str | None = None

    @classmethod
    def load(cls, path: Path) -> "SceneGrid":
        path = path.expanduser().resolve()
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict) or metadata.get("format_version") not in (1, 2):
            raise ValueError(f"{path}: expected a version 1 or 2 GOOSE scene manifest")

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

        if metadata["format_version"] == 1:
            return cls(path, metadata, heights, size_x, size_y)

        try:
            coarse_output = metadata["outputs"]["semantic_coarse"]
            legend_output = metadata["outputs"]["semantic_legend"]
            coarse_path = path.parent / coarse_output["path"]
            legend_path = path.parent / legend_output["path"]
            if not coarse_path.is_file() or not legend_path.is_file():
                raise FileNotFoundError("semantic_coarse.npy or semantic_legend.json is missing")
            coarse_labels = np.load(coarse_path, allow_pickle=False)
            legend = json.loads(legend_path.read_text(encoding="utf-8"))
            taxonomy = legend["coarse_taxonomy"]
            unobserved = int(taxonomy["unobserved_id"])
            categories = taxonomy["categories"]
            names = {int(category["id"]): category["name"] for category in categories}
            if (
                coarse_labels.shape != heights.shape
                or coarse_labels.dtype != np.uint8
                or coarse_output["shape"] != list(heights.shape)
                or coarse_output["dtype"] != "uint8"
            ):
                raise ValueError("semantic_coarse.npy has the wrong shape or dtype")
            if (
                not names or len(names) != len(categories)
                or any(not isinstance(name, str) or not name for name in names.values())
                or unobserved in names
                or not set(map(int, np.unique(coarse_labels))) <= (set(names) | {unobserved})
                or legend["grid_alignment"]["aligned_to"] != height_grid.name
                or legend["grid_alignment"]["row_zero"] != grid["row_zero"]
                or legend["grid_alignment"]["column_zero"] != grid["column_zero"]
                or metadata["semantics"]["coarse_taxonomy"]["unobserved_id"] != unobserved
            ):
                raise ValueError("semantic map and legend disagree with the scene grid")
            taxonomy_name = taxonomy["name"]
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ValueError(f"{path}: invalid version 2 semantic outputs: {exc}") from exc
        return cls(path, metadata, heights, size_x, size_y, coarse_labels,
                   names, unobserved, coarse_path.resolve(), legend_path.resolve(),
                   taxonomy_name)

    def coarse_class_at(self, x: float, y: float) -> str:
        """Class beneath the measured chassis XY; unlabelled cells stay explicit."""
        if self.coarse_labels is None:
            return ""  # Version 1 scenes have no semantic map.
        if not all(map(math.isfinite, (x, y))):
            return "unobserved"
        if abs(x) > self.size_x / 2 or abs(y) > self.size_y / 2:
            return "unobserved"
        col = math.floor((x + self.size_x / 2) * (self.heights.shape[1] - 1)
                         / self.size_x + 0.5)
        row = math.floor((self.size_y / 2 - y) * (self.heights.shape[0] - 1)
                         / self.size_y + 0.5)
        category = int(self.coarse_labels[row, col])
        if category == self.unobserved_id:
            return "unobserved"
        return self.coarse_names[category]

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
        self.validate_start(start_x, start_y)
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

    def validate_start(self, start_x: float, start_y: float) -> None:
        """Keep the starting vehicle footprint within the terrain."""
        if not all(map(math.isfinite, (start_x, start_y))):
            raise ValueError("start coordinates must be finite")
        if (
            abs(start_x) > self.size_x / 2 - VEHICLE_MARGIN_M
            or abs(start_y) > self.size_y / 2 - VEHICLE_MARGIN_M
        ):
            raise ValueError("bulldozer starting footprint leaves the generated terrain")


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


def write_trajectory(samples: list[TrajectorySample], path: Path, scene: SceneGrid) -> None:
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
                scene.coarse_class_at(sample.x_m, sample.y_m),
            ))


def write_route_overlay(scene: SceneGrid, samples: list[TrajectorySample], path: Path) -> None:
    """Show the measured route over semantic classes, or heights for v1 scenes."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(8, 7))
    half_cell_x = scene.size_x / (scene.heights.shape[1] - 1) / 2
    half_cell_y = scene.size_y / (scene.heights.shape[0] - 1) / 2
    extent = (-scene.size_x / 2 - half_cell_x, scene.size_x / 2 + half_cell_x,
              -scene.size_y / 2 - half_cell_y, scene.size_y / 2 + half_cell_y)
    if scene.coarse_labels is None:
        image = axes.imshow(scene.heights, extent=extent, origin="upper", cmap="terrain")
        figure.colorbar(image, ax=axes, label="Initial terrain height (m)")
    else:
        from matplotlib.colors import BoundaryNorm, ListedColormap

        present = sorted(set(map(int, np.unique(scene.coarse_labels))) - {scene.unobserved_id})
        names = [scene.coarse_names[category] for category in present] + ["unobserved"]
        unobserved_index = len(present)
        indices = np.full(scene.coarse_labels.shape, unobserved_index, dtype=np.uint8)
        for index, category in enumerate(present):
            indices[scene.coarse_labels == category] = index
        colors = [plt.get_cmap("tab20")(index) for index in range(len(present))]
        colors.append("lightgray")
        cmap = ListedColormap(colors)
        norm = BoundaryNorm(np.arange(len(names) + 1) - 0.5, cmap.N)
        image = axes.imshow(indices, extent=extent, origin="upper", cmap=cmap, norm=norm)
        figure.colorbar(image, ax=axes, ticks=range(len(names)), label="Coarse semantic class")
        image.colorbar.ax.set_yticklabels(names)
    axes.plot([sample.x_m for sample in samples], [sample.y_m for sample in samples],
              color="crimson", linewidth=2, label="Bulldozer route")
    axes.scatter(samples[0].x_m, samples[0].y_m, color="lime", edgecolors="black",
                 s=75, zorder=3, label="Start")
    axes.scatter(samples[-1].x_m, samples[-1].y_m, color="dodgerblue", edgecolors="black",
                 s=75, zorder=3, label="End")
    axes.set(xlabel="Chrono X (m)", ylabel="Chrono Y (m)", title="GOOSE-Ex bulldozer traversal")
    axes.set_xlim(-scene.size_x / 2, scene.size_x / 2)
    axes.set_ylim(-scene.size_y / 2, scene.size_y / 2)
    axes.set_aspect("equal")
    axes.legend(loc="best")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
