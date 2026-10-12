# Scripts

One-line index of every tool here. See [USER_GUIDE.md](../USER_GUIDE.md) for
the actual walkthrough — this is just a map of what exists.

## Setup

| Script | Purpose |
| --- | --- |
| `download_goose_dataset.sh` | Download and prepare the GOOSE-Ex validation dataset into `data/goose/` |
| `run_tests.sh` | Run the full automated test suite |
| `run_graphics.sh` | Launch a standalone vehicle graphics demo (bulldozer/excavator, outside the GOOSE pipeline) |

## Terrain and vehicles

| Script | Purpose |
| --- | --- |
| `goose_to_heightmaps.py` | Discover labelled GOOSE-Ex data, generate terrain, and launch Chrono |
| `inspect_outputs.py` | List/show previous simulation run results without re-simulating |

## Vegetation export

| Script | Purpose |
| --- | --- |
| `export_trees.py` | Export trunk-derived tree placements (these get real physics collision) |
| `export_vegetation.py` | Export generic label-derived vegetation placements (visual only) |

## Vegetation preview (one per category, deliberately separate)

These three cover different placement categories (trunk-derived trees,
label-derived generic vegetation, and semantic-guided rural objects/rocks)
with different underlying data and placement logic, so they're kept as
separate tools rather than merged into one:

| Script | Purpose |
| --- | --- |
| `inspect_tree_placements.py` | Visualize tree placement candidates from GOOSE trunk labels |
| `inspect_vegetation.py` | Visualise GOOSE vegetation labels and placement candidates |
| `preview_goose_rural.py` | Preview GOOSE terrain, trees, rural vegetation, and rocks together |

Rural object *placement generation itself* (as opposed to preview) is
`python -m environments.vegetation.goose_rural_placement` — not in this
directory; see [USER_GUIDE.md](../USER_GUIDE.md).
