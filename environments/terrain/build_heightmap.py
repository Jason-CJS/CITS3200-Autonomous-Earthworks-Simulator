#!/usr/bin/env python3
"""Convert a labelled GOOSE/GOOSE-Ex LiDAR frame to a Chrono heightmap."""

from __future__ import annotations

import argparse
import csv
import json
import math
import struct
import warnings
from pathlib import Path
from typing import Iterable

import numpy as np

if __package__:
    from .goose_dataset import frame_name_for, select_frame
    from .goose_quality import (
        DEFAULT_QUALITY_PRESET,
        QUALITY_PRESET_NAMES,
        resolve_quality,
    )
else:
    from goose_dataset import frame_name_for, select_frame
    from goose_quality import (
        DEFAULT_QUALITY_PRESET,
        QUALITY_PRESET_NAMES,
        resolve_quality,
    )


# Official 64-class GOOSE ontology. The CSV included with each dataset is still
# read when available; this table is a defensive fallback and documents the IDs
# used by the terrain filter.
GOOSE_CLASS_NAMES = (
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

DEFAULT_GROUND_CLASSES = {
    "snow",
    "cobble",
    "leaves",
    "bikeway",
    "pedestrian_crossing",
    "road_marking",
    "moss",
    "sidewalk",
    "curb",
    "asphalt",
    "gravel",
    "rail_track",
    "soil",
    "low_grass",
}

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPOSITORY_ROOT / "data" / "goose"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "outputs" / "goose"


def read_pointcloud(path: Path) -> np.ndarray:
    size = path.stat().st_size
    if size == 0 or size % 16 != 0:
        raise ValueError(
            f"{path} does not contain a non-empty sequence of XYZI float32 points"
        )
    scan = np.fromfile(path, dtype="<f4")
    return scan.reshape((-1, 4))


def read_labels(path: Path, expected_count: int) -> tuple[np.ndarray, np.ndarray]:
    size = path.stat().st_size
    if size != expected_count * 4:
        raise ValueError(
            f"Point/label count mismatch: {expected_count} points but "
            f"{size} label bytes in {path}; expected {expected_count * 4} bytes"
        )
    encoded = np.fromfile(path, dtype="<u4")
    semantic = encoded & np.uint32(0xFFFF)
    instance = encoded >> np.uint32(16)
    return semantic, instance


def _normalise_heading(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def load_class_names(mapping_path: Path | None) -> dict[int, str]:
    fallback = {index: name for index, name in enumerate(GOOSE_CLASS_NAMES)}
    if mapping_path is None:
        warnings.warn(
            "No goose_label_mapping.csv found; using the original 64-class GOOSE "
            "IDs. Remapped/challenge labels require their own --mapping CSV.",
            stacklevel=2,
        )
        return fallback
    if not mapping_path.is_file():
        raise FileNotFoundError(f"Label mapping CSV not found: {mapping_path}")

    with mapping_path.open(newline="", encoding="utf-8-sig") as mapping_file:
        reader = csv.DictReader(mapping_file)
        if not reader.fieldnames:
            raise ValueError(f"Label mapping CSV is empty: {mapping_path}")
        normalised = {_normalise_heading(name): name for name in reader.fieldnames}
        id_column = next(
            (
                normalised[name]
                for name in ("id", "labelid", "labelkey", "classid")
                if name in normalised
            ),
            None,
        )
        name_column = next(
            (
                normalised[name]
                for name in ("name", "classname", "labelname", "class")
                if name in normalised
            ),
            None,
        )
        if id_column is None or name_column is None:
            raise ValueError(
                f"Unrecognised label mapping columns in {mapping_path}. "
                "Expected per-point semantic IDs (label_key, label_id or id) "
                "and class names (class_name or name); coarse category IDs "
                "must not replace the original per-point IDs."
            )

        parsed: dict[int, str] = {}
        for row in reader:
            try:
                class_id = int(row[id_column])
            except (KeyError, TypeError, ValueError):
                continue
            class_name = (
                (row.get(name_column) or "")
                .strip()
                .lower()
                .replace(" ", "_")
                .replace("-", "_")
            )
            if class_name:
                parsed[class_id] = class_name

    if not parsed:
        raise ValueError(f"No semantic IDs and class names found in {mapping_path}")
    return parsed


def find_frame_pair(
    dataset_root: Path,
    split: str,
    scenario: str | None,
    sequence: str | None,
    frame_index: int,
) -> tuple[Path, Path]:
    frame = select_frame(dataset_root, split, scenario, sequence, frame_index)
    return frame.pointcloud, frame.label


def _cell_percentiles(
    cell_ids: np.ndarray,
    heights: np.ndarray,
    cell_count: int,
    percentile: float,
) -> np.ndarray:
    result = np.full(cell_count, np.nan, dtype=np.float64)
    order = np.argsort(cell_ids)
    sorted_cells = cell_ids[order]
    sorted_heights = heights[order]
    unique_cells, starts = np.unique(sorted_cells, return_index=True)
    ends = np.r_[starts[1:], len(sorted_cells)]
    for cell, start, end in zip(unique_cells, starts, ends):
        result[cell] = np.percentile(sorted_heights[start:end], percentile)
    return result


def fill_missing(grid: np.ndarray, max_passes: int | None = None) -> np.ndarray:
    result = np.asarray(grid, dtype=np.float64).copy()
    if not np.isfinite(result).any():
        raise ValueError("Height grid contains no finite samples")

    # Scattered linear interpolation avoids the square wavefront artifacts that
    # appear when large LiDAR shadows are filled one pixel layer at a time.
    # Nearest-neighbour values cover pixels outside the observed convex hull.
    # SciPy is part of the project environment, but the iterative fallback keeps
    # the converter usable in a minimal NumPy-only test environment.
    try:
        from scipy.interpolate import LinearNDInterpolator
        from scipy.spatial import QhullError, cKDTree

        observed = np.isfinite(result)
        missing = ~observed
        if not missing.any():
            return result
        observed_coordinates = np.column_stack(np.nonzero(observed))
        missing_coordinates = np.column_stack(np.nonzero(missing))
        observed_values = result[observed]
        try:
            interpolator = LinearNDInterpolator(
                observed_coordinates, observed_values, fill_value=np.nan
            )
            interpolated = np.asarray(interpolator(missing_coordinates))
        except QhullError:
            # Degenerate synthetic or narrow scans can be collinear. The
            # nearest-neighbour pass below remains well-defined in that case.
            interpolated = np.full(len(missing_coordinates), np.nan)
        outside_hull = ~np.isfinite(interpolated)
        if outside_hull.any():
            tree = cKDTree(observed_coordinates)
            _, nearest_indices = tree.query(
                missing_coordinates[outside_hull], k=1, workers=-1
            )
            interpolated[outside_hull] = observed_values[nearest_indices]
        result[missing] = interpolated
        return result
    except ImportError:
        pass

    if max_passes is None:
        max_passes = max(result.shape)

    for _ in range(max_passes):
        missing = ~np.isfinite(result)
        if not missing.any():
            break
        totals = np.zeros_like(result)
        counts = np.zeros(result.shape, dtype=np.uint8)
        for row_offset, column_offset in (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ):
            source_rows = slice(max(0, -row_offset), result.shape[0] - max(0, row_offset))
            source_cols = slice(
                max(0, -column_offset), result.shape[1] - max(0, column_offset)
            )
            target_rows = slice(max(0, row_offset), result.shape[0] - max(0, -row_offset))
            target_cols = slice(
                max(0, column_offset), result.shape[1] - max(0, -column_offset)
            )
            neighbours = result[source_rows, source_cols]
            valid = np.isfinite(neighbours)
            totals[target_rows, target_cols] += np.where(valid, neighbours, 0.0)
            counts[target_rows, target_cols] += valid

        can_fill = missing & (counts > 0)
        if not can_fill.any():
            break
        result[can_fill] = totals[can_fill] / counts[can_fill]

    if not np.isfinite(result).all():
        result[~np.isfinite(result)] = np.nanmedian(result)
    return result


def smooth_grid(grid: np.ndarray, passes: int) -> np.ndarray:
    result = np.asarray(grid, dtype=np.float64).copy()
    for _ in range(passes):
        padded = np.pad(result, 1, mode="edge")
        result = sum(
            padded[row : row + result.shape[0], column : column + result.shape[1]]
            for row in range(3)
            for column in range(3)
        ) / 9.0
    return result


def rasterize_ground(
    points: np.ndarray,
    semantic: np.ndarray,
    ground_ids: Iterable[int],
    bounds: tuple[float, float, float, float],
    resolution: float,
    height_percentile: float,
    smooth_passes: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    xmin, xmax, ymin, ymax = bounds
    if not (xmin < xmax and ymin < ymax):
        raise ValueError("bounds must satisfy xmin < xmax and ymin < ymax")
    if resolution <= 0:
        raise ValueError("resolution must be positive")

    xyz = points[:, :3]
    finite = np.isfinite(xyz).all(axis=1)
    in_bounds = (
        (xyz[:, 0] >= xmin)
        & (xyz[:, 0] <= xmax)
        & (xyz[:, 1] >= ymin)
        & (xyz[:, 1] <= ymax)
    )
    is_ground = np.isin(semantic, np.fromiter(ground_ids, dtype=np.uint32))
    selected = finite & in_bounds & is_ground
    selected_count = int(selected.sum())
    if selected_count < 50:
        raise ValueError(
            f"Only {selected_count} ground points remain after filtering; choose a "
            "larger area, another frame, or additional ground classes"
        )

    width = int(math.ceil((xmax - xmin) / resolution)) + 1
    height = int(math.ceil((ymax - ymin) / resolution)) + 1
    selected_xyz = xyz[selected]
    columns = np.rint((selected_xyz[:, 0] - xmin) / (xmax - xmin) * (width - 1)).astype(int)
    rows_from_bottom = np.rint(
        (selected_xyz[:, 1] - ymin) / (ymax - ymin) * (height - 1)
    ).astype(int)
    rows = height - 1 - rows_from_bottom
    columns = np.clip(columns, 0, width - 1)
    rows = np.clip(rows, 0, height - 1)
    cells = rows * width + columns

    flat = _cell_percentiles(cells, selected_xyz[:, 2], width * height, height_percentile)
    sparse = flat.reshape((height, width))
    observed = np.isfinite(sparse)
    filled = fill_missing(sparse)
    smoothed = smooth_grid(filled, smooth_passes)
    return smoothed, observed, selected_count


def encode_heightmap(grid: np.ndarray) -> tuple[np.ndarray, float, float]:
    height_min, height_max = np.percentile(grid, (1.0, 99.0))
    if height_max - height_min < 0.05:
        midpoint = float(np.mean(grid))
        height_min = midpoint - 0.025
        height_max = midpoint + 0.025
    clipped = np.clip(grid, height_min, height_max)
    pixels = np.rint((clipped - height_min) * 255.0 / (height_max - height_min)).astype(
        np.uint8
    )
    return pixels, float(height_min), float(height_max)


def write_grayscale_bmp(path: Path, pixels: np.ndarray) -> None:
    """Write an 8-bit indexed grayscale BMP without an image dependency."""
    image = np.asarray(pixels, dtype=np.uint8)
    if image.ndim != 2:
        raise ValueError("BMP pixels must be a two-dimensional array")
    height, width = image.shape
    row_stride = (width + 3) & ~3
    pixel_bytes = row_stride * height
    pixel_offset = 14 + 40 + 256 * 4
    file_size = pixel_offset + pixel_bytes

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        output.write(struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset))
        output.write(
            struct.pack(
                "<IiiHHIIiiII",
                40,
                width,
                height,
                1,
                8,
                0,
                pixel_bytes,
                2835,
                2835,
                256,
                256,
            )
        )
        for value in range(256):
            output.write(bytes((value, value, value, 0)))
        padding = bytes(row_stride - width)
        for row in image[::-1]:
            output.write(row.tobytes())
            output.write(padding)


def build_scene(args: argparse.Namespace) -> Path:
    dataset_root = args.dataset.expanduser().resolve()
    quality = resolve_quality(
        args.quality,
        args.resolution,
        args.grid_spacing,
    )
    frame = select_frame(
        dataset_root, args.split, args.scenario, args.sequence, args.frame_index
    )
    mapping_override = getattr(args, "mapping", None)
    mapping_path = mapping_override.expanduser().resolve() if mapping_override else frame.mapping
    class_names = load_class_names(mapping_path)
    ground_names = set(args.ground_classes)
    ground_ids = sorted(
        class_id for class_id, name in class_names.items() if name in ground_names
    )
    if not ground_ids:
        raise ValueError(f"No class IDs found for ground classes: {sorted(ground_names)}")

    pointcloud_path, label_path = frame.pointcloud, frame.label
    pointcloud = read_pointcloud(pointcloud_path)
    semantic, _ = read_labels(label_path, len(pointcloud))
    bounds = tuple(float(value) for value in args.bounds)
    height_grid, observed, selected_count = rasterize_ground(
        pointcloud,
        semantic,
        ground_ids,
        bounds,
        quality.terrain_resolution,
        args.height_percentile,
        args.smooth_passes,
    )
    pixels, height_min, height_max = encode_heightmap(height_grid)

    frame_name = frame_name_for(pointcloud_path)
    output_dir = args.output.expanduser().resolve() / frame_name
    output_dir.mkdir(parents=True, exist_ok=True)
    heightmap_path = output_dir / "heightmap.bmp"
    grid_path = output_dir / "height_grid.npy"
    scene_path = output_dir / "scene.json"
    write_grayscale_bmp(heightmap_path, pixels)
    np.save(grid_path, np.clip(height_grid, height_min, height_max))

    xmin, xmax, ymin, ymax = bounds
    metadata = {
        "format_version": 1,
        "quality": quality.to_manifest(),
        "source": {
            "dataset": "GOOSE/GOOSE-Ex",
            "platform": (
                "ALICE" if frame.scenario.name.lower().startswith("alice_")
                else "Spot" if frame.scenario.name.lower().startswith("spot_")
                else None
            ),
            "dataset_root": str(dataset_root),
            "split": frame.scenario.split,
            "scenario": frame.scenario.name,
            "pointcloud": str(pointcloud_path.relative_to(dataset_root)),
            "labels": str(label_path.relative_to(dataset_root)),
            "mapping": (
                str(mapping_path.relative_to(dataset_root))
                if mapping_path and mapping_path.is_relative_to(dataset_root)
                else str(mapping_path) if mapping_path else None
            ),
        },
        "heightmap": heightmap_path.name,
        "height_grid": grid_path.name,
        "size_x": xmax - xmin,
        "size_y": ymax - ymin,
        "height_min": height_min,
        "height_max": height_max,
        "bounds_xy": {
            "xmin": xmin,
            "xmax": xmax,
            "ymin": ymin,
            "ymax": ymax,
        },
        "grid": {
            "width": int(pixels.shape[1]),
            "height": int(pixels.shape[0]),
            "requested_spacing": quality.terrain_resolution,
            "x_spacing": (xmax - xmin) / (pixels.shape[1] - 1),
            "y_spacing": (ymax - ymin) / (pixels.shape[0] - 1),
            "observed_fraction": float(observed.mean()),
            "row_zero": "ymax",
            "column_zero": "xmin",
        },
        "conversion": {
            "height_percentile": args.height_percentile,
            "smooth_passes": args.smooth_passes,
            "ground_classes": [class_names[class_id] for class_id in ground_ids],
            "ground_class_ids": ground_ids,
            "points_total": int(len(pointcloud)),
            "ground_points_used": selected_count,
        },
    }
    scene_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"Point cloud: {pointcloud_path}")
    print(f"Labels: {label_path}")
    print(f"Ground points used: {selected_count:,} / {len(pointcloud):,}")
    print(f"Observed grid cells before filling: {observed.mean():.1%}")
    print(f"Height range: {height_min:.3f} m to {height_max:.3f} m")
    print(f"Chrono scene metadata: {scene_path}")
    return scene_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"extracted GOOSE dataset root (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--split", choices=("auto", "val", "train", "test"), default="auto",
        help="split to use (default: auto, preferring labelled val then train then test)",
    )
    parser.add_argument(
        "--scenario", default=None, help="scenario directory (default: first with matching 3D labels)"
    )
    parser.add_argument(
        "--mapping", type=Path, default=None,
        help="override semantic-ID/class-name CSV (default: locate goose_label_mapping.csv)",
    )
    parser.add_argument(
        "--sequence",
        default=None,
        help="optional sequence filter, for example 07 or sequence07",
    )
    parser.add_argument(
        "--frame-index",
        type=int,
        default=0,
        help="zero-based frame within the filtered files (default: 0)",
    )
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        metavar=("XMIN", "XMAX", "YMIN", "YMAX"),
        default=(-20.0, 20.0, -20.0, 20.0),
        help="crop in the local LiDAR frame, in metres",
    )
    parser.add_argument(
        "--quality",
        choices=QUALITY_PRESET_NAMES,
        default=DEFAULT_QUALITY_PRESET,
        help=(
            "performance and terrain-detail preset "
            f"(default: {DEFAULT_QUALITY_PRESET})"
        ),
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=None,
        help="override the heightmap resolution selected by --quality, in metres",
    )
    parser.add_argument(
        "--grid-spacing",
        type=float,
        default=None,
        help="override the SCM grid spacing selected by --quality, in metres",
    )
    parser.add_argument(
        "--height-percentile",
        type=float,
        default=20.0,
        help="per-cell ground height percentile (default: 20)",
    )
    parser.add_argument(
        "--smooth-passes",
        type=int,
        default=2,
        help="number of 3x3 mean smoothing passes (default: 2)",
    )
    parser.add_argument(
        "--ground-classes",
        nargs="+",
        default=sorted(DEFAULT_GROUND_CLASSES),
        help="semantic class names treated as ground",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"generated scene directory (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0 <= args.height_percentile <= 100:
        raise ValueError("--height-percentile must be between 0 and 100")
    if args.smooth_passes < 0:
        raise ValueError("--smooth-passes cannot be negative")
    build_scene(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
