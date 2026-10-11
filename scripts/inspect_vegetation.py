"""Visualise GOOSE vegetation labels and placement candidates."""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# Allow this script to import modules from the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(REPO_ROOT),
    )


from environments.vegetation.goose_vegetation import (
    generate_vegetation_placements,
    load_semantic_legend,
)


def load_scene_data(scene_path):
    """Load data required for vegetation visualisation."""

    scene_path = Path(scene_path)

    with scene_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        scene = json.load(file)

    semantic_path = (
        scene_path.parent
        / scene["outputs"]["semantic_coarse"]["path"]
    )

    legend_path = (
        scene_path.parent
        / scene["outputs"]["semantic_legend"]["path"]
    )

    height_grid_path = (
        scene_path.parent
        / scene["outputs"]["height_grid"]["path"]
    )

    semantic_map = np.load(
        semantic_path
    )

    height_grid = np.load(
        height_grid_path
    )

    vegetation_class = (
        load_semantic_legend(
            legend_path
        )
    )

    return (
        scene,
        semantic_map,
        height_grid,
        vegetation_class,
    )


def main():
    """Visualise vegetation labels and placement candidates."""

    parser = argparse.ArgumentParser(
        description=(
            "Visualise GOOSE vegetation labels "
            "and generated vegetation placements."
        )
    )

    parser.add_argument(
        "scene",
        type=Path,
        help="Path to generated scene.json",
    )

    parser.add_argument(
        "--spacing",
        type=float,
        default=3.0,
        help=(
            "Approximate vegetation placement "
            "spacing in metres (default: 3.0)."
        ),
    )

    args = parser.parse_args()

    (
        scene,
        semantic_map,
        height_grid,
        vegetation_class,
    ) = load_scene_data(
        args.scene
    )

    vegetation_mask = (
        semantic_map
        == vegetation_class
    )

    vegetation_cells = int(
        np.count_nonzero(
            vegetation_mask
        )
    )

    total_cells = int(
        semantic_map.size
    )

    vegetation_percentage = (
        vegetation_cells
        / total_cells
        * 100
    )

    bounds = scene[
        "bounds_xy"
    ]

    grid = scene[
        "grid"
    ]

    xmin = float(
        bounds["xmin"]
    )

    xmax = float(
        bounds["xmax"]
    )

    ymin = float(
        bounds["ymin"]
    )

    ymax = float(
        bounds["ymax"]
    )

    x_spacing = float(
        grid["x_spacing"]
    )

    y_spacing = float(
        grid["y_spacing"]
    )

    placements = (
        generate_vegetation_placements(
            semantic_map,
            height_grid,
            vegetation_class,
            x_spacing,
            y_spacing,
            xmin,
            ymax,
            args.spacing,
        )
    )

    print(
        f"Grid size: "
        f"{semantic_map.shape[1]} x "
        f"{semantic_map.shape[0]}"
    )

    print(
        f"Vegetation cells: "
        f"{vegetation_cells}"
    )

    print(
        f"Vegetation coverage: "
        f"{vegetation_percentage:.1f}%"
    )

    print(
        f"Placement spacing: "
        f"{args.spacing:.2f} m"
    )

    print(
        f"Placement candidates: "
        f"{len(placements)}"
    )

    extent = [
        xmin,
        xmax,
        ymin,
        ymax,
    ]

    plt.figure(
        figsize=(8, 8)
    )

    plt.imshow(
        vegetation_mask,
        origin="upper",
        extent=extent,
    )

    if placements:

        placement_x = [
            placement["x"]
            for placement in placements
        ]

        placement_y = [
            placement["y"]
            for placement in placements
        ]

        plt.scatter(
            placement_x,
            placement_y,
            marker="x",
            s=35,
            label="Vegetation placement",
        )

        plt.legend()

    plt.xlabel(
        "World X (m)"
    )

    plt.ylabel(
        "World Y (m)"
    )

    plt.title(
        "GOOSE-Ex Label-Derived "
        "Vegetation Placements"
    )

    plt.xlim(
        xmin,
        xmax,
    )

    plt.ylim(
        ymin,
        ymax,
    )

    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    main()
