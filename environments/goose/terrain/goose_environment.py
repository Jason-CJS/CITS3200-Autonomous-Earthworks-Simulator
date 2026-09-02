#!/usr/bin/env python3
#Load a generated GOOSE-Ex ALICE heightmap as Chrono SCM terrain.

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pychrono as chrono
import pychrono.vehicle as veh


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_SCM_CONFIG = SCRIPT_ROOT.parent / "scene_config" / "alice_scm.json"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def create_system() -> chrono.ChSystemSMC:
    system = chrono.ChSystemSMC()
    system.SetGravitationalAcceleration(chrono.ChVector3d(0, 0, -9.81))
    system.SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
    return system


def create_terrain(
    system: chrono.ChSystemSMC,
    scene_path: Path,
    scene: dict,
    config: dict,
) -> veh.SCMTerrain:
    heightmap_path = (scene_path.parent / scene["heightmap"]).resolve()
    if not heightmap_path.is_file():
        raise FileNotFoundError(f"Generated heightmap not found: {heightmap_path}")

    scm = config["scm"]
    terrain = veh.SCMTerrain(system)
    terrain.SetSoilParameters(
        scm["bekker_kphi"],
        scm["bekker_kc"],
        scm["bekker_n"],
        scm["mohr_cohesion"],
        scm["mohr_friction_degrees"],
        scm["janosi_shear"],
        scm["elastic_stiffness"],
        scm["damping"],
    )
    terrain.EnableBulldozing(bool(scm.get("enable_bulldozing", True)))
    terrain.SetColor(chrono.ChColor(0.36, 0.28, 0.17))
    if config.get("visualization", {}).get("plot_sinkage", False):
        terrain.SetPlotType(veh.SCMTerrain.PLOT_SINKAGE, 0.0, 0.15)

    terrain.Initialize(
        str(heightmap_path),
        float(scene["size_x"]),
        float(scene["size_y"]),
        float(scene["height_min"]),
        float(scene["height_max"]),
        float(config["grid_spacing"]),
    )
    return terrain


def create_visualization(system: chrono.ChSystemSMC, scene: dict):
    import pychrono.irrlicht as irr

    vis = irr.ChVisualSystemIrrlicht()
    vis.SetWindowTitle("GOOSE-Ex ALICE - SCM Terrain")
    vis.SetWindowSize(1280, 720)
    vis.Initialize()
    vis.AddLogo(chrono.GetChronoDataFile("logo_chrono_alpha.png"))
    vis.AddSkyBox()
    camera_height = max(float(scene["height_max"]) + 12.0, 12.0)
    camera_distance = max(float(scene["size_y"]) * 0.65, 15.0)
    target_height = (float(scene["height_min"]) + float(scene["height_max"])) / 2
    vis.AddCamera(
        chrono.ChVector3d(0, -camera_distance, camera_height),
        chrono.ChVector3d(0, 0, target_height),
    )
    vis.AddLightDirectional()
    vis.AttachSystem(system)
    return vis


def run_headless(
    system: chrono.ChSystemSMC,
    terrain: veh.SCMTerrain,
    step_size: float,
    duration: float,
) -> None:
    while system.GetChTime() < duration:
        time = system.GetChTime()
        terrain.Synchronize(time)
        system.DoStepDynamics(step_size)
        terrain.Advance(step_size)


def run_visualized(
    system: chrono.ChSystemSMC,
    terrain: veh.SCMTerrain,
    scene: dict,
    step_size: float,
    duration: float | None,
) -> None:
    vis = create_visualization(system, scene)
    while vis.Run():
        time = system.GetChTime()
        if duration is not None and time >= duration:
            break

        vis.BeginScene()
        vis.Render()
        vis.EndScene()

        terrain.Synchronize(time)
        system.DoStepDynamics(step_size)
        terrain.Advance(step_size)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scene",
        required=True,
        type=Path,
        help="scene.json created by build_heightmap.py",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_SCM_CONFIG,
        help=f"SCM configuration (default: {DEFAULT_SCM_CONFIG})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="initialize and advance without opening Irrlicht",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="optional simulated duration in seconds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scene_path = args.scene.expanduser().resolve()
    config_path = args.config.expanduser().resolve()
    scene = load_json(scene_path)
    config = load_json(config_path)
    step_size = float(config.get("step_size", 0.002))

    system = create_system()
    terrain = create_terrain(system, scene_path, scene, config)
    print(
        f"Loaded {scene['size_x']:.1f} m x {scene['size_y']:.1f} m ALICE "
        f"terrain ({scene['height_min']:.2f} m to {scene['height_max']:.2f} m)."
    )

    if args.headless:
        run_headless(system, terrain, step_size, args.duration or step_size)
        print("Headless initialization test completed.")
    else:
        run_visualized(system, terrain, scene, step_size, args.duration)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
