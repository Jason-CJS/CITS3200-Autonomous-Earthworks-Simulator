# =============================================================================
# PROJECT CHRONO - http://projectchrono.org
#
# Copyright (c) 2014 projectchrono.org
# All rights reserved.
#
# Use of this source code is governed by a BSD-style license that can be found
# in the LICENSE file at the top level of the distribution and at
# http://projectchrono.org/license-chrono.txt.
#
# =============================================================================
# Authors: Radu Serban
# =============================================================================
#
# Demonstration of vehicle over SCM deformable terrain
#
# The vehicle reference frame has Z up, X towards the front of the vehicle, and
# Y pointing to the left. All units SI.
#
# =============================================================================

import argparse
import math
from pathlib import Path

import pychrono as chrono
import pychrono.irrlicht as irr
import pychrono.vehicle as veh

from scm_deformation_export import (
    calculate_scm_grid_geometry,
    collect_deformation_records,
    write_deformation_export,
)


TERRAIN_LENGTH_M = 20.0
TERRAIN_WIDTH_M = 10.0
REQUESTED_GRID_SPACING_M = 0.15
STEP_SIZE_S = 2e-3
SIMULATION_DURATION_S = 6.0

GRID_GEOMETRY = calculate_scm_grid_geometry(
    TERRAIN_LENGTH_M,
    TERRAIN_WIDTH_M,
    REQUESTED_GRID_SPACING_M,
)

SOIL_PARAMETERS = {
    "bekker_kphi": 2e6,
    "bekker_kc": 0,
    "bekker_n": 1.1,
    "mohr_cohesion_pa": 0,
    "mohr_friction_degrees": 30,
    "janosi_shear_m": 0.01,
    "elastic_stiffness_pa_per_m": 2e8,
    "damping_pa_s_per_m": 3e4,
}


class MyDriver(veh.ChDriver):
    def __init__(self, vehicle, delay):
        veh.ChDriver.__init__(self, vehicle)
        self.delay = delay

    def Synchronize(self, time):
        effective_time = time - self.delay
        if effective_time < 0:
            return

        if effective_time > 0.2:
            self.SetThrottle(0.7)
        else:
            self.SetThrottle(3.5 * effective_time)

        if effective_time < 2:
            self.SetSteering(0.0)
        else:
            self.SetSteering(
                0.6 * math.sin(2.0 * math.pi * (effective_time - 2) / 6)
            )

        self.SetBraking(0.0)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the HMMWV SCM terrain deformation demonstration."
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="Optional directory for final deformation CSV and JSON files.",
    )
    return parser.parse_args()


def create_vehicle():
    hmmwv = veh.HMMWV_Full()
    hmmwv.SetContactMethod(chrono.ChContactMethod_SMC)
    hmmwv.SetInitPosition(
        chrono.ChCoordsysd(
            chrono.ChVector3d(-5, -2, 0.6),
            chrono.ChQuaterniond(1, 0, 0, 0),
        )
    )
    hmmwv.SetEngineType(veh.EngineModelType_SHAFTS)
    hmmwv.SetTransmissionType(veh.TransmissionModelType_AUTOMATIC_SHAFTS)
    hmmwv.SetDriveType(veh.DrivelineTypeWV_AWD)
    hmmwv.SetTireType(veh.TireModelType_RIGID)
    hmmwv.Initialize()

    hmmwv.SetChassisVisualizationType(chrono.VisualizationType_NONE)
    hmmwv.SetSuspensionVisualizationType(chrono.VisualizationType_PRIMITIVES)
    hmmwv.SetSteeringVisualizationType(chrono.VisualizationType_PRIMITIVES)
    hmmwv.SetWheelVisualizationType(chrono.VisualizationType_NONE)
    hmmwv.SetTireVisualizationType(chrono.VisualizationType_MESH)

    hmmwv.GetSystem().SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
    return hmmwv


def create_terrain(system, chassis_body):
    terrain = veh.SCMTerrain(system)
    terrain.SetSoilParameters(
        SOIL_PARAMETERS["bekker_kphi"],
        SOIL_PARAMETERS["bekker_kc"],
        SOIL_PARAMETERS["bekker_n"],
        SOIL_PARAMETERS["mohr_cohesion_pa"],
        SOIL_PARAMETERS["mohr_friction_degrees"],
        SOIL_PARAMETERS["janosi_shear_m"],
        SOIL_PARAMETERS["elastic_stiffness_pa_per_m"],
        SOIL_PARAMETERS["damping_pa_s_per_m"],
    )

    terrain.AddActiveDomain(
        chassis_body,
        chrono.ChVector3d(0, 0, 0),
        chrono.ChVector3d(5, 3, 1),
    )
    terrain.SetPlotType(veh.SCMTerrain.PLOT_SINKAGE, 0, 0.1)
    terrain.Initialize(
        TERRAIN_LENGTH_M,
        TERRAIN_WIDTH_M,
        REQUESTED_GRID_SPACING_M,
    )
    return terrain


def create_visualization(hmmwv):
    visualization = veh.ChWheeledVehicleVisualSystemIrrlicht()
    visualization.SetWindowTitle("HMMWV Deformable Soil Demo")
    visualization.SetWindowSize(960, 720)
    visualization.SetChaseCamera(chrono.ChVector3d(0.0, 0.0, 1.75), 6.0, 0.5)
    visualization.Initialize()
    visualization.AddLogo(chrono.GetChronoDataFile("logo_chrono_alpha.png"))
    visualization.AddLightDirectional()
    visualization.AddSkyBox()
    visualization.AttachVehicle(hmmwv.GetVehicle())
    return visualization


def export_final_deformation(terrain, output_directory, simulation_duration_s):
    modified_nodes = terrain.GetModifiedNodes(True)
    records = collect_deformation_records(
        modified_nodes,
        GRID_GEOMETRY.actual_spacing_m,
    )

    simulation_settings = {
        "vehicle": "HMMWV_Full",
        "simulation_duration_s": simulation_duration_s,
        "target_duration_s": SIMULATION_DURATION_S,
        "step_size_s": STEP_SIZE_S,
        "terrain": {
            "requested_length_m": GRID_GEOMETRY.requested_length_m,
            "requested_width_m": GRID_GEOMETRY.requested_width_m,
            "requested_grid_spacing_m": GRID_GEOMETRY.requested_spacing_m,
            "actual_grid_spacing_m": GRID_GEOMETRY.actual_spacing_m,
            "grid_node_count_x": GRID_GEOMETRY.node_count_x,
            "grid_node_count_y": GRID_GEOMETRY.node_count_y,
        },
        "soil_parameters": SOIL_PARAMETERS,
    }
    csv_path, summary_path = write_deformation_export(
        records,
        output_directory,
        simulation_settings,
    )
    print(f"Exported {len(records)} modified SCM nodes to {csv_path}")
    print(f"Exported deformation summary to {summary_path}")


def main(export_directory=None):
    hmmwv = create_vehicle()

    driver = MyDriver(hmmwv.GetVehicle(), 0.5)
    driver.Initialize()

    terrain = create_terrain(hmmwv.GetSystem(), hmmwv.GetChassisBody())
    visualization = create_visualization(hmmwv)
    realtime_timer = chrono.ChRealtimeStepTimer()

    while visualization.Run():
        time = hmmwv.GetSystem().GetChTime()
        if time >= SIMULATION_DURATION_S:
            break

        visualization.BeginScene()
        visualization.Render()
        visualization.EndScene()

        driver_inputs = driver.GetInputs()

        driver.Synchronize(time)
        terrain.Synchronize(time)
        hmmwv.Synchronize(time, driver_inputs, terrain)
        visualization.Synchronize(time, driver_inputs)

        driver.Advance(STEP_SIZE_S)
        terrain.Advance(STEP_SIZE_S)
        hmmwv.Advance(STEP_SIZE_S)
        visualization.Advance(STEP_SIZE_S)
        realtime_timer.Spin(STEP_SIZE_S)

    if export_directory is not None:
        export_final_deformation(
            terrain,
            export_directory,
            hmmwv.GetSystem().GetChTime(),
        )

    return 0


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(main(arguments.export_dir))
