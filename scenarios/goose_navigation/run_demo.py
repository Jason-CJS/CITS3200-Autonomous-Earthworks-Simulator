"""Drive the existing B10 bulldozer across a generated GOOSE-Ex scene."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scenarios.goose_navigation.traversal import (
    SceneGrid,
    TrajectorySample,
    exact_steps,
    write_route_overlay,
    write_trajectory,
)


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "environments/scene_config/alice_scm.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True, type=Path, help="generated GOOSE-Ex scene.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="SCM configuration JSON")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/goose_navigation"))
    parser.add_argument("--start-x", type=float, default=0.0, help="bulldozer start X in metres")
    parser.add_argument("--start-y", type=float, default=0.0, help="bulldozer start Y in metres")
    parser.add_argument("--speed", type=float, default=0.6, help="positive track speed in m/s")
    parser.add_argument("--duration", type=float, default=6.0, help="scripted traversal in seconds")
    parser.add_argument("--sample-period", type=float, default=0.1, help="trajectory sample interval in seconds")
    parser.add_argument("--headless", action="store_true", help="run without an Irrlicht window")
    return parser.parse_args()


def _sample(bulldozer, time_s: float) -> TrajectorySample:
    position = bulldozer.get_chassis_position()
    return TrajectorySample(
        time_s, float(position.x), float(position.y), float(position.z),
        float(bulldozer.get_chassis_heading()),
    )


def run_demo(args: argparse.Namespace) -> int:
    scene = SceneGrid.load(args.scene)
    scene.validate_route(args.start_x, args.start_y, args.speed, args.duration)
    config_path = args.config.expanduser().resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{config_path}: expected an SCM configuration object")
    step_size = float(config["step_size"])
    steps = exact_steps(args.duration, step_size, "duration")
    sample_stride = exact_steps(args.sample_period, step_size, "sample period")

    # Chrono is loaded only after the scene and route have been validated.
    # This also lets --help and the export tests run without PyChrono.
    import pychrono as chrono

    from environments.terrain import goose_environment
    from vehicles.bulldozer.articulation.bulldozer_model import BulldozerModel

    system = goose_environment.create_system()
    terrain = goose_environment.create_terrain(system, scene.path, scene.metadata, config)
    # The existing B10 track contact surface is approximately 0.15 m below
    # its default ground height. Follow the local height-grid elevation.
    start_height = scene.height_at(args.start_x, args.start_y)
    bulldozer = BulldozerModel(
        system,
        show_rigid_ground=False,
        initial_z_offset=start_height - 0.15,
        initial_xy=(args.start_x, args.start_y),
    )
    bulldozer.set_blade_targets(0.12, 0.0)
    bulldozer.set_drive_speeds(args.speed, args.speed)

    visual = None
    if not args.headless:
        from src.demo_common import create_visual_system

        visual = create_visual_system(
            system,
            "GOOSE-Ex - scripted bulldozer traversal",
            chrono.ChVector3d(args.start_x + 4, args.start_y - 10, start_height + 7),
            chrono.ChVector3d(args.start_x - 1, args.start_y, start_height),
            balanced_lighting=True,
        )

    samples = [_sample(bulldozer, 0.0)]
    completed_steps = 0
    render_stride = max(1, round(1 / (30 * step_size)))
    for index in range(steps):
        if visual is not None:
            if not visual.Run():
                break
            if index % render_stride == 0:
                visual.BeginScene()
                visual.Render()
                visual.EndScene()

        terrain.Synchronize(system.GetChTime())
        bulldozer.advance(step_size)
        terrain.Advance(step_size)
        completed_steps = index + 1
        if completed_steps % sample_stride == 0 or completed_steps == steps:
            samples.append(_sample(bulldozer, completed_steps * step_size))

    bulldozer.set_drive_speeds(0.0, 0.0)
    displacement = math.hypot(
        samples[-1].x_m - samples[0].x_m,
        samples[-1].y_m - samples[0].y_m,
    )
    completed = completed_steps == steps and displacement >= 0.5 * args.speed * args.duration

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = output_dir / "trajectory.csv"
    overlay_path = output_dir / "route_overlay.png"
    manifest_path = output_dir / "run_manifest.json"
    write_trajectory(samples, trajectory_path)
    write_route_overlay(scene, samples, overlay_path)
    manifest = {
        "format_version": 1,
        "scenario": "scripted_goose_bulldozer_traversal",
        "status": "completed" if completed else "incomplete",
        "source_scene": str(scene.path),
        "vehicle": "Project Chrono B10 bulldozer",
        "mode": "scripted_straight_negative_x",
        "starting_pose": {
            "x_m": samples[0].x_m,
            "y_m": samples[0].y_m,
            "z_m": samples[0].z_m,
            "yaw_rad": samples[0].yaw_rad,
        },
        "requested_duration_s": args.duration,
        "simulated_duration_s": completed_steps * step_size,
        "step_size_s": step_size,
        "sample_period_s": args.sample_period,
        "track_speed_m_s": args.speed,
        "displacement_m": displacement,
        "quality": scene.metadata.get("quality"),
        "semantic_labels": "pending_issue_22",
        "outputs": {
            "trajectory": trajectory_path.name,
            "route_overlay": overlay_path.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Scene: {scene.path}")
    print(f"Bulldozer traversed {displacement:.2f} m in {completed_steps * step_size:.2f} s")
    print(f"Trajectory: {trajectory_path}")
    print(f"Run manifest: {manifest_path}")
    print(f"Route overlay: {overlay_path}")
    if not completed:
        print("INCOMPLETE: simulation ended early or the bulldozer did not move as expected.")
        return 2
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run_demo(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Could not run bulldozer traversal: {exc}")
        return 2
    except ModuleNotFoundError as exc:
        if exc.name != "pychrono":
            raise
        print("PyChrono is required to run the traversal. Activate the project's chrono environment.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
