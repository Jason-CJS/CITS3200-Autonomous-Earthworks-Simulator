"""Export trunk-derived GOOSE tree placements to JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(REPO_ROOT),
    )


from environments.vegetation.goose_tree_placement import (
    generate_tree_placements,
)


def export_trees(
    scene_path: Path,
    output_path: Path | None = None,
) -> Path:
    """Generate and export trunk-derived tree placements."""

    scene_path = (
        Path(scene_path)
        .expanduser()
        .resolve()
    )

    trees = generate_tree_placements(
        scene_path
    )

    if output_path is None:
        output_path = (
            scene_path.parent
            / "tree_placements.json"
        )
    else:
        output_path = (
            Path(output_path)
            .expanduser()
            .resolve()
        )

    export_data = {
        "source_scene": scene_path.parent.name,
        "scene_manifest": scene_path.name,
        "method": (
            "connected tree_trunk semantic regions"
        ),
        "connectivity": 4,
        "tree_count": len(trees),
        "trees": trees,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as destination:
        json.dump(
            export_data,
            destination,
            indent=2,
        )

    print(
        f"Source scene: "
        f"{scene_path.parent.name}"
    )

    print(
        "Placement method: "
        "connected tree_trunk regions"
    )

    print(
        f"Tree placements: "
        f"{len(trees)}"
    )

    print(
        f"Exported to: "
        f"{output_path}"
    )

    return output_path


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Export GOOSE tree placements "
            "derived from fine semantic "
            "tree_trunk labels."
        )
    )

    parser.add_argument(
        "scene",
        type=Path,
        help="Path to scene.json.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional output JSON path. "
            "Defaults to tree_placements.json "
            "next to scene.json."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Export tree placements."""

    args = parse_arguments()

    export_trees(
        scene_path=args.scene,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
