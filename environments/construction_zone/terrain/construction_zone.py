"""
Construction Zone environment (AARP-reflective)

Scope: This is a basic flat-ground SCM deformable terrain patch only. No vehicle,
no vegetation/structures.

Run `python construction_zone.py` to test on local Linux machine.

Structured into separate functions (system / terrain / visualization)
rather than one flat main(). This eases future integration (e.g. adding a
vehicle, static objects like ramps or stockpiles, or soil parameter tuning) to
extend this without restructuring what's already validated here.

Adding a vehicle later: ChWheeledVehicle (which HMMWV_Full is built on)
supports attaching to an existing ChSystem rather than always creating
its own. Example: `veh.HMMWV_Full(system)` instead of `veh.HMMWV_Full()`.
The intended extension: Developers to pass the `system` this script
already creates into the vehicle constructor, rather than letting the
vehicle create a second, disconnected system.

Soil parameters and grid spacing to be adjusted if AARP-specific
soil data/requirement becomes available.
"""

import pychrono as chrono
import pychrono.vehicle as veh
import pychrono.irrlicht as irr


# Patch dimensions and grid spacing (tentative)

TERRAIN_LENGTH = 20.0   # size in X direction (m)
TERRAIN_WIDTH = 20.0    # size in Y direction (m)
DELTA = 0.15            # SCM grid spacing (m) 

STEP_SIZE = 2e-3


def create_system():
    """
    Creates the standalone ChSystemSMC this scene runs on.

    Note for future vehicle work: don't create a second system alongside
    this one. Either:
    1. Keep this function as the single source of the system (recommended)
    2. If a vehicle's default constructor is used instead:
    	fetch the 'system' it creates via vehicle.GetSystem()
    	pass that into create_terrain() instead. Two independently
    	created systems will not interact with each other.
    """
    system = chrono.ChSystemSMC()
    system.SetGravitationalAcceleration(chrono.ChVector3d(0, 0, -9.81))
    system.SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
    return system


def create_terrain(system):
    """
    Creates the flat SCM deformable terrain patch on the given system.

    Soil parameters are tentative placeholders.
    To be revisited with AARP-specific values here if/when real soil
    data becomes available. 
    """
    terrain = veh.SCMTerrain(system)

    terrain.SetSoilParameters(
        2e6,    # Bekker Kphi
        0,      # Bekker Kc
        1.1,    # Bekker n exponent
        0,      # Mohr cohesive limit (Pa)
        30,     # Mohr friction limit (degrees)
        0.01,   # Janosi shear coefficient (m)
        2e8,    # Elastic stiffness (Pa/m), before plastic yield
        3e4     # Damping (Pa s/m), proportional to negative vertical speed
    )

    # Show terrain sinkage/deformation
    terrain.SetPlotType(veh.SCMTerrain.PLOT_SINKAGE, 0, 0.1)

    terrain.Initialize(TERRAIN_LENGTH, TERRAIN_WIDTH, DELTA)
    return terrain


def add_static_objects(system):
    """
    Placeholder for static scene geometry:
    e.g Ramps, stockpiles, or a temporary test body to visually confirm
    SCM deformation is live before a real vehicle is wired in. 
    """
    pass


def create_visualization(system):
    """
    General-purpose Irrlicht visualization (no vehicle here).

    Note for future vehicle work: this is the piece that changes, not
    the terrain/system setup above. Swap to
    veh.ChWheeledVehicleVisualSystemIrrlicht() + vis.SetChaseCamera(...)
    and vis.AttachVehicle(...) instead of AddCamera()/AttachSystem()
    when a vehicle is added.
    """
    vis = irr.ChVisualSystemIrrlicht()
    vis.SetWindowTitle('AARP Construction Zone - Flat Ground SCM Terrain')
    vis.SetWindowSize(960, 720)
    vis.Initialize()
    vis.AddLogo(chrono.GetChronoDataFile('logo_chrono_alpha.png'))
    vis.AddSkyBox()
    vis.AddCamera(chrono.ChVector3d(0, -7, 3), chrono.ChVector3d(0, 0, 0))
    vis.AddLightDirectional()
    vis.AttachSystem(system)
    return vis


def main():
    system = create_system()
    terrain = create_terrain(system)
    add_static_objects(system)
    vis = create_visualization(system)

    while vis.Run():
        time = system.GetChTime()

        vis.BeginScene()
        vis.Render()
        vis.EndScene()

        terrain.Synchronize(time)
        system.DoStepDynamics(STEP_SIZE)
        terrain.Advance(STEP_SIZE)

    return 0


if __name__ == "__main__":
    main()
