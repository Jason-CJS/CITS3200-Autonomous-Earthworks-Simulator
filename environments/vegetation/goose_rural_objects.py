"""Load lightweight rural vegetation and rock visuals into Project Chrono."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pychrono as chrono


ASSET_DIRECTORY = Path(__file__).resolve().parent / "assets" / "rural"

ASSET_PATHS = {
    "low_grass_patch": ASSET_DIRECTORY / "low_grass_patch/low_grass_patch.obj",
    "tall_wild_grass": ASSET_DIRECTORY / "tall_wild_grass/tall_wild_grass.obj",
    "scrub_bush": ASSET_DIRECTORY / "scrub_bush/scrub_bush.obj",
    "rural_hedge": ASSET_DIRECTORY / "rural_hedge/rural_hedge.obj",
    "broadleaf_sapling": ASSET_DIRECTORY / "broadleaf_sapling/broadleaf_sapling.obj",
}

ROCK_PATHS = [
    ASSET_DIRECTORY / "rocks" / f"rock_{i:02d}.obj"
    for i in range(1, 7)
]

ROCK_TEXTURE = ASSET_DIRECTORY / "rocks" / "RocksCollection.png"

# Final rock widths in metres.
ROCK_SIZE_RANGES = {
    "pebble": (0.05, 0.12),
    "small_rock": (0.15, 0.25),
    "large_rock": (0.30, 0.45),
}

# Cache mesh bounds so we do not reload geometry just to measure it.
MESH_BOUNDS = {}


def _get_mesh_bounds(mesh_path: Path) -> tuple[float, float]:
    """Return the horizontal width and minimum Z coordinate of a mesh."""

    mesh_path = Path(mesh_path)

    if mesh_path not in MESH_BOUNDS:
        if not mesh_path.is_file():
            raise FileNotFoundError(f"Rural asset not found: {mesh_path}")

        mesh = chrono.ChTriangleMeshConnected()
        mesh.LoadWavefrontMesh(str(mesh_path), False, True)

        vertices = mesh.GetCoordsVertices()

        if len(vertices) == 0:
            raise ValueError(f"Empty mesh: {mesh_path}")

        xs = [vertex.x for vertex in vertices]
        ys = [vertex.y for vertex in vertices]
        zs = [vertex.z for vertex in vertices]

        width = max(
            max(xs) - min(xs),
            max(ys) - min(ys),
        )

        if width <= 0:
            raise ValueError(f"Invalid mesh width: {mesh_path}")

        MESH_BOUNDS[mesh_path] = (width, min(zs))

    return MESH_BOUNDS[mesh_path]


def _load_visual_shape(
    mesh_path: Path,
    scale: float,
) -> chrono.ChVisualShapeTriangleMesh:
    """Create a scaled visual-only mesh from an OBJ asset."""

    if not mesh_path.is_file():
        raise FileNotFoundError(f"Rural asset not found: {mesh_path}")

    mesh = chrono.ChTriangleMeshConnected()
    mesh.LoadWavefrontMesh(str(mesh_path), False, True)

    shape = chrono.ChVisualShapeTriangleMesh()
    shape.SetMesh(mesh)
    shape.SetScale(chrono.ChVector3d(scale, scale, scale))

    if mesh_path.parent.name == "rocks" and ROCK_TEXTURE.is_file():
        shape.SetTexture(str(ROCK_TEXTURE))

    return shape


def _rock_size_category(index: int, total: int) -> str:
    """Choose a reproducible mix of pebble, small and large rock sizes."""

    if total <= 0:
        raise ValueError("Rock total must be positive")

    if index < 0 or index >= total:
        raise ValueError("Rock index is out of range")

    pebble_count = round(total * 0.70)
    small_count = round(total * 0.25)

    # Prevent rounded counts from exceeding the total.
    small_count = min(small_count, total - pebble_count)

    if index < pebble_count:
        return "pebble"

    if index < pebble_count + small_count:
        return "small_rock"

    return "large_rock"


def create_rural_object(
    system: chrono.ChSystem,
    placement: dict,
    rock_index: int = 0,
    rock_total: int = 1,
    seed: int = 38,
) -> chrono.ChBody:
    """Create one fixed, noncolliding rural visual object."""

    asset_type = placement["asset_type"]
    variation = float(placement.get("scale", 1.0))

    if variation <= 0:
        raise ValueError("Object scale must be positive")

    if asset_type == "rock":
        mesh_path = ROCK_PATHS[rock_index % len(ROCK_PATHS)]

        category = _rock_size_category(rock_index, rock_total)
        lower, upper = ROCK_SIZE_RANGES[category]

        # Choose a deterministic final width in metres.
        rng = random.Random(seed + rock_index)
        target_width = rng.uniform(lower, upper)

        mesh_width, min_z = _get_mesh_bounds(mesh_path)

        # Scale each rock to its chosen physical width.
        # Rocks intentionally do not apply the generic placement scale
        # again, so they remain inside their size category.
        scale = target_width / mesh_width

        # Align the rock's lowest vertex with the terrain height.
        ground_offset = -min_z * scale

    else:
        if asset_type not in ASSET_PATHS:
            raise ValueError(f"Unknown rural asset type: {asset_type}")

        mesh_path = ASSET_PATHS[asset_type]
        scale = variation
        ground_offset = 0.0

    angle = math.radians(float(placement.get("rotation_z", 0.0)))

    body = chrono.ChBody()
    body.SetFixed(True)
    body.EnableCollision(False)

    body.SetPos(
        chrono.ChVector3d(
            float(placement["x"]),
            float(placement["y"]),
            float(placement["z"]) + ground_offset,
        )
    )

    body.SetRot(chrono.QuatFromAngleZ(angle))
    body.SetName(f"goose_rural_{asset_type}")

    body.AddVisualShape(_load_visual_shape(mesh_path, scale))
    system.Add(body)

    return body


def create_rural_objects(
    system: chrono.ChSystem,
    placement_path: Path,
) -> list[chrono.ChBody]:
    """Load rural placements and create their visual objects."""

    placement_path = Path(placement_path).expanduser().resolve()
    data = json.loads(placement_path.read_text(encoding="utf-8"))

    placements = data["placements"]
    objects = []

    rock_total = sum(
        placement["asset_type"] == "rock"
        for placement in placements
    )

    rock_index = 0
    seed = int(data.get("seed", 38))

    for placement in placements:
        obj = create_rural_object(
            system,
            placement,
            rock_index=rock_index,
            rock_total=rock_total if placement["asset_type"] == "rock" else 1,
            seed=seed,
        )

        objects.append(obj)

        if placement["asset_type"] == "rock":
            rock_index += 1

    return objects
