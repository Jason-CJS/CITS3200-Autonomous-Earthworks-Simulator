# Real issue #22 export fixture

Source: the user-provided archive
`alice_scenario02_sequence07_0001_1697208276047079000.tar.gz`, supplied on
6 October 2026 for viewer integration and testing.

The six exported files are preserved byte-for-byte. The enclosing directory was
renamed to `goose_label_viewer_real` for the test suite. `source.dataset_root` in
the manifest records the original machine; the viewer does not access that path.
No raw point clouds or per-point label files are required.

- Scene version: 2; semantic metadata and legend version: 1.
- Grid: 268 by 268 cells, row 0 at ymax and column 0 at xmin.
- Fine map: uint16; unobserved ID 65535.
- Coarse map: uint8; unobserved ID 255; ignored category ID 0.
- Observed cells: 26,364; unobserved cells: 45,460.
- The legend contains names and category membership but no colours.

These are derived GOOSE-Ex data supplied for this project, not synthetic test
values. Existing dataset attribution and licence terms also apply to this fixture.
