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
class VehicleFootprint:
    """Conservative horizontal bounds relative to the chassis at heading zero."""

    negative_x_m: float
    positive_x_m: float
    half_width_m: float
    name: str


BULLDOZER_FOOTPRINT = VehicleFootprint(1.8, 1.8, 1.8, "bulldozer")
# Includes the raised traversal boom/bucket, track shoes and a small margin.
# Articulating/swinging in manual mode can extend beyond these initial bounds.
EXCAVATOR_FOOTPRINT = VehicleFootprint(2.0, 5.5, 1.7, "excavator")


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

    def validate_route(
        self, start_x: float, start_y: float, speed: float, duration: float,
        *, footprint: VehicleFootprint = BULLDOZER_FOOTPRINT, direction: int = -1,
    ) -> None:
        """Keep the selected vehicle's straight route inside the terrain."""
        if not all(map(math.isfinite, (start_x, start_y, speed, duration))):
            raise ValueError("start coordinates, speed, and duration must be finite")
        if speed <= 0 or duration <= 0:
            raise ValueError("speed and duration must be greater than zero")
        if direction not in (-1, 1):
            raise ValueError("scripted direction must be -1 or 1")
        self.validate_start(start_x, start_y, footprint=footprint)
        end_x = start_x + direction * speed * duration
        if not (
            -self.size_x / 2 + footprint.negative_x_m <= min(start_x, end_x)
            and max(start_x, end_x) <= self.size_x / 2 - footprint.positive_x_m
            and abs(start_y) <= self.size_y / 2 - footprint.half_width_m
        ):
            raise ValueError(
                f"scripted route or {footprint.name} footprint leaves the generated terrain; "
                "adjust --start-x, --start-y, --speed, or --duration"
            )

    def validate_start(
        self, start_x: float, start_y: float,
        *, footprint: VehicleFootprint = BULLDOZER_FOOTPRINT,
    ) -> None:
        """Keep the starting vehicle footprint within the terrain."""
        if not all(map(math.isfinite, (start_x, start_y))):
            raise ValueError("start coordinates must be finite")
        if (
            start_x < -self.size_x / 2 + footprint.negative_x_m
            or start_x > self.size_x / 2 - footprint.positive_x_m
            or abs(start_y) > self.size_y / 2 - footprint.half_width_m
        ):
            raise ValueError(f"{footprint.name} starting footprint leaves the generated terrain")


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


# Natural ground colours for the coarse GOOSE classes. Anything else, including
# unobserved cells, is drawn as bare soil because the converter treats it as ground.
TERRAIN_COLOURS = {
    "vegetation": (0.36, 0.48, 0.22),
    "terrain": (0.55, 0.42, 0.28),
    "road": (0.46, 0.45, 0.43),
    "structure": (0.55, 0.54, 0.52),
    "water": (0.30, 0.36, 0.38),
}
SOIL_COLOUR = (0.56, 0.47, 0.34)


def write_terrain_texture(scene: SceneGrid, path: Path, size: int = 1024) -> None:
    """Save a display texture for the SCM mesh: semantic colours, hillshade and grain.

    ``size`` must be a multiple of 32 so every grain octave fills the image.

    The image's top row is the scene's ymax edge, matching the height grid;
    Chrono flips the mesh's V coordinate when it hands it to Irrlicht.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.image
    from scipy import ndimage

    rows, cols = scene.heights.shape
    colours = np.empty((rows, cols, 3))
    colours[:] = SOIL_COLOUR
    if scene.coarse_labels is not None:
        for category, name in scene.coarse_names.items():
            if name in TERRAIN_COLOURS:
                colours[scene.coarse_labels == category] = TERRAIN_COLOURS[name]
    # Soften the class edges so the cells do not read as pixels on the ground.
    colours = ndimage.gaussian_filter(colours, sigma=(1.0, 1.0, 0))

    # Light from the north-west (-X, +Y). Rows run towards -Y, so slopes that
    # rise with the column or row index face the light.
    dz_drow, dz_dcol = np.gradient(scene.heights, scene.size_y / (rows - 1),
                                   scene.size_x / (cols - 1))
    shade = np.clip(0.8 + 0.9 * (dz_drow + dz_dcol), 0.5, 1.15)

    zoom = (size / rows, size / cols)
    colours = ndimage.zoom(colours, (*zoom, 1), order=1)
    shade = ndimage.zoom(shade, zoom, order=1)
    # Fixed-seed grain: identical runs produce identical frames.
    rng = np.random.default_rng(0)
    grain = sum(
        ndimage.zoom(rng.standard_normal((size // cell, size // cell)), cell, order=1) * weight
        for cell, weight in ((32, 0.06), (8, 0.05), (2, 0.04))
    )
    image = np.clip(colours * (shade * (1 + grain))[..., None], 0, 1)
    matplotlib.image.imsave(path, image)


def footprint_corners(
    footprint: VehicleFootprint, x: float, y: float, yaw: float,
) -> list[tuple[float, float]]:
    """Footprint rectangle corners in scene XY for a chassis pose."""
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
    local = (
        (-footprint.negative_x_m, -footprint.half_width_m),
        (footprint.positive_x_m, -footprint.half_width_m),
        (footprint.positive_x_m, footprint.half_width_m),
        (-footprint.negative_x_m, footprint.half_width_m),
    )
    return [(x + u * cos_yaw - v * sin_yaw, y + u * sin_yaw + v * cos_yaw) for u, v in local]


def write_soil_change_map(records, spacing: float, path: Path,
                          title: str = "GOOSE-Ex excavator soil change") -> None:
    """Map the height change of every modified SCM node: lowered blue, raised red.

    ``records`` are ``DeformationRecord`` values from the shared deformation
    exporter. Changes under half a millimetre are left blank.
    """
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.colors import TwoSlopeNorm
    import matplotlib.pyplot as plt

    changed = [r for r in records if abs(r.height_change_m) >= 5e-4]
    figure, axes = plt.subplots(figsize=(8, 7))
    if changed:
        xs = np.array([r.world_x_m for r in changed])
        ys = np.array([r.world_y_m for r in changed])
        dz = np.array([r.height_change_m for r in changed])
        cols = np.round((xs - xs.min()) / spacing).astype(int)
        rows = np.round((ys - ys.min()) / spacing).astype(int)
        grid = np.full((rows.max() + 1, cols.max() + 1), np.nan)
        grid[rows, cols] = dz
        limit = max(float(np.abs(dz).max()), 1e-3)
        extent = (xs.min() - spacing / 2, xs.max() + spacing / 2,
                  ys.min() - spacing / 2, ys.max() + spacing / 2)
        image = axes.imshow(grid, origin="lower", extent=extent, cmap="RdBu_r",
                            norm=TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit))
        figure.colorbar(image, ax=axes, label="Height change (m)")
        area = spacing * spacing
        axes.text(0.02, 0.98, f"Lowered: {-dz[dz < 0].sum() * area:.3f} m3\n"
                              f"Raised: {dz[dz > 0].sum() * area:.3f} m3",
                  transform=axes.transAxes, va="top",
                  bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"})
    else:
        axes.text(0.5, 0.5, "No soil changed", ha="center", va="center", transform=axes.transAxes)
    axes.set(xlabel="Chrono X (m)", ylabel="Chrono Y (m)", title=title)
    axes.set_aspect("equal")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_route_overlay(
    scene: SceneGrid, samples: list[TrajectorySample], path: Path,
    vehicle_name: str = "Bulldozer", *, footprint: VehicleFootprint | None = None,
) -> None:
    """Show the measured route over semantic classes, or heights for v1 scenes."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.patheffects as path_effects
    from matplotlib.patches import Polygon
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
    if footprint is not None:
        for sample, color, label in ((samples[0], "lime", "Start footprint"),
                                     (samples[-1], "gold", "End footprint")):
            axes.add_patch(Polygon(
                footprint_corners(footprint, sample.x_m, sample.y_m, sample.yaw_rad),
                closed=True, fill=False, edgecolor=color, linewidth=1.5,
                linestyle="--", zorder=2, label=label,
                path_effects=[path_effects.withStroke(linewidth=3, foreground="black")],
            ))
    # The white halo keeps the route readable over dark semantic classes.
    axes.plot([sample.x_m for sample in samples], [sample.y_m for sample in samples],
              color="crimson", linewidth=2.5, label=f"{vehicle_name} route", zorder=3,
              path_effects=[path_effects.withStroke(linewidth=5, foreground="white")])
    axes.scatter(samples[0].x_m, samples[0].y_m, color="lime", edgecolors="black",
                 s=75, zorder=4, label="Start")
    axes.scatter(samples[-1].x_m, samples[-1].y_m, color="gold", edgecolors="black",
                 s=75, zorder=4, label="End")
    axes.set(xlabel="Chrono X (m)", ylabel="Chrono Y (m)",
             title=f"GOOSE-Ex {vehicle_name.lower()} traversal")
    axes.set_xlim(-scene.size_x / 2, scene.size_x / 2)
    axes.set_ylim(-scene.size_y / 2, scene.size_y / 2)
    axes.set_aspect("equal")
    axes.legend(loc="best")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
