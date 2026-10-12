"""Stable semantic categories shared by simulator scenes.

The integer values are part of the exported-data contract. They must not be
renumbered or derived from scene registration order.
"""

from enum import IntEnum


class SemanticCategory(IntEnum):
    UNKNOWN = 0
    TERRAIN = 1
    SAND = 2
    TREE = 3
    ROCK = 4
    DEBRIS = 5
    STRUCTURE = 6
    VEHICLE = 7

    @property
    def class_name(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, value: "SemanticCategory | str") -> "SemanticCategory":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise TypeError("category must be a SemanticCategory or category-name string")
        try:
            return cls[value.upper()]
        except KeyError as error:
            supported = ", ".join(category.class_name for category in cls)
            raise ValueError(f"unknown semantic category {value!r}; expected one of: {supported}") from error


# RGB values are floats in the range expected by chrono.ChColor.
CATEGORY_COLOURS: dict[SemanticCategory, tuple[float, float, float]] = {
    SemanticCategory.UNKNOWN: (0.50, 0.50, 0.50),
    SemanticCategory.TERRAIN: (0.55, 0.35, 0.20),
    SemanticCategory.SAND: (0.95, 0.78, 0.38),
    SemanticCategory.TREE: (0.20, 0.65, 0.25),
    SemanticCategory.ROCK: (0.40, 0.42, 0.45),
    SemanticCategory.DEBRIS: (0.85, 0.25, 0.20),
    SemanticCategory.STRUCTURE: (0.25, 0.50, 0.90),
    SemanticCategory.VEHICLE: (0.80, 0.25, 0.80),
}
