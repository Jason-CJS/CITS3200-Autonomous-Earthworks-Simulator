# GOOSE-Ex (ALICE) Dataset (validation split)

Raw GOOSE-Ex 3D point cloud data used for the GOOSE terrain generation
pipeline. This directory is gitignored (except this file). Run
`scripts/download_goose_dataset.sh` from the repo root to fetch it.

## What's here (after running the extraction script)

**3D point clouds only, validation split.** Not 2D images -- the
terrain pipeline this feeds only consumes point clouds + labels. 2D
GOOSE-Ex download is deferred to a separate labels/manifest export
issue if/when that's picked up. Not the training/test splits -- same
reasoning as before: we're extracting real terrain shape from a
handful of real scenes, not training a segmentation model, and
validation is fully labeled where test is not.

```
data/goose/
├── CHANGELOG
├── goose_label_mapping.csv   # class taxonomy
├── LICENSE
├── lidar/val/<scenario>/      # per-scenario LiDAR point clouds (.bin)
└── labels/val/<scenario>/     # per-scenario point cloud labels (.label)
```

## Source

Official GOOSE-Ex dataset, published by Fraunhofer IOSB / University
of the Bundeswehr Munich / University of Koblenz -- an extension of
the base GOOSE dataset, recorded from ALICE (a modified Liebherr R924
excavator) and a Boston Dynamics Spot quadruped, covering construction
sites, quarries, and landfill environments.

- Website: https://goose-dataset.de/
- Download page: https://goose-dataset.de/docs/setup/#download-dataset
- Official repo (sample scripts this project's download script was
  adapted from): https://github.com/FraunhoferIOSB/goose_dataset
- Direct URL used by `scripts/download_goose_dataset.sh`:
  - 3D: https://goose-dataset.de/storage/gooseEx_3d_val.zip

## License and attribution

The **data** is published under **CC BY-SA 4.0** (attribution +
share-alike required). The official repo's code (which this project's
download script is adapted from) is MIT licensed.

If this data is used in any report or publication, cite the GOOSE-Ex
paper (check the official site/repo for the exact citation -- this
project's earlier base-GOOSE citation does not necessarily apply
as-is to GOOSE-Ex, and hasn't been separately confirmed).

## Class taxonomy

`goose_label_mapping.csv` maps GOOSE-Ex's semantic classes for this
scene. Turning these labels into terrain/vegetation placement
decisions is out of scope for this download step -- see the GOOSE
terrain-generation pipeline for how `lidar/`/`labels/` are consumed.

## Usage

```bash
bash scripts/download_goose_dataset.sh
```

Safe to re-run -- an already-downloaded, validated split is detected
via a completion marker and skipped, not re-fetched.