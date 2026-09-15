"""Purpose-built terrain and measurement helpers for Issue #17."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from statistics import fmean
import struct
from typing import Mapping

from deformation.scm_deformation_export import calculate_scm_grid_geometry


GridPoint = tuple[int, int]


@dataclass(frozen=True)
class TerrainProfile:
    """Deterministic SCM heightmap containing a mound and shallow hole."""

    length_m: float = 12.0
    width_m: float = 8.0
    grid_spacing_m: float = 0.10
    height_min_m: float = -0.14
    height_max_m: float = 0.26

    hole_center_x_m: float = -2.85
    hole_center_y_m: float = 0.0
    hole_radius_m: float = 0.40
    hole_depth_m: float = 0.08
    hole_sigma_m: float = 0.32

    mound_center_x_m: float = -2.00
    mound_center_y_m: float = 0.0
    mound_height_m: float = 0.22
    mound_sigma_x_m: float = 0.35
    mound_sigma_y_m: float = 0.75

    @property
    def geometry(self):
        return calculate_scm_grid_geometry(
            self.length_m,
            self.width_m,
            self.grid_spacing_m,
        )

    def raw_height_at(self, x_m: float, y_m: float) -> float:
        """Return the analytic mound-and-hole terrain height."""

        hole_distance = (
            ((x_m - self.hole_center_x_m) / self.hole_sigma_m) ** 2
            + ((y_m - self.hole_center_y_m) / self.hole_sigma_m) ** 2
        )
        mound_distance = (
            (
                (x_m - self.mound_center_x_m)
                / self.mound_sigma_x_m
            )
            ** 2
            + (
                (y_m - self.mound_center_y_m)
                / self.mound_sigma_y_m
            )
            ** 2
        )

        height = (
            -self.hole_depth_m * math.exp(-0.5 * hole_distance)
            + self.mound_height_m * math.exp(-0.5 * mound_distance)
        )
        return max(self.height_min_m, min(self.height_max_m, height))

    def grayscale_at(self, x_m: float, y_m: float) -> int:
        return height_to_grayscale(
            self.raw_height_at(x_m, y_m),
            self.height_min_m,
            self.height_max_m,
        )

    def initial_height_at(self, x_m: float, y_m: float) -> float:
        """Return the quantised height Chrono receives from the bitmap."""

        grayscale = self.grayscale_at(x_m, y_m)
        return self.height_min_m + (
            grayscale / 255.0
        ) * (self.height_max_m - self.height_min_m)

    def initial_grid(self) -> dict[GridPoint, float]:
        geometry = self.geometry
        half_x = (geometry.node_count_x - 1) // 2
        half_y = (geometry.node_count_y - 1) // 2

        return {
            (grid_x, grid_y): self.initial_height_at(
                grid_x * geometry.actual_spacing_m,
                grid_y * geometry.actual_spacing_m,
            )
            for grid_y in range(-half_y, half_y + 1)
            for grid_x in range(-half_x, half_x + 1)
        }


def height_to_grayscale(
    height_m: float,
    minimum_m: float,
    maximum_m: float,
) -> int:
    if maximum_m <= minimum_m:
        raise ValueError("maximum_m must be greater than minimum_m")

    normalised = (height_m - minimum_m) / (maximum_m - minimum_m)
    return round(255 * max(0.0, min(1.0, normalised)))


def calculate_hole_metrics(
    profile: TerrainProfile,
    initial_grid: Mapping[GridPoint, float],
    final_grid: Mapping[GridPoint, float],
) -> dict[str, float | int]:
    """Measure average height across every node inside the target hole."""

    spacing = profile.geometry.actual_spacing_m
    hole_points = [
        point
        for point in initial_grid
        if math.hypot(
            point[0] * spacing - profile.hole_center_x_m,
            point[1] * spacing - profile.hole_center_y_m,
        )
        <= profile.hole_radius_m
    ]
    if not hole_points:
        raise ValueError("No SCM grid nodes fall inside the target hole")

    initial_average = fmean(initial_grid[point] for point in hole_points)
    final_average = fmean(
        final_grid.get(point, initial_grid[point]) for point in hole_points
    )
    changed_points = sum(
        not math.isclose(
            final_grid.get(point, initial_grid[point]),
            initial_grid[point],
            abs_tol=1e-12,
        )
        for point in hole_points
    )

    return {
        "hole_node_count": len(hole_points),
        "modified_node_count_in_hole": changed_points,
        "initial_average_height_m": initial_average,
        "final_average_height_m": final_average,
        "average_height_increase_m": final_average - initial_average,
    }


def write_profile_heightmap(
    profile: TerrainProfile,
    output_path: str | Path,
) -> Path:
    """Write the purpose-built terrain as a dependency-free 24-bit BMP."""

    geometry = profile.geometry
    half_x = (geometry.node_count_x - 1) // 2
    half_y = (geometry.node_count_y - 1) // 2

    rows = [
        [
            profile.grayscale_at(
                grid_x * geometry.actual_spacing_m,
                grid_y * geometry.actual_spacing_m,
            )
            for grid_x in range(-half_x, half_x + 1)
        ]
        for grid_y in range(-half_y, half_y + 1)
    ]
    return write_grayscale_bmp(output_path, rows)


def write_grayscale_bmp(
    output_path: str | Path,
    rows: list[list[int]],
) -> Path:
    """Write grayscale values as an uncompressed 24-bit BMP."""

    if not rows or not rows[0]:
        raise ValueError("BMP requires at least one pixel")

    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("All BMP rows must have the same width")

    height = len(rows)
    row_size = (width * 3 + 3) & ~3
    pixel_data = bytearray()

    for row in reversed(rows):
        for value in row:
            grayscale = max(0, min(255, int(value)))
            pixel_data.extend((grayscale, grayscale, grayscale))
        pixel_data.extend(b"\x00" * (row_size - width * 3))

    pixel_offset = 54
    file_size = pixel_offset + len(pixel_data)
    header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset)
    information = struct.pack(
        "<IIIHHIIIIII",
        40,
        width,
        height,
        1,
        24,
        0,
        len(pixel_data),
        2835,
        2835,
        0,
        0,
    )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + information + pixel_data)
    return path