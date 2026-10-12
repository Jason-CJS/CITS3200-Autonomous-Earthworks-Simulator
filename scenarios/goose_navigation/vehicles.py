"""Small adapters for the existing vehicle models and keyboard controllers.

Selection and footprint validation work without importing PyChrono. The model
and controller imports happen only when a validated simulation needs them.
"""

from __future__ import annotations

from dataclasses import dataclass

from scenarios.goose_navigation.traversal import (
    BULLDOZER_FOOTPRINT,
    EXCAVATOR_FOOTPRINT,
    VehicleFootprint,
)


DRIVE_CONTROLS = (
    "W / S     Drive forward / reverse",
    "A / D     Steer left / right",
    "SPACE     Stop",
)
CAMERA_CONTROLS = (
    "",
    "Left drag          Rotate camera",
    "Right drag         Pan camera",
    "Scroll             Zoom camera",
    "Left+Right drag    Zoom camera",
)
EXCAVATOR_TARGETS = (0.0, 0.25, -0.45, 0.45)


@dataclass(frozen=True)
class NavigationVehicle:
    key: str
    label: str
    direction: int
    footprint: VehicleFootprint
    articulation_controls: tuple[str, ...]
    # Initial camera position and target relative to the start pose, in metres.
    camera_offset: tuple[float, float, float]
    camera_target_offset: tuple[float, float, float]

    @property
    def controls(self) -> tuple[str, ...]:
        return DRIVE_CONTROLS + self.articulation_controls + CAMERA_CONTROLS

    def create_model(self, system, initial_xy: tuple[float, float], terrain_height: float):
        # Both existing models place track contact about 0.15 m below their
        # default origin. The anchor remains collision-free in SCM scenarios.
        options = dict(
            show_rigid_ground=False,
            initial_z_offset=terrain_height - 0.15,
            initial_xy=initial_xy,
        )
        if self.key == "bulldozer":
            from vehicles.bulldozer.articulation.bulldozer_model import BulldozerModel

            model = BulldozerModel(system, **options)
            model.set_blade_targets(0.12, 0.0)
        else:
            from vehicles.excavator.articulation.excavator_model import ExcavatorModel

            model = ExcavatorModel(system, **options)
            model.set_articulation_targets(*EXCAVATOR_TARGETS)
        return model

    def create_controller(self, model, keyboard):
        if self.key == "bulldozer":
            from src.bulldozer_main import BulldozerController

            controller = BulldozerController(model, keyboard)
            controller.blade[0] = 0.12
            return controller
        from src.excavator_main import ExcavatorController

        return ExcavatorController(model, keyboard, calibration=False)


VEHICLES = {
    "bulldozer": NavigationVehicle(
        "bulldozer", "Project Chrono B10 bulldozer", -1, BULLDOZER_FOOTPRINT,
        ("R / F     Raise / lower blade", "T / G     Tilt blade forward / back",
         "X         Reset blade"),
        # The original Issue #26 view, unchanged.
        camera_offset=(4.0, -10.0, 7.0),
        camera_target_offset=(-1.0, 0.0, 0.0),
    ),
    "excavator": NavigationVehicle(
        "excavator", "MathScavator9000 excavator", 1, EXCAVATOR_FOOTPRINT,
        ("Q / E     Swing left / right", "R / F     Raise / lower boom",
         "T / G     Extend / retract arm", "Y / H     Curl / uncurl bucket",
         "X         Reset articulation"),
        # The standalone excavator demo's view: the boom and bucket face the
        # camera's right, so the whole arm stays in frame.
        camera_offset=(8.5, -11.0, 6.0),
        camera_target_offset=(1.8, 0.0, 1.2),
    ),
}


def select_vehicle(name: str) -> NavigationVehicle:
    if name not in VEHICLES:
        raise ValueError("vehicle must be bulldozer or excavator")
    return VEHICLES[name]
