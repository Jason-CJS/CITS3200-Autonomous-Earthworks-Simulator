#!/bin/bash
#
# Downloads the GOOSE dataset validation split (2D images + labels, and
# 3D point clouds) needed for the GOOSE-aligned environment terrain
# pipeline. Adapted from the official sample script at
# https://github.com/FraunhoferIOSB/goose_dataset/blob/main/scripts/download_goose.sh
#
# Deliberately uses the VALIDATION split only, not the full training set:
# - Training/test splits are an ML-training concept this project doesn't
#   need. We're extracting real terrain shape from a handful of real
#   scenes, not training a segmentation model.
# - Validation is properly labeled (test split is unlabeled - raw
#   images / xyzi points only, per the dataset's own docs) and is a
#   fraction of the size of training (~3GB vs ~27GB for 3D).
#
# Data license: CC BY-SA 4.0 (attribution + share-alike required).
# See data/goose/README.md for full citation and license details.
#
# Usage: bash download_goose.sh

set -euo pipefail

# Resolve paths relative to the repo root (this script's parent directory),
# not the caller's current working directory - so this works whether
# it's run as `bash scripts/download_goose_dataset.sh` from repo root, or
# `./download_goose_dataset.sh` from inside scripts/.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$REPO_ROOT/data/goose"

GOOSE_2D_URL="https://goose-dataset.de/storage/goose_2d_val.zip"
GOOSE_3D_URL="https://goose-dataset.de/storage/goose_3d_val.zip"

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

# -----------------------------------------------------------------------
# 2D images + labels (validation split)
# -----------------------------------------------------------------------
if [ -d "images/val" ] && [ -d "labels/val" ]; then
    echo "[goose 2D] Already present, skipping download."
else
    echo "[goose 2D] Downloading validation split..."

    if [ ! -f "goose_2d_val.zip" ]; then
        wget https://goose-dataset.de/storage/goose_2d_val.zip
    fi

    echo "[goose 2D] Unzipping..."
    unzip -q goose_2d_val.zip -d goose_2d_val

    mkdir -p images/val labels/val

    # Only copy the shared metadata files once (they're identical across
    # splits in the official layout)
    if [ ! -f "goose_label_mapping.csv" ]; then
        cp goose_2d_val/goose_label_mapping.csv . 2>/dev/null || \
            echo "[goose 2D] WARNING: goose_label_mapping.csv not found at expected path -- check goose_2d_val/ structure manually."
    fi
    if [ ! -f "CHANGELOG" ]; then
        cp goose_2d_val/CHANGELOG . 2>/dev/null || true
    fi
    if [ ! -f "LICENSE" ]; then
        cp goose_2d_val/LICENSE . 2>/dev/null || true
    fi

    mv goose_2d_val/images/val/* images/val/ 2>/dev/null || \
        echo "[goose 2D] WARNING: expected images/val/ path not found inside the zip -- inspect goose_2d_val/ manually and adjust this script."
    mv goose_2d_val/labels/val/* labels/val/ 2>/dev/null || \
        echo "[goose 2D] WARNING: expected labels/val/ path not found inside the zip -- inspect goose_2d_val/ manually and adjust this script."

    # Cleanup intermediate files
    rm -rf goose_2d_val goose_2d_val.zip

    echo "[goose 2D] Done."
fi

# -----------------------------------------------------------------------
# 3D point clouds (validation split)
#
# NOTE: the internal zip structure here has NOT been verified against a
# real download (unlike the 2D block above, which mirrors the official
# script exactly). This extracts into data/goose/3d/val/ preserving
# whatever structure is inside, rather than guessing at subpaths. After
# the first real run, inspect data/goose/3d/val/ and tighten this section
# to match the 2D block's pattern if the structure allows it.
# -----------------------------------------------------------------------
if [ -d "3d/val" ] && [ "$(ls -A 3d/val 2>/dev/null)" ]; then
    echo "[goose 3D] Already present, skipping download."
else
    echo "[goose 3D] Downloading validation split..."

    if [ ! -f "goose_3d_val.zip" ]; then
        wget https://goose-dataset.de/storage/goose_3d_val.zip
    fi

    echo "[goose 3D] Unzipping..."
    mkdir -p 3d/val
    unzip -q goose_3d_val.zip -d 3d/val

    rm -f goose_3d_val.zip

    echo "[goose 3D] Done. Inspect data/goose/3d/val/ structure -- this"
    echo "  script has not been validated against a real download."
fi

echo ""
echo "GOOSE validation split ready under $DATA_DIR/"
echo "  2D: $DATA_DIR/images/val, $DATA_DIR/labels/val"
echo "  3D: $DATA_DIR/3d/val"
