"""Preview GOOSE terrain, trees, rural vegetation, and rocks.

Run from the repository root:

    python scripts/preview_goose_rural.py --scene outputs/goose/SCENE_NAME/scene.json

The scene directory must contain rural_placements.json.
tree_placements.json is optional.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pychrono as chrono

# Allow running this script directly from the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from environments.terrain import goose_environment
from environments.vegetation.goose_rural_objects import create_rural_objects
from environments.vegetation.goose_vegetation_objects import create_trees
from vehicles.bulldozer.articulation.bulldozer_model import BulldozerModel
from src.demo_common import create_visual_system


DEFAULT_SCENE = (
    "outputs/goose/"
    "alice_scenario02_sequence07_0000_1697208271047525000/"
    "scene.json"
)

DEFAULT_CONFIG = "environments/scene_config/alice_scm.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Preview rural vegetation and rocks in a GOOSE scene."
    )

    parser.add_argument(
        "--scene",
        type=Path,
        default=Path(DEFAULT_SCENE),
        help="Path to a generated GOOSE scene.json file.",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(DEFAULT_CONFIG),
        help="Path to the Chrono terrain configuration JSON.",
    )

    parser.add_argument(
        "--no-trees",
        action="store_true",
        help="Skip loading existing trees.",
    )

    parser.add_argument(
        "--no-bulldozer",
        action="store_true",
        help="Skip loading the stationary bulldozer.",
    )

    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    """Resolve relative paths from the repository root."""
    path = path.expanduser()

    if not path.is_absolute():
        path = REPO_ROOT / path

    return path.resolve()


def read_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Required file not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def terrain_height_at_origin(scene: dict, scene_dir: Path) -> float:
    """Read terrain height near world position (0, 0)."""

    height_path = Path(scene["height_grid"])

    if not height_path.is_absolute():
        height_path = scene_dir / height_path

    heights = np.load(height_path)

    bounds = scene["bounds_xy"]
    grid = scene["grid"]

    column = round(
        (0.0 - bounds["xmin"]) / grid["x_spacing"]
    )

    row = round(
        (bounds["ymax"] - 0.0) / grid["y_spacing"]
    )

    # Handle scenes that do not include the world origin.
    row = max(0, min(row, heights.shape[0] - 1))
    column = max(0, min(column, heights.shape[1] - 1))

    return float(heights[row, column])


def main():
    args = parse_args()

    scene_path = resolve_path(args.scene)
    config_path = resolve_path(args.config)

    scene_dir = scene_path.parent
    rural_path = scene_dir / "rural_placements.json"
    tree_path = scene_dir / "tree_placements.json"

    scene = read_json(scene_path)
    config = read_json(config_path)
    rural_data = read_json(rural_path)

    placements = rural_data["placements"]

    system = goose_environment.create_system()

    # Load terrain.
    goose_environment.create_terrain(
        system,
        scene_path,
        scene,
        config,
    )

    # Load rural vegetation and rocks.
    rural_objects = create_rural_objects(system, rural_path)

    # Existing Beech/Oak trees are optional.
    trees = []

    if not args.no_trees:
        if tree_path.is_file():
            trees = create_trees(system, tree_path)
        else:
            print(
                f"Tree placements not found: {tree_path}\n"
                "Continuing without trees."
            )

    # Stationary bulldozer for visual scale reference.
    bulldozer_loaded = False

    if not args.no_bulldozer:
        start_height = terrain_height_at_origin(scene, scene_dir)

        bulldozer = BulldozerModel(
            system,
            show_rigid_ground=False,
            initial_z_offset=start_height - 0.15,
        )

        bulldozer.set_drive_speeds(0.0, 0.0)
        bulldozer_loaded = True

    counts = Counter(
        placement["asset_type"]
        for placement in placements
    )

    print("\n--- GOOSE Rural Visualization ---")
    print("Scene:", scene_path)
    print("Rural objects:", len(rural_objects))
    print("Trees:", len(trees))
    print("Bulldozer:", "loaded" if bulldozer_loaded else "disabled")
    print("Types:", dict(counts))

    print("\nClose the visualization window when finished.", flush=True)

    visual = create_visual_system(
        system,
        "GOOSE-Ex Rural Vegetation and Rocks",
        chrono.ChVector3d(8, -12, 8),
        chrono.ChVector3d(0, 0, 0),
        balanced_lighting=True,
    )

    # Static preview: no physics steps.
    while visual.Run():
        visual.BeginScene()
        visual.Render()
        visual.EndScene()


if __name__ == "__main__":
    main()
