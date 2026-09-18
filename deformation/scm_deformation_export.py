"""Utilities for exporting Project Chrono SCM terrain deformation data.

The functions in this module operate on plain Python values after the small
``collect_deformation_records`` adapter has converted Chrono's node objects.
This keeps the calculations and file output reusable and testable without a
running Chrono simulation.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Callable, Iterable, Mapping, Sequence


CSV_FILENAME = "deformation_nodes.csv"
SUMMARY_FILENAME = "deformation_summary.json"
CSV_FIELDS = (
    "grid_x",
    "grid_y",
    "world_x_m",
    "world_y_m",
    "initial_height_m",
    "final_height_m",
    "height_change_m",
    "sinkage_m",
)


@dataclass(frozen=True)
class DeformationRecord:
    """Final deformation values for one modified SCM grid node."""

    grid_x: int
    grid_y: int
    world_x_m: float
    world_y_m: float
    initial_height_m: float
    final_height_m: float
    height_change_m: float
    sinkage_m: float


@dataclass(frozen=True)
class SCMGridGeometry:
    """Grid geometry produced by Chrono's flat SCM initialization."""

    requested_length_m: float
    requested_width_m: float
    requested_spacing_m: float
    actual_spacing_m: float
    node_count_x: int
    node_count_y: int


def calculate_scm_grid_geometry(
    length_m: float,
    width_m: float,
    requested_spacing_m: float,
) -> SCMGridGeometry:
    """Calculate the spacing and node counts Chrono uses for a flat SCM grid.

    Chrono may slightly decrease the requested grid spacing so an integer
    number of cells spans the terrain's X dimension. The same adjusted spacing
    is then used in both horizontal directions.
    """

    if length_m <= 0 or width_m <= 0:
        raise ValueError("SCM terrain dimensions must be greater than zero")
    if requested_spacing_m <= 0:
        raise ValueError("requested_spacing_m must be greater than zero")

    half_cells_x = math.ceil((length_m / 2) / requested_spacing_m)
    half_cells_y = math.ceil((width_m / 2) / requested_spacing_m)
    actual_spacing_m = length_m / (2 * half_cells_x)

    return SCMGridGeometry(
        requested_length_m=float(length_m),
        requested_width_m=float(width_m),
        requested_spacing_m=float(requested_spacing_m),
        actual_spacing_m=actual_spacing_m,
        node_count_x=2 * half_cells_x + 1,
        node_count_y=2 * half_cells_y + 1,
    )


def _component(vector: Any, name: str) -> int:
    """Read a vector component exposed as either an attribute or method."""

    value = getattr(vector, name)
    return int(value() if callable(value) else value)


def _unpack_node_level(node_level: Any) -> tuple[Any, float]:
    """Unpack a Chrono NodeLevel represented as a pair object or sequence."""

    if hasattr(node_level, "first") and hasattr(node_level, "second"):
        first = node_level.first
        second = node_level.second
        return (
            first() if callable(first) else first,
            float(second() if callable(second) else second),
        )

    if isinstance(node_level, Sequence) and len(node_level) == 2:
        return node_level[0], float(node_level[1])

    raise TypeError(
        "Expected each modified SCM node to be a two-item sequence or an "
        "object exposing 'first' and 'second'."
    )


def collect_deformation_records(
    modified_nodes: Iterable[Any],
    grid_spacing_m: float,
    initial_height_at: Callable[[float, float], float] | None = None,
    world_position_at: Callable[[float, float], tuple[float, float]] | None = None,
) -> list[DeformationRecord]:
    """Convert Chrono modified-node values into deterministic plain records.

    Chrono reports a grid coordinate and final node height relative to the SCM
    reference plane for each modified node. Grid coordinates are converted to
    metres in that reference frame. For the default horizontal SCM frame used
    by the project demos, these are also world X and Y coordinates. Callers
    using a transformed SCM frame can supply ``world_position_at``. Any
    ``initial_height_at`` callback must return a height relative to the same SCM
    reference plane as the final node height.
    """

    if grid_spacing_m <= 0:
        raise ValueError("grid_spacing_m must be greater than zero")

    initial_height_at = initial_height_at or (lambda _x, _y: 0.0)
    world_position_at = world_position_at or (lambda x, y: (x, y))

    records: list[DeformationRecord] = []
    for node_level in modified_nodes:
        grid_position, final_height = _unpack_node_level(node_level)
        grid_x = _component(grid_position, "x")
        grid_y = _component(grid_position, "y")
        scm_x = grid_x * grid_spacing_m
        scm_y = grid_y * grid_spacing_m
        world_x, world_y = world_position_at(scm_x, scm_y)
        initial_height = float(initial_height_at(scm_x, scm_y))
        height_change = final_height - initial_height

        records.append(
            DeformationRecord(
                grid_x=grid_x,
                grid_y=grid_y,
                world_x_m=float(world_x),
                world_y_m=float(world_y),
                initial_height_m=initial_height,
                final_height_m=final_height,
                height_change_m=height_change,
                sinkage_m=max(-height_change, 0.0),
            )
        )

    return sorted(records, key=lambda record: (record.grid_x, record.grid_y))


def calculate_deformation_summary(
    records: Iterable[DeformationRecord],
) -> dict[str, float | int]:
    """Calculate summary metrics, treating sinkage as positive downward."""

    record_list = list(records)
    sinkages = [record.sinkage_m for record in record_list]

    return {
        "modified_node_count": len(record_list),
        "maximum_sinkage_m": max(sinkages, default=0.0),
        "mean_sinkage_m": fmean(sinkages) if sinkages else 0.0,
    }


def write_deformation_export(
    records: Iterable[DeformationRecord],
    output_directory: str | Path,
    simulation_settings: Mapping[str, Any],
) -> tuple[Path, Path]:
    """Write deformation records to CSV and metrics/settings to JSON."""

    record_list = sorted(records, key=lambda record: (record.grid_x, record.grid_y))
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    csv_path = output_path / CSV_FILENAME
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(record) for record in record_list)

    summary = {
        "format_version": 1,
        **calculate_deformation_summary(record_list),
        "simulation_settings": dict(simulation_settings),
    }
    summary_path = output_path / SUMMARY_FILENAME
    with summary_path.open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, sort_keys=True)
        summary_file.write("\n")

    return csv_path, summary_path
