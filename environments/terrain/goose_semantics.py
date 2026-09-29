"""Semantic taxonomy and aligned rasterisation for GOOSE terrain scenes."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence

import numpy as np


SCENE_FORMAT_VERSION = 2
SEMANTIC_FORMAT_VERSION = 1
FINE_TAXONOMY_NAME = "GOOSE-64"
COARSE_TAXONOMY_NAME = "project-coarse-v1"
FINE_UNOBSERVED = np.uint16(65535)
COARSE_UNOBSERVED = np.uint8(255)

# Official GOOSE class IDs. Tuple position is the stable numerical class ID.
FINE_CLASS_NAMES = (
    "undefined",
    "traffic_cone",
    "snow",
    "cobble",
    "obstacle",
    "leaves",
    "street_light",
    "bikeway",
    "ego_vehicle",
    "pedestrian_crossing",
    "road_block",
    "road_marking",
    "car",
    "bicycle",
    "person",
    "bus",
    "forest",
    "bush",
    "moss",
    "traffic_light",
    "motorcycle",
    "sidewalk",
    "curb",
    "asphalt",
    "gravel",
    "boom_barrier",
    "rail_track",
    "tree_crown",
    "tree_trunk",
    "debris",
    "crops",
    "soil",
    "rider",
    "animal",
    "truck",
    "on_rails",
    "caravan",
    "trailer",
    "building",
    "wall",
    "rock",
    "fence",
    "guard_rail",
    "bridge",
    "tunnel",
    "pole",
    "traffic_sign",
    "misc_sign",
    "barrier_tape",
    "kick_scooter",
    "low_grass",
    "high_grass",
    "scenery_vegetation",
    "sky",
    "water",
    "wire",
    "outlier",
    "heavy_machinery",
    "container",
    "hedge",
    "barrel",
    "pipe",
    "tree_root",
    "military_vehicle",
)

COARSE_CATEGORIES = {
    0: "ignored",
    1: "vegetation",
    2: "terrain",
    3: "structure",
    4: "vehicle",
    5: "road",
    6: "object",
    7: "sign",
    8: "human",
    9: "water",
    10: "animal",
    11: "sky",
}

# Indexed by original GOOSE class ID. These IDs never depend on registration
# order. "construction" is exposed as "structure" for this project's API.
FINE_TO_COARSE = (
    0, 7, 2, 2, 6, 1, 6, 5,
    0, 5, 7, 5, 4, 4, 8, 4,
    1, 1, 1, 7, 4, 5, 5, 2,
    2, 7, 5, 1, 1, 3, 1, 2,
    8, 10, 4, 4, 4, 4, 3, 3,
    6, 3, 3, 3, 3, 6, 7, 7,
    7, 4, 1, 1, 1, 11, 9, 3,
    0, 4, 3, 1, 6, 6, 1, 4,
)

SOURCE_CATEGORY_BY_COARSE = {
    0: "void",
    1: "vegetation",
    2: "terrain",
    3: "construction",
    4: "vehicle",
    5: "road",
    6: "object",
    7: "sign",
    8: "human",
    9: "water",
    10: "animal",
    11: "sky",
}


def validate_taxonomy() -> None:
    if len(FINE_CLASS_NAMES) != 64 or len(FINE_TO_COARSE) != 64:
        raise ValueError("GOOSE taxonomy must contain every fine ID from 0 through 63")
    if len(set(FINE_CLASS_NAMES)) != len(FINE_CLASS_NAMES):
        raise ValueError("GOOSE taxonomy class names must be unique")
    if set(COARSE_CATEGORIES) != set(range(12)):
        raise ValueError("Project coarse taxonomy must contain IDs 0 through 11")
    if set(SOURCE_CATEGORY_BY_COARSE) != set(COARSE_CATEGORIES):
        raise ValueError("Every coarse class must have a source-category assignment")
    invalid = {
        coarse_id for coarse_id in FINE_TO_COARSE
        if coarse_id not in COARSE_CATEGORIES
    }
    if invalid:
        raise ValueError(f"Fine taxonomy references invalid coarse IDs: {sorted(invalid)}")


def validate_class_names(class_names: Mapping[int, str]) -> None:
    expected_ids = set(range(64))
    supplied_ids = set(class_names)
    if supplied_ids != expected_ids:
        missing = sorted(expected_ids - supplied_ids)
        extra = sorted(supplied_ids - expected_ids)
        raise ValueError(
            "GOOSE semantic mapping must contain IDs 0 through 63 exactly once; "
            f"missing={missing}, extra={extra}"
        )
    mismatched = [
        fine_id for fine_id, expected_name in enumerate(FINE_CLASS_NAMES)
        if class_names[fine_id] != expected_name
    ]
    if mismatched:
        details = ", ".join(
            f"{fine_id}: {class_names[fine_id]!r} != {FINE_CLASS_NAMES[fine_id]!r}"
            for fine_id in mismatched[:5]
        )
        raise ValueError(
            "Semantic mapping is not the original GOOSE-64 taxonomy; " + details
        )


def taxonomy_mapping_sha256() -> str:
    entries = [
        {
            "id": fine_id,
            "name": name,
            "coarse_id": FINE_TO_COARSE[fine_id],
            "coarse_name": COARSE_CATEGORIES[FINE_TO_COARSE[fine_id]],
        }
        for fine_id, name in enumerate(FINE_CLASS_NAMES)
    ]
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


FINE_MAPPING_SHA256 = taxonomy_mapping_sha256()


def grid_shape(
    bounds: Sequence[float],
    resolution: float,
) -> tuple[int, int]:
    if len(bounds) != 4:
        raise ValueError("bounds must contain xmin, xmax, ymin and ymax")
    xmin, xmax, ymin, ymax = (float(value) for value in bounds)
    if not all(math.isfinite(value) for value in (xmin, xmax, ymin, ymax)):
        raise ValueError("bounds must contain finite values")
    if not (xmin < xmax and ymin < ymax):
        raise ValueError("bounds must satisfy xmin < xmax and ymin < ymax")
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("resolution must be a finite number greater than zero")
    width = int(math.ceil((xmax - xmin) / resolution)) + 1
    height = int(math.ceil((ymax - ymin) / resolution)) + 1
    return height, width


def point_grid_indices(
    points: np.ndarray,
    bounds: Sequence[float],
    resolution: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, int]]:
    """Return the common point mask and row/column conversion for all maps."""
    xyz = np.asarray(points)
    if xyz.ndim != 2 or xyz.shape[1] < 3:
        raise ValueError("points must be a two-dimensional array with XYZ columns")
    height, width = grid_shape(bounds, resolution)
    xmin, xmax, ymin, ymax = (float(value) for value in bounds)
    finite = np.isfinite(xyz[:, :3]).all(axis=1)
    in_bounds = (
        (xyz[:, 0] >= xmin)
        & (xyz[:, 0] <= xmax)
        & (xyz[:, 1] >= ymin)
        & (xyz[:, 1] <= ymax)
    )
    selected = finite & in_bounds
    selected_xyz = xyz[selected]
    columns = np.rint(
        (selected_xyz[:, 0] - xmin) / (xmax - xmin) * (width - 1)
    ).astype(np.int64)
    rows_from_bottom = np.rint(
        (selected_xyz[:, 1] - ymin) / (ymax - ymin) * (height - 1)
    ).astype(np.int64)
    rows = height - 1 - rows_from_bottom
    return (
        selected,
        np.clip(rows, 0, height - 1),
        np.clip(columns, 0, width - 1),
        (height, width),
    )


def rasterize_semantics(
    points: np.ndarray,
    semantic: np.ndarray,
    bounds: Sequence[float],
    resolution: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Rasterise all finite in-bounds labels using deterministic majority vote."""
    labels = np.asarray(semantic)
    if labels.ndim != 1:
        raise ValueError("semantic labels must be a one-dimensional array")
    if not np.issubdtype(labels.dtype, np.integer):
        raise ValueError("semantic labels must contain integer class IDs")
    if len(labels) != len(points):
        raise ValueError(
            f"Point/label count mismatch: {len(points)} points but {len(labels)} labels"
        )
    unknown = sorted(
        int(value) for value in np.unique(labels)
        if int(value) < 0 or int(value) >= len(FINE_CLASS_NAMES)
    )
    if unknown:
        raise ValueError(f"Unknown GOOSE semantic class IDs: {unknown}")

    selected, rows, columns, shape = point_grid_indices(points, bounds, resolution)
    fine_map = np.full(shape, FINE_UNOBSERVED, dtype=np.uint16)
    coarse_map = np.full(shape, COARSE_UNOBSERVED, dtype=np.uint8)
    selected_count = int(selected.sum())
    if selected_count == 0:
        return fine_map, coarse_map, 0

    width = shape[1]
    cells = rows * width + columns
    selected_labels = labels[selected].astype(np.int64, copy=False)
    pairs = np.column_stack((cells, selected_labels))
    unique_pairs, counts = np.unique(pairs, axis=0, return_counts=True)
    order = np.lexsort((unique_pairs[:, 1], -counts, unique_pairs[:, 0]))
    ordered_pairs = unique_pairs[order]
    first_for_cell = np.r_[
        True,
        ordered_pairs[1:, 0] != ordered_pairs[:-1, 0],
    ]
    winners = ordered_pairs[first_for_cell]
    winner_cells = winners[:, 0].astype(np.int64)
    winner_fine = winners[:, 1].astype(np.uint16)
    fine_map.reshape(-1)[winner_cells] = winner_fine
    lookup = np.asarray(FINE_TO_COARSE, dtype=np.uint8)
    coarse_map.reshape(-1)[winner_cells] = lookup[winner_fine]
    return fine_map, coarse_map, selected_count


def semantic_legend() -> dict:
    return {
        "format_version": SEMANTIC_FORMAT_VERSION,
        "fine_taxonomy": {
            "name": FINE_TAXONOMY_NAME,
            "mapping_sha256": FINE_MAPPING_SHA256,
            "unobserved_id": int(FINE_UNOBSERVED),
        },
        "coarse_taxonomy": {
            "name": COARSE_TAXONOMY_NAME,
            "unobserved_id": int(COARSE_UNOBSERVED),
            "categories": [
                {"id": coarse_id, "name": name}
                for coarse_id, name in COARSE_CATEGORIES.items()
            ],
        },
        "grid_alignment": {
            "aligned_to": "height_grid.npy",
            "row_zero": "ymax",
            "column_zero": "xmin",
            "x_direction": "increasing",
            "y_direction": "decreasing",
        },
        "classes": [
            {
                "id": fine_id,
                "name": name,
                "coarse_id": FINE_TO_COARSE[fine_id],
                "coarse_name": COARSE_CATEGORIES[FINE_TO_COARSE[fine_id]],
                "source_category": SOURCE_CATEGORY_BY_COARSE[
                    FINE_TO_COARSE[fine_id]
                ],
            }
            for fine_id, name in enumerate(FINE_CLASS_NAMES)
        ],
    }


def class_distribution(
    values: np.ndarray,
    names: Mapping[int, str] | Sequence[str],
    unobserved: int,
) -> list[dict]:
    observed = np.asarray(values)
    observed = observed[observed != unobserved]
    if observed.size == 0:
        return []
    identifiers, counts = np.unique(observed, return_counts=True)
    return [
        {
            "id": int(identifier),
            "name": names[int(identifier)],
            "count": int(count),
        }
        for identifier, count in zip(identifiers, counts, strict=True)
    ]


validate_taxonomy()
