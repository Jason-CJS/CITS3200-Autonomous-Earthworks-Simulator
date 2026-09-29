"""GOOSE vegetation placement utilities.

Vegetation placement is derived from the semantic map generated from
GOOSE data rather than from random positions across the terrain.

The module can run in two modes:

1. Demo mode:
   Uses a small synthetic semantic map for development/testing.

2. Real GOOSE mode:
   Loads semantic_coarse.npy, semantic_legend.json and height_grid.npy
   using a generated scene.json manifest.
"""

import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np


# Used only by the synthetic demo.
# Real GOOSE scenes obtain this value from semantic_legend.json.
VEGETATION_CLASS = 1


def load_semantic_map(path):
    """Load a GOOSE coarse semantic map."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Semantic map not found: {path}"
        )

    semantic_map = np.load(path)

    if semantic_map.ndim != 2:
        raise ValueError(
            "Expected semantic_coarse.npy to contain a 2D grid, "
            f"but received shape {semantic_map.shape}."
        )

    return semantic_map


def load_height_grid(path):
    """Load the GOOSE terrain height grid."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Height grid not found: {path}"
        )

    height_grid = np.load(path)

    if height_grid.ndim != 2:
        raise ValueError(
            "Expected height_grid.npy to contain a 2D grid, "
            f"but received shape {height_grid.shape}."
        )

    return height_grid


def load_semantic_legend(path):
    """Load the semantic legend and return the vegetation class ID."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Semantic legend not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        legend = json.load(file)

    categories = legend["coarse_taxonomy"]["categories"]

    for category in categories:
        if category["name"].lower() == "vegetation":
            return int(category["id"])

    raise ValueError(
        "Vegetation class was not found in semantic_legend.json."
    )


def load_scene(scene_path):
    """Load a generated GOOSE scene manifest."""

    scene_path = Path(scene_path)

    if not scene_path.exists():
        raise FileNotFoundError(
            f"Scene manifest not found: {scene_path}"
        )

    with scene_path.open("r", encoding="utf-8") as file:
        scene = json.load(file)

    return scene


def get_output_path(scene_path, scene, output_name):
    """Get the path of an output file referenced by scene.json."""

    scene_path = Path(scene_path)

    output_info = scene["outputs"][output_name]
    output_path = scene_path.parent / output_info["path"]

    return output_path


def load_goose_scene(scene_path):
    """Load all data required for GOOSE vegetation placement."""

    scene_path = Path(scene_path)
    scene = load_scene(scene_path)

    semantic_path = get_output_path(
        scene_path,
        scene,
        "semantic_coarse",
    )

    legend_path = get_output_path(
        scene_path,
        scene,
        "semantic_legend",
    )

    height_grid_path = get_output_path(
        scene_path,
        scene,
        "height_grid",
    )

    semantic_map = load_semantic_map(
        semantic_path
    )

    height_grid = load_height_grid(
        height_grid_path
    )

    vegetation_class = load_semantic_legend(
        legend_path
    )

    if semantic_map.shape != height_grid.shape:
        raise ValueError(
            "Semantic map and height grid are not aligned: "
            f"semantic shape={semantic_map.shape}, "
            f"height shape={height_grid.shape}"
        )

    bounds = scene["bounds_xy"]
    grid = scene["grid"]

    xmin = float(bounds["xmin"])
    ymax = float(bounds["ymax"])

    x_spacing = float(grid["x_spacing"])
    y_spacing = float(grid["y_spacing"])

    return {
        "scene": scene,
        "semantic_map": semantic_map,
        "height_grid": height_grid,
        "vegetation_class": vegetation_class,
        "xmin": xmin,
        "ymax": ymax,
        "x_spacing": x_spacing,
        "y_spacing": y_spacing,
    }


def find_vegetation_cells(
    semantic_map,
    vegetation_class=VEGETATION_CLASS,
):
    """Return grid cells classified as vegetation."""

    rows, columns = np.where(
        semantic_map == vegetation_class
    )

    return np.column_stack(
        (rows, columns)
    )


def cells_to_world_positions(
    vegetation_cells,
    height_grid,
    x_spacing,
    y_spacing,
    xmin=0.0,
    ymax=0.0,
):
    """Convert vegetation grid cells into GOOSE world coordinates.

    GOOSE grid alignment:

        column 0 = xmin
        row 0 = ymax

        x increases as column increases.
        y decreases as row increases.

    X and Y spacing are handled separately because the generated
    scene manifest records x_spacing and y_spacing independently.
    """

    positions = []

    for row, column in vegetation_cells:

        x = xmin + column * x_spacing
        y = ymax - row * y_spacing
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
    """Find connected vegetation regions in the semantic map.

    Four-directional connectivity is used:

        up
        down
        left
        right

    Diagonal-only cells are therefore treated as separate regions.
    """

    rows, columns = semantic_map.shape

    visited = np.zeros(
        semantic_map.shape,
        dtype=bool,
    )

    regions = []

    neighbours = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
    ]

    for row in range(rows):
        for column in range(columns):

            if (
                semantic_map[row, column]
                != vegetation_class
            ):
                continue

            if visited[row, column]:
                continue

            region = []

            queue = deque(
                [(row, column)]
            )

            visited[row, column] = True

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

                for (
                    row_offset,
                    column_offset,
                ) in neighbours:

                    neighbour_row = (
                        current_row
                        + row_offset
                    )

                    neighbour_column = (
                        current_column
                        + column_offset
                    )

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

    rows = [
        cell[0]
        for cell in region
    ]

    columns = [
        cell[1]
        for cell in region
    ]

    centre_row = (
        sum(rows) / len(rows)
    )

    centre_column = (
        sum(columns) / len(columns)
    )

    return (
        centre_row,
        centre_column,
    )


def print_results(
    vegetation_cells,
    positions,
    regions,
    max_positions=None,
):
    """Print vegetation detection results."""

    print()
    print(
        f"Vegetation cells found: "
        f"{len(vegetation_cells)}"
    )

    print()

    print(
        f"Vegetation regions found: "
        f"{len(regions)}"
    )

    print()
    print("Vegetation world positions:")

    positions_to_print = positions

    if max_positions is not None:
        positions_to_print = positions[
            :max_positions
        ]

    for position in positions_to_print:

        print(
            f"  grid=("
            f"{position['row']}, "
            f"{position['column']}) "
            f"-> world=("
            f"{position['x']:.2f}, "
            f"{position['y']:.2f}, "
            f"{position['z']:.2f})"
        )

    if (
        max_positions is not None
        and len(positions) > max_positions
    ):
        print(
            f"  ... "
            f"{len(positions) - max_positions} "
            f"additional vegetation cells not shown"
        )

    print()
    print("Vegetation regions:")

    for index, region in enumerate(
        regions,
        start=1,
    ):

        centre_row, centre_column = (
            get_region_centre(region)
        )

        print(
            f"  Region {index}: "
            f"{len(region)} cells, "
            f"centre=("
            f"{centre_row:.2f}, "
            f"{centre_column:.2f})"
        )


def run_demo():
    """Run the small synthetic vegetation demonstration."""

    print(
        "Running synthetic GOOSE vegetation demo."
    )

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

    x_spacing = 1.0
    y_spacing = 1.0

    xmin = 0.0
    ymax = 6.0

    vegetation_class = VEGETATION_CLASS

    vegetation_cells = find_vegetation_cells(
        semantic_map,
        vegetation_class,
    )

    positions = cells_to_world_positions(
        vegetation_cells,
        height_grid,
        x_spacing,
        y_spacing,
        xmin,
        ymax,
    )

    regions = find_vegetation_regions(
        semantic_map,
        vegetation_class,
    )

    print()
    print("Semantic map:")
    print(semantic_map)

    print_results(
        vegetation_cells,
        positions,
        regions,
    )


def run_goose_scene(scene_path):
    """Process vegetation from a real generated GOOSE scene."""

    print(
        f"Loading GOOSE scene: {scene_path}"
    )

    data = load_goose_scene(
        scene_path
    )

    semantic_map = data[
        "semantic_map"
    ]

    height_grid = data[
        "height_grid"
    ]

    vegetation_class = data[
        "vegetation_class"
    ]

    print(
        f"Vegetation semantic class: "
        f"{vegetation_class}"
    )

    print(
        f"Semantic grid shape: "
        f"{semantic_map.shape}"
    )

    print(
        f"Grid spacing: "
        f"x={data['x_spacing']:.3f} m, "
        f"y={data['y_spacing']:.3f} m"
    )

    print(
        f"Grid origin: "
        f"xmin={data['xmin']:.3f}, "
        f"ymax={data['ymax']:.3f}"
    )

    vegetation_cells = find_vegetation_cells(
        semantic_map,
        vegetation_class,
    )

    positions = cells_to_world_positions(
        vegetation_cells,
        height_grid,
        data["x_spacing"],
        data["y_spacing"],
        data["xmin"],
        data["ymax"],
    )

    regions = find_vegetation_regions(
        semantic_map,
        vegetation_class,
    )

    # Real GOOSE scenes may contain thousands of vegetation cells.
    # Only display the first 20 positions to keep terminal output usable.
    print_results(
        vegetation_cells,
        positions,
        regions,
        max_positions=20,
    )


def parse_arguments():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate vegetation placement information "
            "from GOOSE semantic labels."
        )
    )

    parser.add_argument(
        "scene",
        nargs="?",
        type=Path,
        help=(
            "Path to a generated GOOSE scene.json. "
            "If omitted, the synthetic demo is run."
        ),
    )

    return parser.parse_args()


def main():
    """Run either demo mode or real GOOSE scene mode."""

    args = parse_arguments()

    if args.scene is None:
        run_demo()
    else:
        run_goose_scene(
            args.scene
        )


if __name__ == "__main__":
    main()
