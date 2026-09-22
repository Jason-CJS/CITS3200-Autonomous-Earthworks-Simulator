"""Small PyChrono construction helpers shared by both vehicle models."""

from __future__ import annotations

from collections.abc import Sequence

import pychrono as chrono


Color = tuple[float, float, float]
Vector = Sequence[float]


def vector(values: Vector) -> chrono.ChVector3d:
    return chrono.ChVector3d(float(values[0]), float(values[1]), float(values[2]))


def color(values: Color) -> chrono.ChColor:
    return chrono.ChColor(*values)


def make_box(
    system: chrono.ChSystem,
    size: Vector,
    position: Vector,
    paint: Color,
    *,
    visible: bool = True,
    collidable: bool = False,
) -> chrono.ChBody:
    material = None
    if collidable:
        material = chrono.ChContactMaterialNSC()
        material.SetFriction(0.8)
    body = chrono.ChBodyEasyBox(
        float(size[0]),
        float(size[1]),
        float(size[2]),
        780.0,
        visible,
        collidable,
        material,
    )
    body.SetPos(vector(position))
    if visible:
        body.GetVisualShape(0).SetColor(color(paint))
    system.Add(body)
    return body


def add_box_visual(
    body: chrono.ChBody,
    size: Vector,
    position: Vector,
    paint: Color,
    rotation: chrono.ChQuaterniond | None = None,
    opacity: float = 1.0,
) -> None:
    shape = chrono.ChVisualShapeBox(float(size[0]), float(size[1]), float(size[2]))
    shape.SetColor(color(paint))
    shape.SetOpacity(opacity)
    body.AddVisualShape(shape, chrono.ChFramed(vector(position), rotation or chrono.QUNIT))


def add_cylinder_visual(
    body: chrono.ChBody,
    radius: float,
    length: float,
    position: Vector,
    rotation: chrono.ChQuaterniond,
    paint: Color,
) -> None:
    shape = chrono.ChVisualShapeCylinder(radius, length)
    shape.SetColor(color(paint))
    body.AddVisualShape(shape, chrono.ChFramed(vector(position), rotation))


def add_mesh_visual(
    body: chrono.ChBody,
    mesh: chrono.ChTriangleMeshConnected,
    position: Vector,
    rotation: chrono.ChQuaterniond,
    paint: Color,
    name: str,
) -> None:
    shape = chrono.ChVisualShapeTriangleMesh(mesh, False)
    shape.SetName(name)
    shape.SetColor(color(paint))
    body.AddVisualShape(shape, chrono.ChFramed(vector(position), rotation))


def add_box_collision(body: chrono.ChBody, size: Vector, position: Vector) -> None:
    material = chrono.ChContactMaterialNSC()
    material.SetFriction(0.8)
    shape = chrono.ChCollisionShapeBox(material, float(size[0]), float(size[1]), float(size[2]))
    body.AddCollisionShape(shape, chrono.ChFramed(vector(position)))
    body.EnableCollision(True)


def make_angle_motor(
    system: chrono.ChSystem,
    child: chrono.ChBody,
    parent: chrono.ChBody,
    pivot: Vector,
    orientation: chrono.ChQuaterniond | None = None,
) -> chrono.ChLinkMotorRotationAngle:
    motor = chrono.ChLinkMotorRotationAngle()
    motor.Initialize(child, parent, chrono.ChFramed(vector(pivot), orientation or chrono.QUNIT))
    motor.SetAngleFunction(chrono.ChFunctionConst(0.0))
    system.Add(motor)
    return motor
