# Autonomous Earthworks Simulator

**Project Leads:** Adrian Boeing, Fabian Deuser, Kieran Quirke-Brown

### Group Members

| **Student Number** | **Name** | **GitHub Username** |
| :--- | :--- | :--- |
| 24618514 | Jieh Shuen Chia (Jason) | Jason-CJS |
| 24270886 | Aron Zombori | CheggGH |
| 21111977 | Robin Candy | robinbmc |
| 23964287 | Houssein Marouff | Big-H-21 |
| 24441384 | Youhei Azuka Arya Arya | tera-A-A |

## Description

A 3D robotics simulation for studying deformable terrain and earthworks vehicle
interaction, with labelled outputs for comparison against real-world datasets.

The current documented workflow uses **Project Chrono**, **SCM deformable
terrain**, and labelled LiDAR data from the **GOOSE-Ex ALICE excavator** platform.
It converts recorded ground points into a heightmap and provides tools for
inspecting the exported semantic labels and running a navigation scenario.

## Repository Structure

```text
CITS3200-AES/
├── README.md                  # Project overview, setup, and run instructions
├── .gitignore
├── environment.yml            # Shared Conda environment and dependencies
├── CMakeLists.txt             # Top-level build configuration
│
├── environments/
│   ├── README.md              # GOOSE setup, generation and launch guide
│   ├── terrain/               # GOOSE converter, dataset helper and Chrono loader
│   ├── scene_config/          # SCM terrain configuration
│   └── construction_zone/     # Construction-zone work from the original scope
│       ├── terrain/
│       ├── vegetation/
│       └── scene_config/
│
├── vehicles/
│   ├── excavator/
│   │   ├── model/
│   │   └── articulation/
│   └── bulldozer/
│       ├── model/
│       └── articulation/
│   └── common/
│
├── sensors/
│   ├── camera/
│   └── lidar/
│
├── deformation/               # Terrain deformation and output inspection
│
├── labelling/                 # Object/asset labelling and metadata export
│
├── scenarios/
│   ├── goose_label_viewer/
│   │   ├── README.md          # Label viewer setup and usage
│   │   ├── __init__.py
│   │   ├── view_scene.py      # Command-line entry point
│   │   └── viewer.py          # Label rendering and heightmap overlays
│   └── goose_navigation/
│       ├── run_demo.py        # Navigation demo entry point
│       └── traversal.py       # Navigation and traversal logic
│
├── src/                       # Core application code
│   ├── main.cpp
│   ├── vehicle_control/
│   ├── terrain/
│   └── sensors/
│
├── scripts/                   # Build/setup automation and run scripts
│   ├── download_goose_dataset.sh
│   └── goose_to_heightmaps.py # Terrain conversion and Chrono launcher
│
├── tests/                     # Automated validation and test scripts
│   ├── test_goose_heightmap.py
│   ├── test_goose_label_viewer.py
│   └── fixtures/
│       └── goose_scene.tar.gz # Compressed real scene used by viewer tests
│
├── data/                      # Local dataset files; excluded from Git
│   └── goose/                # Prepared GOOSE-Ex dataset
│
└── outputs/                   # Generated files; excluded from Git
    ├── goose/
    │   └── <frame-name>/
    │       ├── heightmap.bmp
    │       ├── height_grid.npy
    │       ├── semantic_fine.npy
    │       ├── semantic_coarse.npy
    │       ├── semantic_legend.json
    │       └── scene.json
    ├── goose_label_viewer/    # Label previews and heightmap overlays
    └── goose_navigation_manual/ # Manual navigation run outputs
```

## Environment Setup

This project uses **Python 3.12** and **PyChrono 10.0.0**. Shared dependencies are
defined in `environment.yml`; use this file to keep development environments
consistent.

### Prerequisites

- Native Linux, or WSL2 with Ubuntu 24.04 LTS.
- Miniconda, Miniforge or Anaconda.
- A working graphical display for Chrono's Irrlicht window. Label preview
  rendering and headless terrain initialisation do not require a window.

### Create the environment

Clone the repository and enter its root directory:

```bash
git clone https://github.com/Jason-CJS/CITS3200-Autonomous-Earthworks-Simulator.git
cd CITS3200-Autonomous-Earthworks-Simulator
```

Create and activate the environment:

```bash
conda env create -f environment.yml
conda activate chrono
```

Verify PyChrono:

```bash
conda list pychrono
```

The installed PyChrono version should be `10.0.0`.

### Update an existing environment

After pulling changes to `environment.yml`:

```bash
conda env update -n chrono -f environment.yml
conda activate chrono
```

When adding a dependency, update the shared `environment.yml`, verify the
environment, and include that change in your PR. Avoid relying on packages
installed only on your own machine.

The terrain converter uses NumPy and SciPy. The semantic label viewer also
requires Matplotlib and Pillow; ensure these packages are included in the shared
environment.

## Prepare the GOOSE-Ex Dataset

GOOSE-Ex point clouds and labels are not stored in the repository. From the
repository root, run the dataset preparation helper:

```bash
bash scripts/download_goose_dataset.sh
```

The helper introduced in PR #24 prepares the labelled validation data under
`data/goose/`, including `goose_label_mapping.csv` and the matching 3D point
clouds and labels. Dataset preparation is handled separately from terrain
conversion and label viewing.

See the [GOOSE environment guide](environments/README.md) for the supported
dataset layout and troubleshooting. Two-dimensional image labels cannot replace
the per-point 3D labels required by the terrain pipeline.

## Generate and Open a GOOSE Terrain

Run all commands below from the repository root with the `chrono` environment
active.

List the available labelled scenarios:

```bash
python scripts/goose_to_heightmaps.py --list-scenarios
```

Generate a scene if necessary and open it in Chrono:

```bash
python scripts/goose_to_heightmaps.py
```

Select a specific scenario and frame:

```bash
python scripts/goose_to_heightmaps.py \
  --scenario alice_scenario06 \
  --frame-index 0
```

Available launcher options include:

| Option | Purpose |
| --- | --- |
| `--dataset PATH` | Use a different prepared dataset root |
| `--split val` | Select the validation split |
| `--scenario NAME` | Choose a scenario listed by `--list-scenarios` |
| `--sequence 07` | Restrict selection to a sequence present in that scenario |
| `--frame-index 0` | Select a zero-based frame within the filtered selection |
| `--rebuild` | Regenerate a cached scene |
| `--headless` | Initialise Chrono without opening a graphical window |
| `--duration SECONDS` | Set an optional simulated duration |

Use `--help` for the installed launcher's full option list. For quality presets,
SCM settings and detailed terrain usage, see
[environments/README.md](environments/README.md).

## Generated Scene Outputs

Each generated frame is stored under `outputs/goose/<frame-name>/`.
The semantic export implemented in
[Issue #22](https://github.com/Jason-CJS/CITS3200-Autonomous-Earthworks-Simulator/issues/22)
adds fine/coarse label maps and a machine-readable legend to the terrain outputs.

| File | Contents |
| --- | --- |
| `heightmap.bmp` | Grayscale terrain heightmap |
| `height_grid.npy` | Numeric elevation grid |
| `semantic_fine.npy` | Fine-grained semantic class IDs |
| `semantic_coarse.npy` | Reduced semantic category IDs |
| `semantic_legend.json` | Class names, category mapping and unobserved IDs |
| `scene.json` | Output paths, source information, grid properties and conversion metadata |

Older scenes may contain only heightmap files and `scene.json`. To add semantic
outputs, rebuild the selected frame using the updated converter.

Raw dataset files and generated outputs should remain outside Git. Small test
fixtures under `tests/fixtures/` are versioned so automated tests can run without
the full dataset.

## View Semantic Labels

The viewer reads the saved scene, label maps and legend and writes colour-coded
PNGs with a class key. It does not rerun terrain generation or change labels.

First check which frame directories exist:

```bash
ls outputs/goose
```

The following examples use the real frame validated during viewer development.
If it is not present in your checkout, replace the entire frame directory with
one listed by the command above:

```bash
python -m scenarios.goose_label_viewer.view_scene \
  --scene outputs/goose/alice_scenario02_sequence07_0001_1697208276047079000/scene.json \
  --output-dir outputs/goose_label_viewer
```

Both maps are rendered by default. Add `--map fine` or `--map coarse` to select
one. Add `--overlay --alpha 0.55` to blend labels over the saved heightmap.

Open the saved PNGs in your normal image viewer. Their legends show class IDs,
names and grid-cell counts.

Unobserved cells are gray in label-only images and transparent in overlays.
The exported fine and coarse maps use unobserved IDs `65535` and `255`,
respectively. Coarse ID `0` is the observed `ignored` category. Semantic gaps
are expected because labels are not interpolated to fill missing observations.

When the exported legend contains no colours, the viewer assigns a stable
display palette. See the
[label viewer README](scenarios/goose_label_viewer/README.md) for supported input
formats, colour handling, overlays and error messages.

## Run the Manual Navigation Demo

Use a generated scene with the navigation module:

```bash
python -m scenarios.goose_navigation.run_demo \
  --scene outputs/goose/alice_scenario02_sequence07_0001_1697208276047079000/scene.json \
  --mode manual \
  --output-dir outputs/goose_navigation_manual
```

Use a frame directory that exists on your machine. Inspect the navigation
module's available options with:

```bash
python -m scenarios.goose_navigation.run_demo --help
```

## Testing

Run the terrain converter tests:

```bash
python -m unittest discover -s tests -p 'test_goose_heightmap.py' -v
```

Run the semantic viewer tests:

```bash
python -m unittest discover -s tests -p 'test_goose_label_viewer.py' -v
```

The viewer tests generate small artificial inputs in temporary directories and
unpack a real saved scene from `tests/fixtures/goose_scene.tar.gz`. Temporary
files are cleaned up after the tests. The real fixture exercises fine/coarse
rendering, overlays and consistency with the exported manifest.

Before merging viewer changes, also have a teammate inspect the maps and
overlays on another machine and record the result in the PR.

## Common Problems

### Python cannot find `scenarios`

Run package-based scenario tools from the repository root using `python -m`:

```bash
python -m scenarios.goose_navigation.run_demo --help
```

Running `python scenarios/goose_navigation/run_demo.py` directly can prevent
Python from finding the top-level project package.

### A command reports a file-redirection error

Text such as `<frame-name>` is a placeholder, not a literal folder name.
Replace it with an existing directory name and remove the angle brackets.
Use the complete examples above as a starting point.

### The scene has no semantic labels

Check that the selected frame contains `semantic_fine.npy`,
`semantic_coarse.npy` and `semantic_legend.json`, and that `scene.json`
references them. Rebuild an older scene with the updated converter.
The viewer reports missing data; it does not regenerate it.

### Testing with software rendering

If you need to test the navigation demo with software rendering, prefix its
command with `env LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe`.
This requests Mesa's software renderer where supported and can be substantially
slower than GPU rendering.

## Further Documentation

- [GOOSE environment setup and terrain generation](environments/README.md)
- [Semantic label viewer](scenarios/goose_label_viewer/README.md)
- [Semantic export task — Issue #22](https://github.com/Jason-CJS/CITS3200-Autonomous-Earthworks-Simulator/issues/22)
