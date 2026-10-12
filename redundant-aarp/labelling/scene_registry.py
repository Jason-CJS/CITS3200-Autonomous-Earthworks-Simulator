"""Validated scene metadata and deterministic JSON manifest export.

Coordinates use the Chrono world frame: right-handed, metres, +X forward,
+Y left and +Z up. ``position`` is the object's approximate centre and
``size`` is its full axis-aligned extent along X, Y and Z.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Iterable

from .semantic_labels import SemanticCategory


SCHEMA_VERSION = "1.0"


def _vector3(name: str, values: Iterable[float]) -> tuple[float, float, float]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of three real numbers")
    try:
        result = tuple(values)
    except TypeError as error:
        raise TypeError(f"{name} must be a sequence of three real numbers") from error
    if len(result) != 3:
        raise ValueError(f"{name} must contain exactly three values")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in result):
        raise TypeError(f"{name} must contain only real numbers")
    converted = tuple(float(value) for value in result)
    if not all(math.isfinite(value) for value in converted):
        raise ValueError(f"{name} values must be finite")
    return converted


@dataclass(frozen=True)
class SemanticObject:
    instance_id: str
    category: SemanticCategory | str
    position: tuple[float, float, float]
    size: tuple[float, float, float]
    display_name: str | None = None
    source_object: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise ValueError("instance_id must be a non-empty string")
        if self.display_name is not None and (
            not isinstance(self.display_name, str) or not self.display_name.strip()
        ):
            raise ValueError("display_name must be a non-empty string or None")
        category = SemanticCategory.parse(self.category)
        position = _vector3("position", self.position)
        size = _vector3("size", self.size)
        if any(value <= 0 for value in size):
            raise ValueError("size values must all be greater than zero")
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "position", position)
        object.__setattr__(self, "size", size)

    @property
    def class_id(self) -> int:
        return int(self.category)

    @property
    def class_name(self) -> str:
        return self.category.class_name

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "instance_id": self.instance_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "position": list(self.position),
            "size": list(self.size),
        }
        if self.display_name is not None:
            record["display_name"] = self.display_name
        return record


class SceneRegistry:
    """Collection of unique semantic objects for one simulator scene."""

    def __init__(self) -> None:
        self._objects: dict[str, SemanticObject] = {}

    def register(self, semantic_object: SemanticObject) -> SemanticObject:
        if not isinstance(semantic_object, SemanticObject):
            raise TypeError("register expects a SemanticObject")
        if semantic_object.instance_id in self._objects:
            raise ValueError(f"duplicate semantic instance_id: {semantic_object.instance_id!r}")
        self._objects[semantic_object.instance_id] = semantic_object
        return semantic_object

    def __len__(self) -> int:
        return len(self._objects)

    def __iter__(self):
        return iter(sorted(self._objects.values(), key=lambda item: item.instance_id))

    def manifest(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "coordinate_system": {
                "frame": "chrono_world",
                "handedness": "right-handed",
                "units": "metres",
                "axes": {"x": "forward", "y": "left", "z": "up"},
            },
            "objects": [semantic_object.to_record() for semantic_object in self],
        }

    def to_json(self) -> str:
        return json.dumps(self.manifest(), indent=2, sort_keys=True) + "\n"

    def export_json(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.write_text(self.to_json(), encoding="utf-8")
        return output_path
