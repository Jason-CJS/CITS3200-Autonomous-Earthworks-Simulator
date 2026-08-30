"""Project Chrono B10 bulldozer model implemented with PyChrono."""

from __future__ import annotations

import math

import pychrono as chrono

from vehicles.common.chrono_utils import (
    add_box_collision,
    add_box_visual,
    add_cylinder_visual,
    add_mesh_visual,
    color,
    make_box,
)
from vehicles.common.differential_drive import DifferentialDrive


YELLOW = (0.78, 0.54, 0.10)
DARK_METAL = (0.12, 0.13, 0.13)


def _style_blade(blade: chrono.ChBody) -> None:
    blade.GetVisualModel().Clear()
    steel = (0.12, 0.14, 0.15)
    facets = (
        ((-0.07, 0.0, 0.28), -0.14),
        ((0.00, 0.0, 0.14), -0.07),
        ((0.03, 0.0, 0.00), 0.00),
        ((0.00, 0.0, -0.14), 0.07),
        ((-0.07, 0.0, -0.28), 0.14),
    )
    for position, angle in facets:
        add_box_visual(
            blade,
            (0.10, 1.82, 0.15),
            position,
            YELLOW,
            chrono.QuatFromAngleY(angle),
        )
    add_box_visual(blade, (0.16, 1.94, 0.08), (-0.10, 0.0, -0.40), steel)
    add_box_visual(blade, (0.18, 0.08, 0.80), (0.0, 0.94, 0.0), YELLOW)
    add_box_visual(blade, (0.18, 0.08, 0.80), (0.0, -0.94, 0.0), YELLOW)


def _style_blade_carriage(carriage: chrono.ChBody) -> None:
    carriage.GetVisualModel().Clear()
    silver = (0.62, 0.66, 0.68)
    add_box_visual(
        carriage, (1.32, 0.12, 0.13), (0.14, 0.58, -0.18), YELLOW, chrono.QuatFromAngleY(0.03)
    )
    add_box_visual(
        carriage, (1.32, 0.12, 0.13), (0.14, -0.58, -0.18), YELLOW, chrono.QuatFromAngleY(0.03)
    )
    add_box_visual(carriage, (0.16, 1.32, 0.17), (-0.52, 0.0, -0.14), YELLOW)

    cylinder_rotation = chrono.QuatFromAngleY(-0.10) * chrono.Q_ROTATE_Z_TO_X
    for y in (-0.36, 0.36):
        add_cylinder_visual(carriage, 0.055, 0.45, (0.52, y, 0.23), cylinder_rotation, YELLOW)
        add_cylinder_visual(carriage, 0.030, 0.75, (-0.08, y, 0.17), cylinder_rotation, silver)
    add_cylinder_visual(carriage, 0.060, 0.30, (0.05, 0.0, 0.37), chrono.Q_ROTATE_Z_TO_X, YELLOW)
    add_cylinder_visual(carriage, 0.032, 0.40, (-0.30, 0.0, 0.37), chrono.Q_ROTATE_Z_TO_X, silver)

    lateral_pin = chrono.QuatFromAngleX(-chrono.CH_PI_2)
    add_cylinder_visual(carriage, 0.065, 0.18, (-0.52, 0.58, -0.18), lateral_pin, DARK_METAL)
    add_cylinder_visual(carriage, 0.065, 0.18, (-0.52, -0.58, -0.18), lateral_pin, DARK_METAL)


def _add_chassis_details(chassis: chrono.ChBody) -> None:
    glass = (0.07, 0.14, 0.18)
    interior = (0.07, 0.08, 0.08)
    add_box_visual(chassis, (0.54, 0.70, 0.48), (0.48, 0.0, 0.91), interior)
    add_box_visual(chassis, (0.50, 0.018, 0.40), (0.48, 0.43, 1.04), glass, opacity=0.78)
    add_box_visual(chassis, (0.50, 0.018, 0.40), (0.48, -0.43, 1.04), glass, opacity=0.78)
    add_box_visual(chassis, (0.018, 0.70, 0.40), (0.18, 0.0, 1.04), glass, opacity=0.78)
    add_box_visual(chassis, (0.018, 0.70, 0.40), (0.78, 0.0, 1.04), glass, opacity=0.72)

    add_cylinder_visual(chassis, 0.050, 0.52, (-0.92, -0.30, 1.06), chrono.QUNIT, DARK_METAL)
    add_box_visual(chassis, (0.14, 0.12, 0.06), (-0.92, -0.30, 1.34), DARK_METAL)
    add_box_visual(chassis, (0.42, 0.025, 0.22), (-0.72, -0.49, 0.58), DARK_METAL)
    for y in (-0.58, 0.58):
        add_box_visual(chassis, (0.20, 0.16, 0.22), (-0.20, y, -0.56), YELLOW)


def _load_chrono_mesh(relative_path: str) -> chrono.ChTriangleMeshConnected:
    path = chrono.GetChronoDataFile(relative_path)
    mesh = chrono.ChTriangleMeshConnected.CreateFromWavefrontFile(path)
    if mesh is None or mesh.GetNumVertices() == 0:
        raise RuntimeError(f"Could not load Project Chrono vehicle asset: {path}")
    return mesh


def _imported_body(
    system: chrono.ChSystem,
    position: tuple[float, float, float],
    mesh: chrono.ChTriangleMeshConnected,
) -> chrono.ChBody:
    body = chrono.ChBody()
    body.SetPos(chrono.ChVector3d(*position))
    body.SetMass(350.0)
    body.SetInertiaXX(chrono.ChVector3d(13.8, 13.5, 10.0))
    add_mesh_visual(
        body,
        mesh,
        (0.0, 0.0, 0.0),
        chrono.QuatFromAngleX(chrono.CH_PI_2),
        YELLOW,
        "Project Chrono B10 bulldozer body",
    )
    system.Add(body)
    return body


def _track_rotor(
    system: chrono.ChSystem,
    position: tuple[float, float, float],
    wheel_mesh: chrono.ChTriangleMeshConnected,
) -> chrono.ChBody:
    body = chrono.ChBody()
    body.SetPos(chrono.ChVector3d(*position))
    body.SetMass(40.0)
    body.SetInertiaXX(chrono.ChVector3d(4.0, 4.0, 4.0))
    add_mesh_visual(
        body,
        wheel_mesh,
        (0.0, 0.0, 0.0),
        chrono.QUNIT,
        (0.14, 0.15, 0.15),
        "Project Chrono B10 drive sprocket",
    )
    outward = -0.15 if position[1] < 0.0 else 0.15
    add_cylinder_visual(
        body,
        0.10,
        0.055,
        (0.0, outward, 0.0),
        chrono.QuatFromAngleX(chrono.CH_PI_2),
        YELLOW,
    )
    system.Add(body)
    return body


def _add_imported_track(
    chassis: chrono.ChBody,
    lateral_position: float,
    shoe_mesh: chrono.ChTriangleMeshConnected,
    wheel_mesh: chrono.ChTriangleMeshConnected,
) -> None:
    track_center_z = -0.55
    wheel_center_x = 0.80
    track_radius = 0.31
    shoe_length = 0.20
    add_box_collision(chassis, (2.22, 0.34, 0.64), (0.0, lateral_position, track_center_z))

    shoe_shape = chrono.ChVisualShapeTriangleMesh(shoe_mesh, False)
    shoe_shape.SetName("Project Chrono B10 track shoes")
    shoe_shape.SetColor(color((0.075, 0.080, 0.080)))
    source_to_simulator = chrono.QuatFromAngleX(chrono.CH_PI_2)

    def add_shoe(path_position: tuple[float, float, float], source_angle: float) -> None:
        rotation = chrono.QuatFromAngleY(-source_angle) * source_to_simulator
        position = chrono.ChVector3d(*path_position) + rotation.Rotate(
            chrono.ChVector3d(-0.5 * shoe_length, 0.0, 0.0)
        )
        chassis.AddVisualShape(shoe_shape, chrono.ChFramed(position, rotation))

    for index in range(7):
        x = -0.60 + shoe_length * index
        add_shoe((x, lateral_position, track_center_z - track_radius), 0.0)
        add_shoe((-x, lateral_position, track_center_z + track_radius), chrono.CH_PI)
    for index in range(6):
        right_angle = chrono.CH_PI * index / 5
        add_shoe(
            (
                wheel_center_x + track_radius * math.sin(right_angle),
                lateral_position,
                track_center_z - track_radius * math.cos(right_angle),
            ),
            right_angle,
        )
        left_angle = chrono.CH_PI + chrono.CH_PI * index / 5
        add_shoe(
            (
                -wheel_center_x + track_radius * math.sin(left_angle),
                lateral_position,
                track_center_z - track_radius * math.cos(left_angle),
            ),
            left_angle,
        )

    for x in (-0.25, 0.30, 0.80):
        add_mesh_visual(
            chassis,
            wheel_mesh,
            (x, lateral_position, track_center_z),
            chrono.QUNIT,
            (0.14, 0.15, 0.15),
            "Project Chrono B10 road wheel",
        )
        outward = -0.15 if lateral_position < 0.0 else 0.15
        add_cylinder_visual(
            chassis,
            0.095,
            0.05,
            (x, lateral_position + outward, track_center_z),
            chrono.QuatFromAngleX(chrono.CH_PI_2),
            YELLOW,
        )


class BulldozerModel:
    """B10 asset-backed bulldozer with independent tracks and an articulated blade."""

    def __init__(self, system: chrono.ChSystem, show_rigid_ground: bool = True) -> None:
        self.system = system
        initial_body_count = len(system.GetBodies())
        self.ground = make_box(
            system,
            (30.0, 20.0, 0.1),
            (4.0, 0.0, -0.05),
            (0.38, 0.30, 0.18),
            visible=show_rigid_ground,
        )
        self.ground.SetFixed(True)

        body_mesh = _load_chrono_mesh("models/bulldozer/bulldozerB10.obj")
        shoe_mesh = _load_chrono_mesh("models/bulldozer/shoe_view.obj")
        wheel_mesh = _load_chrono_mesh("models/bulldozer/wheel_view.obj")
        self._meshes = body_mesh, shoe_mesh, wheel_mesh
        self.imported_vertex_count = sum(mesh.GetNumVertices() for mesh in self._meshes)

        self.chassis = _imported_body(system, (0.0, 0.0, 1.0), body_mesh)
        _add_chassis_details(self.chassis)
        _add_imported_track(self.chassis, 0.60, shoe_mesh, wheel_mesh)
        _add_imported_track(self.chassis, -0.60, shoe_mesh, wheel_mesh)
        self.left_track = _track_rotor(system, (-0.80, 0.60, 0.45), wheel_mesh)
        self.right_track = _track_rotor(system, (-0.80, -0.60, 0.45), wheel_mesh)
        self.blade_carriage = make_box(system, (0.20, 1.30, 0.20), (-1.00, 0.0, 0.62), YELLOW)
        _style_blade_carriage(self.blade_carriage)
        self.blade = make_box(
            system,
            (0.20, 1.95, 0.84),
            (-1.62, 0.0, 0.62),
            YELLOW,
            collidable=True,
        )
        _style_blade(self.blade)

        self.drive = DifferentialDrive(system, self.chassis, self.ground, 2.8)
        hinge_y = chrono.QuatFromAngleX(chrono.CH_PI_2)
        self.left_track_drive = chrono.ChLinkMotorRotationSpeed()
        self.left_track_drive.Initialize(
            self.left_track,
            self.chassis,
            chrono.ChFramed(chrono.ChVector3d(-0.80, 0.60, 0.45), hinge_y),
        )
        self.left_track_drive.SetSpeedFunction(chrono.ChFunctionConst(0.0))
        system.Add(self.left_track_drive)
        self.right_track_drive = chrono.ChLinkMotorRotationSpeed()
        self.right_track_drive.Initialize(
            self.right_track,
            self.chassis,
            chrono.ChFramed(chrono.ChVector3d(-0.80, -0.60, 0.45), hinge_y),
        )
        self.right_track_drive.SetSpeedFunction(chrono.ChFunctionConst(0.0))
        system.Add(self.right_track_drive)

        self.blade_lift = chrono.ChLinkMotorLinearPosition()
        self.blade_lift.Initialize(
            self.blade_carriage,
            self.chassis,
            chrono.ChFramed(chrono.ChVector3d(-1.00, 0.0, 0.62)),
        )
        self.blade_lift.SetMotionFunction(chrono.ChFunctionConst(0.0))
        system.Add(self.blade_lift)
        self.blade_tilt = chrono.ChLinkMotorRotationAngle()
        self.blade_tilt.Initialize(
            self.blade,
            self.blade_carriage,
            chrono.ChFramed(chrono.ChVector3d(-1.38, 0.0, 0.62), hinge_y),
        )
        self.blade_tilt.SetAngleFunction(chrono.ChFunctionConst(0.0))
        system.Add(self.blade_tilt)
        self.body_count = len(system.GetBodies()) - initial_body_count

    def set_drive_speeds(self, left: float, right: float) -> None:
        self.drive.set_speeds(-left, -right)
        self.left_track_drive.SetSpeedFunction(chrono.ChFunctionConst(-left))
        self.right_track_drive.SetSpeedFunction(chrono.ChFunctionConst(-right))

    def set_blade_targets(self, lift: float, tilt: float) -> None:
        self.blade_lift.SetMotionFunction(chrono.ChFunctionConst(lift))
        self.blade_tilt.SetAngleFunction(chrono.ChFunctionConst(tilt))

    def advance(self, step: float) -> None:
        self.drive.synchronize(self.system.GetChTime() + step)
        self.system.DoStepDynamics(step)

    def get_chassis_position(self) -> chrono.ChVector3d:
        position = self.chassis.GetPos()
        return chrono.ChVector3d(position.x, position.y, position.z)

    def get_chassis_heading(self) -> float:
        return self.chassis.GetRot().GetCardanAnglesXYZ().z

    def get_blade_state(self) -> tuple[float, float]:
        return self.blade_lift.GetMotorPos(), self.blade_tilt.GetMotorAngle()

    def get_track_angles(self) -> tuple[float, float]:
        return self.left_track_drive.GetMotorAngle(), self.right_track_drive.GetMotorAngle()
