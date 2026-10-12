from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pychrono as chrono

from environments.construction_zone.terrain import construction_zone
from labelling.scene_registry import SCHEMA_VERSION, SceneRegistry, SemanticObject
from labelling.semantic_labels import SemanticCategory


class SemanticCategoryTests(unittest.TestCase):
    def test_fixed_class_ids(self) -> None:
        self.assertEqual(
            {category.class_name: category.value for category in SemanticCategory},
            {
                "unknown": 0,
                "terrain": 1,
                "sand": 2,
                "tree": 3,
                "rock": 4,
                "debris": 5,
                "structure": 6,
                "vehicle": 7,
            },
        )

    def test_category_serialisation(self) -> None:
        semantic_object = SemanticObject("tree-001", "tree", (1, 2, 3), (4, 5, 6))
        self.assertEqual(semantic_object.class_id, 3)
        self.assertEqual(semantic_object.class_name, "tree")
        self.assertEqual(semantic_object.to_record()["class_name"], "tree")

    def test_invalid_category_is_not_changed_to_unknown(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown semantic category"):
            SemanticObject("bad-001", "shrub", (0, 0, 0), (1, 1, 1))
        with self.assertRaisesRegex(TypeError, "category"):
            SemanticObject("bad-002", 3, (0, 0, 0), (1, 1, 1))


class SceneRegistryTests(unittest.TestCase):
    @staticmethod
    def _object(instance_id: str, category: str = "rock") -> SemanticObject:
        return SemanticObject(instance_id, category, (1, 2, 3), (4, 5, 6))

    def test_unique_instance_ids(self) -> None:
        registry = SceneRegistry()
        first = registry.register(self._object("rock-001"))
        second = registry.register(self._object("rock-002"))
        self.assertEqual([item.instance_id for item in registry], ["rock-001", "rock-002"])
        self.assertIs(first, next(iter(registry)))
        self.assertEqual(len(registry), 2)
        self.assertNotEqual(first.instance_id, second.instance_id)

    def test_duplicate_instance_id_is_rejected(self) -> None:
        registry = SceneRegistry()
        registry.register(self._object("rock-001"))
        with self.assertRaisesRegex(ValueError, "duplicate.*rock-001"):
            registry.register(self._object("rock-001", "debris"))

    def test_position_and_size_validation(self) -> None:
        invalid_cases = (
            ("position", (0, 0), (1, 1, 1), ValueError),
            ("position", (0, "x", 0), (1, 1, 1), TypeError),
            ("position", (0, float("nan"), 0), (1, 1, 1), ValueError),
            ("size", (0, 0, 0), (1, 0, 1), ValueError),
            ("size", (0, 0, 0), (1, True, 1), TypeError),
        )
        for expected_message, position, size, error_type in invalid_cases:
            with self.subTest(position=position, size=size):
                with self.assertRaisesRegex(error_type, expected_message):
                    SemanticObject("object-001", "rock", position, size)

    def test_malformed_identifiers_and_registration_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "instance_id"):
            SemanticObject(" ", "rock", (0, 0, 0), (1, 1, 1))
        with self.assertRaisesRegex(ValueError, "display_name"):
            SemanticObject("rock-001", "rock", (0, 0, 0), (1, 1, 1), "")
        with self.assertRaisesRegex(TypeError, "SemanticObject"):
            SceneRegistry().register({"instance_id": "rock-001"})

    def test_ordering_and_json_are_deterministic(self) -> None:
        first = SceneRegistry()
        second = SceneRegistry()
        for instance_id in ("tree-010", "rock-002", "debris-005"):
            first.register(self._object(instance_id))
        for instance_id in ("debris-005", "tree-010", "rock-002"):
            second.register(self._object(instance_id))
        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual(
            [item["instance_id"] for item in json.loads(first.to_json())["objects"]],
            ["debris-005", "rock-002", "tree-010"],
        )

    def test_empty_registry_export(self) -> None:
        registry = SceneRegistry()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scene.json"
            returned = registry.export_json(output)
            self.assertEqual(returned, output)
            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], SCHEMA_VERSION)
        self.assertEqual(data["objects"], [])
        self.assertEqual(data["coordinate_system"]["axes"]["z"], "up")


class AarpIntegrationTests(unittest.TestCase):
    def test_scene_registers_the_existing_terrain(self) -> None:
        system = construction_zone.create_system()
        registry = SceneRegistry()
        terrain = construction_zone.create_terrain(system, registry)
        registered = tuple(registry)
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0].instance_id, "aarp-terrain-001")
        self.assertEqual(registered[0].category, SemanticCategory.TERRAIN)
        self.assertEqual(registered[0].size[:2], (20.0, 20.0))
        self.assertIs(registered[0].source_object, terrain)

    def test_uses_caller_created_chsystemsmc(self) -> None:
        system = chrono.ChSystemSMC()
        system.SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
        registry = SceneRegistry()
        terrain = construction_zone.create_terrain(system, registry)
        self.assertIs(tuple(registry)[0].source_object, terrain)
        system.DoStepDynamics(construction_zone.STEP_SIZE)
        self.assertAlmostEqual(system.GetChTime(), construction_zone.STEP_SIZE)

    def test_existing_creation_without_registry(self) -> None:
        system = construction_zone.create_system()
        terrain = construction_zone.create_terrain(system)
        construction_zone.add_static_objects(system)
        self.assertIsNotNone(terrain)

    def test_invalid_registry_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "SceneRegistry"):
            construction_zone.create_terrain(construction_zone.create_system(), {})

    def test_import_has_no_filesystem_side_effects(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import labelling.semantic_labels; import labelling.scene_registry",
                ],
                cwd=directory,
                env={"PYTHONPATH": str(repository)},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
