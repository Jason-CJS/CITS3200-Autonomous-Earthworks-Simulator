# GOOSE semantic label viewer

View the saved semantic maps exported by issue #22 without running the terrain
pipeline or Chrono. The command writes fine and coarse colour-coded PNGs with
class names, IDs and cell counts alongside each image. It can also blend labels
over the saved heightmap. Open the PNGs in your normal image viewer.

## Run the viewer

For the scene used to validate this implementation:

```bash
python -m scenarios.goose_label_viewer.view_scene \
  --scene outputs/goose/alice_scenario02_sequence07_0001_1697208276047079000/scene.json \
  --output-dir outputs/goose_label_viewer
```

Replace the frame directory to inspect another saved scene. The default is both
maps; use `--map fine` or `--map coarse` to select one. Output filenames are:

- `<frame-name>_fine_labels.png`
- `<frame-name>_coarse_labels.png`

To overlay both maps on the heightmap:

```bash
python -m scenarios.goose_label_viewer.view_scene \
  --scene outputs/goose/alice_scenario02_sequence07_0001_1697208276047079000/scene.json \
  --output-dir outputs/goose_label_viewer \
  --overlay --alpha 0.55
```

Overlay filenames end in `_fine_overlay.png` and `_coarse_overlay.png`.
`--alpha 0` shows the grayscale heightmap; `--alpha 1` shows full label colours.
Unobserved cells always show the heightmap in overlay mode. The legend displays
the original class colours, before blending. Repeated runs replace preview PNGs
with the same names but cannot overwrite declared scene inputs.

Use `--dpi` (50..600, default 150) to change the PNG resolution.

## Issue #22 input format

Tested against a real export with scene version 2, semantics version 1 and
semantic legend version 1:

| File | Contents |
| --- | --- |
| `scene.json` | Relative output paths, grid dimensions and semantic metadata |
| `semantic_fine.npy` | 2D fine-class IDs; uint16 in the tested export |
| `semantic_coarse.npy` | 2D coarse-category IDs; uint8 in the tested export |
| `semantic_legend.json` | Fine classes, coarse categories and unobserved IDs |
| `height_grid.npy` | Height values, preferred for overlays |
| `heightmap.bmp` | Grayscale overlay fallback when the height grid is absent |

The manifest's `outputs` object supplies paths, for example:

```json
{
  "format_version": 2,
  "outputs": {
    "semantic_fine": {"path": "semantic_fine.npy"},
    "semantic_coarse": {"path": "semantic_coarse.npy"},
    "semantic_legend": {"path": "semantic_legend.json"},
    "height_grid": {"path": "height_grid.npy"},
    "heightmap": {"path": "heightmap.bmp"}
  }
}
```

Paths resolve relative to `scene.json`. The original machine's absolute
`source.dataset_root` is provenance only and is not accessed. Copying the entire
exported frame folder to another computer is sufficient.

The legend's `classes` list provides fine IDs and names. Its
`coarse_taxonomy.categories` list provides coarse IDs and names. The viewer reads
the already-exported coarse map; it does not perform class reduction. The supplied
legend contains 64 fine classes and 12 coarse entries, including `ignored`.

Unobserved IDs come from `fine_taxonomy.unobserved_id` and
`coarse_taxonomy.unobserved_id` in the legend and/or the manifest's `semantics`.
The tested export uses **65535 for fine** and **255 for coarse**. Conflicting
declarations are rejected. Coarse ID 0 (`ignored`) remains an observed class.

## Colours and interpretation

The supplied #22 legend has no colour values. The viewer therefore assigns a
stable display palette: coarse category names select fixed colours, and fine
class IDs select deterministic HSV colours. Colours do not depend on which
classes happen to be present or on the legend's entry order. These are viewer
colours, not colours claimed to have come from GOOSE. Optional `color` fields on
fine class or coarse category entries override the palette; accepted values are
`#RRGGBB` or three integer RGB channels in `0..255`.

- Only classes present in the raster appear in the key. Counts are grid cells,
  not LiDAR-point counts.
- Unobserved cells are light gray in label-only images and transparent in
  overlays. They are not classified as soil or ignored.
- IDs absent from the legend are magenta and have an explicit `Unknown ID`
  entry and console warning.
- Rows and columns are displayed directly, with row 0 at the top. For #22's
  exported alignment, this is `ymax`; column 0 is `xmin`. Axes show pixel indices.
- Fine/coarse/height grids must share a shape. Declared opposite orientations
  and label shape/dtype mismatches are rejected. No resizing, flipping or
  semantic interpolation is performed.

The supplied scene has 26,364 observed semantic cells out of 71,824 (36.7%).
Its other 45,460 cells are unobserved. The heightmap has interpolated heights,
but semantic maps are not interpolated. Gray gaps are therefore expected.
Vegetation labels show where vegetation was observed; they do not indicate that
tree or bush meshes have been created in the Chrono scene.

## Other inputs and errors

The earlier viewer `label_maps` manifest format and separate `fine`/`coarse`
legend lists remain supported. Scene versions 1 and 2 are accepted; unsupported
future versions receive a clear error.

Explicit paths can override manifest references:

```bash
python -m scenarios.goose_label_viewer.view_scene \
  --scene "outputs/goose/<frame-name>/scene.json" \
  --fine-map "outputs/goose/<frame-name>/semantic_fine.npy" \
  --coarse-map "outputs/goose/<frame-name>/semantic_coarse.npy" \
  --legend "outputs/goose/<frame-name>/semantic_legend.json"
```

Override paths are relative to the working directory. `--heightmap PATH`
requires `--overlay`. Overrides still use the legend's taxonomy and unobserved
IDs; they do not translate an arbitrary legend schema.

Rasters must be non-empty 2D integer arrays. Supported label files are NPY
(without pickle), single-channel or palette PNG, BMP and TIFF. Palette indices
are retained as IDs. RGB previews, floating-point label maps, NPZ archives and
one-dimensional per-point labels are rejected.

Old heightmap-only manifests, missing files, malformed metadata and mismatched
grids produce a concise message and exit code 2, without running the converter.
If only one map is declared, `--map both` renders it with a warning; explicitly
requesting the absent map fails. Successful rendering returns exit code 0.

## Testing

Run the viewer tests, including the bundled real #22 export:

```bash
python -m unittest discover -s tests -p 'test_goose_label_viewer.py' -v
```

The suite checks fine/coarse distributions and roll-up consistency against the
real manifest, correct unobserved IDs, stable colours, output rendering, input
preservation, shape/alignment checks and missing-data handling. It does not
require raw LiDAR files or Chrono.

Render the bundled real scene:

```bash
python -m scenarios.goose_label_viewer.view_scene \
  --scene tests/fixtures/goose_label_viewer_real/scene.json \
  --output-dir outputs/goose_label_viewer --overlay
```

To also use another scene for the rendering integration test (works in Fish):

```bash
env GOOSE_LABEL_SCENE="outputs/goose/<frame-name>/scene.json" \
  python -m unittest discover -s tests -p 'test_goose_label_viewer.py' -v
```

That scene must have both maps, complete legend coverage, and a matching
heightmap. Real-output tests run by default; they are no longer skipped.

The issue's independent-machine acceptance check remains for a teammate: run
the commands on the same scene, inspect fine/coarse maps and overlays, and record
the commit, scene name, operating system, Python version and result in the PR.
