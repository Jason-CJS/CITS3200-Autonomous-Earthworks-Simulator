#!/usr/bin/env python3
"""Discover labelled GOOSE/GOOSE-Ex data, generate terrain, and launch Chrono."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "environments" / "terrain"))

from goose_dataset import (
    SelectedFrame,
    discover_scenarios,
    frame_source_fingerprints,
    frame_name_for,
    no_clouds_message,
    scenario_listing,
    select_frame,
)
from goose_semantics import (
    COARSE_TAXONOMY_NAME,
    COARSE_UNOBSERVED,
    FINE_MAPPING_SHA256,
    FINE_TAXONOMY_NAME,
    FINE_UNOBSERVED,
    SCENE_FORMAT_VERSION,
    SEMANTIC_FORMAT_VERSION,
)

from goose_quality import (
    DEFAULT_QUALITY_PRESET,
    QUALITY_PRESET_NAMES,
    ResolvedQuality,
    resolve_quality,
)

DATASET_ROOT = REPOSITORY_ROOT / "data" / "goose"
GENERATED_ROOT = REPOSITORY_ROOT / "outputs" / "goose"
CONVERTER = REPOSITORY_ROOT / "environments" / "terrain" / "build_heightmap.py"
ENVIRONMENT = REPOSITORY_ROOT / "environments" / "terrain" / "goose_environment.py"


def run(command: list[str]) -> None:
    print(f"\n$ {shlex.join(command)}", flush=True)
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)


def dataset_is_ready(dataset_root: Path) -> bool:
    if not dataset_root.expanduser().is_dir():
        return False
    return any(scenario.pairs() for scenario in discover_scenarios(dataset_root))


def select_pointcloud(
    dataset_root: Path,
    scenario: str | None,
    sequence: str | None,
    frame_index: int,
    split: str = "auto",
) -> Path:
    return select_frame(dataset_root, split, scenario, sequence, frame_index).pointcloud


def scene_path_for(pointcloud: Path) -> Path:
    return GENERATED_ROOT / frame_name_for(pointcloud) / "scene.json"


def scene_matches_source(
    scene_path: Path,
    frame: SelectedFrame,
    quality: ResolvedQuality,
) -> bool:
    """Rebuild older scenes or a scene generated from a different input dataset."""
    try:
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        source = scene["source"]
        root = Path(source["dataset_root"])
        outputs = scene["outputs"]
        semantics = scene["semantics"]

        def source_file(value: str | None) -> Path | None:
            if not value:
                return None
            path = Path(value)
            return (path if path.is_absolute() else root / path).resolve()

        def output_file(name: str) -> Path:
            return scene_path.parent / outputs[name]["path"]

        return (
            scene["format_version"] == SCENE_FORMAT_VERSION
            and source_file(source["pointcloud"]) == frame.pointcloud
            and source_file(source["labels"]) == frame.label
            and source_file(source.get("mapping")) == frame.mapping
            and source_file(source.get("changelog")) == frame.changelog
            and source["fingerprints"] == frame_source_fingerprints(frame)
            and scene.get("quality") == quality.to_manifest()
            and (scene_path.parent / scene["heightmap"]).is_file()
            and (scene_path.parent / scene["height_grid"]).is_file()
            and output_file("semantic_fine").is_file()
            and output_file("semantic_coarse").is_file()
            and output_file("semantic_legend").is_file()
            and semantics["format_version"] == SEMANTIC_FORMAT_VERSION
            and semantics["fine_taxonomy"] == {
                "name": FINE_TAXONOMY_NAME,
                "mapping_sha256": FINE_MAPPING_SHA256,
                "unobserved_id": int(FINE_UNOBSERVED),
            }
            and semantics["coarse_taxonomy"]["name"] == COARSE_TAXONOMY_NAME
            and semantics["coarse_taxonomy"]["unobserved_id"]
            == int(COARSE_UNOBSERVED)
            and semantics["aligned_to"] == scene["height_grid"]
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def build_converter_command(
    args: argparse.Namespace,
    dataset_root: Path,
    frame: SelectedFrame,
    quality: ResolvedQuality,
) -> list[str]:
    command = [
        sys.executable,
        str(CONVERTER),
        "--dataset",
        str(dataset_root),
        "--split",
        frame.scenario.split,
        "--scenario",
        frame.scenario.name,
        "--frame-index",
        str(args.frame_index),
        "--quality",
        quality.preset,
    ]

    if args.sequence:
        command.extend(("--sequence", args.sequence))
    if args.mapping is not None:
        command.extend(("--mapping", str(frame.mapping)))
    if args.resolution is not None:
        command.extend(("--resolution", str(args.resolution)))
    if args.grid_spacing is not None:
        command.extend(("--grid-spacing", str(args.grid_spacing)))

    return command


def ensure_pychrono() -> None:
    if importlib.util.find_spec("pychrono") is None:
        raise RuntimeError(
            "PyChrono is not available in the current Python environment. "
            "Use scripts/run_goose.sh or activate the chrono Conda environment first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=DATASET_ROOT,
        help=f"prepared GOOSE/GOOSE-Ex dataset directory (default: {DATASET_ROOT})",
    )
    parser.add_argument(
        "--split", choices=("auto", "val", "train", "test"), default="auto",
        help="split to use (default: auto, preferring labelled val then train then test)",
    )
    parser.add_argument(
        "--scenario", default=None,
        help="scenario to load (default: first with matching 3D labels)",
    )
    parser.add_argument(
        "--list-scenarios", action="store_true",
        help="show discovered 3D scenarios and matching-label counts, then exit",
    )
    parser.add_argument(
        "--mapping", type=Path, default=None,
        help="override semantic-ID/class-name CSV (default: locate goose_label_mapping.csv)",
    )
    parser.add_argument(
        "--sequence", default=None,
        help="optional sequence number, for example 07 or sequence07",
    )
    parser.add_argument(
        "--frame-index", type=int, default=0,
        help="zero-based labelled frame within the selected scenario/sequence",
    )
    parser.add_argument(
        "--quality",
        choices=QUALITY_PRESET_NAMES,
        default=DEFAULT_QUALITY_PRESET,
        help=(
            "performance and terrain-detail preset "
            f"(default: {DEFAULT_QUALITY_PRESET})"
        ),
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=None,
        help="override the heightmap resolution selected by --quality, in metres",
    )
    parser.add_argument(
        "--grid-spacing",
        type=float,
        default=None,
        help="override the SCM grid spacing selected by --quality, in metres",
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="regenerate the heightmap even when scene.json already exists",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="run the Chrono initialisation check without a graphical window",
    )
    parser.add_argument(
        "--duration", type=float, default=None,
        help="optional simulated duration in seconds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = args.dataset.expanduser().resolve()

    if args.list_scenarios:
        scenarios = discover_scenarios(dataset_root)
        if not scenarios:
            raise FileNotFoundError(no_clouds_message(dataset_root))
        selected = [
            item for item in scenarios
            if (args.split == "auto" or item.split == args.split)
            and (args.scenario is None or item.name == args.scenario)
        ]
        if not selected:
            raise FileNotFoundError(
                f"No scenarios match the requested filters.\n{scenario_listing(scenarios)}"
            )
        print(scenario_listing(selected))
        return 0

    quality = resolve_quality(
        args.quality,
        args.resolution,
        args.grid_spacing,
    )

    frame = select_frame(
        dataset_root, args.split, args.scenario, args.sequence, args.frame_index
    )
    if args.mapping is not None:
        mapping = args.mapping.expanduser().resolve()
        if not mapping.is_file():
            raise FileNotFoundError(f"Label mapping CSV not found: {mapping}")
        frame = replace(frame, mapping=mapping)
    print(f"Selected {frame.scenario.split}/{frame.scenario.name}: {frame.pointcloud.name}")
    print(f"3D labels: {frame.label}")
    print(f"Quality preset: {quality.preset}")
    print(f"Terrain resolution: {quality.terrain_resolution:g} m")
    print(f"SCM grid spacing: {quality.scm_grid_spacing:g} m")
    print(f"Overrides: {', '.join(quality.overrides) or 'none'}")
    ensure_pychrono()
    scene_path = scene_path_for(frame.pointcloud)

    if args.rebuild or not scene_matches_source(
        scene_path, frame, quality
    ):
        print(f"Generating Chrono terrain from {frame.pointcloud.name}")
        converter_command = build_converter_command(
            args,
            dataset_root,
            frame,
            quality,
        )
        run(converter_command)
    else:
        print(f"Using existing generated scene: {scene_path}")

    launch_command = [sys.executable, str(ENVIRONMENT), "--scene", str(scene_path)]
    if args.headless:
        launch_command.append("--headless")
    if args.duration is not None:
        launch_command.extend(("--duration", str(args.duration)))
    run(launch_command)
    return 0


def cli() -> int:
    try:
        return main()
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, ValueError, IndexError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
