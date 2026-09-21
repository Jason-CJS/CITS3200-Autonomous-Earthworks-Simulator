# GOOSE / GOOSE-Ex Chrono environment

This pipeline creates an initial Project Chrono environment from a labelled
GOOSE-Ex LiDAR frame, including ALICE excavator recordings.

GOOSE is a recorded perception dataset, not a simulation-ready 3D world.
The pipeline therefore reconstructs a 2.5D ground surface from semantic LiDAR
points and loads it as an SCM deformable heightmap. It does not copy the
recorded excavator into the scene.

## One-command launch

The pipeline uses these source and configuration files:

| File | Location from repository root |
| --- | --- |
| Launcher | `scripts/goose_to_heightmaps.py` |
| Converter | `environments/terrain/build_heightmap.py` |
| Dataset helper | `environments/terrain/goose_dataset.py` |
| Viewer | `environments/terrain/goose_environment.py` |
| SCM configuration | `environments/scene_config/alice_scm.json` |

Prepared data lives under `data/goose/`. Generated scenes are written to
`outputs/goose/<frame-name>/`. Both paths are excluded from Git.

With the `chrono` Conda environment active, run this from the repository root:

```bash
python scripts/goose_to_heightmaps.py
```

The launcher automatically:

1. discovers `lidar/` directory beneath `data/goose/`;
2. selects a scenario with matching 3D labels, preferring `val`, then `train`, then `test`;
3. converts the selected frame if its scene is missing, comes from a different source, or was generated with different quality settings; and
4. opens the generated SCM environment in Irrlicht.

Scenarios are selected alphabetically within the chosen split. Pass `--scenario`
to select a specific one; there is no required `alice_scenario02` directory.
The optional `./scripts/run_goose.sh` wrapper activates the `chrono` environment.
`scripts/run_goose_environment.py` is a compatibility entry point for the same launcher.

The launcher reports the expected dataset location and stops if the required
files are absent. Later runs reuse the generated scene.

To force heightmap regeneration or perform a non-graphical check:

```bash
python scripts/goose_to_heightmaps.py --rebuild
python scripts/goose_to_heightmaps.py --headless
```

### Quality presets

The launcher and direct converter provide three quality presets. Each preset
controls both the heightmap cell size and the Chrono SCM grid spacing. Smaller
values preserve more terrain detail but require more processing and simulation
work.

| Preset | Heightmap resolution | SCM grid spacing | Intended use |
| --- | ---: | ---: | --- |
| `low` | 0.30 m | 0.30 m | Faster iteration and lower resource use |
| `balanced` | 0.15 m | 0.15 m | General use and the default behaviour |
| `high` | 0.10 m | 0.10 m | Higher terrain detail where performance permits |

When `--quality` is omitted, `balanced` is selected. For each setting, precedence
is: an explicit individual override, the selected preset, then the `balanced`
default.

Select a preset with `--quality`:

```bash
python scripts/goose_to_heightmaps.py --quality low
python scripts/goose_to_heightmaps.py --quality high --headless
```

The optional `--resolution` and `--grid-spacing` arguments override only their
corresponding preset values:

```bash
python scripts/goose_to_heightmaps.py \
  --quality balanced \
  --resolution 0.20 \
  --grid-spacing 0.12
```

The selected preset, resolved values and explicit overrides are recorded in
`scene.json`. The launcher regenerates a cached scene whenever this quality
configuration changes.

#### Representative benchmark

The presets were compared using GOOSE-Ex `alice_scenario02`, sequence 07,
frame 0, with fixed 40 m by 40 m bounds. Testing used Python 3.12.14,
PyChrono 10.0.0 and WSL2 with llvmpipe software rendering.

| Preset | Raster grid | Generation time | Grid file | Effective FPS | Peak memory |
| --- | ---: | ---: | ---: | ---: | ---: |
| `low` | 135 × 135 | 0.40 s | 142.5 KB | 28.5 | 359.5 MB |
| `balanced` | 268 × 268 | 0.99 s | 561.2 KB | 12.1 | 418.1 MB |
| `high` | 401 × 401 | 1.39 s | 1,256.4 KB | 6.4 | 439.3 MB |

The graphical results are medians from three runs of approximately 250 rendered
frames at 1280 × 720. Effective FPS includes process and terrain initialization,
so the figures are intended as relative comparisons rather than precise
in-engine frame rates. Generation times were initial validation runs rather
than repeated measurements.

The `low` preset was approximately 2.4 times faster than `balanced` and used
about 14% less peak memory, but appeared blockier and lost smaller terrain
features. The `high` preset retained additional fine surface variation, but
produced about 47% lower effective FPS than `balanced` and used about 5% more
peak memory. These results cover one scene on one software-rendered machine
without a vehicle or active deformation workload, so performance will vary
between systems.

## What the first version provides

- GOOSE-Ex point-cloud and semantic-label pairing;
- scene selection by dataset, split, scenario, sequence and labelled frame index;
- a fixed ground filter using the GOOSE 64-class ontology;
- point-cloud rasterisation, hole filling and noise smoothing;
- an 8-bit grayscale BMP heightmap for Chrono;
- JSON metadata preserving dimensions, elevation and source provenance;
- a configurable Chrono `SCMTerrain` viewer;
- a headless initialization mode for automated checks.

The fixed filter includes soil, gravel, asphalt, cobble, snow, leaves, moss,
low grass, bikeways, pedestrian crossings, road markings, sidewalks, curbs and
rail tracks. Low vegetation can provide ground-surface returns where bare-soil
returns are sparse. Tall vegetation and structures are excluded.

Simplified category maps and configurable terrain classes are deferred to a
separate PR. This version produces a heightmap and scene metadata. Vegetation,
rocks, structures and the excavator need separate meshes or proxy geometry.

## Supported data and layouts

The input must contain SemanticKITTI-style XYZI `.bin` files (four little-endian
float32 values per point) and matching uint32 `.label` files. The original GOOSE
64-class ontology is the default. This is format compatibility, not a guarantee
for every release or repackaging. The official formats are documented in the
[GOOSE dataset structure](https://goose-dataset.de/docs/dataset-structure/).

The teammate-prepared layout is supported with either `lidar` or `velodyne`:

```text
data/goose/
├── CHANGELOG
├── goose_label_mapping.csv
├── LICENSE
├── lidar/val/
├── labels/val/
```

Flat extracted archives containing `lidar/<split>/<scenario>/` and sibling `labels/<split>/<scenario>/` are also
supported, including archives nested inside `3d/val/` or other wrapper folders.
Root-level image labels are never substituted for a nested 3D dataset's labels.

The paired label uses the same frame prefix with `_goose.label`; matching
`<prefix>.label` and `<point-cloud-stem>.label` exports are also accepted.
Recognised point-cloud suffixes are `_pcl.bin`, `_vls128.bin`, and `.bin`.

List available scenarios and matched/total frame counts before opening Chrono:

```bash
python scripts/goose_to_heightmaps.py --dataset data/goose --list-scenarios
```

This listing uses only Python's standard library and does not require PyChrono.
To use a different prepared dataset directory:

```bash
python scripts/goose_to_heightmaps.py --dataset /path/to/data/goose
```

Choose a particular split and scenario using the exact name from the listing:

```bash
python scripts/goose_to_heightmaps.py --split train --scenario "SCENARIO_FROM_LIST"
```

`--frame-index` counts only frames with matching 3D labels, after applying any
`--sequence` filter. Duplicate copies of the same split/scenario under one root
require a more specific `--dataset` directory.

The mapping CSV is found beside the selected 3D archive or in its parents, up to
the supplied dataset root. An explicit `--mapping /path/to/mapping.csv` overrides
this selection. Missing maps use the built-in original 64-class IDs with a
warning; unrecognised CSV schemas are rejected. The CSV's semantic ID/class-name
columns are used, rather than its coarse category IDs.

2D-only data, unlabelled point clouds/test splits, raw ROS bags, PCD/PLY files,
and arbitrary remapped challenge labels are not ready inputs to this converter.
Remapped labels require a CSV matching their per-point IDs to the original
GOOSE class names. Challenge taxonomies differ from the original IDs, as described in the
[GOOSE class definitions](https://goose-dataset.de/docs/class-definitions/).

GOOSE data is published under CC BY-SA 4.0. Retain its included `LICENSE` and
cite the GOOSE-Ex publication when distributing derived environment assets.

The converter uses SciPy for scattered-data interpolation and nearest-neighbour
gap filling. It is included in `environment.yml`; update an existing
environment before running the converter:

```bash
conda env update -f environment.yml --prune
```

## 1. Generate a heightmap

The default command selects the first available labelled scenario and crops a
40 m by 40 m region around the LiDAR origin:

```bash
python environments/terrain/build_heightmap.py
```

The command prints the generated `scene.json` path. Output is placed under:

```text
outputs/goose/<frame-name>/
├── heightmap.bmp
├── height_grid.npy
└── scene.json
```

To choose a particular sequence or frame:

```bash
python environments/terrain/build_heightmap.py \
  --scenario alice_scenario02 \
  --sequence 07 \
  --frame-index 10
```

The one-command launcher supports the same scenario selection. List the
available names, then select a different recorded terrain with:

```bash
python scripts/goose_to_heightmaps.py --list-scenarios

python scripts/goose_to_heightmaps.py \
  --scenario alice_scenario06 \
  --sequence 11 \
  --frame-index 0
```

Use a scenario and sequence present in your prepared files. Omit `--sequence`
to select among all labelled frames in that scenario. Index `0` means the first
matching frame, `1` the second, and so on. The launcher reports the valid range
if the requested index is too large.

Each selected frame has its own output folder. A compatible generated scene is
reused on later runs. Use `--rebuild` to force regeneration. Scenes produced by
earlier converter versions are rebuilt once with the fixed ground filter.

Useful direct-converter tuning options also include `--quality`, `--bounds`,
`--resolution`, `--grid-spacing`, `--height-percentile`, and
`--smooth-passes`. Run either script with `--help` for full descriptions.

## 2. Load the environment in Chrono

Pass the generated metadata path to the viewer:

```bash
python environments/terrain/goose_environment.py \
  --scene "outputs/goose/<frame-name>/scene.json"
```

For a non-graphical initialization check:

```bash
python environments/terrain/goose_environment.py \
  --scene "outputs/goose/<frame-name>/scene.json" \
  --headless
```

## Coordinate and fidelity limitations

- A processed GOOSE-Ex `.bin` stores `x`, `y`, `z`, and intensity as four
  consecutive `float32` values per point.
- A `.label` stores semantic ID in the low 16 bits and instance ID in the high
  16 bits of each `uint32` value.
- This first version uses one local LiDAR frame. It is suitable for proving the
  conversion and Chrono integration, but it is not a globally consistent map.
- Frames must use metre units with Z representing height. Different sensor-frame
  orientations require a coordinate transform before conversion.
- A larger environment must transform and merge frames with odometry and TF
  from an ALICE ROS bag before running the same rasterisation stage.
- GOOSE semantic labels do not contain soil strength measurements. The SCM
  values in `environments/scene_config/alice_scm.json` are starting values and must be
  calibrated independently.

## Tests

The converter tests exercise flat and nested GOOSE/GOOSE-Ex layouts, correct 3D
label pairing, split selection, mapping validation, and synthetic terrain generation.
They do not require real GOOSE files or PyChrono:

```bash
python -m unittest discover -s tests -p 'test_goose_heightmap.py' -v
```

Run the launcher selection, listing, scene-cache and converter CLI checks too:

```bash
python -m unittest discover -s tests -p 'test_run_goose_environment.py' -v
```

Directory tests use synthetic fixtures. Actual dataset content and graphical
rendering should also be checked on the machine with the prepared data and PyChrono.
