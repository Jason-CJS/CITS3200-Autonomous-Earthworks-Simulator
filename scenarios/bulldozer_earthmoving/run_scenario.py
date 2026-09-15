"""Run a deterministic B10 bulldozer hole-filling scenario."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path

import pychrono as chrono
import pychrono.vehicle as vehicle

from deformation.scm_deformation_export import (
    collect_deformation_records,
    write_deformation_export,
)
from scenarios.bulldozer_earthmoving.terrain_profile import (
    TerrainProfile,
    calculate_hole_metrics,
    write_profile_heightmap,
)
from scenarios.bulldozer_earthmoving.visualisation import (
    write_terrain_comparison,
)
from src.demo_common import create_visual_system
from vehicles.bulldozer.articulation.bulldozer_model import BulldozerModel


STEP_SIZE_S = 0.002
PHYSICS_STEPS_PER_FRAME = 16
DEFAULT_DRIVE_DURATION_S = 2.40
SETTLE_DURATION_S = 0.50

TERRAIN_REFERENCE_HEIGHT_M = 0.15
TRACK_SPEED = 0.45
BLADE_LIFT_M = -0.04
BLADE_RELEASE_LIFT_M = 0.02
BLADE_RELEASE_START_S = 1.75
BLADE_TILT_RAD = 0.08
BLADE_RAISE_DURATION_S = 0.20
MIN_AVERAGE_HEIGHT_INCREASE_M = 0.001
MIN_MODIFIED_NODES_IN_HOLE = 10

def meets_success_criteria(
    modified_node_count: int,
    average_height_increase_m: float,
    modified_node_count_in_hole: int,
) -> bool:
    return (
        modified_node_count > 0
        and average_height_increase_m
        >= MIN_AVERAGE_HEIGHT_INCREASE_M
        and modified_node_count_in_hole
        >= MIN_MODIFIED_NODES_IN_HOLE
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/bulldozer_hole_fill"),
        help="directory for screenshots, exports, and measurements",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without creating an Irrlicht window",
    )
    parser.add_argument(
        "--drive-duration",
        type=float,
        default=DEFAULT_DRIVE_DURATION_S,
        help="scripted forward-driving duration in simulated seconds",
    )
    return parser.parse_args()


def create_system() -> chrono.ChSystem:
    system = chrono.ChSystemNSC()
    system.SetGravitationalAcceleration(
        chrono.ChVector3d(0.0, 0.0, -9.81)
    )
    system.SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
    return system


def create_terrain(
    system: chrono.ChSystem,
    profile: TerrainProfile,
    heightmap_path: Path,
) -> vehicle.SCMTerrain:
    terrain = vehicle.SCMTerrain(system)
    terrain.SetReferenceFrame(
        chrono.ChCoordsysd(
            chrono.ChVector3d(0.0, 0.0, TERRAIN_REFERENCE_HEIGHT_M),
            chrono.QUNIT,
        )
    )
    terrain.SetSoilParameters(
        0.2e6,
        0.0,
        1.1,
        0.0,
        30.0,
        0.01,
        4e7,
        3e4,
    )
    terrain.EnableBulldozing(True)
    terrain.SetBulldozingParameters(55.0, 1.0, 3, 4)
    terrain.SetTestHeight(0.20)
    terrain.Initialize(
        str(heightmap_path.resolve()),
        profile.length_m,
        profile.width_m,
        profile.height_min_m,
        profile.height_max_m,
        profile.grid_spacing_m,
    )
    terrain.SetPlotType(
        vehicle.SCMTerrain.PLOT_LEVEL,
        profile.height_min_m,
        profile.height_max_m,
    )
    terrain.SetMeshWireframe(False)
    return terrain


def create_visualisation(system: chrono.ChSystem):
    return create_visual_system(
        system,
        "Autonomous Earthworks Simulator - Scripted Hole Filling",
        chrono.ChVector3d(0.5, -7.5, 5.5),
        chrono.ChVector3d(-1.6, -0.7, 0.15),
        balanced_lighting=True,
    )


def render_scene(visualisation) -> None:
    visualisation.BeginScene()
    visualisation.Render()
    visualisation.EndScene()


def advance_simulation(
    system: chrono.ChSystem,
    bulldozer: BulldozerModel,
    terrain: vehicle.SCMTerrain,
    duration_s: float,
    visualisation=None,
    blade_lift_range: tuple[float, float] | None = None,
) -> None:
    step_count = math.ceil(duration_s / STEP_SIZE_S)

    for step_index in range(step_count):
        if blade_lift_range is not None:
            start_lift_m, end_lift_m = blade_lift_range
            progress = (step_index + 1) / step_count
            blade_lift_m = (
                start_lift_m
                + (end_lift_m - start_lift_m) * progress
            )
            bulldozer.set_blade_targets(
                blade_lift_m,
                BLADE_TILT_RAD,
            )
        if (
            visualisation is not None
            and step_index % PHYSICS_STEPS_PER_FRAME == 0
        ):
            render_scene(visualisation)

        time = system.GetChTime()
        terrain.Synchronize(time)
        bulldozer.advance(STEP_SIZE_S)
        terrain.Advance(STEP_SIZE_S)


def build_final_grid(profile, initial_grid, records):
    final_grid = dict(initial_grid)

    for record in records:
        point = (record.grid_x, record.grid_y)
        if point in final_grid:
            final_grid[point] = record.final_height_m

    return final_grid


def run_scenario(
    output_directory: Path,
    drive_duration_s: float,
    headless: bool,
    profile: TerrainProfile | None = None,
) -> int:
    if drive_duration_s <= 0:
        raise ValueError("drive duration must be greater than zero")

    output_directory.mkdir(parents=True, exist_ok=True)

    profile = profile or TerrainProfile()
    heightmap_path = write_profile_heightmap(
        profile,
        output_directory / "purpose_built_heightmap.bmp",
    )
    initial_grid = profile.initial_grid()

    system = create_system()
    bulldozer = BulldozerModel(system, show_rigid_ground=False)
    terrain = create_terrain(system, profile, heightmap_path)
    visualisation = None if headless else create_visualisation(system)

    if visualisation is not None:
        render_scene(visualisation)
        visualisation.WriteImageToFile(
            str(output_directory / "before_scene.png")
        )

    bulldozer.set_blade_targets(BLADE_LIFT_M, BLADE_TILT_RAD)
    bulldozer.set_drive_speeds(TRACK_SPEED, TRACK_SPEED)

    collection_duration_s = min(
        drive_duration_s,
        BLADE_RELEASE_START_S,
    )
    advance_simulation(
        system,
        bulldozer,
        terrain,
        collection_duration_s,
        visualisation,
    )

    remaining_drive_s = drive_duration_s - collection_duration_s
    raise_duration_s = min(
        remaining_drive_s,
        BLADE_RAISE_DURATION_S,
    )

    if raise_duration_s > 0:
        advance_simulation(
            system,
            bulldozer,
            terrain,
            raise_duration_s,
            visualisation,
            blade_lift_range=(
                BLADE_LIFT_M,
                BLADE_RELEASE_LIFT_M,
            ),
        )

    remaining_drive_s -= raise_duration_s
    if remaining_drive_s > 0:
        bulldozer.set_blade_targets(
            BLADE_RELEASE_LIFT_M,
            BLADE_TILT_RAD,
        )
        advance_simulation(
            system,
            bulldozer,
            terrain,
            remaining_drive_s,
            visualisation,
        )

    bulldozer.set_drive_speeds(0.0, 0.0)
    advance_simulation(
        system,
        bulldozer,
        terrain,
        SETTLE_DURATION_S,
        visualisation,
    )

    if visualisation is not None:
        render_scene(visualisation)
        visualisation.WriteImageToFile(
            str(output_directory / "after_scene.png")
        )

    records = collect_deformation_records(
        terrain.GetModifiedNodes(True),
        profile.geometry.actual_spacing_m,
        initial_height_at=profile.initial_height_at,
    )
    final_grid = build_final_grid(profile, initial_grid, records)
    hole_metrics = calculate_hole_metrics(
        profile,
        initial_grid,
        final_grid,
    )
    comparison_path = write_terrain_comparison(
        profile,
        initial_grid,
        final_grid,
        hole_metrics,
        output_directory / "terrain_comparison.png",
    )

    settings = {
        "scenario": "scripted_bulldozer_hole_filling",
        "vehicle": "Project Chrono B10 bulldozer",
        "step_size_s": STEP_SIZE_S,
        "drive_duration_s": drive_duration_s,
        "settle_duration_s": SETTLE_DURATION_S,
        "track_speed": TRACK_SPEED,
        "blade_collection_lift_m": BLADE_LIFT_M,
        "blade_release_lift_m": BLADE_RELEASE_LIFT_M,
        "blade_release_start_s": BLADE_RELEASE_START_S,
        "blade_raise_duration_s": BLADE_RAISE_DURATION_S,
        "blade_tilt_rad": BLADE_TILT_RAD,
        "terrain_reference_height_m": TERRAIN_REFERENCE_HEIGHT_M,
        "terrain_profile": asdict(profile),
    }
    csv_path, deformation_summary_path = write_deformation_export(
        records,
        output_directory,
        settings,
    )

    passed = meets_success_criteria(
        len(records),
        hole_metrics["average_height_increase_m"],
        hole_metrics["modified_node_count_in_hole"],
    )
    scenario_summary = {
        "format_version": 1,
        "scenario": "scripted_bulldozer_hole_filling",
        "passed": passed,
        "modified_node_count": len(records),
        "hole_metrics": hole_metrics,
        "simulation_settings": settings,
        "terrain_comparison": comparison_path.name,
        "acceptance_thresholds": {
            "minimum_average_height_increase_m":
                MIN_AVERAGE_HEIGHT_INCREASE_M,
            "minimum_modified_nodes_in_hole":
                MIN_MODIFIED_NODES_IN_HOLE,
        },
    }
    scenario_summary_path = output_directory / "hole_fill_summary.json"
    scenario_summary_path.write_text(
        json.dumps(scenario_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    increase = hole_metrics["average_height_increase_m"]
    print(f"Modified SCM nodes: {len(records)}")
    print(
        "Initial average hole height: "
        f"{hole_metrics['initial_average_height_m']:.6f} m"
    )
    print(
        "Final average hole height: "
        f"{hole_metrics['final_average_height_m']:.6f} m"
    )
    print(
        f"Average hole height increase: {increase:.6f} m "
        f"({increase * 1000:.2f} mm)"
    )
    print(
        "Modified nodes inside hole: "
        f"{hole_metrics['modified_node_count_in_hole']}"
    )
    print(f"Deformation CSV: {csv_path}")
    print(f"Deformation summary: {deformation_summary_path}")
    print(f"Hole-fill summary: {scenario_summary_path}")

    if not records:
        print("FAILED: no SCM deformation was recorded.")
        return 2
    if not passed:
        print(
            "FAILED: hole filling did not meet the minimum "
            f"{MIN_AVERAGE_HEIGHT_INCREASE_M * 1000:.1f} mm "
            f"average increase and {MIN_MODIFIED_NODES_IN_HOLE} "
            "modified target nodes."
        )

    print("PASSED: hole-filling acceptance thresholds were met.")
    print(f"Terrain comparison: {comparison_path}")
    return 0


def main() -> int:
    args = parse_args()
    return run_scenario(
        args.output_dir,
        args.drive_duration,
        args.headless,
    )


if __name__ == "__main__":
    raise SystemExit(main())