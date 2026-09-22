"""Shared deformable SCM soil patch for the PyChrono demos."""

from __future__ import annotations

import pychrono as chrono
import pychrono.vehicle as vehicle


class SCMDemoTerrain:
    def __init__(self, system: chrono.ChSystem) -> None:
        self.terrain = vehicle.SCMTerrain(system)
        self.terrain.SetReferenceFrame(
            chrono.ChCoordsysd(chrono.ChVector3d(4.0, 0.0, 0.15), chrono.QUNIT)
        )
        self.terrain.Initialize(20.0, 12.0, 0.10)
        self.terrain.SetSoilParameters(
            0.2e6,
            0.0,
            1.1,
            0.0,
            30.0,
            0.01,
            4e7,
            3e4,
        )
        self.terrain.EnableBulldozing(True)
        self.terrain.SetBulldozingParameters(55.0, 1.0, 3, 4)
        self.terrain.SetTestHeight(0.20)
        self.terrain.SetPlotType(vehicle.SCMTerrain.PLOT_NONE, 0.0, 0.16)
        self.terrain.SetColor(chrono.ChColor(0.30, 0.18, 0.08))
        self.terrain.SetMeshWireframe(False)

    def get_modified_node_count(self) -> int:
        return len(self.terrain.GetModifiedNodes(True))
