#!/usr/bin/env python3
#Script to run build_heightmap.py and goose_environment.py and launch GUI
from __future__ import annotations

import argparse
import importlib.util
import shlex
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPOSITORY_ROOT / "environments" / "goose" / "data"
DATASET_ROOT = DATA_ROOT / "gooseEx_3d_val"
GENERATED_ROOT = REPOSITORY_ROOT / "environments" / "goose" / "generated"
DOWNLOADER = REPOSITORY_ROOT / "scripts" / "download_goose_ex.py"
CONVERTER = (
    REPOSITORY_ROOT / "environments" / "goose" / "terrain" / "build_heightmap.py"
)
ENVIRONMENT = (
    REPOSITORY_ROOT / "environments" / "goose" / "terrain" / "goose_environment.py"
)


def run(command: list[str]) -> None:
    print(f"\n$ {shlex.join(command)}", flush=True)
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)


def dataset_is_ready(dataset_root: Path) -> bool:
    mapping = dataset_root / "goose_label_mapping.csv"
    clouds = dataset_root / "lidar" / "val"
    labels = dataset_root / "labels" / "val"
    return (
        mapping.is_file()
        and any(clouds.glob("alice_*/*.bin"))
        and any(labels.glob("alice_*/*.label"))
    )


def select_pointcloud(
    dataset_root: Path,
    scenario: str,
    sequence: str | None,
    frame_index: int,
) -> Path:
    cloud_root = dataset_root / "lidar" / "val" / scenario
    clouds = sorted(cloud_root.glob("*.bin"))
    if sequence:
        token = sequence if sequence.startswith("sequence") else f"sequence{sequence}"
        clouds = [path for path in clouds if token in path.name]
    if not clouds:
        raise FileNotFoundError(
            f"No ALICE point clouds matched scenario={scenario!r}, sequence={sequence!r}"
        )
    if not 0 <= frame_index < len(clouds):
        raise IndexError(
            f"Frame index {frame_index} is outside the available range "
            f"0..{len(clouds) - 1}"
        )
    return clouds[frame_index]


def scene_path_for(pointcloud: Path) -> Path:
    frame_name = pointcloud.name
    for suffix in ("_pcl.bin", "_vls128.bin", ".bin"):
        if frame_name.endswith(suffix):
            frame_name = frame_name[: -len(suffix)]
            break
    return GENERATED_ROOT / frame_name / "scene.json"


def ensure_pychrono() -> None:
    if importlib.util.find_spec("pychrono") is None:
        raise RuntimeError(
            "PyChrono is not available in the current Python environment. "
            "Run this launcher through scripts/run_goose.sh or activate the "
            "chrono Conda environment first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        default="alice_scenario02",
        help="ALICE scenario to load (default: alice_scenario02)",
    )
    parser.add_argument(
        "--sequence",
        default=None,
        help="optional sequence filter, for example 07 or sequence07",
    )
    parser.add_argument(
        "--frame-index",
        type=int,
        default=0,
        help="zero-based frame within the selected scenario/sequence",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="regenerate the heightmap even when scene.json already exists",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run the Chrono initialization check without a graphical window",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="optional simulated duration in seconds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_pychrono()

    if not dataset_is_ready(DATASET_ROOT):
        print("GOOSE-Ex ALICE data is missing; downloading the 3D validation split.")
        run([sys.executable, str(DOWNLOADER), "--split", "val"])
    else:
        print(f"Using existing GOOSE-Ex data: {DATASET_ROOT}")

    pointcloud = select_pointcloud(
        DATASET_ROOT, args.scenario, args.sequence, args.frame_index
    )
    scene_path = scene_path_for(pointcloud)

    if args.rebuild or not scene_path.is_file():
        print(f"Generating Chrono terrain from {pointcloud.name}")
        converter_command = [
            sys.executable,
            str(CONVERTER),
            "--dataset",
            str(DATASET_ROOT),
            "--scenario",
            args.scenario,
            "--frame-index",
            str(args.frame_index),
        ]
        if args.sequence:
            converter_command.extend(("--sequence", args.sequence))
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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error
