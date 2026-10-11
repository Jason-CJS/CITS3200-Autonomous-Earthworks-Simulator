"""Reusable simulator ground-truth labelling primitives."""

from importlib import import_module

_EXPORTS = {
    "CATEGORY_COLOURS": ".semantic_labels",
    "SceneRegistry": ".scene_registry",
    "SemanticCategory": ".semantic_labels",
    "SemanticObject": ".scene_registry",
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    """Load public objects only when they are requested."""
    if name not in _EXPORTS:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    module = import_module(_EXPORTS[name], package=__name__)
    value = getattr(module, name)
    globals()[name] = value
    return value