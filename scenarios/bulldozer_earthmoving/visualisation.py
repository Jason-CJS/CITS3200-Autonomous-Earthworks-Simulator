"""Before-and-after terrain visualisation for the hole-filling scenario."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

from scenarios.bulldozer_earthmoving.terrain_profile import (
    GridPoint,
    TerrainProfile,
)


def grid_to_array(
    profile: TerrainProfile,
    grid: Mapping[GridPoint, float],
) -> np.ndarray:
    """Convert the SCM coordinate dictionary into a plot-ready array."""

    geometry = profile.geometry
    half_x = (geometry.node_count_x - 1) // 2
    half_y = (geometry.node_count_y - 1) // 2
    result = np.empty(
        (geometry.node_count_y, geometry.node_count_x),
        dtype=float,
    )

    for row, grid_y in enumerate(range(-half_y, half_y + 1)):
        for column, grid_x in enumerate(range(-half_x, half_x + 1)):
            point = (grid_x, grid_y)
            if point not in grid:
                raise ValueError(f"Terrain grid is missing node {point}")
            result[row, column] = grid[point]

    return result


def write_terrain_comparison(
    profile: TerrainProfile,
    initial_grid: Mapping[GridPoint, float],
    final_grid: Mapping[GridPoint, float],
    hole_metrics: Mapping[str, float | int],
    output_path: str | Path,
) -> Path:
    """Write initial, final, and difference terrain plots to one PNG."""

    initial = grid_to_array(profile, initial_grid)
    final = grid_to_array(profile, final_grid)
    difference_mm = (final - initial) * 1000.0

    shared_minimum = float(min(initial.min(), final.min()))
    shared_maximum = float(max(initial.max(), final.max()))
    if math.isclose(shared_minimum, shared_maximum):
        shared_maximum = shared_minimum + 1e-9

    measured_increase_mm = abs(
        float(hole_metrics["average_height_increase_m"]) * 1000.0
    )
    difference_limit = max(
        25.0,
        min(75.0, measured_increase_mm * 2.0),
    )

    geometry = profile.geometry
    half_x = (geometry.node_count_x - 1) // 2
    half_y = (geometry.node_count_y - 1) // 2
    extent = (
        -half_x * geometry.actual_spacing_m,
        half_x * geometry.actual_spacing_m,
        -half_y * geometry.actual_spacing_m,
        half_y * geometry.actual_spacing_m,
    )
    action_xlim = (-3.5, 1.5)
    action_ylim = (-2.5, 1.8)

    figure, axes = plt.subplots(
        1,
        3,
        figsize=(16, 5.5),
        constrained_layout=True,
    )

    for axis, data, title in (
        (axes[0], initial, "Before"),
        (axes[1], final, "After"),
    ):
        image = axis.imshow(
            data,
            origin="lower",
            extent=extent,
            cmap="terrain",
            vmin=shared_minimum,
            vmax=shared_maximum,
            interpolation="nearest",
        )
        axis.add_patch(
            Circle(
                (
                    profile.hole_center_x_m,
                    profile.hole_center_y_m,
                ),
                profile.hole_radius_m,
                fill=False,
                edgecolor="white",
                linewidth=2.0,
                linestyle="--",
            )
        )
        axis.set_title(title)
        axis.set_xlabel("Terrain X (m)")
        axis.set_ylabel("Terrain Y (m)")
        axis.set_aspect("equal")
        axis.set_xlim(*action_xlim)
        axis.set_ylim(*action_ylim)
        figure.colorbar(
            image,
            ax=axis,
            label="Terrain height (m)",
            shrink=0.82,
        )

    difference_image = axes[2].imshow(
        difference_mm,
        origin="lower",
        extent=extent,
        cmap="RdBu_r",
        vmin=-difference_limit,
        vmax=difference_limit,
        interpolation="nearest",
    )
    axes[2].add_patch(
        Circle(
            (
                profile.hole_center_x_m,
                profile.hole_center_y_m,
            ),
            profile.hole_radius_m,
            fill=False,
            edgecolor="black",
            linewidth=2.0,
            linestyle="--",
        )
    )
    axes[2].set_title(
        f"Height change (±{difference_limit:.0f} mm scale)"
    )
    axes[2].set_xlabel("Terrain X (m)")
    axes[2].set_ylabel("Terrain Y (m)")
    axes[2].set_aspect("equal")
    axes[2].set_xlim(*action_xlim)
    axes[2].set_ylim(*action_ylim)
    axes[2].annotate(
        f"Target average\n+{measured_increase_mm:.2f} mm",
        xy=(
            profile.hole_center_x_m,
            profile.hole_center_y_m,
        ),
        xytext=(0.72, 0.10),
        textcoords="axes fraction",
        ha="center",
        arrowprops={
            "arrowstyle": "->",
            "color": "black",
            "linewidth": 1.5,
        },
        bbox={
            "boxstyle": "round,pad=0.3",
            "facecolor": "white",
            "alpha": 0.9,
        },
    )
    figure.colorbar(
        difference_image,
        ax=axes[2],
        label="Height change (mm)",
        shrink=0.82,
    )

    initial_average_mm = (
        float(hole_metrics["initial_average_height_m"]) * 1000.0
    )
    final_average_mm = (
        float(hole_metrics["final_average_height_m"]) * 1000.0
    )
    increase_mm = (
        float(hole_metrics["average_height_increase_m"]) * 1000.0
    )

    figure.suptitle(
        "Scripted bulldozer hole-filling result\n"
        f"Average target height: {initial_average_mm:.2f} mm "
        f"to {final_average_mm:.2f} mm "
        f"({increase_mm:+.2f} mm)",
        fontsize=14,
        fontweight="bold",
    )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return path