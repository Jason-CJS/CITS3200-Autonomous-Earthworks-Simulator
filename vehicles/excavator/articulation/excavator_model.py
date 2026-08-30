"""MathScavator9000 excavator model implemented with PyChrono."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import pychrono as chrono

from vehicles.common.chrono_utils import (
    add_box_collision,
    add_box_visual,
    color,
    make_angle_motor,
    make_box,
    vector,
)
from vehicles.common.differential_drive import DifferentialDrive


ASSET_DIR = Path(__file__).resolve().parents[1] / "model" / "assets" / "mathscavator9000"
MATHSCAVATOR_SCALE = 2.8 / 6.24
YELLOW = (0.95, 0.65, 0.05)


@dataclass(frozen=True)
class MeshCalibration:
    translation: tuple[float, float, float]
    rotation_degrees: tuple[float, float, float]
    scale: float


def _load_calibration(path: Path) -> dict[str, MeshCalibration]:
    result: dict[str, MeshCalibration] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        values = raw_line.split("#", 1)[0].split()
        if not values:
            continue
        if len(values) != 8:
            raise ValueError(f"Invalid excavator visual calibration at {path}:{line_number}")
        part = values[0]
        if part not in {"base", "boom", "arm", "bucket"}:
            raise ValueError(f"Unknown excavator part {part!r} at {path}:{line_number}")
        numbers = tuple(float(value) for value in values[1:])
        if not math.isfinite(numbers[6]) or numbers[6] <= 0.0:
            raise ValueError(f"Excavator visual scale must be positive at {path}:{line_number}")
        if part in result:
            raise ValueError(f"Duplicate excavator part {part!r} in {path}")
        result[part] = MeshCalibration(numbers[:3], numbers[3:6], numbers[6])
    missing = {"base", "boom", "arm", "bucket"} - result.keys()
    if missing:
        raise ValueError(f"Missing excavator calibration parts in {path}: {sorted(missing)}")
    return result


def _calibration_frame(calibration: MeshCalibration) -> chrono.ChFramed:
    roll, pitch, yaw = (math.radians(value) for value in calibration.rotation_degrees)
    rotation = (
        chrono.QuatFromAngleZ(yaw)
        * chrono.QuatFromAngleY(pitch)
        * chrono.QuatFromAngleX(roll)
    )
    return chrono.ChFramed(vector(calibration.translation), rotation)


def _load_mesh(filename: str, scale: float) -> chrono.ChTriangleMeshConnected:
    path = ASSET_DIR / filename
    mesh = chrono.ChTriangleMeshConnected.CreateFromSTLFile(str(path))
    if mesh is None or mesh.GetNumVertices() == 0:
        raise RuntimeError(f"Could not load MathScavator9000 vehicle asset: {path}")
    mesh.Transform(chrono.VNULL, chrono.ChMatrix33d(scale))
    return mesh


def _set_imported_visual(
    body: chrono.ChBody,
    mesh: chrono.ChTriangleMeshConnected,
    name: str,
    frame: chrono.ChFramed,
    paint: tuple[float, float, float],
) -> None:
    body.GetVisualModel().Clear()
    shape = chrono.ChVisualShapeTriangleMesh(mesh, False)
    shape.SetName(name)
    shape.SetColor(color(paint))
    body.AddVisualShape(shape, frame)


def _style_cab(cabin: chrono.ChBody) -> None:
    glass = (0.08, 0.18, 0.22)
    add_box_visual(cabin, (0.035, 1.35, 0.72), (1.01, 0.0, 0.18), glass)
    add_box_visual(cabin, (1.20, 0.035, 0.72), (0.20, 0.91, 0.18), glass)
    add_box_visual(cabin, (1.20, 0.035, 0.72), (0.20, -0.91, 0.18), glass)
    add_box_visual(cabin, (2.15, 1.95, 0.12), (0.0, 0.0, 0.80), (0.92, 0.58, 0.02))


def _style_track(chassis: chrono.ChBody, center: tuple[float, float, float]) -> None:
    add_box_visual(chassis, (3.8, 0.55, 0.65), center, (0.12, 0.12, 0.12))
    for index in range(13):
        x = -1.72 + 3.44 * index / 12
        add_box_visual(
            chassis,
            (0.20, 0.60, 0.07),
            (center[0] + x, center[1], center[2] - 0.36),
            (0.20, 0.20, 0.19),
        )
        add_box_visual(
            chassis,
            (0.20, 0.60, 0.07),
            (center[0] + x, center[1], center[2] + 0.36),
            (0.20, 0.20, 0.19),
        )


def _style_track_rotor(rotor: chrono.ChBody) -> None:
    add_box_visual(rotor, (0.45, 0.50, 0.45), (0.0, 0.0, 0.0), (0.18, 0.18, 0.17))
    add_box_visual(rotor, (0.12, 0.58, 0.10), (0.0, 0.0, 0.25), (0.95, 0.65, 0.05))


def _add_joint_marker(body: chrono.ChBody, paint: tuple[float, float, float]) -> None:
    marker = chrono.ChVisualShapeSphere(0.16)
    marker.SetColor(color(paint))
    body.AddVisualShape(marker, chrono.ChFramed(chrono.ChVector3d(0.0, -0.42, 0.0)))


class ExcavatorModel:
    """Asset-backed excavator with imposed track drive and four motorized joints."""

    def __init__(
        self,
        system: chrono.ChSystem,
        show_rigid_ground: bool = True,
        show_calibration_markers: bool = False,
    ) -> None:
        self.system = system
        initial_body_count = len(system.GetBodies())
        self.visual_calibration_path = ASSET_DIR / "visual_calibration.cfg"
        calibration = _load_calibration(self.visual_calibration_path)

        self.ground = make_box(
            system,
            (30.0, 20.0, 0.1),
            (4.0, 0.0, -0.05),
            (0.38, 0.30, 0.18),
            visible=show_rigid_ground,
        )
        self.ground.SetFixed(True)
        self.chassis = make_box(system, (3.6, 2.4, 0.45), (0.0, 0.0, 0.75), (0.22, 0.22, 0.20))
        self.cabin = make_box(system, (2.0, 1.8, 1.5), (0.0, 0.0, 1.75), YELLOW)
        self.left_track = make_box(
            system, (0.20, 0.20, 0.20), (0.0, 1.35, 0.48), (0.12, 0.12, 0.12), visible=False
        )
        self.right_track = make_box(
            system, (0.20, 0.20, 0.20), (0.0, -1.35, 0.48), (0.12, 0.12, 0.12), visible=False
        )
        _style_track_rotor(self.left_track)
        _style_track_rotor(self.right_track)

        boom_pivot = (0.75, 0.0, 2.25)
        arm_pivot = (boom_pivot[0] + 6.24 * MATHSCAVATOR_SCALE, 0.0, boom_pivot[2])
        bucket_pivot = (
            arm_pivot[0] - 0.0091425 * MATHSCAVATOR_SCALE,
            0.0,
            arm_pivot[2] - 2.9796 * MATHSCAVATOR_SCALE,
        )
        self.boom = make_box(system, (2.8, 0.35, 0.35), boom_pivot, YELLOW)
        self.arm = make_box(system, (2.2, 0.30, 0.30), arm_pivot, YELLOW)
        self.bucket = make_box(system, (0.9, 0.52, 1.0), bucket_pivot, (0.90, 0.55, 0.03))
        _style_cab(self.cabin)

        meshes = {
            "base": _load_mesh("base_link.STL", calibration["base"].scale),
            "boom": _load_mesh("chassis_boom_link.STL", calibration["boom"].scale),
            "arm": _load_mesh("boom_stick_link.STL", calibration["arm"].scale),
            "bucket": _load_mesh("stick_bucket_link.STL", calibration["bucket"].scale),
        }
        self._meshes = meshes
        self.imported_vertex_count = sum(mesh.GetNumVertices() for mesh in meshes.values())
        _set_imported_visual(
            self.chassis,
            meshes["base"],
            "MathScavator9000 undercarriage",
            _calibration_frame(calibration["base"]),
            (0.20, 0.20, 0.20),
        )
        _set_imported_visual(
            self.boom,
            meshes["boom"],
            "MathScavator9000 boom",
            _calibration_frame(calibration["boom"]),
            YELLOW,
        )
        _set_imported_visual(
            self.arm,
            meshes["arm"],
            "MathScavator9000 stick",
            _calibration_frame(calibration["arm"]),
            YELLOW,
        )
        _set_imported_visual(
            self.bucket,
            meshes["bucket"],
            "MathScavator9000 bucket",
            _calibration_frame(calibration["bucket"]),
            (0.90, 0.55, 0.03),
        )
        add_box_collision(self.bucket, (0.88, 0.52, 1.00), (-0.384, -0.002, 0.044))
        if show_calibration_markers:
            _add_joint_marker(self.boom, (1.0, 0.0, 0.8))
            _add_joint_marker(self.arm, (0.1, 1.0, 0.1))
            _add_joint_marker(self.bucket, (0.0, 0.9, 1.0))

        left_track_center = (0.0, 1.35, -0.27)
        right_track_center = (0.0, -1.35, -0.27)
        _style_track(self.chassis, left_track_center)
        _style_track(self.chassis, right_track_center)
        add_box_collision(self.chassis, (3.8, 0.55, 0.72), left_track_center)
        add_box_collision(self.chassis, (3.8, 0.55, 0.72), right_track_center)

        self.drive = DifferentialDrive(system, self.chassis, self.ground, 2.7)
        hinge_y = chrono.QuatFromAngleX(chrono.CH_PI_2)
        self.joints = [
            make_angle_motor(system, self.cabin, self.chassis, (0.0, 0.0, 1.0)),
            make_angle_motor(system, self.boom, self.cabin, boom_pivot, hinge_y),
            make_angle_motor(system, self.arm, self.boom, arm_pivot, hinge_y),
            make_angle_motor(system, self.bucket, self.arm, bucket_pivot, hinge_y),
        ]

        self.left_track_drive = chrono.ChLinkMotorRotationSpeed()
        self.left_track_drive.Initialize(
            self.left_track,
            self.chassis,
            chrono.ChFramed(chrono.ChVector3d(0.0, 1.35, 0.48), hinge_y),
        )
        self.left_track_drive.SetSpeedFunction(chrono.ChFunctionConst(0.0))
        system.Add(self.left_track_drive)
        self.right_track_drive = chrono.ChLinkMotorRotationSpeed()
        self.right_track_drive.Initialize(
            self.right_track,
            self.chassis,
            chrono.ChFramed(chrono.ChVector3d(0.0, -1.35, 0.48), hinge_y),
        )
        self.right_track_drive.SetSpeedFunction(chrono.ChFunctionConst(0.0))
        system.Add(self.right_track_drive)
        self.body_count = len(system.GetBodies()) - initial_body_count

    def set_drive_speeds(self, left: float, right: float) -> None:
        self.drive.set_speeds(left, right)
        self.left_track_drive.SetSpeedFunction(chrono.ChFunctionConst(left))
        self.right_track_drive.SetSpeedFunction(chrono.ChFunctionConst(right))

    def set_articulation_targets(self, swing: float, boom: float, arm: float, bucket: float) -> None:
        for motor, target in zip(self.joints, (swing, boom, arm, bucket), strict=True):
            motor.SetAngleFunction(chrono.ChFunctionConst(target))

    def advance(self, step: float) -> None:
        self.drive.synchronize(self.system.GetChTime() + step)
        self.system.DoStepDynamics(step)

    def get_chassis_position(self) -> chrono.ChVector3d:
        position = self.chassis.GetPos()
        return chrono.ChVector3d(position.x, position.y, position.z)

    def get_chassis_heading(self) -> float:
        return self.chassis.GetRot().GetCardanAnglesXYZ().z

    def get_joint_angles(self) -> tuple[float, float, float, float]:
        return tuple(motor.GetMotorAngle() for motor in self.joints)

    def get_track_angles(self) -> tuple[float, float]:
        return self.left_track_drive.GetMotorAngle(), self.right_track_drive.GetMotorAngle()

    def get_articulation_body_positions(self) -> tuple[chrono.ChVector3d, ...]:
        return tuple(
            chrono.ChVector3d(position.x, position.y, position.z)
            for position in (self.boom.GetPos(), self.arm.GetPos(), self.bucket.GetPos())
        )
