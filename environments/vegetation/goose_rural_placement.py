
"""Deterministic, semantic-guided rural vegetation placement for GOOSE-Ex."""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path

import numpy as np


# --------------------------------------------------
# GOOSE fine semantic class IDs
# --------------------------------------------------

LOW_GRASS = 50
HIGH_GRASS = 51
BUSH = 17
HEDGE = 59
FOREST = 16
SCENERY_VEGETATION = 52
SOIL = 31
COBBLE = 3
GRAVEL = 24
ROCK = 40


# Initial placement limits to keep the simulation lightweight.
DEFAULT_COUNTS = {
    "low_grass_patch": 40,
    "tall_wild_grass": 15,
    "scrub_bush": 10,
    "rural_hedge": 5,
    "broadleaf_sapling": 5,
    "rock": 25,
}


# Preferred semantic labels and optional fallback labels.
# Fallbacks are used only when no preferred cells exist.
PLACEMENT_CLASSES = {
    "low_grass_patch": ((LOW_GRASS,), ()),
    "tall_wild_grass": ((HIGH_GRASS,), ()),
    "scrub_bush": (
        (BUSH,),
        (HIGH_GRASS, LOW_GRASS),
    ),
    "rural_hedge": ((HEDGE,), ()),
    "broadleaf_sapling": (
        (FOREST, SCENERY_VEGETATION),
        (LOW_GRASS, HIGH_GRASS),
    ),
    "rock": (
        (ROCK, GRAVEL, COBBLE, SOIL),
        (),
    ),
}


# Minimum distance between object centres, in metres.
MIN_SPACING = {
    "low_grass_patch": 0.5,
    "tall_wild_grass": 0.7,
    "scrub_bush": 1.5,
    "rural_hedge": 2.0,
    "broadleaf_sapling": 3.0,
    "rock": 0.3,
}


# Keep larger vegetation away from existing Beech/Oak trunks.
TREE_EXCLUSION_RADIUS = {
    "scrub_bush": 2.0,
    "rural_hedge": 2.0,
    "broadleaf_sapling": 2.0,
}


def _distance(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    """Calculate horizontal distance between two points."""
    return math.hypot(x1 - x2, y1 - y2)


def _is_valid_position(
    x: float,
    y: float,
    asset_type: str,
    placed: list[dict],
    trees: list[dict],
) -> bool:
    """Check object spacing and existing tree exclusion zones."""

    spacing = MIN_SPACING[asset_type]

    for existing in placed:
        required = max(
            spacing,
            MIN_SPACING[existing["asset_type"]],
        )

        if _distance(
            x,
            y,
            existing["x"],
            existing["y"],
        ) < required:
            return False

    exclusion = TREE_EXCLUSION_RADIUS.get(
        asset_type,
        0.0,
    )

    if exclusion > 0:
        for tree in trees:
            if _distance(
                x,
                y,
                float(tree["x"]),
                float(tree["y"]),
            ) < exclusion:
                return False

    return True


def generate_placements(
    semantic_map: np.ndarray,
    height_grid: np.ndarray,
    grid: dict,
    counts: dict[str, int] | None = None,
    seed: int = 38,
    trees: list[dict] | None = None,
) -> list[dict]:
    """Generate reproducible placements using GOOSE semantic labels."""

    if semantic_map.shape != height_grid.shape:
        raise ValueError(
            "Semantic and height grids must have the same shape"
        )

    rng = random.Random(seed)

    counts = (
        DEFAULT_COUNTS
        if counts is None
        else counts
    )

    trees = [] if trees is None else trees

    xmin = float(grid["xmin"])
    ymax = float(grid["ymax"])
    x_spacing = float(grid["x_spacing"])
    y_spacing = float(grid["y_spacing"])

    if x_spacing <= 0 or y_spacing <= 0:
        raise ValueError("Grid spacing must be positive")

    placements = []

    # Larger objects are placed first to reserve enough space.
    placement_order = (
        "broadleaf_sapling",
        "rural_hedge",
        "scrub_bush",
        "tall_wild_grass",
        "low_grass_patch",
        "rock",
    )

    for asset_type in placement_order:
        count = counts.get(asset_type, 0)

        if type(count) is not int or count < 0:
            raise ValueError(
                f"Invalid placement count for {asset_type}"
            )

        if count == 0:
            continue

        preferred, fallback = PLACEMENT_CLASSES[asset_type]

        candidate_cells = np.argwhere(
            np.isin(semantic_map, preferred)
        )

        if len(candidate_cells) == 0 and fallback:
            candidate_cells = np.argwhere(
                np.isin(semantic_map, fallback)
            )

        if len(candidate_cells) == 0:
            continue

        indices = list(range(len(candidate_cells)))
        rng.shuffle(indices)

        accepted = 0

        # Each candidate is examined at most once,
        # preventing an endless search for positions.
        for index in indices:
            if accepted >= count:
                break

            row, column = map(
                int,
                candidate_cells[index],
            )

            x = xmin + column * x_spacing
            y = ymax - row * y_spacing
            z = float(height_grid[row, column])

            if not math.isfinite(z):
                continue

            if not _is_valid_position(
                x,
                y,
                asset_type,
                placements,
                trees,
            ):
                continue

            placements.append({
                "asset_type": asset_type,
                "row": row,
                "column": column,
                "x": float(x),
                "y": float(y),
                "z": z,
                "rotation_z": rng.uniform(0.0, 360.0),
                "scale": round(
                    rng.uniform(0.85, 1.15),
                    3,
                ),
            })

            accepted += 1

    return placements


def generate_from_scene(
    scene_path: Path,
    output_path: Path,
    seed: int = 38,
    tree_path: Path | None = None,
) -> dict:
    """Generate rural placements from a GOOSE scene."""

    scene_path = (
        Path(scene_path)
        .expanduser()
        .resolve()
    )

    directory = scene_path.parent

    scene = json.loads(
        scene_path.read_text(encoding="utf-8")
    )

    semantic_map = np.load(
        directory
        / scene["outputs"]["semantic_fine"]["path"]
    )

    height_grid = np.load(
        directory / scene["height_grid"]
    )

    bounds = scene["bounds_xy"]
    grid_data = scene["grid"]

    grid = {
        "xmin": bounds["xmin"],
        "ymax": bounds["ymax"],
        "x_spacing": grid_data["x_spacing"],
        "y_spacing": grid_data["y_spacing"],
    }

    trees = []

    if tree_path is not None:
        tree_path = (
            Path(tree_path)
            .expanduser()
            .resolve()
        )

        tree_data = json.loads(
            tree_path.read_text(encoding="utf-8")
        )

        trees = tree_data["trees"]

    placements = generate_placements(
        semantic_map,
        height_grid,
        grid,
        seed=seed,
        trees=trees,
    )

    result = {
        "format_version": 1,
        "source_scene": str(scene_path),
        "seed": seed,
        "tree_exclusion_enabled": tree_path is not None,
        "placements": placements,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--scene",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--trees",
        type=Path,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=38,
    )

    args = parser.parse_args()

    result = generate_from_scene(
        args.scene,
        args.output,
        seed=args.seed,
        tree_path=args.trees,
    )

    counts = Counter(
        item["asset_type"]
        for item in result["placements"]
    )

    print(
        f"Generated {len(result['placements'])} "
        "rural placements:"
    )

    for asset, count in sorted(counts.items()):
        print(f"  {asset}: {count}")

    print(
        "Tree exclusion enabled:",
        result["tree_exclusion_enabled"],
    )

    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
