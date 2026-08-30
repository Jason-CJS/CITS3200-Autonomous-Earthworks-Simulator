"""Interactive and deterministic PyChrono B10 bulldozer demonstration."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pychrono as chrono

from src.demo_common import KeyboardState, axis, clamp, create_visual_system
from src.scm_demo_terrain import SCMDemoTerrain
from vehicles.bulldozer.articulation.bulldozer_model import BulldozerModel


class BulldozerController:
    def __init__(self, bulldozer: BulldozerModel, keyboard: KeyboardState) -> None:
        self.bulldozer = bulldozer
        self.keyboard = keyboard
        self.blade = [0.0, 0.0]

    def update(self, frame_time: float) -> None:
        forward = axis(self.keyboard, "w", "s")
        turn = axis(self.keyboard, "a", "d")
        left = 0.70 * forward + 0.48 * turn
        right = 0.70 * forward - 0.48 * turn
        if self.keyboard.is_down("space"):
            left = right = 0.0
        self.bulldozer.set_drive_speeds(clamp(left, -1.0, 1.0), clamp(right, -1.0, 1.0))

        self.blade[0] += axis(self.keyboard, "r", "f") * 0.30 * frame_time
        self.blade[1] += axis(self.keyboard, "t", "g") * 0.40 * frame_time
        if self.keyboard.is_down("x"):
            self.blade = [0.0, 0.0]
        self.blade[0] = clamp(self.blade[0], -0.28, 0.45)
        self.blade[1] = clamp(self.blade[1], -0.45, 0.45)
        self.bulldozer.set_blade_targets(*self.blade)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke-test", action="store_true", help="run a short graphics/SCM test")
    mode.add_argument("--capture", metavar="OUTPUT.png", type=Path, help="alias for --capture-front")
    mode.add_argument("--capture-front", metavar="OUTPUT.png", type=Path)
    mode.add_argument("--capture-side", metavar="OUTPUT.png", type=Path)
    mode.add_argument("--capture-opposite", metavar="OUTPUT.png", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    capture_path = args.capture or args.capture_front or args.capture_side or args.capture_opposite
    if args.capture_side:
        capture_view = "side"
    elif args.capture_opposite:
        capture_view = "opposite-side"
    else:
        capture_view = "front three-quarter"

    system = chrono.ChSystemNSC()
    system.SetGravitationalAcceleration(chrono.ChVector3d(0.0, 0.0, -9.81))
    system.SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
    bulldozer = BulldozerModel(system, show_rigid_ground=False)
    terrain = SCMDemoTerrain(system)
    bulldozer.set_blade_targets(0.0, 0.0)
    start = bulldozer.get_chassis_position()

    if capture_path is not None:
        bulldozer.set_blade_targets(-0.06, 0.08)
        bulldozer.set_drive_speeds(0.40, 0.50)
    else:
        bulldozer.set_drive_speeds(0.0, 0.0)

    if args.capture_side:
        camera_offset = chrono.ChVector3d(0.0, -6.0, 1.6)
    elif args.capture_opposite:
        camera_offset = chrono.ChVector3d(-3.6, 4.6, 1.8)
    else:
        camera_offset = chrono.ChVector3d(-3.6, -4.6, 1.8)
    camera_target_offset = chrono.ChVector3d(-0.55, 0.0, 0.70)
    visual = create_visual_system(
        system,
        "Autonomous Earthworks Simulator - Interactive Bulldozer",
        start + camera_offset,
        start + camera_target_offset,
        null_driver=args.smoke_test,
        balanced_lighting=True,
    )
    keyboard = KeyboardState(("w", "a", "r", "t") if args.smoke_test else ())
    controller = None if capture_path is not None else BulldozerController(bulldozer, keyboard)
    if controller is not None:
        controller.update(0.0)

    if args.smoke_test:
        print("Running short Python bulldozer keyboard, graphics, and SCM smoke test.")
    elif capture_path is not None:
        print(f"Capturing Python bulldozer {capture_view} SCM demonstration frame.")
    else:
        print("Controls: W/S drive, A/D steer, Space stop, R/F blade lift, T/G blade tilt, X reset.")
        keyboard.start()

    physics_step = 0.002
    physics_steps_per_frame = 8
    frame_time = physics_step * physics_steps_per_frame
    scripted_drive_stopped = False

    def render_frame() -> None:
        nonlocal scripted_drive_stopped
        if controller is not None:
            controller.update(frame_time)
        position = bulldozer.get_chassis_position()
        if capture_path is not None:
            visual.SetCameraPosition(position + camera_offset)
        visual.SetCameraTarget(position + camera_target_offset)
        visual.BeginScene()
        visual.Render()
        visual.EndScene()
        for _ in range(physics_steps_per_frame):
            bulldozer.advance(physics_step)
        if controller is None and not scripted_drive_stopped and system.GetChTime() >= 1.25:
            bulldozer.set_drive_speeds(0.0, 0.0)
            scripted_drive_stopped = True

    try:
        if args.smoke_test or capture_path is not None:
            for _ in range(100 if capture_path is not None else 12):
                render_frame()
            if capture_path is not None:
                visual.WriteImageToFile(str(capture_path))
                print(f"Bulldozer screenshot written to {capture_path}")
            else:
                print("Bulldozer Python graphics smoke test passed.")
        else:
            timer = chrono.ChRealtimeStepTimer()
            while visual.Run():
                render_frame()
                timer.Spin(frame_time)
    finally:
        keyboard.stop()

    finish = bulldozer.get_chassis_position()
    blade = bulldozer.get_blade_state()
    displacement = (finish - start).Length()
    modified_nodes = terrain.get_modified_node_count()
    print(f"Bulldozer loaded with {bulldozer.body_count} bodies")
    print(f"Imported Project Chrono B10 vertices: {bulldozer.imported_vertex_count}")
    print(f"Chassis displacement: {displacement:.3f} m")
    print(f"Blade [lift tilt]: {blade[0]:.3f} {blade[1]:.3f}")
    print(f"SCM modified soil nodes: {modified_nodes}")
    if args.smoke_test and modified_nodes == 0:
        print("SCM smoke test failed: the bulldozer did not deform soil.", file=sys.stderr)
        return 3
    if args.smoke_test and (displacement < 0.02 or abs(blade[0]) < 0.01 or abs(blade[1]) < 0.01):
        print("Keyboard smoke test failed: drive or blade input had no measured effect.", file=sys.stderr)
        return 4
    if args.smoke_test and finish.x >= start.x - 0.02:
        print("Keyboard smoke test failed: W did not move toward the blade.", file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
