# Chrono SCM terrain deformation validation

This demonstration validates that Project Chrono's Soil Contact Model (SCM) produces visible terrain deformation under vehicle contact.

The test uses Chrono's existing HMMWV model on a flat SCM terrain patch. An automatic driver moves and steers the vehicle so that the resulting tyre tracks can be observed.

## Requirements

- Python with the Project Chrono Python bindings
- Chrono Vehicle and Irrlicht modules
- A graphical environment with OpenGL support

## Running the demonstration

From the repository root:

```bash
python deformation/demo_hmmwv_scm.py
```

The simulation runs automatically and closes after approximately six seconds of simulated time. No keyboard input is required.

To export the final terrain deformation state as CSV and JSON files:

```bash
python deformation/demo_hmmwv_scm.py --export-dir outputs/hmmwv_scm
```

The command creates:

- `deformation_nodes.csv`, containing one row for every SCM grid node modified since the simulation began;
- `deformation_summary.json`, containing deformation metrics and the settings needed to interpret the output.

The CSV records grid coordinates, world X/Y coordinates, initial and final
height relative to the SCM reference plane, total height change, and sinkage.
`height_change_m` is positive when a node rises and negative when it sinks.
`sinkage_m` is positive downward and is zero for raised nodes.

The JSON summary records the modified-node count, maximum and mean sinkage,
simulation duration, timestep, requested terrain dimensions, requested and
actual grid spacing, grid node counts, vehicle, and soil parameters. Chrono may
slightly decrease the requested spacing so an integer number of cells spans
the terrain. If no nodes were modified, the CSV contains only its header and
all summary metrics are zero.

Generated files under the top-level `outputs/` directory are ignored by Git.

## Expected behaviour

When the demonstration runs:

1. The HMMWV begins on the terrain surface.
2. The automatic driver accelerates and steers the vehicle.
3. The tyres visibly sink into and deform the SCM terrain.
4. Persistent wheel tracks remain behind the vehicle.
5. Sinkage is displayed using false-colour terrain rendering.

## Terrain configuration

The demonstration uses:

- a 20 m by 10 m flat terrain patch;
- an SCM grid spacing of 0.15 m;
- Bekker pressure-sinkage soil parameters;
- Mohr-Coulomb friction behaviour;
- an active SCM domain around the vehicle.

The 0.15 m spacing was selected because it produced clearer terrain detail while maintaining acceptable performance in the test environment.

## Validation result

Tested on 10 August 2026 using Ubuntu 24.04 in a VMware virtual machine.

The HMMWV produced clearly visible and persistent wheel tracks through direct tyre contact with the SCM terrain. This confirms that Chrono can provide the basic terrain deformation required by issue #1.

## Limitations

- The export contains only the final terrain state, not a time series.
- Exported terrain states cannot currently be reloaded into a later simulation.
- The test uses the HMMWV benchmark rather than an earthmoving vehicle.
- The terrain begins as a flat patch.
- False-colour rendering emphasises deformation and is not intended to represent final terrain materials.
- This test covers tyre-induced deformation only. Excavator, bulldozer and sensor functionality are handled separately.
