# Saved synthetic viewer fixture

These 6-by-8 rasters were constructed for viewer tests. They are **not** saved
output from issue #22 or a real GOOSE-Ex frame. The category assignments and
colours here exercise the viewer; they do not define the project's taxonomy.

`labels_fine.npy` contains IDs 0, 16, 31, 38 and 50, with one no-data cell
(65535) at the top left. `labels_coarse.npy` groups these into IDs 0, 1, 2 and
3. `height_grid.npy` contains a simple sloped surface. All arrays have the same
shape, row order and column order.

The JSON manifests use the provisional schema documented in
`scenarios/goose_label_viewer/README.md`. Replace or supplement this fixture
with an actual exporter sample once the #22 format is settled.
