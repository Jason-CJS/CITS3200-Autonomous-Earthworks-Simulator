"""Reusable simulator ground-truth labelling primitives."""

from .scene_registry import SceneRegistry, SemanticObject
from .semantic_labels import CATEGORY_COLOURS, SemanticCategory

__all__ = ["CATEGORY_COLOURS", "SceneRegistry", "SemanticCategory", "SemanticObject"]
