# GOOSE-Ex ALICE Chrono environment

This pipeline creates an initial Project Chrono environment from a labelled
GOOSE-Ex LiDAR frame recorded by the ALICE excavator.

Vegetation, rocks, structures and the excavator model are deliberately kept
separate from the heightmap. They require reusable meshes or proxy geometry;
LiDAR points alone are not watertight simulation meshes.

The converter uses SciPy for scattered-data interpolation and nearest-neighbour
gap filling. It is included in `environment.yml`; update an existing
environment before running the converter:

```bash
conda env update -f environment.yml --prune
```

## 1. Generate the first ALICE heightmap

The default command selects the first frame from `alice_scenario02` and crops a
40 m by 40 m region around the LiDAR origin:

```bash
python environments/goose/terrain/build_heightmap.py
```

The command prints the generated `scene.json` path. Output is placed under:

```text
environments/goose/generated/<frame-name>/
├── heightmap.bmp
├── height_grid.npy
└── scene.json
```

To choose a particular sequence or frame:

```bash
python environments/goose/terrain/build_heightmap.py \
  --scenario alice_scenario02 \
  --sequence 07 \
  --frame-index 10
```

Useful tuning options include `--bounds`, `--resolution`,
`--height-percentile`, `--smooth-passes`, and `--ground-classes`. Run the
script with `--help` for their full descriptions.

## 2. Load the environment in Chrono

Pass the generated metadata path to the viewer:

```bash
python environments/goose/terrain/goose_environment.py \
  --scene environments/goose/generated/<frame-name>/scene.json
```

For a non-graphical initialization check:

```bash
python environments/goose/terrain/goose_environment.py \
  --scene environments/goose/generated/<frame-name>/scene.json \
  --headless
```
## Tests

The converter tests use a synthetic labelled point cloud and do not download
GOOSE-Ex or require PyChrono:

```bash
python -m unittest tests.test_goose_heightmap -v
```
