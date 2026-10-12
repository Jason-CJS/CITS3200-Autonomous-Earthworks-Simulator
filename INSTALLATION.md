# Installation Guide

This guide covers everything needed to set up the Autonomous Earthworks
Simulator on a fresh machine: environment setup, dependency verification, and
preparing the GOOSE-Ex dataset. For how to actually run the simulator once
installed, see [USER_GUIDE.md](USER_GUIDE.md).

## Prerequisites

- Native Linux, or WSL2 with Ubuntu 24.04 LTS (Windows users).
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html), Miniforge, or
  Anaconda installed.
- A working graphical display for Chrono's Irrlicht window. Headless terrain
  initialisation and label preview rendering do not require a window.

## 1. Clone the repository

```bash
git clone https://github.com/Jason-CJS/CITS3200-Autonomous-Earthworks-Simulator.git
cd CITS3200-Autonomous-Earthworks-Simulator
```

## 2. Create the Conda environment

This project uses **Python 3.12** and **PyChrono 10.0.0**. All dependencies
are pinned in `environment.yml` to keep every machine consistent.

```bash
conda env create -f environment.yml
conda activate chrono
```

Verify PyChrono installed correctly:

```bash
conda list pychrono
```

The installed version should read `10.0.0`. Checking via
`python -c "import pychrono"` is not sufficient — it will succeed even on a
broken install; always check the version through `conda list`.

> **Watch out:** if you ever install PyChrono manually instead of through
> `environment.yml`, it must be channel-pinned:
> `conda install projectchrono::pychrono=10.0.0 -c conda-forge`. Installing
> with `-c conda-forge -c projectchrono` alone can silently produce a build
> that's missing `pychrono.irrlicht`, which breaks every graphical demo.

### Updating an existing environment

After pulling changes that touch `environment.yml`:

```bash
conda env update -n chrono -f environment.yml
conda activate chrono
```

If you need to add a new dependency yourself, add it to `environment.yml` and
include that change in your PR — don't install packages ad hoc only on your
own machine, or other people's environments will silently drift out of sync.

## 3. WSL2-specific setup (Windows users only)

If your GPU falls back to software rendering (`llvmpipe`) under WSL2, add
this to `~/.bashrc`:

```bash
export GALLIUM_DRIVER=d3d12
```

Always work from your Linux home directory (`~/...`) inside WSL2, never from
`/mnt/c/...` — crossing the Windows/Linux filesystem boundary causes
significant slowdowns and odd behaviour with Chrono's file I/O.

## 4. Prepare the GOOSE-Ex dataset

GOOSE-Ex point clouds and labels are not stored in the repository — they're
downloaded separately. From the repository root, with the `chrono`
environment active:

```bash
bash scripts/download_goose_dataset.sh
```

This prepares the labelled validation split under `data/goose/`, including
`goose_label_mapping.csv` and the matching 3D point clouds (`lidar/val/`) and
labels (`labels/val/`). The script is idempotent — re-running it after a
partial/interrupted download will pick up where it left off rather than
re-downloading everything.

See [environments/README.md](environments/README.md) for the supported
dataset layout if you need to troubleshoot a non-standard setup. Note that
2D image labels cannot substitute for the 3D point labels this pipeline
requires.

## 5. Confirm the install works end to end

Run the full automated test suite — this exercises the terrain pipeline,
vehicle models, and output tooling without needing a graphical window:

```bash
bash scripts/run_tests.sh
```

All tests should pass. If PyChrono isn't importable, this script fails fast
with a clear message rather than a cryptic test error.

If that passes, you're fully set up. Head to
[USER_GUIDE.md](USER_GUIDE.md) to start running scenarios.

## Troubleshooting

**`ModuleNotFoundError` for a project package (e.g. `scenarios`, `src`)** —
run scenario/demo tools as a module from the repository root, not as a
direct script path:

```bash
python -m scenarios.goose_navigation.run_demo --help
```

Running `python scenarios/goose_navigation/run_demo.py` directly can prevent
Python from finding the top-level project package.

**Graphical window doesn't open, or rendering looks wrong** — demos use
OpenGL by default, which is usually hardware-accelerated and the fastest
option. If OpenGL fails on your setup, switch to Chrono's own lightweight
software renderer instead:

```bash
AES_IRRLICHT_DRIVER=software python -m <module> ...
```

Avoid `LIBGL_ALWAYS_SOFTWARE=1`/`GALLIUM_DRIVER=llvmpipe` — those force the
entire graphics stack onto CPU emulation underneath OpenGL itself, which is
far slower than `AES_IRRLICHT_DRIVER=software` and defeats the point of
using OpenGL at all. Only reach for them if `AES_IRRLICHT_DRIVER=software`
still doesn't work.
