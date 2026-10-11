"""Export label-derived GOOSE vegetation placements to JSON."""

import argparse
import json
import sys
from pathlib import Path


# Allow imports from the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(REPO_ROOT),
    )


from environments.vegetation.goose_vegetation import (
    generate_vegetation_placements,
    load_goose_scene,
)


def export_vegetation(
    scene_path,
    placement_spacing,
    output_path=None,
):
    """Generate and export vegetation placements."""

    scene_path = Path(scene_path)

    data = load_goose_scene(
        scene_path
    )

    placements = generate_vegetation_placements(
        data["semantic_map"],
        data["height_grid"],
        data["vegetation_class"],
        data["x_spacing"],
        data["y_spacing"],
        data["xmin"],
        data["ymax"],
        placement_spacing,
    )

    if output_path is None:
        output_path = (
            scene_path.parent
            / "vegetation_placements.json"
        )
    else:
        output_path = Path(
            output_path
        )

    export_data = {
        "source_scene": scene_path.parent.name,
        "scene_manifest": scene_path.name,
        "vegetation_class": data[
            "vegetation_class"
        ],
        "placement_spacing_metres": (
            placement_spacing
        ),
        "placement_count": len(
            placements
        ),
        "grid": {
            "x_spacing": data[
                "x_spacing"
            ],
            "y_spacing": data[
                "y_spacing"
            ],
            "xmin": data[
                "xmin"
            ],
            "ymax": data[
                "ymax"
            ],
        },
        "placements": placements,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            export_data,
            file,
            indent=2,
        )

    print(
        f"Source scene: "
        f"{scene_path.parent.name}"
    )

    print(
        f"Placement spacing: "
        f"{placement_spacing:.2f} m"
    )

    print(
        f"Vegetation placements: "
        f"{len(placements)}"
    )

    print(
        f"Exported to: "
        f"{output_path}"
    )

    return output_path


def parse_arguments():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Export label-derived GOOSE "
            "vegetation placements to JSON."
        )
    )

    parser.add_argument(
        "scene",
        type=Path,
        help=(
            "Path to a generated "
            "GOOSE scene.json."
        ),
    )

    parser.add_argument(
        "--spacing",
        type=float,
        default=3.0,
        help=(
            "Approximate vegetation placement "
            "spacing in metres "
            "(default: 3.0)."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional output JSON path. "
            "By default the file is written "
            "next to scene.json."
        ),
    )

    return parser.parse_args()


def main():
    """Generate and export vegetation placements."""

    args = parse_arguments()

    export_vegetation(
        args.scene,
        args.spacing,
        args.output,
    )


if __name__ == "__main__":
    main()
