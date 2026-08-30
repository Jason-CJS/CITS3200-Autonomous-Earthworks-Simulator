"""Differential-drive motion implemented with a real Chrono imposed link."""

from __future__ import annotations

from dataclasses import dataclass
import math

import pychrono as chrono


@dataclass(frozen=True)
class DrivePose:
    x: float
    y: float
    heading: float


class DifferentialDrive:
    """Piecewise-constant track commands feeding a ``ChLinkMotionImposed``."""

    def __init__(
        self,
        system: chrono.ChSystem,
        chassis: chrono.ChBody,
        ground: chrono.ChBody,
        track_width: float,
    ) -> None:
        self._system = system
        self._track_width = track_width
        self._start_time = system.GetChTime()
        self._start_pose = DrivePose(0.0, 0.0, 0.0)
        self._linear_speed = 0.0
        self._angular_speed = 0.0

        self._position_function = chrono.ChFunctionPositionSetpoint()
        self._rotation_function = chrono.ChFunctionRotationSetpoint()
        self._position_function.SetSetpoint(chrono.VNULL, self._start_time)
        self._rotation_function.SetSetpoint(chrono.QUNIT, self._start_time)

        self.link = chrono.ChLinkMotionImposed()
        self.link.Initialize(chassis, ground, chrono.ChFramed(chassis.GetPos()))
        self.link.SetPositionFunction(self._position_function)
        self.link.SetRotationFunction(self._rotation_function)
        system.Add(self.link)

    def set_speeds(self, left: float, right: float) -> None:
        now = self._system.GetChTime()
        self._start_pose = self.evaluate(now)
        self._start_time = now
        self._linear_speed = 0.5 * (left + right)
        self._angular_speed = (right - left) / self._track_width
        self.synchronize(now)

    def evaluate(self, time: float) -> DrivePose:
        elapsed = max(0.0, time - self._start_time)
        heading = self._start_pose.heading + self._angular_speed * elapsed
        x = self._start_pose.x
        y = self._start_pose.y
        if abs(self._angular_speed) < 1e-12:
            x += self._linear_speed * math.cos(self._start_pose.heading) * elapsed
            y += self._linear_speed * math.sin(self._start_pose.heading) * elapsed
        else:
            radius = self._linear_speed / self._angular_speed
            x += radius * (math.sin(heading) - math.sin(self._start_pose.heading))
            y -= radius * (math.cos(heading) - math.cos(self._start_pose.heading))
        return DrivePose(x, y, heading)

    def synchronize(self, time: float) -> None:
        pose = self.evaluate(time)
        self._position_function.SetSetpoint(chrono.ChVector3d(pose.x, pose.y, 0.0), time)
        self._rotation_function.SetSetpoint(chrono.QuatFromAngleZ(pose.heading), time)
