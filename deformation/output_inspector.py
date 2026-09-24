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


def _summarise(kind: str, data: dict[str, Any]) -> str:
    if kind == HOLE_FILL_SUMMARY:
        status = "PASSED" if data.get("passed") else "FAILED"
        metrics = data.get("hole_metrics", {})
        increase_mm = metrics.get("average_height_increase_m", 0.0) * 1000
        return (
            f"{data.get('scenario', 'scenario')}: {status}, "
            f"hole height +{increase_mm:.2f} mm, "
            f"{data.get('modified_node_count', 0)} nodes modified"
        )

    if kind == DEFORMATION_SUMMARY:
        return (
            f"deformation export: {data.get('modified_node_count', 0)} nodes modified, "
            f"mean sinkage {data.get('mean_sinkage_m', 0.0) * 1000:.2f} mm"
        )

    if kind == GOOSE_SCENE:
        source = data.get("source", {})
        quality = data.get("quality", {})
        return (
            f"GOOSE scene: {source.get('scenario', 'unknown scenario')} "
            f"({quality.get('preset', 'unknown')} quality, "
            f"{data.get('size_x', '?')}m x {data.get('size_y', '?')}m)"
        )

    return "unrecognised output file"


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
