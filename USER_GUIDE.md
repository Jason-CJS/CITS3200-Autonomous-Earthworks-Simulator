# User Guide

This guide covers running the simulator once it's installed — generating
terrain, viewing semantic labels, adding vegetation, driving the bulldozer
or excavator, and inspecting results. If you haven't set up the environment
yet, start with [INSTALLATION.md](INSTALLATION.md).

All commands below assume you're running from the repository root with the
`chrono` Conda environment active (`conda activate chrono`), unless noted
otherwise.

## Repository structure

```text
CITS3200-AES/
├── environments/
│   ├── README.md              # GOOSE setup, generation and launch guide
│   ├── terrain/                # GOOSE converter, dataset helper and Chrono loader
│   ├── scene_config/           # SCM terrain configuration
│   └── vegetation/             # Tree/vegetation/rural object placement and models
├── vehicles/
│   ├── excavator/
│   └── bulldozer/
├── deformation/                # Terrain deformation export and output inspection
├── sensors/                    # GPS reference check; camera/LiDAR are future-team stretch goals
├── scenarios/
│   ├── bulldozer_earthmoving/  # Scripted hole-filling scenario
│   ├── goose_label_viewer/     # Semantic label visualisation
│   └── goose_navigation/       # Scripted/manual bulldozer or excavator traversal demo
├── scripts/                    # See scripts/README.md for the full index
│   ├── download_goose_dataset.sh
│   ├── goose_to_heightmaps.py  # Terrain conversion and Chrono launcher
│   ├── export_trees.py         # Tree placement export (real collision)
│   ├── export_vegetation.py    # Generic vegetation placement export (visual only)
│   └── inspect_outputs.py      # View previous run results without re-simulating
├── src/                        # Shared demo helpers (camera/keyboard, standalone vehicle demos)
├── tests/                      # Automated test suite
├── data/goose/                 # Prepared GOOSE-Ex dataset (not in Git)
├── outputs/                    # All generated run outputs (not in Git)
└── redundant-aarp/             # Archived pre-rescope AARP work, kept for record only
```

## 1. Generate and open a GOOSE terrain

List the available labelled scenarios:

```bash
python scripts/goose_to_heightmaps.py --list-scenarios
```

Generate the default scene and open it in Chrono:

```bash
python scripts/goose_to_heightmaps.py
```

Select a specific scenario and frame:

```bash
python scripts/goose_to_heightmaps.py --scenario alice_scenario06 --frame-index 0
```

Run without opening a graphical window (useful for quick validation):

```bash
python scripts/goose_to_heightmaps.py --headless
```

Common options:

| Option | Purpose |
| --- | --- |
| `--dataset PATH` | Use a different prepared dataset root |
| `--split val` | Select the validation split |
| `--scenario NAME` | Choose a scenario listed by `--list-scenarios` |
| `--sequence 07` | Restrict selection to a sequence within that scenario |
| `--frame-index 0` | Select a zero-based frame within the filtered selection |
| `--quality {low,balanced,high}` | Trade off terrain detail against performance |
| `--resolution` / `--grid-spacing` | Override the heightmap resolution / SCM grid spacing selected by `--quality` |
| `--rebuild` | Regenerate a cached scene |
| `--headless` | Initialise Chrono without opening a graphical window |
| `--duration SECONDS` | Set an optional simulated duration |

Run `--help` for the full list. Quality presets and SCM terrain settings are
covered in detail in [environments/README.md](environments/README.md).

A previously-generated scene is reused automatically if its configuration
hasn't changed. If you change `--quality`/`--resolution`/`--grid-spacing`,
the scene regenerates automatically even without `--rebuild`.

### Generated scene outputs

Each generated frame is stored under `outputs/goose/<frame-name>/`:

| File | Contents |
| --- | --- |
| `heightmap.bmp` | Grayscale terrain heightmap |
| `height_grid.npy` | Numeric elevation grid |
| `semantic_fine.npy` | Fine-grained (64-class) semantic label IDs |
| `semantic_coarse.npy` | Rolled-up coarse semantic category IDs |
| `semantic_legend.json` | Class names, category mapping, and unobserved IDs |
| `scene.json` | Output paths, source provenance, grid geometry, quality settings |

Scenes generated before the semantic export was added will only contain the
heightmap files and `scene.json`. Rebuild the frame (`--rebuild`) with the
current converter to add the semantic outputs.

## 2. View semantic labels

The label viewer reads a saved scene's label maps and legend and writes
colour-coded PNGs with a class key — it does not re-run terrain generation.

Check which generated frames exist:

```bash
ls outputs/goose
```

Then, using a real frame directory from that listing:

```bash
python -m scenarios.goose_label_viewer.view_scene \
  --scene outputs/goose/<frame-name>/scene.json \
  --output-dir outputs/goose_label_viewer
```

Both the fine and coarse maps render by default. Use `--map fine` or
`--map coarse` to select just one, or `--overlay --alpha 0.55` to blend
labels over the saved heightmap. Open the resulting PNGs in any image
viewer — their legend shows class IDs, names, and grid-cell counts.

Gray cells (label-only images) or transparent cells (overlays) are
unobserved — labels aren't interpolated to fill gaps, so some are expected.

See [scenarios/goose_label_viewer/README.md](scenarios/goose_label_viewer/README.md)
for supported formats and error messages.

## 3. Add vegetation (optional, before driving)

Trees and rural vegetation (rocks, grass, bushes, hedges) aren't generated
automatically with the terrain — export them once per scene, then every
later run picks them up automatically with no extra flags:

```bash
python scripts/export_trees.py outputs/goose/<frame-name>/scene.json
python scripts/export_vegetation.py outputs/goose/<frame-name>/scene.json
python -m environments.vegetation.goose_rural_placement \
  --scene outputs/goose/<frame-name>/scene.json \
  --output outputs/goose/<frame-name>/rural_placements.json \
  --trees outputs/goose/<frame-name>/tree_placements.json
```

This writes `tree_placements.json`, `vegetation_placements.json`, and
`rural_placements.json` next to `scene.json`. The navigation demo below
auto-detects and loads any of these that are present — nothing to pass on
the command line. Trees have real physics collision; the other two are
visual only. Skip this step entirely if you just want bare terrain.

## 4. Drive the bulldozer or excavator across GOOSE terrain

Scripted straight-line traversal, logging trajectory and the semantic class
under each sampled position:

```bash
python -m scenarios.goose_navigation.run_demo \
  --scene outputs/goose/<frame-name>/scene.json \
  --headless \
  --output-dir outputs/goose_navigation
```

Add `--vehicle excavator` to drive the excavator instead (default is the
bulldozer). Drop `--headless` for a graphical window. To drive it yourself
with the keyboard instead of the scripted path:

```bash
python -m scenarios.goose_navigation.run_demo \
  --scene outputs/goose/<frame-name>/scene.json \
  --mode manual \
  --output-dir outputs/goose_navigation_manual
```

Bulldozer controls (click the window first to give it focus): `W`/`S`
drive, `A`/`D` steer, `Space` stop, `R`/`F` raise/lower blade, `T`/`G` tilt
blade, `X` reset blade. Excavator (`--vehicle excavator`): `W`/`S` drive,
`A`/`D` steer, `Q`/`E` swing, `R`/`F` boom, `T`/`G` arm, `Y`/`H` bucket,
`X` reset articulation. Camera (both): left-drag rotate, right-drag pan,
left+right-drag zoom. Close the window to save the run.

Other useful flags: `--fullscreen` (fills the screen; `Esc` ends the run
instead of the close button), `--capture OUTPUT.png` (saves the final frame
of a scripted run instead of needing to watch it), `--smoke-test`
(deterministic manual key inputs with the null renderer — mainly for
automated testing).

### Tree collision

If trees were exported (step 3), the bulldozer treats them as real
obstacles:

- **Scripted mode**: the bulldozer stops before reaching a tree in its path
  (`status: "blocked_by_tree"` in the manifest, with the tree ID recorded).
- **Manual mode**: driving into a tree — forward or reverse — is blocked
  before contact; the run keeps going and you can steer or reverse away.
  Encountered tree IDs are recorded in the manifest, but the run doesn't
  stop. This also applies to the excavator's chassis and boom/arm/bucket.

This only prevents *driving* into a tree — raising/lowering the blade or
articulating the excavator's arm while stationary near one isn't checked.

Outputs are written to the chosen `--output-dir`:

| File | Contents |
| --- | --- |
| `trajectory.csv` | Time, chassis X/Y/Z and yaw, and the semantic class under each sample |
| `run_manifest.json` | Source scene, starting pose, quality, duration, status, tree encounters |
| `route_overlay.png` | Route plotted over the scene's coarse semantic map |

Run `--help` for the full option list.

## 5. Run the bulldozer hole-filling scenario

A separate, deterministic demonstration scenario — a purpose-built mound and
target hole, not GOOSE-derived terrain — showing the bulldozer measurably
filling a hole with its blade over one scripted pass.

```bash
python -m scenarios.bulldozer_earthmoving.run_scenario \
  --headless \
  --output-dir outputs/bulldozer_hole_fill
```

Drop `--headless` for the graphical version:

```bash
python -m scenarios.bulldozer_earthmoving.run_scenario \
  --output-dir outputs/bulldozer_hole_fill
```

If OpenGL rendering fails on your setup, prefix with
`AES_IRRLICHT_DRIVER=software` (see Common problems below).

The scenario measures the average terrain height inside the target hole
before and after the pass, and reports `PASSED`/exits non-zero on failure
against its acceptance thresholds (minimum 1mm average height increase,
minimum 10 modified nodes in the hole). See
[scenarios/bulldozer_earthmoving/README.md](scenarios/bulldozer_earthmoving/README.md)
for full details and the reference result.

## 6. Inspect previous run results without re-running anything

Every scenario above writes structured JSON output. `scripts/inspect_outputs.py`
reads it back — listing or summarising previous runs without touching
PyChrono or re-simulating anything.

List every known output file found under a directory as a summary table:

```bash
python -m scripts.inspect_outputs list outputs/
```

Print a full, human-readable report for one specific file:

```bash
python -m scripts.inspect_outputs show outputs/bulldozer_hole_fill/hole_fill_summary.json
```

Add `--raw` to `show` to print the exact unrounded JSON instead of the
formatted report. It recognises three output formats automatically:
`deformation_summary.json`, `hole_fill_summary.json`, and GOOSE `scene.json`.
A missing or corrupted file is reported as a warning, not a crash — one bad
file won't stop the rest of a directory from listing. See
[deformation/README.md](deformation/README.md) for more detail.

## Testing

Run the full automated suite:

```bash
bash scripts/run_tests.sh
```

Or target a specific area:

```bash
python -m unittest discover -s tests -p 'test_goose_heightmap.py' -v
python -m unittest discover -s tests -p 'test_goose_label_viewer.py' -v
python -m unittest discover -s tests -p 'test_bulldozer_earthmoving.py' -v
python -m unittest discover -s tests -p 'test_goose_navigation.py' -v
python -m unittest discover -s tests -p 'test_output_inspector.py' -v
python -m unittest discover -s tests -p 'test_tree_placement.py' -v
python -m unittest discover -s tests -p 'test_tree_collision.py' -v
python -m unittest discover -s tests -p 'test_goose_tree_navigation.py' -v
python -m unittest discover -s tests -p 'test_manual_tree_avoidance.py' -v
python -m unittest discover -s tests -p 'test_goose_rural_placement.py' -v
```

Most of these run without real GOOSE data or PyChrono (synthetic fixtures).
Tests that need PyChrono require the `chrono` environment to be active.

## Common problems

**`ModuleNotFoundError` for `scenarios`, `src`, etc.** — run tools as a
module from the repository root (`python -m scenarios.xxx.run_demo`), not as
a direct script path. Running the `.py` file directly can prevent Python
from finding the top-level project package.

**A command fails on `<frame-name>`** — that's a placeholder, not a literal
folder name. List real generated frames with `ls outputs/goose` first and
substitute one of those.

**A GOOSE scene has no semantic labels** — check it contains
`semantic_fine.npy`, `semantic_coarse.npy`, and `semantic_legend.json`, and
that `scene.json` references them. Rebuild the frame with `--rebuild` using
the current converter; older scenes won't have these until regenerated.

**Graphical window doesn't open, or rendering looks wrong** — demos use
OpenGL by default. If it fails on your setup, fall back to Chrono's
lightweight software renderer instead of forcing the whole graphics stack
onto software emulation:

```bash
AES_IRRLICHT_DRIVER=software python -m <module> ...
```

## Further documentation

- [GOOSE environment setup and terrain generation](environments/README.md)
- [Semantic label viewer](scenarios/goose_label_viewer/README.md)
- [Bulldozer hole-filling scenario](scenarios/bulldozer_earthmoving/README.md)
- [Output inspector and deformation export](deformation/README.md)
