"""GOOSE vegetation placement utilities.

Vegetation placement is derived from the semantic map generated from
GOOSE data rather than from random positions across the terrain.
"""

from pathlib import Path
from collections import deque

import numpy as np


# Temporary coarse vegetation class.
# Later this can be loaded from semantic_legend.json.
VEGETATION_CLASS = 1


def load_semantic_map(path):
    """Load a GOOSE coarse semantic map."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Semantic map not found: {path}\n"
            "Generate the GOOSE semantic outputs before running "
            "vegetation placement."
        )

    semantic_map = np.load(path)

    if semantic_map.ndim != 2:
        raise ValueError(
            "Expected semantic_coarse.npy to contain a 2D grid, "
            f"but received shape {semantic_map.shape}."
        )

    return semantic_map


def find_vegetation_cells(
    semantic_map,
    vegetation_class=VEGETATION_CLASS,
):
    """Return grid cells classified as vegetation."""

    rows, columns = np.where(
        semantic_map == vegetation_class
    )

    return np.column_stack((rows, columns))


def cells_to_world_positions(
    vegetation_cells,
    height_grid,
    grid_spacing,
    origin_x=0.0,
    origin_y=0.0,
):
    """Convert vegetation grid cells into 3D world coordinates."""

    positions = []

    for row, column in vegetation_cells:

        x = origin_x + column * grid_spacing
        y = origin_y + row * grid_spacing
        z = height_grid[row, column]

        positions.append(
            {
                "row": int(row),
                "column": int(column),
                "x": float(x),
                "y": float(y),
                "z": float(z),
            }
        )

    return positions


def find_vegetation_regions(
    semantic_map,
    vegetation_class=VEGETATION_CLASS,
):
    """Find connected vegetation regions in the semantic map."""

    rows, columns = semantic_map.shape

    visited = np.zeros(
        semantic_map.shape,
        dtype=bool,
    )

    regions = []

    # Up, down, left, right.
    neighbours = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
    ]

    for row in range(rows):
        for column in range(columns):

            if semantic_map[row, column] != vegetation_class:
                continue

            if visited[row, column]:
                continue

            region = []

            queue = deque()
            queue.append((row, column))

            visited[row, column] = True

            while queue:

                current_row, current_column = queue.popleft()

                region.append(
                    (current_row, current_column)
                )

                for row_offset, column_offset in neighbours:

                    neighbour_row = current_row + row_offset
                    neighbour_column = current_column + column_offset

                    if (
                        neighbour_row < 0
                        or neighbour_row >= rows
                        or neighbour_column < 0
                        or neighbour_column >= columns
                    ):
                        continue

                    if visited[
                        neighbour_row,
                        neighbour_column
                    ]:
                        continue

                    if (
                        semantic_map[
                            neighbour_row,
                            neighbour_column
                        ]
                        != vegetation_class
                    ):
                        continue

                    visited[
                        neighbour_row,
                        neighbour_column
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
    """Calculate the average grid position of a vegetation region."""

    rows = [cell[0] for cell in region]
    columns = [cell[1] for cell in region]

    centre_row = sum(rows) / len(rows)
    centre_column = sum(columns) / len(columns)

    return centre_row, centre_column


def main():

    # Temporary semantic map while PR #34 is not yet on main.
    #
    # 0 = terrain
    # 1 = vegetation
    semantic_map = np.array(
        [
            [0, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 0, 0],
            [0, 1, 1, 1, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 0],
            [0, 0, 0, 1, 1, 0],
        ],
        dtype=np.uint8,
    )

    # Temporary terrain heights.
    # Later this will be replaced with height_grid.npy.
    height_grid = np.array(
        [
            [0.0, 0.0, 0.1, 0.1, 0.2, 0.2],
            [0.0, 0.1, 0.2, 0.3, 0.3, 0.4],
            [0.1, 0.2, 0.3, 0.4, 0.4, 0.5],
            [0.1, 0.2, 0.4, 0.5, 0.5, 0.6],
            [0.2, 0.3, 0.5, 0.6, 0.7, 0.7],
            [0.2, 0.4, 0.6, 0.7, 0.8, 0.9],
        ],
        dtype=float,
    )

    grid_spacing = 1.0

    vegetation_cells = find_vegetation_cells(
        semantic_map
    )

    positions = cells_to_world_positions(
        vegetation_cells,
        height_grid,
        grid_spacing,
    )

    regions = find_vegetation_regions(
        semantic_map
    )

    print("Semantic map:")
    print(semantic_map)

    print()
    print(
        f"Vegetation cells found: {len(vegetation_cells)}"
    )

    print()
    print("Vegetation world positions:")

    for position in positions:
        print(
            f"  grid=({position['row']}, "
            f"{position['column']}) "
            f"-> world=("
            f"{position['x']:.2f}, "
            f"{position['y']:.2f}, "
            f"{position['z']:.2f})"
        )

    print()
    print(
        f"Vegetation regions found: {len(regions)}"
    )

    for index, region in enumerate(
        regions,
        start=1,
    ):

        centre_row, centre_column = get_region_centre(
            region
        )

        print()
        print(f"Region {index}:")
        print(f"  Cells: {len(region)}")
        print(
            f"  Centre: "
            f"({centre_row:.2f}, "
            f"{centre_column:.2f})"
        )

        print("  Grid cells:")

        for row, column in region:
            print(
                f"    ({row}, {column})"
            )


if __name__ == "__main__":
    main()
