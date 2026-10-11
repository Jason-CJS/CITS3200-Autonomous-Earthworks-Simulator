"""Visualize tree placement candidates derived from GOOSE trunk labels."""

import argparse
import json
from collections import deque
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


TREE_CROWN_ID = 27
TREE_TRUNK_ID = 28


def find_connected_regions(mask):
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

                for row_offset, column_offset in [
                    (-1, 0),
                    (1, 0),
                    (0, -1),
                    (0, 1),
                ]:

                    neighbour_row = (
                        current_row
                        + row_offset
                    )

                    neighbour_column = (
                        current_column
                        + column_offset
                    )

                    if (
                        0 <= neighbour_row < rows
                        and 0 <= neighbour_column < columns
                        and mask[
                            neighbour_row,
                            neighbour_column,
                        ]
                        and not visited[
                            neighbour_row,
                            neighbour_column,
                        ]
                    ):

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


def get_region_centre(region):
    """Return the average row and column of a region."""

    rows = [
        row
        for row, column in region
    ]

    columns = [
        column
        for row, column in region
    ]

    return (
        float(np.mean(rows)),
        float(np.mean(columns)),
    )


def grid_to_world(
    row,
    column,
    xmin,
    ymax,
    x_spacing,
    y_spacing,
):
    """Convert a GOOSE grid coordinate to world X/Y."""

    x = (
        xmin
        + column * x_spacing
    )

    y = (
        ymax
        - row * y_spacing
    )

    return x, y


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Visualize GOOSE tree placement "
            "candidates from trunk labels."
        )
    )

    parser.add_argument(
        "scene",
        type=Path,
        help="Path to scene.json",
    )

    args = parser.parse_args()

    scene_path = (
        args.scene
        .expanduser()
        .resolve()
    )

    scene_directory = (
        scene_path.parent
    )

    with scene_path.open(
        encoding="utf-8"
    ) as source:
        scene = json.load(source)

    fine = np.load(
        scene_directory
        / "semantic_fine.npy"
    )

    trunk_mask = (
        fine == TREE_TRUNK_ID
    )

    crown_mask = (
        fine == TREE_CROWN_ID
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

    tree_positions = []

    for region in regions:

        centre_row, centre_column = (
            get_region_centre(region)
        )

        x, y = grid_to_world(
            centre_row,
            centre_column,
            xmin,
            ymax,
            x_spacing,
            y_spacing,
        )

        tree_positions.append(
            (
                x,
                y,
                len(region),
            )
        )

    vegetation_image = np.zeros(
        fine.shape,
        dtype=np.uint8,
    )

    vegetation_image[
        crown_mask
    ] = 1

    vegetation_image[
        trunk_mask
    ] = 2

    extent = [
        xmin,
        xmin + fine.shape[1] * x_spacing,
        ymax - fine.shape[0] * y_spacing,
        ymax,
    ]

    plt.figure(
        figsize=(10, 10)
    )

    plt.imshow(
        vegetation_image,
        origin="upper",
        extent=extent,
        interpolation="nearest",
    )

    tree_x = [
        position[0]
        for position in tree_positions
    ]

    tree_y = [
        position[1]
        for position in tree_positions
    ]

    plt.scatter(
        tree_x,
        tree_y,
        marker="x",
        s=100,
        label="Tree placement candidate",
    )

    for index, (
        x,
        y,
        region_size,
    ) in enumerate(
        tree_positions,
        start=1,
    ):

        plt.text(
            x,
            y,
            str(index),
            fontsize=8,
        )

    plt.xlabel(
        "GOOSE world X (m)"
    )

    plt.ylabel(
        "GOOSE world Y (m)"
    )

    plt.title(
        "GOOSE trunk-derived tree placements"
    )

    plt.legend()

    plt.tight_layout()

    print(
        f"Tree trunk cells: "
        f"{np.sum(trunk_mask)}"
    )

    print(
        f"Connected trunk regions: "
        f"{len(regions)}"
    )

    print()

    print(
        "Tree placement candidates:"
    )

    for index, (
        x,
        y,
        region_size,
    ) in enumerate(
        tree_positions,
        start=1,
    ):

        print(
            f"  Tree {index:>2}: "
            f"({x:6.2f}, {y:6.2f}) "
            f"from {region_size} trunk cells"
        )

    plt.show()


if __name__ == "__main__":
    main()

