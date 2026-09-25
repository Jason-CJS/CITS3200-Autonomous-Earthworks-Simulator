"""Load and summarise previously-generated simulation output files.

This module reads the JSON files already produced by the project's
exporters (``deformation_summary.json``, ``hole_fill_summary.json``, GOOSE
``scene.json``) so they can be listed and inspected without re-running the
simulation that produced them. It never imports PyChrono.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFORMATION_SUMMARY = "deformation_summary"
HOLE_FILL_SUMMARY = "hole_fill_summary"
GOOSE_SCENE = "goose_scene"
UNKNOWN = "unknown"

KNOWN_FILENAMES = (
    "deformation_summary.json",
    "hole_fill_summary.json",
    "scene.json",
)


@dataclass(frozen=True)
class OutputRecord:
    """A single loaded output file, or a placeholder describing why it failed."""

    path: Path
    kind: str
    format_version: int | None
    summary: str
    data: dict[str, Any] | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def detect_output_kind(data: dict[str, Any]) -> str:
    """Identify which exporter produced this JSON, based on its shape."""

    if "hole_metrics" in data and "acceptance_thresholds" in data:
        return HOLE_FILL_SUMMARY
    if "modified_node_count" in data and "simulation_settings" in data:
        return DEFORMATION_SUMMARY
    if "heightmap" in data and "source" in data and "grid" in data:
        return GOOSE_SCENE
    return UNKNOWN


def _nested_dict(value: Any) -> dict[str, Any]:
    """Return ``value`` if it is a dict, otherwise an empty dict.

    JSON fields are sometimes present but set to ``null`` rather than
    omitted. ``dict.get(key, {})`` only supplies its default when the key is
    absent, so a null nested object would otherwise reach ``.get`` calls as
    ``None`` and raise ``AttributeError``.
    """

    return value if isinstance(value, dict) else {}


def _summarise(kind: str, data: dict[str, Any]) -> str:
    if kind == HOLE_FILL_SUMMARY:
        status = "PASSED" if data.get("passed") else "FAILED"
        metrics = _nested_dict(data.get("hole_metrics"))
        increase_mm = metrics.get("average_height_increase_m", 0.0) * 1000
        return (
            f"{status} - {data.get('scenario', 'scenario')}, "
            f"hole height +{increase_mm:.2f} mm, "
            f"{data.get('modified_node_count', 0)} nodes modified"
        )

    if kind == DEFORMATION_SUMMARY:
        return (
            f"{data.get('modified_node_count', 0)} nodes modified, "
            f"mean sinkage {data.get('mean_sinkage_m', 0.0) * 1000:.2f} mm"
        )

    if kind == GOOSE_SCENE:
        source = _nested_dict(data.get("source"))
        quality = _nested_dict(data.get("quality"))
        return (
            f"{source.get('scenario', 'unknown scenario')}, "
            f"{quality.get('preset', 'unknown')} quality, "
            f"{data.get('size_x', '?')}m x {data.get('size_y', '?')}m"
        )

    return "unrecognised output file"


KIND_LABELS = {
    HOLE_FILL_SUMMARY: "hole-fill result",
    DEFORMATION_SUMMARY: "deformation export",
    GOOSE_SCENE: "goose scene",
    UNKNOWN: "unrecognised",
}

KIND_TITLES = {
    HOLE_FILL_SUMMARY: "Bulldozer hole-fill result",
    DEFORMATION_SUMMARY: "Terrain deformation export",
    GOOSE_SCENE: "GOOSE terrain scene",
}


def _format_hole_fill_report(data: dict[str, Any]) -> list[str]:
    status = "PASSED" if data.get("passed") else "FAILED"
    metrics = _nested_dict(data.get("hole_metrics"))
    thresholds = _nested_dict(data.get("acceptance_thresholds"))
    return [
        f"Scenario: {data.get('scenario', 'unknown')}",
        f"Result:   {status}",
        "",
        "Hole metrics:",
        f"  Initial average height   {metrics.get('initial_average_height_m', 0.0) * 1000:>8.2f} mm",
        f"  Final average height     {metrics.get('final_average_height_m', 0.0) * 1000:>8.2f} mm",
        f"  Average height increase  {metrics.get('average_height_increase_m', 0.0) * 1000:>+8.2f} mm",
        f"  Nodes modified in hole   {metrics.get('modified_node_count_in_hole', 0):>8} / {metrics.get('hole_node_count', 0)}",
        "",
        "Acceptance thresholds:",
        f"  Minimum height increase  {thresholds.get('minimum_average_height_increase_m', 0.0) * 1000:>8.2f} mm",
        f"  Minimum modified nodes   {thresholds.get('minimum_modified_nodes_in_hole', 0):>8}",
        "",
        f"Total modified nodes (whole terrain): {data.get('modified_node_count', 0)}",
    ]


def _format_deformation_report(data: dict[str, Any]) -> list[str]:
    return [
        f"Modified nodes:  {data.get('modified_node_count', 0)}",
        f"Mean sinkage:    {data.get('mean_sinkage_m', 0.0) * 1000:.2f} mm",
        f"Maximum sinkage: {data.get('maximum_sinkage_m', 0.0) * 1000:.2f} mm",
    ]


def _format_goose_scene_report(data: dict[str, Any]) -> list[str]:
    source = _nested_dict(data.get("source"))
    quality = _nested_dict(data.get("quality"))
    resolved = _nested_dict(quality.get("resolved"))
    grid = _nested_dict(data.get("grid"))
    return [
        f"Scenario:      {source.get('scenario', 'unknown')} ({source.get('split', 'unknown')} split)",
        f"Quality:       {quality.get('preset', 'unknown')} preset",
        f"Resolution:    {resolved.get('terrain_resolution', '?')} m",
        f"Grid spacing:  {resolved.get('scm_grid_spacing', '?')} m",
        f"Size:          {data.get('size_x', '?')} m x {data.get('size_y', '?')} m",
        f"Height range:  {data.get('height_min', 0.0):.2f} m to {data.get('height_max', 0.0):.2f} m",
        f"Grid nodes:    {grid.get('width', '?')} x {grid.get('height', '?')}",
    ]


def format_report(record: "OutputRecord") -> str:
    """Render a labelled, unit-formatted report for a loaded output record."""

    if not record.ok:
        return f"Could not read {record.path}\n  {record.error}"

    data = record.data or {}
    title = KIND_TITLES.get(record.kind, "Unrecognised output file")
    lines = [title, f"File: {record.path}", ""]

    if record.kind == HOLE_FILL_SUMMARY:
        lines.extend(_format_hole_fill_report(data))
    elif record.kind == DEFORMATION_SUMMARY:
        lines.extend(_format_deformation_report(data))
    elif record.kind == GOOSE_SCENE:
        lines.extend(_format_goose_scene_report(data))
    else:
        lines.append("This file's contents were not recognised as a known output format.")

    return "\n".join(lines)


def load_output_file(path: str | Path) -> OutputRecord:
    """Load and classify a single output JSON file.

    Never raises: unreadable or malformed files are returned as an
    ``OutputRecord`` with ``error`` set, so callers can skip and warn rather
    than crashing a batch listing.
    """

    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return OutputRecord(path, UNKNOWN, None, "", None, error=f"could not read file: {exc}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return OutputRecord(path, UNKNOWN, None, "", None, error=f"invalid JSON: {exc}")

    if not isinstance(data, dict):
        return OutputRecord(path, UNKNOWN, None, "", None, error="expected a JSON object at the top level")

    kind = detect_output_kind(data)
    format_version = data.get("format_version")
    summary = _summarise(kind, data) if kind != UNKNOWN else "unrecognised output file"

    return OutputRecord(path, kind, format_version, summary, data)


def discover_output_files(root: str | Path) -> list[Path]:
    """Find known output JSON files anywhere under ``root``, sorted by path."""

    root = Path(root)
    if not root.exists():
        return []

    found: list[Path] = []
    for filename in KNOWN_FILENAMES:
        found.extend(root.rglob(filename))
    return sorted(set(found))


def load_output_directory(root: str | Path) -> list[OutputRecord]:
    """Discover and load every known output file under ``root``."""

    return [load_output_file(path) for path in discover_output_files(root)]
