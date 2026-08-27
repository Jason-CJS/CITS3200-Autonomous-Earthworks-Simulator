# GOOSE Dataset (validation split)

Raw GOOSE data used for the GOOSE-aligned environment's terrain
generation pipeline. This directory is gitignored (except this file) --
run `scripts/download_goose_data.sh` from the repo root to fetch it.

## What's here

**Validation split only** (2D images + labels, 3D point clouds) -- not
the full training set. Training/test splits are an ML-training concept
this project doesn't need: we're extracting real terrain shape from a
handful of real scenes to build a heightmap, not training a
segmentation model. Validation is fully labeled and a fraction of the
size of training (~3GB vs ~27GB for the 3D data). The test split was
not usable here regardless -- it ships unlabeled (raw images / xyzi
points only).

```
data/goose/
├── CHANGELOG
├── goose_label_mapping.csv   # 64-class -> 11-coarse-category taxonomy
├── LICENSE
├── images/val/                # 2D RGB images
├── labels/val/                # 2D per-pixel semantic labels
└── 3d/
    └── val/
        ├── labels/val/         # per-scenario point cloud labels
        └── lidar/val/          # per-scenario LiDAR point clouds
```

## Source

Official GOOSE dataset, published by Fraunhofer IOSB / University of
the Bundeswehr Munich / University of Koblenz.

- Website: https://goose-dataset.de/
- Download page: https://goose-dataset.de/docs/setup/#download-dataset
- Official repo (sample scripts this project's download script was
  adapted from): https://github.com/FraunhoferIOSB/goose_dataset
- Direct URLs used by `scripts/download_goose_data.sh`:
  - 2D: https://goose-dataset.de/storage/goose_2d_val.zip
  - 3D: https://goose-dataset.de/storage/goose_3d_val.zip

## License and attribution

The **data** is published under **CC BY-SA 4.0** (attribution +
share-alike required). The official repo's code (which this project's
download script is adapted from) is MIT licensed.

If this data is used in any report or publication, cite:

```
@article{goose-dataset,
    author = {Peter Mortimer and Raphael Hagmanns and Miguel Granero
              and Thorsten Luettel and Janko Petereit and Hans-Joachim Wuensche},
    title = {The GOOSE Dataset for Perception in Unstructured Environments},
    url={https://arxiv.org/abs/2310.16788},
    conference={2024 IEEE International Conference on Robotics and Automation (ICRA)}
    year = 2024
}
```

## Class taxonomy

`goose_label_mapping.csv` maps GOOSE's 64 fine-grained semantic classes
to 11 coarse categories (e.g. Vegetation, Terrain, Vehicle). Turning
these labels into terrain/vegetation placement decisions is out of
scope for this download step -- see the GOOSE terrain-generation
pipeline issue (depends on this one).

## Usage

```bash
bash scripts/download_goose_data.sh
```

Safe to re-run -- already-downloaded splits are detected and skipped,
not re-fetched.
