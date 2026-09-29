"""Create Chrono vegetation objects from exported GOOSE placements.

This module supports:

1. Generic vegetation markers generated from coarse vegetation labels.
2. Detailed tree objects generated from fine semantic tree_trunk labels.

Tree positions come from the GOOSE semantic data.

Each detailed tree uses:
- a simple cylindrical Chrono body for the trunk/physics representation;
- a detailed Beech or Oak OBJ mesh for visualization.

The visual tree mesh is attached to the trunk body. This keeps the
physics representation simple while allowing a more detailed tree
appearance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pychrono as chrono


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

VEGETATION_DIRECTORY = Path(
    __file__
).resolve().parent

TREE_ASSET_DIRECTORY = (
    VEGETATION_DIRECTORY
    / "assets"
    / "trees"
)

BEECH_TREE_PATH = (
    TREE_ASSET_DIRECTORY
    / "beech"
    / "beech_tree.obj"
)

OAK_TREE_PATH = (
    TREE_ASSET_DIRECTORY
    / "oak"
    / "oak_tree.obj"
)


# ---------------------------------------------------------------------
# Generic vegetation marker settings
# ---------------------------------------------------------------------

DEFAULT_MARKER_RADIUS = 0.15
DEFAULT_MARKER_HEIGHT = 2.5
DEFAULT_MARKER_DENSITY = 700.0


# ---------------------------------------------------------------------
# Tree physics settings
# ---------------------------------------------------------------------

DEFAULT_TREE_TRUNK_RADIUS = 0.20
DEFAULT_TREE_TRUNK_DENSITY = 700.0


# Approximate visual model heights after conversion:
#
# Beech:
#     3.80 m
#
# Oak:
#     8.83 m
#
# The physics cylinder represents only the main trunk rather than
# the complete visual model.

BEECH_TRUNK_HEIGHT = 2.3
OAK_TRUNK_HEIGHT = 4.5


# ---------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------

def load_json(
    path: Path,
) -> dict:
    """Load a JSON file."""

    path = (
        Path(path)
        .expanduser()
        .resolve()
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"JSON file not found: "
            f"{path}"
        )

    with path.open(
        encoding="utf-8"
    ) as source:
        return json.load(
            source
        )


def load_vegetation_placements(
    placement_path: Path,
) -> dict:
    """Load generic vegetation placements."""

    data = load_json(
        placement_path
    )

    if "placements" not in data:
        raise ValueError(
            "Vegetation placement file "
            "does not contain a "
            "'placements' list."
        )

    return data


def load_tree_placements(
    placement_path: Path,
) -> dict:
    """Load trunk-derived tree placements."""

    data = load_json(
        placement_path
    )

    if "trees" not in data:
        raise ValueError(
            "Tree placement file "
            "does not contain a "
            "'trees' list."
        )

    return data


# ---------------------------------------------------------------------
# Visual helpers
# ---------------------------------------------------------------------

def set_body_color(
    body: chrono.ChBody,
    red: float,
    green: float,
    blue: float,
) -> None:
    """Set the color of the body's first visual shape."""

    shape = body.GetVisualShape(
        0
    )

    if shape is not None:
        shape.SetColor(
            chrono.ChColor(
                red,
                green,
                blue,
            )
        )


def load_visual_mesh(
    mesh_path: Path,
) -> chrono.ChVisualShapeTriangleMesh:
    """Load an OBJ file as a Chrono visual triangle mesh."""

    mesh_path = (
        Path(mesh_path)
        .expanduser()
        .resolve()
    )

    if not mesh_path.is_file():
        raise FileNotFoundError(
            f"Tree OBJ not found: "
            f"{mesh_path}"
        )

    triangle_mesh = (
        chrono.ChTriangleMeshConnected()
    )

    triangle_mesh.LoadWavefrontMesh(
        str(mesh_path),
        False,
        True,
    )

    visual_shape = (
        chrono.ChVisualShapeTriangleMesh()
    )

    visual_shape.SetMesh(
        triangle_mesh
    )

    return visual_shape


# ---------------------------------------------------------------------
# Generic vegetation
# ---------------------------------------------------------------------

def create_vegetation_marker(
    system: chrono.ChSystemSMC,
    x: float,
    y: float,
    z: float,
    radius: float = DEFAULT_MARKER_RADIUS,
    height: float = DEFAULT_MARKER_HEIGHT,
    density: float = DEFAULT_MARKER_DENSITY,
) -> chrono.ChBody:
    """Create one generic vegetation marker."""

    body = chrono.ChBodyEasyCylinder(
        chrono.ChAxis_Z,
        radius,
        height,
        density,
        True,
        False,
    )

    body.SetFixed(
        True
    )

    body.SetPos(
        chrono.ChVector3d(
            float(x),
            float(y),
            float(z)
            + height / 2.0,
        )
    )

    body.SetName(
        "goose_vegetation_marker"
    )

    set_body_color(
        body,
        0.30,
        0.55,
        0.20,
    )

    system.Add(
        body
    )

    return body


def create_vegetation_markers(
    system: chrono.ChSystemSMC,
    placement_path: Path,
    radius: float = DEFAULT_MARKER_RADIUS,
    height: float = DEFAULT_MARKER_HEIGHT,
    density: float = DEFAULT_MARKER_DENSITY,
) -> list:
    """Create all generic vegetation markers."""

    data = load_vegetation_placements(
        placement_path
    )

    bodies = []

    for placement in data[
        "placements"
    ]:

        body = create_vegetation_marker(
            system=system,
            x=placement["x"],
            y=placement["y"],
            z=placement["z"],
            radius=radius,
            height=height,
            density=density,
        )

        bodies.append(
            body
        )

    return bodies


# ---------------------------------------------------------------------
# Detailed GOOSE trees
# ---------------------------------------------------------------------

def choose_tree_asset(
    tree_id: int,
) -> tuple[str, Path, float]:
    """Choose a deterministic visual tree model.

    Odd tree IDs use the Beech model.
    Even tree IDs use the Oak model.

    The GOOSE semantic data determines tree placement, but it does not
    determine whether a particular tree is Beech or Oak. The alternating
    species assignment is therefore only a visual choice.
    """

    if tree_id % 2 == 1:
        return (
            "beech",
            BEECH_TREE_PATH,
            BEECH_TRUNK_HEIGHT,
        )

    return (
        "oak",
        OAK_TREE_PATH,
        OAK_TRUNK_HEIGHT,
    )


def create_tree(
    system: chrono.ChSystemSMC,
    tree: dict,
) -> chrono.ChBody:
    """Create one detailed GOOSE tree.

    The tree uses a simple cylinder as its current physics
    representation and a detailed OBJ model as its visual
    representation.
    """

    tree_id = int(
        tree["tree_id"]
    )

    x = float(
        tree["x"]
    )

    y = float(
        tree["y"]
    )

    ground_z = float(
        tree["z"]
    )

    (
        species,
        mesh_path,
        trunk_height,
    ) = choose_tree_asset(
        tree_id
    )

    # -----------------------------------------------------------------
    # Simplified physics trunk
    # -----------------------------------------------------------------

    trunk = chrono.ChBodyEasyCylinder(
        chrono.ChAxis_Z,
        DEFAULT_TREE_TRUNK_RADIUS,
        trunk_height,
        DEFAULT_TREE_TRUNK_DENSITY,
        True,
        False,
    )

    trunk.SetFixed(
        True
    )

    # ChBodyEasyCylinder is centred around the body's origin.
    #
    # The body is therefore positioned half the trunk height above the
    # GOOSE terrain position so that the bottom of the cylinder touches
    # the terrain.

    trunk.SetPos(
        chrono.ChVector3d(
            x,
            y,
            ground_z
            + trunk_height / 2.0,
        )
    )

    trunk.SetName(
        f"goose_tree_"
        f"{tree_id}_"
        f"{species}"
    )

    # Brown debug representation of the physics trunk.
    set_body_color(
        trunk,
        0.36,
        0.20,
        0.08,
    )

    # -----------------------------------------------------------------
    # Detailed visual tree
    # -----------------------------------------------------------------

    visual_shape = load_visual_mesh(
        mesh_path
    )

    # The converted OBJ has its base at local Z = 0.
    #
    # The Chrono body origin is halfway up the simplified physics trunk.
    # Therefore the visual mesh is shifted downward by half the trunk
    # height so that its base coincides with the GOOSE terrain position.

    visual_frame = chrono.ChFramed(
        chrono.ChVector3d(
            0.0,
            0.0,
            -trunk_height / 2.0,
        ),
        chrono.QUNIT,
    )

    trunk.AddVisualShape(
        visual_shape,
        visual_frame,
    )

    system.Add(
        trunk
    )

    return trunk


def create_trees(
    system: chrono.ChSystemSMC,
    placement_path: Path,
) -> list:
    """Create all trunk-derived detailed GOOSE trees."""

    data = load_tree_placements(
        placement_path
    )

    trees = []

    for tree_data in data[
        "trees"
    ]:

        tree = create_tree(
            system=system,
            tree=tree_data,
        )

        trees.append(
            tree
        )

    return trees
