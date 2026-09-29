"""Create simple Chrono vegetation objects from exported GOOSE placements.

This module provides a first integration between the label-derived
vegetation placement system and the Project Chrono simulation.

The initial vegetation representation is intentionally simple:
each placement is represented by a fixed vertical cylinder.

These cylinders are temporary visual markers used to verify that
GOOSE-derived vegetation coordinates align correctly with the
generated SCM terrain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pychrono as chrono


DEFAULT_TRUNK_RADIUS = 0.15
DEFAULT_TRUNK_HEIGHT = 2.5
DEFAULT_TRUNK_DENSITY = 700.0


def load_vegetation_placements(
    placement_path: Path,
) -> dict:
    """Load an exported vegetation_placements.json file."""

    placement_path = Path(placement_path)

    if not placement_path.is_file():
        raise FileNotFoundError(
            f"Vegetation placement file not found: "
            f"{placement_path}"
        )

    with placement_path.open(
        encoding="utf-8"
    ) as source:
        data = json.load(source)

    if "placements" not in data:
        raise ValueError(
            "Vegetation placement file does not contain "
            "a 'placements' list."
        )

    return data


def create_tree_marker(
    system: chrono.ChSystemSMC,
    x: float,
    y: float,
    z: float,
    radius: float = DEFAULT_TRUNK_RADIUS,
    height: float = DEFAULT_TRUNK_HEIGHT,
    density: float = DEFAULT_TRUNK_DENSITY,
) -> chrono.ChBody:
    """Create one fixed vertical cylinder representing a tree.

    The exported vegetation Z coordinate represents terrain height.
    Chrono positions the cylinder using its centre, so half of the
    trunk height is added to Z.
    """

    body = chrono.ChBodyEasyCylinder(
        chrono.ChAxis_Z,
        radius,
        height,
        density,
        True,
        False,
    )

    body.SetFixed(True)

    body.SetPos(
        chrono.ChVector3d(
            float(x),
            float(y),
            float(z) + height / 2.0,
        )
    )

    body.SetName("goose_vegetation_marker")

    system.Add(body)

    return body


def create_vegetation_markers(
    system: chrono.ChSystemSMC,
    placement_path: Path,
    radius: float = DEFAULT_TRUNK_RADIUS,
    height: float = DEFAULT_TRUNK_HEIGHT,
    density: float = DEFAULT_TRUNK_DENSITY,
) -> list:
    """Create tree markers for all exported vegetation placements."""

    data = load_vegetation_placements(
        placement_path
    )

    placements = data["placements"]

    bodies = []

    for placement in placements:
        body = create_tree_marker(
            system=system,
            x=placement["x"],
            y=placement["y"],
            z=placement["z"],
            radius=radius,
            height=height,
            density=density,
        )

        bodies.append(body)

    return bodies
