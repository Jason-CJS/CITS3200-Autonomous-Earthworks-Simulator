"""Load saved label rasters and render PNG previews without running Chrono.

Supports issue #22's scene v2 / semantic legend v1 exports, plus the earlier
viewer fixture format. See README.md for the input contract and colour policy.
"""

from __future__ import annotations

import colorsys
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError


class ViewerError(ValueError):
    """An input cannot be viewed; suitable for a concise CLI error."""


@dataclass(frozen=True)
class LegendEntry:
    class_id: int
    name: str
    color: tuple[int, int, int]


@dataclass(frozen=True)
class LabelMap:
    kind: str
    path: Path
    values: np.ndarray
    legend: dict[int, LegendEntry]
    nodata: int | None = None


@dataclass(frozen=True)
class SceneLabels:
    path: Path
    maps: tuple[LabelMap, ...]
    heightmap_path: Path | None
    heightmap: np.ndarray | None
    legend_path: Path
    warnings: tuple[str, ...]
    input_paths: tuple[Path, ...]


@dataclass(frozen=True)
class PreviewResult:
    paths: tuple[Path, ...]
    warnings: tuple[str, ...]


# Display colours only: IDs, names and category membership come from the legend.
COARSE_COLOURS = {
    "ignored": (91, 100, 112),
    "vegetation": (38, 139, 74),
    "terrain": (170, 119, 68),
    "structure": (189, 86, 84),
    "vehicle": (55, 111, 195),
    "road": (137, 119, 156),
    "object": (223, 146, 50),
    "sign": (209, 183, 32),
    "human": (214, 92, 157),
    "water": (43, 177, 200),
    "animal": (130, 92, 61),
    "sky": (147, 206, 238),
}


def fallback_colour(kind: str, class_id: int, name: str) -> tuple[int, int, int]:
    """Stable across scenes, map selections, and legend ordering; no random seed."""
    if kind == "coarse" and name in COARSE_COLOURS:
        return COARSE_COLOURS[name]
    if name in {"undefined", "ignored"}:
        return (91, 100, 112)
    hue = (class_id * 0.618033988749895) % 1
    saturation = 0.55 + 0.15 * ((class_id // 8) % 2)
    value = 0.80 + 0.15 * ((class_id // 16) % 2)
    return tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, saturation, value))


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ViewerError(f"Cannot read JSON file {path}: {error}") from error
    if not isinstance(value, dict):
        raise ViewerError(f"Expected a JSON object in {path}.")
    return value


def referenced_path(root: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ViewerError(f"{field} must be a non-empty file path.")
    # Path joining preserves absolute paths; relative paths belong to the scene.
    return (root / Path(value).expanduser()).resolve()


def parse_color(value: object, context: str) -> tuple[int, int, int]:
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
    if (
        isinstance(value, list)
        and len(value) == 3
        and all(type(channel) is int and 0 <= channel <= 255 for channel in value)
    ):
        return tuple(value)
    raise ViewerError(
        f"Invalid colour for {context}; use #RRGGBB or three integer RGB values (0..255)."
    )


def load_legend(
    path: Path, kinds: tuple[str, ...], *, document: dict | None = None,
) -> dict[str, dict[int, LegendEntry]]:
    document = read_json(path) if document is None else document
    version = document.get("format_version", 1)
    if type(version) is not int or version != 1:
        raise ViewerError(f"Unsupported legend format_version {version!r} in {path}.")
    result = {}
    for kind in kinds:
        if "classes" in document:
            taxonomy = document.get("coarse_taxonomy", {})
            if not isinstance(taxonomy, dict):
                raise ViewerError("Legend coarse_taxonomy must be an object.")
            rows = document.get("classes") if kind == "fine" else taxonomy.get("categories")
        else:
            rows = document.get(kind)
        if not isinstance(rows, list) or not rows:
            raise ViewerError(f"Legend {path} needs a non-empty '{kind}' class list.")
        entries = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ViewerError(f"Every '{kind}' legend entry must be an object.")
            class_id = row.get("id")
            name = row.get("name")
            if type(class_id) is not int or not isinstance(name, str) or not name.strip():
                raise ViewerError(f"Each '{kind}' legend entry needs an integer id and name.")
            if class_id in entries:
                raise ViewerError(f"Duplicate {kind} class ID {class_id} in {path}.")
            name = name.strip()
            color = (
                parse_color(row["color"], f"{kind} ID {class_id}") if "color" in row
                else fallback_colour(kind, class_id, name)
            )
            entries[class_id] = LegendEntry(class_id, name, color)
        result[kind] = entries
    return result


def path_value(reference: object) -> object:
    return reference.get("path") if isinstance(reference, dict) else reference


def output_reference(scene: dict, key: str) -> object:
    outputs = scene.get("outputs", {})
    if not isinstance(outputs, dict):
        raise ViewerError("scene.json 'outputs' must be an object.")
    return outputs.get(key, scene.get(key))


def label_metadata(scene: dict) -> dict:
    outputs = scene.get("outputs", {})
    if not isinstance(outputs, dict):
        raise ViewerError("scene.json 'outputs' must be an object.")
    if any(key in outputs for key in ("semantic_fine", "semantic_coarse", "semantic_legend")):
        return {
            name: outputs[key] for name, key in (
                ("fine", "semantic_fine"), ("coarse", "semantic_coarse"),
                ("legend", "semantic_legend"),
            ) if key in outputs
        }
    metadata = scene.get("label_maps", {})
    if not isinstance(metadata, dict):
        raise ViewerError("scene.json 'label_maps' must be an object.")
    return metadata


def unobserved_id(kind: str, declared: int | None, semantics: dict, legend: dict) -> int | None:
    candidates = [] if declared is None else [declared]
    for source in (semantics, legend):
        taxonomy = source.get(f"{kind}_taxonomy", {})
        if not isinstance(taxonomy, dict):
            raise ViewerError(f"{kind}_taxonomy must be an object.")
        if "unobserved_id" in taxonomy:
            candidates.append(taxonomy["unobserved_id"])
    if any(type(value) is not int for value in candidates):
        raise ViewerError(f"{kind} unobserved/no-data ID must be an integer.")
    if len(set(candidates)) > 1:
        raise ViewerError(f"Conflicting {kind} unobserved/no-data IDs in scene and legend.")
    return candidates[0] if candidates else None


def validate_alignment(scene: dict, legend: dict) -> None:
    expected = {"row_zero": "ymax", "column_zero": "xmin",
                "x_direction": "increasing", "y_direction": "decreasing"}
    for name, metadata in (("scene grid", scene.get("grid", {})),
                           ("legend grid_alignment", legend.get("grid_alignment", {}))):
        if not isinstance(metadata, dict):
            raise ViewerError(f"{name} must be an object.")
        for key, value in expected.items():
            if key in metadata and metadata[key] != value:
                raise ViewerError(f"Unsupported {name} {key}={metadata[key]!r}; expected {value!r}.")


def validate_raster_metadata(reference: object, values: np.ndarray, name: str) -> None:
    if not isinstance(reference, dict):
        return
    if "shape" in reference and reference["shape"] != list(values.shape):
        raise ViewerError(f"{name} shape {values.shape} does not match its manifest shape.")
    if "dtype" in reference and reference["dtype"] != str(values.dtype):
        raise ViewerError(f"{name} dtype {values.dtype} does not match its manifest dtype.")


def read_array(path: Path) -> np.ndarray:
    try:
        if path.suffix.lower() == ".npy":
            values = np.load(path, allow_pickle=False)
        elif path.suffix.lower() in {".png", ".bmp", ".tif", ".tiff"}:
            with Image.open(path) as source:
                # Do not convert palette images to RGB: their indices are class IDs.
                values = np.array(source)
        else:
            raise ViewerError(f"Unsupported raster {path}; use .npy or a single-channel image.")
    except (OSError, ValueError, EOFError, UnidentifiedImageError) as error:
        raise ViewerError(f"Cannot load raster {path}: {error}") from error
    if not isinstance(values, np.ndarray):
        # np.load also recognises ZIP archives even when named with .npy.
        values.close()
        raise ViewerError(f"Expected a single raster in {path}; archives are not supported.")
    if values.ndim != 2 or values.size == 0:
        raise ViewerError(
            f"Expected a non-empty 2D raster in {path}; got shape {values.shape}. "
            "Per-point label arrays and RGB previews are not label-map rasters."
        )
    return values


def read_label_map(path: Path) -> np.ndarray:
    values = read_array(path)
    if values.dtype.kind not in "iu":
        raise ViewerError(f"Label map {path} must contain integer IDs; got {values.dtype}.")
    return values


def normalise_heightmap(path: Path) -> np.ndarray:
    values = read_array(path)
    if values.dtype.kind not in "iuf":
        raise ViewerError(f"Heightmap {path} must contain numeric heights.")
    values = values.astype(np.float64)
    if not np.isfinite(values).all():
        raise ViewerError(f"Heightmap {path} contains non-finite heights.")
    low, high = float(values.min()), float(values.max())
    if low == high:
        return np.full(values.shape, 0.5)
    return (values - low) / (high - low)


def load_scene(
    scene_path: Path,
    *,
    selection: str = "both",
    fine_map: Path | None = None,
    coarse_map: Path | None = None,
    legend_path: Path | None = None,
    overlay: bool = False,
    heightmap_path: Path | None = None,
) -> SceneLabels:
    if selection not in {"fine", "coarse", "both"}:
        raise ViewerError("Map selection must be fine, coarse, or both.")
    scene_path = scene_path.expanduser().resolve()
    scene = read_json(scene_path)
    version = scene.get("format_version", 1)
    if type(version) is not int or version not in (1, 2):
        raise ViewerError(f"Unsupported scene format_version {version!r}; supported versions are 1 and 2.")
    semantics = scene.get("semantics", {})
    if not isinstance(semantics, dict):
        raise ViewerError("scene.json 'semantics' must be an object.")
    version = semantics.get("format_version", 1)
    if type(version) is not int or version != 1:
        raise ViewerError(f"Unsupported semantics format_version {version!r}.")
    root = scene_path.parent
    metadata = label_metadata(scene)
    requested = ("fine", "coarse") if selection == "both" else (selection,)
    overrides = {"fine": fine_map, "coarse": coarse_map}
    available = []
    messages = []
    for kind in requested:
        reference = metadata.get(kind)
        override = overrides[kind]
        if override is None and reference is None:
            messages.append(f"No {kind} label map is declared in {scene_path.name}.")
            continue
        if isinstance(reference, dict):
            map_name = reference.get("path")
            nodata = reference.get("nodata")
        else:
            map_name, nodata = reference, None
        if nodata is not None and type(nodata) is not int:
            raise ViewerError(f"label_maps.{kind}.nodata must be an integer.")
        path = (
            override.expanduser().resolve() if override is not None
            else referenced_path(root, map_name, f"label_maps.{kind}")
        )
        available.append((kind, path, nodata))
    if not available:
        raise ViewerError(
            "No requested semantic label maps are available. This scene may predate "
            "the label export from issue #22. Use a scene with saved 2D label rasters, "
            "or specify --fine-map/--coarse-map and --legend. The viewer does not generate labels."
        )
    if legend_path is None:
        if "legend" not in metadata:
            raise ViewerError("No label legend is declared; supply --legend or outputs.semantic_legend.")
        legend_path = referenced_path(root, path_value(metadata["legend"]), "semantic legend")
    else:
        legend_path = legend_path.expanduser().resolve()
    legend_document = read_json(legend_path)
    legends = load_legend(legend_path, tuple(kind for kind, _, _ in available), document=legend_document)
    validate_alignment(scene, legend_document)
    loaded = []
    for kind, path, nodata in available:
        values = read_label_map(path)
        if overrides[kind] is None:
            validate_raster_metadata(metadata.get(kind), values, f"{kind} label map")
        nodata = unobserved_id(kind, nodata, semantics, legend_document)
        if nodata is not None and not np.iinfo(values.dtype).min <= nodata <= np.iinfo(values.dtype).max:
            raise ViewerError(f"{kind} unobserved ID {nodata} cannot be represented by {values.dtype}.")
        if nodata in legends[kind]:
            raise ViewerError(f"{kind} unobserved ID {nodata} is also defined as a class in the legend.")
        loaded.append(LabelMap(kind, path, values, legends[kind], nodata))
    maps = tuple(loaded)
    if len({item.values.shape for item in maps}) > 1:
        raise ViewerError("Fine and coarse maps have different shapes; expected the same scene grid.")
    grid = scene.get("grid", {})
    for key, actual in (("height", maps[0].values.shape[0]), ("width", maps[0].values.shape[1])):
        if key in grid and (type(grid[key]) is not int or grid[key] != actual):
            raise ViewerError(f"Scene grid {key} does not match the label-map shape.")

    heightmap = None
    chosen_heightmap = None
    if overlay:
        if heightmap_path is not None:
            chosen_heightmap = heightmap_path.expanduser().resolve()
        else:
            for key in ("height_grid", "heightmap"):
                reference = output_reference(scene, key)
                if reference is not None:
                    candidate = referenced_path(root, path_value(reference), key)
                    if candidate.is_file():
                        chosen_heightmap = candidate
                        break
        if chosen_heightmap is None:
            raise ViewerError("No heightmap is available for the overlay; supply --heightmap.")
        heightmap = normalise_heightmap(chosen_heightmap)
        if heightmap.shape != maps[0].values.shape:
            raise ViewerError(
                f"Heightmap shape {heightmap.shape} differs from label-map shape "
                f"{maps[0].values.shape}; automatic resizing could misalign labels."
            )
    # Protect all declared source files, including maps not selected for display
    # and the heightmap when no overlay was requested.
    inputs = {scene_path, legend_path, *(item.path for item in maps)}
    references = [scene.get("height_grid"), scene.get("heightmap"), metadata.get("legend")]
    references.extend(scene.get("outputs", {}).values())
    for kind in ("fine", "coarse"):
        reference = metadata.get(kind)
        references.append(reference.get("path") if isinstance(reference, dict) else reference)
    for reference in references:
        reference = path_value(reference)
        if isinstance(reference, str) and reference.strip():
            inputs.add(referenced_path(root, reference, "input"))
    if chosen_heightmap is not None:
        inputs.add(chosen_heightmap)
    return SceneLabels(
        scene_path, maps, chosen_heightmap, heightmap, legend_path, tuple(messages),
        tuple(sorted(inputs)),
    )


def colourise(label_map: LabelMap) -> tuple[np.ndarray, list[LegendEntry], list[str]]:
    """Use exact legend RGB values; show unknown IDs rather than mislabelling them."""
    rgb = np.empty((*label_map.values.shape, 3), dtype=np.uint8)
    entries = []
    messages = []
    for value in np.unique(label_map.values):
        class_id = int(value)
        if class_id == label_map.nodata:
            entry = LegendEntry(class_id, "No data", (210, 210, 210))
        elif class_id in label_map.legend:
            entry = label_map.legend[class_id]
        else:
            entry = LegendEntry(class_id, f"Unknown ID {class_id}", (255, 0, 255))
            messages.append(f"{label_map.kind} ID {class_id} is absent from the legend; shown in magenta.")
        rgb[label_map.values == value] = entry.color
        entries.append(entry)
    return rgb, entries, messages


def composite(
    rgb: np.ndarray,
    label_map: LabelMap,
    heightmap: np.ndarray | None,
    alpha: float,
) -> np.ndarray:
    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ViewerError("Overlay alpha must be between 0 and 1.")
    if heightmap is None:
        return rgb
    background = np.repeat(heightmap[:, :, None], 3, axis=2) * 255
    result = np.rint(alpha * rgb + (1 - alpha) * background)
    if label_map.nodata is not None:
        missing = label_map.values == label_map.nodata
        result[missing] = np.rint(background[missing])
    return result.astype(np.uint8)


def render_previews(
    scene: SceneLabels,
    output_dir: Path,
    *,
    alpha: float = 0.55,
    dpi: int = 150,
) -> PreviewResult:
    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ViewerError("Overlay alpha must be between 0 and 1.")
    if type(dpi) is not int or not 50 <= dpi <= 600:
        raise ViewerError("DPI must be an integer between 50 and 600.")
    # Use Agg directly so saving works without a display server or PyChrono.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import Patch

    output_dir = output_dir.expanduser().resolve()
    name = scene.path.parent.name if scene.path.name == "scene.json" else scene.path.stem
    mode = "overlay" if scene.heightmap is not None else "labels"
    paths = tuple(output_dir / f"{name}_{item.kind}_{mode}.png" for item in scene.maps)
    inputs = scene.input_paths
    for path in paths:
        # Protect against explicit name collisions and links to an input file.
        if path.resolve() in inputs or any(
            path.exists() and source.exists() and path.samefile(source) for source in inputs
        ):
            raise ViewerError(f"Output {path} would overwrite an input; choose another output directory.")
    output_dir.mkdir(parents=True, exist_ok=True)
    messages = list(scene.warnings)
    for item, path in zip(scene.maps, paths):
        rgb, entries, warnings = colourise(item)
        messages.extend(warnings)
        pixels = composite(rgb, item, scene.heightmap, alpha)
        columns = max(1, math.ceil(len(entries) / 22))
        figure = Figure(figsize=(8 + 3.3 * columns, 7), layout="constrained")
        FigureCanvasAgg(figure)
        axes, key = figure.subplots(
            1, 2, gridspec_kw={"width_ratios": [8, 3.3 * columns]}
        )
        axes.imshow(pixels, interpolation="nearest", origin="upper")
        axes.set_xlabel("Column")
        axes.set_ylabel("Row (0 at top)")
        axes.set_title(f"{item.kind.capitalize()} semantic labels" + (" over heightmap" if scene.heightmap is not None else ""))
        key.axis("off")
        patches = [
            Patch(
                facecolor=np.array(entry.color) / 255,
                label=f"{entry.class_id}: {entry.name} ({np.count_nonzero(item.values == entry.class_id):,})",
            )
            for entry in entries
        ]
        key.legend(
            handles=patches, loc="center left", frameon=False,
            title="Class ID: name (cells)", ncol=columns, fontsize=9,
        )
        figure.suptitle(name, fontsize=14)
        if scene.heightmap is not None:
            figure.supxlabel(f"Label opacity: {alpha:.0%}; legend shows original class colours", fontsize=9)
        try:
            figure.savefig(path, dpi=dpi, metadata={"Description": f"{item.kind} labels from {scene.path}"})
        finally:
            figure.clear()
    return PreviewResult(paths, tuple(messages))
