"""Display-only detail for the excavator: cab, joints, tracks and hydraulics.

Nothing here adds bodies, collision shapes or mass. Static parts are ordinary
visual shapes; hydraulic cylinders span two moving bodies, so they are mutable
meshes whose vertices are rewritten by ``HydraulicCylinder.update``.
"""

from __future__ import annotations

import math

import numpy as np
import pychrono as chrono

from vehicles.common.chrono_utils import add_box_visual, add_cylinder_visual, color


YELLOW = (0.95, 0.65, 0.05)  # the model's original paint
ROOF = (0.92, 0.58, 0.02)
DEEP_YELLOW = (0.86, 0.58, 0.05)
CHARCOAL = (0.16, 0.16, 0.15)
STEEL = (0.32, 0.31, 0.29)
CHROME = (0.82, 0.83, 0.84)
GLASS = (0.08, 0.18, 0.22)
TRACK = (0.11, 0.11, 0.10)

AXIS_Y = chrono.QuatFromAngleX(chrono.CH_PI_2)  # cylinder axis Z -> Y


def style_cab(cabin: chrono.ChBody) -> None:
    """The original yellow cab, ending just behind the boom foot.

    Coordinates are in the cabin body frame: the swing bearing is at z=-0.75
    and the boom pivot at (0.75, 0, 0.5). The cab used to enclose that pivot,
    so the boom appeared to grow out of the cab front.
    """
    cabin.GetVisualModel().Clear()
    add_box_visual(cabin, (1.55, 1.8, 1.5), (-0.225, 0.0, 0.0), YELLOW)
    add_box_visual(cabin, (0.035, 1.35, 0.72), (0.56, 0.0, 0.18), GLASS)
    for side in (-1, 1):
        add_box_visual(cabin, (1.10, 0.035, 0.72), (-0.10, side * 0.91, 0.18), GLASS)
    add_box_visual(cabin, (1.70, 1.95, 0.12), (-0.225, 0.0, 0.80), ROOF)
    # Front deck and boom foot: lugs either side of the boom root and the pin.
    add_box_visual(cabin, (0.62, 1.8, 0.30), (0.86, 0.0, -0.60), STEEL)
    add_box_visual(cabin, (0.55, 0.50, 0.80), (0.83, 0.0, -0.10), DEEP_YELLOW)
    for side in (-1, 1):
        add_box_visual(cabin, (0.50, 0.06, 0.50), (0.75, side * 0.21, 0.45), DEEP_YELLOW)
    add_cylinder_visual(cabin, 0.08, 0.54, (0.75, 0.0, 0.50), AXIS_Y, STEEL)
    # Cross pin carrying the twin boom cylinders.
    add_cylinder_visual(cabin, 0.07, 0.72, (1.05, 0.0, -0.40), AXIS_Y, STEEL)


def add_joint_pin(body: chrono.ChBody, position: tuple[float, float, float],
                  length: float = 0.50) -> None:
    """A steel pin through a hinge, so the links read as connected."""
    add_cylinder_visual(body, 0.065, length, position, AXIS_Y, STEEL)


def style_track(chassis: chrono.ChBody, center: tuple[float, float, float]) -> None:
    """A track loop with round idler/sprocket ends and rollers; ``TrackShoes`` adds the shoes."""
    cx, cy, cz = center
    outer = 1 if cy > 0 else -1
    half_length, radius = 1.575, 0.325
    add_box_visual(chassis, (2 * half_length, 0.55, 0.65), center, TRACK)
    for end in (-1, 1):
        add_cylinder_visual(chassis, radius, 0.55, (cx + end * half_length, cy, cz), AXIS_Y, TRACK)
    # Track frame, rollers and end hubs on the outer face.
    face = cy + outer * 0.285
    add_box_visual(chassis, (2.8, 0.03, 0.30), (cx, face, cz), STEEL)
    for index in range(5):
        x = cx - 1.0 + 0.5 * index
        add_cylinder_visual(chassis, 0.09, 0.05, (x, face + outer * 0.02, cz - 0.20), AXIS_Y, CHARCOAL)
    for x in (cx - 0.6, cx + 0.6):
        add_cylinder_visual(chassis, 0.07, 0.05, (x, face + outer * 0.02, cz + 0.22), AXIS_Y, CHARCOAL)
    add_cylinder_visual(chassis, 0.24, 0.06, (cx - half_length, face + outer * 0.01, cz),
                        AXIS_Y, STEEL)
    add_cylinder_visual(chassis, 0.20, 0.06, (cx + half_length, face + outer * 0.01, cz),
                        AXIS_Y, STEEL)
    add_cylinder_visual(chassis, 0.10, 0.08, (cx - half_length, face + outer * 0.03, cz),
                        AXIS_Y, DEEP_YELLOW)


TRACK_HALF_LENGTH_M = 1.575  # straight run, centre to idler/sprocket axle
SHOE_LOOP_RADIUS_M = 0.36    # shoe centres around the idler and sprocket
SHOE_SIZE_M = (0.17, 0.60, 0.06)  # along the loop, across the track, thickness
SHOES_PER_TRACK = 40


def shoe_poses(distance: float, count: int = SHOES_PER_TRACK) -> tuple[np.ndarray, np.ndarray]:
    """Shoe centres (x, z) and outward normals around one track loop, track-local.

    ``distance`` is how far the track has turned. Going forward, the bottom run
    moves back towards the sprocket, over the rear wheel, forward along the top
    and down round the front idler, as on a real crawler.
    """
    half, r = TRACK_HALF_LENGTH_M, SHOE_LOOP_RADIUS_M
    straight, arc = 2 * half, np.pi * r
    perimeter = 2 * (straight + arc)
    p = (np.arange(count) * perimeter / count + distance) % perimeter
    centres, normals = np.empty((count, 2)), np.empty((count, 2))
    for k, q in enumerate(p):
        if q < straight:                       # bottom run, moving back
            centres[k], normals[k] = (half - q, -r), (0.0, -1.0)
        elif q < straight + arc:               # round the rear sprocket
            phi = (q - straight) / r
            normals[k] = (-np.sin(phi), -np.cos(phi))
            centres[k] = (-half + r * normals[k][0], r * normals[k][1])
        elif q < 2 * straight + arc:           # top run, moving forward
            centres[k], normals[k] = (-half + (q - straight - arc), r), (0.0, 1.0)
        else:                                  # round the front idler
            phi = (q - 2 * straight - arc) / r
            normals[k] = (np.sin(phi), np.cos(phi))
            centres[k] = (half + r * normals[k][0], r * normals[k][1])
    return centres, normals


_BOX_TRIANGLES = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
                  (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


class TrackShoes:
    """Grouser shoes that travel around a track loop as the track turns (display only)."""

    def __init__(self, chassis: chrono.ChBody, center: tuple[float, float, float]) -> None:
        self.center = np.array(center, dtype=float)
        triangles = [(8 * k + a, 8 * k + b, 8 * k + c)
                     for k in range(SHOES_PER_TRACK) for a, b, c in _BOX_TRIANGLES]
        self.mesh = MutableMesh(chassis, 8 * SHOES_PER_TRACK, triangles, (0.20, 0.20, 0.19))
        self.update(0.0)

    def update(self, distance: float) -> None:
        length, width, thickness = SHOE_SIZE_M
        centres, normals = shoe_poses(distance)
        tangents = np.stack((-normals[:, 1], normals[:, 0]), axis=1)
        points = np.empty((SHOES_PER_TRACK, 8, 3))
        corner = 0
        for a in (-0.5, 0.5):          # along the loop
            for b in (-0.5, 0.5):      # across the track
                for c in (-0.5, 0.5):  # through the shoe
                    xz = centres + a * length * tangents + c * thickness * normals
                    points[:, corner, 0] = self.center[0] + xz[:, 0]
                    points[:, corner, 1] = self.center[1] + b * width
                    points[:, corner, 2] = self.center[2] + xz[:, 1]
                    corner += 1
        self.mesh.set_vertices(points.reshape(-1, 3))


def style_track_rotor(rotor: chrono.ChBody) -> None:
    """The track-drive indicator: a hub with one yellow spoke that turns with the track."""
    add_cylinder_visual(rotor, 0.15, 0.64, (0.0, 0.0, 0.0), AXIS_Y, STEEL)
    add_box_visual(rotor, (0.05, 0.66, 0.26), (0.0, 0.0, 0.0), DEEP_YELLOW)


def prism_triangles(sides: int) -> list[tuple[int, int, int]]:
    """Triangles for a closed prism built by ``prism_vertices``."""
    triangles = []
    for k in range(sides):
        a0, a1 = k, (k + 1) % sides
        b0, b1 = a0 + sides, a1 + sides
        triangles += [(a0, a1, b1), (a0, b1, b0)]
        triangles += [(2 * sides, a1, a0), (2 * sides + 1, b0, b1)]
    return triangles


def prism_vertices(start: np.ndarray, end: np.ndarray, radius: float, sides: int) -> np.ndarray:
    """Vertices for a ``sides``-gon tube from ``start`` to ``end`` with cap centres."""
    axis = end - start
    length = float(np.linalg.norm(axis))
    axis = axis / length if length > 1e-9 else np.array([0.0, 0.0, 1.0])
    helper = np.array([0.0, 1.0, 0.0]) if abs(axis[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    angles = 2 * np.pi * np.arange(sides) / sides
    ring = radius * (np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * v)
    return np.vstack((start + ring, end + ring, start, end))


class MutableMesh:
    """A triangle mesh on ``body`` whose vertices can be rewritten every frame."""

    def __init__(self, body: chrono.ChBody, n_vertices: int,
                 triangles: list[tuple[int, int, int]], paint: tuple[float, float, float]) -> None:
        self.mesh = chrono.ChTriangleMeshConnected()
        vertices = self.mesh.GetCoordsVertices()
        for _ in range(n_vertices):
            vertices.push_back(chrono.ChVector3d(0.0, 0.0, 0.0))
        indices = self.mesh.GetIndicesVertices()
        for triangle in triangles:
            indices.push_back(chrono.ChVector3i(*triangle))
        self.shape = chrono.ChVisualShapeTriangleMesh()
        self.shape.SetMesh(self.mesh)
        self.shape.SetMutable(True)
        self.shape.SetDoubleFaced(True)
        self.shape.SetColor(color(paint))
        body.AddVisualShape(self.shape)

    def set_vertices(self, points: np.ndarray) -> None:
        vertices = self.mesh.GetCoordsVertices()
        for index, (x, y, z) in enumerate(points):
            vertices[index] = chrono.ChVector3d(float(x), float(y), float(z))


class HydraulicCylinder:
    """Barrel on ``base_body`` and chrome rod reaching an anchor on ``rod_body``."""

    SIDES = 10

    def __init__(self, base_body: chrono.ChBody, base_local: tuple[float, float, float],
                 rod_body: chrono.ChBody, rod_local: tuple[float, float, float],
                 radius: float, barrel_share: float = 0.58) -> None:
        self.base_body, self.rod_body = base_body, rod_body
        self.base_local = np.array(base_local, dtype=float)
        self.rod_local = chrono.ChVector3d(*rod_local)
        self.radius, self.barrel_share = radius, barrel_share
        triangles = prism_triangles(self.SIDES)
        count = 2 * self.SIDES + 2
        self.barrel = MutableMesh(base_body, count, triangles, CHARCOAL)
        self.rod = MutableMesh(base_body, count, triangles, CHROME)
        self.update()

    def update(self) -> None:
        # Express the rod anchor in the barrel body's frame, where the mesh lives.
        anchor = self.rod_body.TransformPointLocalToParent(self.rod_local)
        local = self.base_body.TransformPointParentToLocal(anchor)
        end = np.array([local.x, local.y, local.z])
        split = self.base_local + self.barrel_share * (end - self.base_local)
        overlap = self.base_local + (self.barrel_share - 0.08) * (end - self.base_local)
        self.barrel.set_vertices(prism_vertices(self.base_local, split, self.radius, self.SIDES))
        self.rod.set_vertices(prism_vertices(overlap, end, 0.55 * self.radius, self.SIDES))
