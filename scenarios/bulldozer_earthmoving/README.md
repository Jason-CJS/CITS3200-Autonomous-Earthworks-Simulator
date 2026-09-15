# Bulldozer hole-filling scenario

## Overview

This scenario demonstrates a repeatable bulldozer earthmoving task using the Project Chrono B10 bulldozer and SCM deformable terrain.

The generated terrain contains a raised mound positioned in front of a shallow hole. The bulldozer follows a scripted path, collects material with its blade and raises the blade as it reaches the target. The final terrain is then compared with its initial state to determine whether the average height inside the hole increased.

The scenario demonstrates a measurable partial fill from one pass. It does not attempt to completely fill the hole.

## Requirements

The project Conda environment includes the required versions of Python, PyChrono, NumPy and Matplotlib.

Create or update the environment from the repository root:

```bash
conda env update -f environment.yml --prune
conda activate chrono
```

The scenario uses:

* The B10 bulldozer model developed for Issue #2
* Chrono SCM deformable terrain
* The deformation exporter added in PR #15
* Matplotlib for the before-and-after comparison

## Running the scenario

Run the default scenario without opening a graphical window:

```bash
python -m scenarios.bulldozer_earthmoving.run_scenario \
  --headless \
  --output-dir outputs/bulldozer_hole_fill
```

Run the graphical version on Linux or WSL using software rendering:

```bash
LIBGL_ALWAYS_SOFTWARE=1 \
GALLIUM_DRIVER=llvmpipe \
python -m scenarios.bulldozer_earthmoving.run_scenario \
  --output-dir outputs/bulldozer_hole_fill
```

The graphical run is scripted and does not require keyboard input.

A different scripted driving duration can be supplied when testing scenario parameters:

```bash
python -m scenarios.bulldozer_earthmoving.run_scenario \
  --headless \
  --drive-duration 2.40 \
  --output-dir outputs/bulldozer_hole_fill
```

The default duration has been tuned and validated for the purpose-built terrain. Changing it may cause the scenario to fail its acceptance thresholds.

## Generated outputs

The selected output directory contains:

| File                          | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| `purpose_built_heightmap.bmp` | Heightmap containing the initial mound and hole         |
| `deformation_nodes.csv`       | Initial and final heights for modified SCM nodes        |
| `deformation_summary.json`    | General deformation statistics and simulation settings  |
| `hole_fill_summary.json`      | Scenario result, hole measurements and pass/fail status |
| `terrain_comparison.png`      | Before, after and height-change visualisation           |

Graphical runs also produce:

| File               | Description                                          |
| ------------------ | ---------------------------------------------------- |
| `before_scene.png` | Irrlicht screenshot taken before the bulldozer moves |
| `after_scene.png`  | Irrlicht screenshot taken after the scripted pass    |

Generated output files are excluded from Git.

## Success criteria

The scenario passes when all of the following conditions are met:

* At least one SCM terrain node was modified
* The average terrain height inside the target hole increased by at least `0.001 m` or `1 mm`
* At least 10 SCM nodes inside the target hole changed

The target average includes every SCM grid node whose centre falls within the configured hole radius. Requiring both a minimum average increase and a minimum number of changed nodes prevents numerical noise or a very small local change from being reported as a successful fill.

The process exits with a non-zero status when the acceptance thresholds are not met.

## Reference result

The default scenario was validated with the following result:

```text
Modified SCM nodes: 1287
Initial average hole height: -0.035915 m
Final average hole height: -0.033829 m
Average hole height increase: 0.002086 m (2.09 mm)
Modified nodes inside hole: 14
PASSED: hole-filling acceptance thresholds were met.
```

Repeated runs with the same initial conditions produced the same measured result. Small differences may still occur on another system or PyChrono build.

## Interpreting the visualisation

The terrain comparison contains three panels:

* **Before:** the purpose-built mound and target hole before movement
* **After:** the reconstructed terrain after the bulldozer pass
* **Height change:** the difference between the initial and final node heights

In the height-change panel, positive values show where the terrain rose and negative values show where it was lowered. The outlined circle identifies the target hole, and its annotation reports the average height increase inside that area.

## Testing

Run the scenario-specific automated tests:

```bash
python -m unittest discover \
  -s tests \
  -p 'test_bulldozer_earthmoving.py' \
  -v
```

Run the complete project test suite:

```bash
bash scripts/run_tests.sh
```

Check the Python files for syntax errors:

```bash
python -m py_compile \
  scenarios/bulldozer_earthmoving/terrain_profile.py \
  scenarios/bulldozer_earthmoving/run_scenario.py \
  scenarios/bulldozer_earthmoving/visualisation.py
```

## Assumptions and limitations

* Chrono SCM represents soil using a deformable height field rather than individual soil particles.
* The model can demonstrate redistribution, sinkage and raised terrain, but it does not reproduce fully realistic bulk soil flow.
* The current result is a measurable partial fill from one pass, not a completely filled hole.
* The bulldozer chassis movement is prescribed from the track commands. Contact-generated traction, track slip and individual track-shoe dynamics are not currently simulated.
* The soil parameters are suitable for demonstrating SCM interaction but have not been calibrated against AARP site measurements.
* The current scenario uses a deterministic purpose-built heightmap. Adapting it to GOOSE-derived terrain remains dependent on completion and alignment of the GOOSE terrain pipeline.
* Software rendering may be required when running Irrlicht under WSL.

## Relevant files

* `terrain_profile.py` defines the mound, hole, heightmap generation and target measurements.
* `run_scenario.py` creates and runs the scripted Chrono simulation.
* `visualisation.py` produces the terrain comparison image.
* `tests/test_bulldozer_earthmoving.py` tests the terrain, measurements and acceptance criteria.
