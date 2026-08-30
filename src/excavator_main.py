"""Interactive and deterministic PyChrono excavator demonstration."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pychrono as chrono

from src.demo_common import KeyboardState, axis, clamp, create_visual_system
from src.scm_demo_terrain import SCMDemoTerrain
from vehicles.excavator.articulation.excavator_model import ExcavatorModel


class ExcavatorController:
    def __init__(self, excavator: ExcavatorModel, keyboard: KeyboardState, calibration: bool) -> None:
        self.excavator = excavator
        self.keyboard = keyboard
        self.calibration = calibration
        self.targets = [0.0, 0.0, 0.0, 0.0] if calibration else [0.0, 0.25, -0.45, 0.45]

    def update(self, frame_time: float) -> None:
        forward = axis(self.keyboard, "w", "s")
        turn = axis(self.keyboard, "a", "d")
        left = 0.75 * forward - 0.50 * turn
        right = 0.75 * forward + 0.50 * turn
        if self.keyboard.is_down("space") or self.calibration:
            left = right = 0.0
        self.excavator.set_drive_speeds(clamp(left, -1.0, 1.0), clamp(right, -1.0, 1.0))

        self.targets[0] += axis(self.keyboard, "q", "e") * 0.70 * frame_time
        self.targets[1] += axis(self.keyboard, "r", "f") * 0.55 * frame_time
        self.targets[2] += axis(self.keyboard, "t", "g") * 0.65 * frame_time
        self.targets[3] += axis(self.keyboard, "y", "h") * 0.85 * frame_time
        if self.keyboard.is_down("x"):
            self.targets = [0.0, 0.0, 0.0, 0.0] if self.calibration else [0.0, 0.25, -0.45, 0.45]
        limits = ((-1.50, 1.50), (-0.70, 0.80), (-1.25, 0.80), (-1.30, 1.30))
        self.targets = [clamp(value, *limit) for value, limit in zip(self.targets, limits, strict=True)]
        self.excavator.set_articulation_targets(*self.targets)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke-test", action="store_true", help="run a short graphics/SCM test")
    mode.add_argument("--capture", metavar="OUTPUT.png", type=Path, help="write a deterministic SCM screenshot")
    mode.add_argument("--calibrate", action="store_true", help="show imported-link calibration markers")
    mode.add_argument(
        "--capture-calibration",
        metavar="OUTPUT.png",
        type=Path,
        help="write a deterministic calibration screenshot",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    calibration = args.calibrate or args.capture_calibration is not None
    capture_path = args.capture or args.capture_calibration

    system = chrono.ChSystemNSC()
    system.SetGravitationalAcceleration(chrono.ChVector3d(0.0, 0.0, -9.81))
    system.SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
    excavator = ExcavatorModel(system, show_rigid_ground=calibration, show_calibration_markers=calibration)
    terrain = None if calibration else SCMDemoTerrain(system)
    default_targets = (0.0, 0.0, 0.0, 0.0) if calibration else (0.0, 0.25, -0.45, 0.45)
    excavator.set_articulation_targets(*default_targets)
    start = excavator.get_chassis_position()

    if capture_path is not None and not calibration:
        excavator.set_drive_speeds(0.45, 0.45)
    else:
        excavator.set_drive_speeds(0.0, 0.0)

    visual = create_visual_system(
        system,
        "Autonomous Earthworks Simulator - Interactive Excavator",
        chrono.ChVector3d(8.5, -11.0, 6.0),
        chrono.ChVector3d(1.8, 0.0, 1.2),
        null_driver=args.smoke_test,
    )
    keyboard = KeyboardState(("w", "q", "r", "t", "y") if args.smoke_test else ())
    controller = None if capture_path is not None else ExcavatorController(excavator, keyboard, calibration)
    if controller is not None:
        controller.update(0.0)

    if args.smoke_test:
        print("Running short Python excavator keyboard, graphics, and SCM smoke test.")
    elif args.capture_calibration:
        print("Capturing the source-aligned Python excavator pose with joint markers.")
    elif args.capture:
        print("Capturing a Python excavator SCM demonstration frame.")
    elif calibration:
        print(f"Calibration mode. Edit {excavator.visual_calibration_path}, close, and rerun.")
    else:
        print("Controls: W/S drive, A/D steer, Space stop, Q/E swing, R/F boom, T/G arm, Y/H bucket, X reset.")
        keyboard.start()

    physics_step = 0.002
    physics_steps_per_frame = 8
    frame_time = physics_step * physics_steps_per_frame
    scripted_drive_stopped = False

    def render_frame() -> None:
        nonlocal scripted_drive_stopped
        if controller is not None:
            controller.update(frame_time)
        visual.SetCameraTarget(excavator.get_chassis_position() + chrono.ChVector3d(1.5, 0.0, 1.2))
        visual.BeginScene()
        visual.Render()
        visual.EndScene()
        for _ in range(physics_steps_per_frame):
            excavator.advance(physics_step)
        if controller is None and not scripted_drive_stopped and system.GetChTime() >= 1.25:
            excavator.set_drive_speeds(0.0, 0.0)
            scripted_drive_stopped = True

    try:
        if args.smoke_test or capture_path is not None:
            for _ in range(100 if capture_path is not None else 12):
                render_frame()
            if capture_path is not None:
                visual.WriteImageToFile(str(capture_path))
                print(f"Excavator screenshot written to {capture_path}")
            else:
                print("Excavator Python graphics smoke test passed.")
        else:
            timer = chrono.ChRealtimeStepTimer()
            while visual.Run():
                render_frame()
                timer.Spin(frame_time)
    finally:
        keyboard.stop()

    finish = excavator.get_chassis_position()
    joints = excavator.get_joint_angles()
    displacement = (finish - start).Length()
    print(f"Excavator loaded with {excavator.body_count} bodies")
    print(f"Imported MathScavator9000 vertices: {excavator.imported_vertex_count}")
    print(f"Chassis displacement: {displacement:.3f} m")
    print("Joint angles [swing boom arm bucket]: " + " ".join(f"{value:.3f}" for value in joints))
    if calibration:
        positions = excavator.get_articulation_body_positions()
        print(
            "Link origins [boom | arm | bucket]: "
            + " | ".join(f"{value.x:.3f} {value.y:.3f} {value.z:.3f}" for value in positions)
        )
    modified_nodes = terrain.get_modified_node_count() if terrain is not None else 0
    print(f"SCM modified soil nodes: {modified_nodes}")
    if args.smoke_test and terrain is not None and modified_nodes == 0:
        print("SCM smoke test failed: the excavator did not deform soil.", file=sys.stderr)
        return 3
    if args.smoke_test and (displacement < 0.02 or abs(joints[0]) < 0.01):
        print("Keyboard smoke test failed: drive or articulation had no measured effect.", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
