"""GOOSE tree placement extraction from fine semantic labels.

Individual tree placement candidates are derived from connected
regions of cells labelled as tree_trunk in semantic_fine.npy.

Each connected trunk region produces one tree placement candidate.
The final anchor is an actual trunk-labelled cell nearest to the
geometric centre of the region.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np


TREE_TRUNK_NAME = "tree_trunk"


def load_fine_semantic_map(
    scene_directory: Path,
) -> np.ndarray:
    """Load semantic_fine.npy."""

    path = (
        Path(scene_directory)
        / "semantic_fine.npy"
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"Fine semantic map not found: {path}"
        )

    return np.load(path)


def load_height_grid(
    scene_directory: Path,
) -> np.ndarray:
    """Load height_grid.npy."""

    path = (
        Path(scene_directory)
        / "height_grid.npy"
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"Height grid not found: {path}"
        )

    return np.load(path)


def load_semantic_legend(
    scene_directory: Path,
) -> dict:
    """Load semantic_legend.json."""

    path = (
        Path(scene_directory)
        / "semantic_legend.json"
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"Semantic legend not found: {path}"
        )

    with path.open(
        encoding="utf-8"
    ) as source:
        return json.load(source)


def find_class_id(
    legend: dict,
    class_name: str,
) -> int:
    """Find a fine semantic class ID by name."""

    for semantic_class in legend["classes"]:

        if (
            semantic_class["name"].lower()
            == class_name.lower()
        ):
            return int(
                semantic_class["id"]
            )

    raise ValueError(
        f"Semantic class '{class_name}' "
        f"was not found in the legend."
    )


def find_connected_regions(
    mask: np.ndarray,
) -> list[list[tuple[int, int]]]:
    """Find 4-neighbour connected regions in a boolean mask."""

    visited = np.zeros(
        mask.shape,
        dtype=bool,
    )

    regions = []

    rows, columns = mask.shape

    for row in range(rows):

        for column in range(columns):

            if (
                not mask[row, column]
                or visited[row, column]
            ):
                continue

            queue = deque(
                [(row, column)]
            )

            visited[
                row,
                column,
            ] = True

            region = []

            while queue:

                current_row, current_column = (
                    queue.popleft()
                )

                region.append(
                    (
                        current_row,
                        current_column,
                    )
                )

                neighbours = [
                    (
                        current_row - 1,
                        current_column,
                    ),
                    (
                        current_row + 1,
                        current_column,
                    ),
                    (
                        current_row,
                        current_column - 1,
                    ),
                    (
                        current_row,
                        current_column + 1,
                    ),
                ]

                for (
                    neighbour_row,
                    neighbour_column,
                ) in neighbours:

                    if not (
                        0
                        <= neighbour_row
                        < rows
                    ):
                        continue

                    if not (
                        0
                        <= neighbour_column
                        < columns
                    ):
                        continue

                    if not mask[
                        neighbour_row,
                        neighbour_column,
                    ]:
                        continue

                    if visited[
                        neighbour_row,
                        neighbour_column,
                    ]:
                        continue

                    visited[
                        neighbour_row,
                        neighbour_column,
                    ] = True

                    queue.append(
                        (
                            neighbour_row,
                            neighbour_column,
                        )
                    )

            regions.append(region)

    return regions


def choose_anchor_cell(
    region: list[tuple[int, int]],
) -> tuple[int, int]:
    """Choose the region cell nearest its geometric centre."""

    coordinates = np.asarray(
        region,
        dtype=float,
    )

    centre = np.mean(
        coordinates,
        axis=0,
    )

    squared_distances = np.sum(
        (
            coordinates
            - centre
        )
        ** 2,
        axis=1,
    )

    closest_index = int(
        np.argmin(
            squared_distances
        )
    )

    row, column = region[
        closest_index
    ]

    return int(row), int(column)


def grid_to_world(
    row: int,
    column: int,
    height_grid: np.ndarray,
    xmin: float,
    ymax: float,
    x_spacing: float,
    y_spacing: float,
) -> tuple[float, float, float]:
    """Convert a grid cell to GOOSE world X/Y/Z."""

    x = (
        xmin
        + column * x_spacing
    )

    y = (
        ymax
        - row * y_spacing
    )

    z = float(
        height_grid[
            row,
            column,
        ]
    )

    return (
        float(x),
        float(y),
        z,
    )


def generate_tree_placements(
    scene_path: Path,
) -> list[dict]:
    """Generate one tree candidate for each trunk region."""

    scene_path = (
        Path(scene_path)
        .expanduser()
        .resolve()
    )

    if not scene_path.is_file():
        raise FileNotFoundError(
            f"Scene manifest not found: "
            f"{scene_path}"
        )

    scene_directory = (
        scene_path.parent
    )

    with scene_path.open(
        encoding="utf-8"
    ) as source:
        scene = json.load(source)

    fine_map = load_fine_semantic_map(
        scene_directory
    )

    height_grid = load_height_grid(
        scene_directory
    )

    if (
        fine_map.shape
        != height_grid.shape
    ):
        raise ValueError(
            "Fine semantic map and height grid "
            "do not have matching shapes."
        )

    legend = load_semantic_legend(
        scene_directory
    )

    trunk_class = find_class_id(
        legend,
        TREE_TRUNK_NAME,
    )

    trunk_mask = (
        fine_map == trunk_class
    )

    regions = find_connected_regions(
        trunk_mask
    )

    grid = scene["grid"]

    xmin = float(
        scene["bounds_xy"]["xmin"]
    )

    ymax = float(
        scene["bounds_xy"]["ymax"]
    )

    x_spacing = float(
        grid["x_spacing"]
    )

    y_spacing = float(
        grid["y_spacing"]
    )

    placements = []

    for index, region in enumerate(
        regions,
        start=1,
    ):

        row, column = (
            choose_anchor_cell(
                region
            )
        )

        x, y, z = grid_to_world(
            row=row,
            column=column,
            height_grid=height_grid,
            xmin=xmin,
            ymax=ymax,
            x_spacing=x_spacing,
            y_spacing=y_spacing,
        )

        placements.append(
            {
                "tree_id": index,
                "row": row,
                "column": column,
                "x": x,
                "y": y,
                "z": z,
                "source": TREE_TRUNK_NAME,
                "region_size": len(region),
            }
        )

    return placements
