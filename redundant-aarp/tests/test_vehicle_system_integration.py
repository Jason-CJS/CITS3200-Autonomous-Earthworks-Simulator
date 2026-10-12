from __future__ import annotations

import unittest

import pychrono as chrono

from environments.construction_zone.terrain import construction_zone
from src import bulldozer_main, excavator_main
from vehicles.bulldozer.articulation.bulldozer_model import BulldozerModel
from vehicles.excavator.articulation.excavator_model import ExcavatorModel


class VehicleSystemIntegrationTest(unittest.TestCase):
    def test_vehicles_use_external_aarp_system_and_deform_its_scm_terrain(self) -> None:
        cases = (
            (
                "excavator",
                ExcavatorModel,
                lambda model: model.set_articulation_targets(0.1, 0.2, -0.2, 0.2),
            ),
            (
                "bulldozer",
                BulldozerModel,
                lambda model: model.set_blade_targets(0.05, 0.05),
            ),
        )

        for name, model_type, set_articulation in cases:
            with self.subTest(vehicle=name):
                system = construction_zone.create_system()
                terrain = construction_zone.create_terrain(system)
                construction_zone.add_static_objects(system)
                scene_object = chrono.ChBody()
                scene_object.SetFixed(True)
                system.Add(scene_object)

                model = model_type(
                    system,
                    show_rigid_ground=False,
                    initial_z_offset=-0.15,
                )
                self.assertIs(model.system, system)
                self.assertFalse(model.ground.IsCollisionEnabled())

                model.set_drive_speeds(0.2, 0.2)
                set_articulation(model)
                for _ in range(20):
                    model.advance(0.001)

                self.assertAlmostEqual(system.GetChTime(), 0.02)
                self.assertGreater(len(terrain.GetModifiedNodes(True)), 0)

        self.assertTrue(callable(excavator_main.main))
        self.assertTrue(callable(bulldozer_main.main))


if __name__ == "__main__":
    unittest.main()
