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

Semantic metadata can be exported without opening a window with::

    python -m environments.construction_zone.terrain.construction_zone \
        --manifest semantic_outputs/aarp.scene-manifest.json --smoke-test

Add ``--semantic-debug`` for fixed class colouring and the on-screen legend.
Floating world-space text is deliberately omitted because PyChrono 10 does
not provide a reliable world-to-screen text attachment for ``SCMTerrain``.
"""

from __future__ import annotations

import argparse
import ctypes
from pathlib import Path
import sys

import pychrono as chrono
import pychrono.vehicle as veh
import pychrono.irrlicht as irr

from labelling.scene_registry import SceneRegistry, SemanticObject
from labelling.semantic_labels import CATEGORY_COLOURS, SemanticCategory


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


def create_terrain(system, registry=None, semantic_debug=False):
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

    if semantic_debug:
        terrain.SetPlotType(veh.SCMTerrain.PLOT_NONE, 0, 0.1)
    else:
        # Preserve the normal sinkage/deformation display.
        terrain.SetPlotType(veh.SCMTerrain.PLOT_SINKAGE, 0, 0.1)

    terrain.Initialize(TERRAIN_LENGTH, TERRAIN_WIDTH, DELTA)
    if semantic_debug:
        terrain.SetMeshWireframe(False)
        terrain.SetColor(chrono.ChColor(*CATEGORY_COLOURS[SemanticCategory.TERRAIN]))

    if registry is not None:
        if not isinstance(registry, SceneRegistry):
            raise TypeError("registry must be a SceneRegistry or None")
        registry.register(
            SemanticObject(
                instance_id="aarp-terrain-001",
                category=SemanticCategory.TERRAIN,
                display_name="AARP SCM terrain",
                position=(0.0, 0.0, 0.0),
                size=(TERRAIN_LENGTH, TERRAIN_WIDTH, DELTA),
                source_object=terrain,
            )
        )
    return terrain


def add_static_objects(system):
    """
    Placeholder for static scene geometry:
    e.g Ramps, stockpiles, or a temporary test body to visually confirm
    SCM deformation is live before a real vehicle is wired in. 
    """
    pass


def create_visualization(system, semantic_debug=False, driver=None):
    """
    General-purpose Irrlicht visualization (no vehicle here).

    Note for future vehicle work: this is the piece that changes, not
    the terrain/system setup above. Swap to
    veh.ChWheeledVehicleVisualSystemIrrlicht() + vis.SetChaseCamera(...)
    and vis.AttachVehicle(...) instead of AddCamera()/AttachSystem()
    when a vehicle is added.
    """
    vis = irr.ChVisualSystemIrrlicht()
    if driver is not None:
        _set_linux_irrlicht_driver(vis, driver)
    vis.SetWindowTitle('AARP Construction Zone - Flat Ground SCM Terrain')
    vis.SetWindowSize(960, 720)
    vis.Initialize()
    vis.AddLogo(chrono.GetChronoDataFile('logo_chrono_alpha.png'))
    vis.AddSkyBox()
    vis.AddCamera(chrono.ChVector3d(0, -7, 3), chrono.ChVector3d(0, 0, 0))
    vis.AddLightDirectional()
    vis.AttachSystem(system)
    if semantic_debug:
        _add_semantic_legend(vis)
    return vis


def _add_semantic_legend(vis):
    """Add a reliable screen-space legend for semantic debug mode."""
    lines = ["SEMANTIC CLASSES"]
    for category in SemanticCategory:
        red, green, blue = CATEGORY_COLOURS[category]
        lines.append(
            f"{category.value}  {category.class_name:<9}  "
            f"RGB({round(red * 255):3}, {round(green * 255):3}, {round(blue * 255):3})"
        )
    vis.GetGUIEnvironment().addStaticText(
        "\n".join(lines),
        irr.recti(638, 12, 948, 42 + 18 * len(lines)),
        True,
        False,
        None,
        -1,
        True,
    )


def _set_linux_irrlicht_driver(vis, driver):
    """Select null (0) or BurningVideo (2) despite a PyChrono Linux binding gap."""
    if not sys.platform.startswith("linux"):
        return
    library = ctypes.CDLL(str(Path(irr.__file__).resolve().parents[3] / "libChrono_irrlicht.so"))
    setter = getattr(
        library,
        "_ZN6chrono8irrlicht22ChVisualSystemIrrlicht13SetDriverTypeEN3irr5video13E_DRIVER_TYPEE",
    )
    setter.argtypes = [ctypes.c_void_p, ctypes.c_int]
    setter.restype = None
    shared_pointer_address = int(vis.this)
    object_address = ctypes.c_void_p.from_address(shared_pointer_address).value
    setter(object_address, driver)


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Run the AARP construction-zone scene")
    parser.add_argument("--semantic-debug", action="store_true", help="show semantic colours and legend")
    parser.add_argument("--manifest", type=Path, help="export the semantic scene manifest")
    parser.add_argument("--capture", type=Path, help="write one deterministic scene image and exit")
    parser.add_argument("--smoke-test", action="store_true", help="render headlessly and exit")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    system = create_system()
    registry = SceneRegistry()
    terrain = create_terrain(system, registry, args.semantic_debug)
    add_static_objects(system)
    if args.manifest is not None:
        registry.export_json(args.manifest)
        print(f"Semantic manifest written to {args.manifest}")
    driver = 0 if args.smoke_test else (2 if args.capture is not None else None)
    vis = create_visualization(system, args.semantic_debug, driver)

    while vis.Run():
        time = system.GetChTime()

        vis.BeginScene()
        vis.Render()
        vis.EndScene()

        terrain.Synchronize(time)
        system.DoStepDynamics(STEP_SIZE)
        terrain.Advance(STEP_SIZE)

        if args.capture is not None:
            vis.WriteImageToFile(str(args.capture))
            print(f"AARP scene screenshot written to {args.capture}")
            break
        if args.smoke_test:
            print("AARP graphics smoke test passed")
            break

    return 0


if __name__ == "__main__":
    main()
