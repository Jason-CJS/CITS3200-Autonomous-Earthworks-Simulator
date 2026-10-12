# Archived AARP / construction-zone work

This directory holds code from the project's original AARP/construction-zone
scope, before the client rescope moved the project to GOOSE-Ex exclusively
("AARP/Construction Zone and base GOOSE are both dropped — do not build on
either"). It's kept here for record-keeping, not as working code.

Nothing in the live GOOSE-Ex product imports anything under this directory.
Moving it here was confirmed safe by checking the import graph of the actual
shipped code before the move.

## What's here

- `construction_zone/` — the AARP construction-zone Chrono terrain scene
  (moved from `environments/construction_zone/`).
- `labelling/` — a semantic-label registry and scene-manifest exporter built
  for the AARP scene, superseded for GOOSE-Ex by the pipeline in
  `environments/terrain/` and `scenarios/goose_label_viewer/`.
- `tests/` — the AARP-specific test files that exercised the above
  (`test_semantic_labelling.py`, `test_vehicle_system_integration.py`).

## This code is frozen, not maintained

These files are **not** part of `tests/` discovery anymore, so they don't run
as part of `scripts/run_tests.sh` or `python -m unittest discover -s tests`.
Their internal imports (`from labelling import ...`,
`from environments.construction_zone import ...`) were written assuming the
original repo-root locations and were **not** updated when this directory
was moved — running them from here as-is will fail on import. If a future
team wants to resurrect this work, expect to fix those import paths first.
