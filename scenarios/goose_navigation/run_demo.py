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
    parser.add_argument("--mode", choices=("scripted", "manual"), default="scripted")
    parser.add_argument("--start-x", type=float, default=0.0, help="bulldozer start X in metres")
    parser.add_argument("--start-y", type=float, default=0.0, help="bulldozer start Y in metres")
    parser.add_argument("--speed", type=float, default=0.6, help="scripted track speed in m/s")
    parser.add_argument("--duration", type=float, help="scripted duration (default 6 s); optional manual limit")
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
    mode = getattr(args, "mode", "scripted")
    if mode not in ("scripted", "manual"):
        raise ValueError("mode must be scripted or manual")
    if mode == "manual" and args.headless:
        raise ValueError("manual mode needs a window; remove --headless")
    duration = args.duration if args.duration is not None else (6.0 if mode == "scripted" else None)
    if mode == "scripted":
        scene.validate_route(args.start_x, args.start_y, args.speed, duration)
    else:
        scene.validate_start(args.start_x, args.start_y)
    config_path = args.config.expanduser().resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{config_path}: expected an SCM configuration object")
    step_size = float(config["step_size"])
    steps = exact_steps(duration, step_size, "duration") if duration is not None else None
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
    if mode == "scripted":
        bulldozer.set_drive_speeds(args.speed, args.speed)
    else:
        bulldozer.set_drive_speeds(0.0, 0.0)

    visual = None
    if not args.headless:
        from src.demo_common import create_visual_system

        visual = create_visual_system(
            system,
            f"GOOSE-Ex - {mode} bulldozer traversal",
            chrono.ChVector3d(args.start_x + 4, args.start_y - 10, start_height + 7),
            chrono.ChVector3d(args.start_x - 1, args.start_y, start_height),
            controls=(
                "W / S     Drive forward / reverse",
                "A / D     Steer left / right",
                "SPACE     Stop",
                "R / F     Raise / lower blade",
                "T / G     Tilt blade forward / back",
                "X         Reset blade",
            ) if mode == "manual" else (),
            balanced_lighting=True,
        )

    samples = [_sample(bulldozer, 0.0)]
    completed_steps = 0
    render_stride = max(1, round(1 / (30 * step_size)))
    keyboard = controller = timer = None
    if mode == "manual":
        from src.bulldozer_main import BulldozerController
        from src.demo_common import KeyboardState

        keyboard = KeyboardState()
        controller = BulldozerController(bulldozer, keyboard)
        controller.blade[0] = 0.12
        timer = chrono.ChRealtimeStepTimer()
        print("Controls: W/S drive, A/D steer, Space stop, R/F blade lift, T/G tilt, X reset.")
        print("Close the window to save the trajectory and route overlay.")

    try:
        if keyboard is not None:
            keyboard.start()
        while steps is None or completed_steps < steps:
            if visual is not None and completed_steps % render_stride == 0:
                if not visual.Run():
                    break
                if controller is not None:
                    controller.update(render_stride * step_size)
                    position = bulldozer.get_chassis_position()
                    visual.SetCameraPosition(position + chrono.ChVector3d(4, -10, 6))
                    visual.SetCameraTarget(position + chrono.ChVector3d(-1, 0, -0.15))
                visual.BeginScene()
                visual.Render()
                visual.EndScene()

            terrain.Synchronize(system.GetChTime())
            bulldozer.advance(step_size)
            terrain.Advance(step_size)
            completed_steps += 1
            if completed_steps % sample_stride == 0 or completed_steps == steps:
                samples.append(_sample(bulldozer, completed_steps * step_size))
            if timer is not None and completed_steps % render_stride == 0:
                timer.Spin(render_stride * step_size)
    finally:
        bulldozer.set_drive_speeds(0.0, 0.0)
        if keyboard is not None:
            keyboard.stop()

    if completed_steps and samples[-1].time_s < completed_steps * step_size - 1e-9:
        samples.append(_sample(bulldozer, completed_steps * step_size))
    displacement = math.hypot(
        samples[-1].x_m - samples[0].x_m,
        samples[-1].y_m - samples[0].y_m,
    )
    completed = (
        completed_steps == steps and displacement >= 0.5 * args.speed * duration
        if mode == "scripted" else completed_steps > 0
    )

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
        "mode": "scripted_straight_negative_x" if mode == "scripted" else "manual_keyboard",
        "starting_pose": {
            "x_m": samples[0].x_m,
            "y_m": samples[0].y_m,
            "z_m": samples[0].z_m,
            "yaw_rad": samples[0].yaw_rad,
        },
        "requested_duration_s": duration,
        "simulated_duration_s": completed_steps * step_size,
        "step_size_s": step_size,
        "sample_period_s": args.sample_period,
        "track_speed_m_s": args.speed if mode == "scripted" else None,
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
