#!/bin/bash
#
# Downloads the GOOSE dataset validation split (2D images + labels, and
# 3D point clouds) needed for the GOOSE-aligned environment terrain
# pipeline. Adapted from the official sample script at
# https://github.com/FraunhoferIOSB/goose_dataset/blob/main/scripts/download_goose.sh
#
# Deliberately uses the VALIDATION split only, not the full training set:
# - Training/test splits are an ML-training concept this project doesn't
#   need -- we're extracting real terrain shape from a handful of real
#   scenes, not training a segmentation model.
# - Validation is properly labeled (test split is unlabeled -- raw
#   images / xyzi points only, per the dataset's own docs) and is a
#   fraction of the size of training (~3GB vs ~27GB for 3D).
#
# Extraction is validated BEFORE being treated as complete: each split
# is extracted into a temporary directory first, checked for the
# specific files/folders it's expected to contain, and only moved into
# its final location -- with a completion marker written -- once that
# validation passes. Idempotency checks on re-run look for the
# completion marker, not just directory existence, so a partial/failed
# prior run is correctly re-attempted rather than silently treated as
# done.
#
# Data license: CC BY-SA 4.0 (attribution + share-alike required).
# See data/goose/README.md for full citation and license details.
#
# Usage: bash scripts/download_goose_dataset.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$REPO_ROOT/data/goose"

GOOSE_2D_URL="https://goose-dataset.de/storage/goose_2d_val.zip"
GOOSE_3D_URL="https://goose-dataset.de/storage/goose_3d_val.zip"

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

# require_nonempty_dir <path> <description>
# Exits non-zero if the given directory doesn't exist or contains no files.
require_nonempty_dir() {
    local path="$1"
    local desc="$2"
    if [ ! -d "$path" ]; then
        fail "$desc: expected directory '$path' not found after extraction."
    fi
    if [ -z "$(find "$path" -type f -print -quit)" ]; then
        fail "$desc: directory '$path' exists but contains no files."
    fi
}

# require_file <path> <description>
require_file() {
    local path="$1"
    local desc="$2"
    if [ ! -s "$path" ]; then
        fail "$desc: expected file '$path' not found or empty."
    fi
}

# -----------------------------------------------------------------------
# 2D images + labels (validation split)
# -----------------------------------------------------------------------
if [ -f ".goose_2d_val_complete" ]; then
    echo "[goose 2D] Already present and validated, skipping download."
else
    echo "[goose 2D] Downloading validation split..."

    if [ ! -f "goose_2d_val.zip" ]; then
        wget "$GOOSE_2D_URL"
    fi

    echo "[goose 2D] Unzipping..."
    rm -rf goose_2d_val_tmp
    unzip -q goose_2d_val.zip -d goose_2d_val_tmp

    echo "[goose 2D] Validating extracted contents..."
    require_file "goose_2d_val_tmp/goose_label_mapping.csv" "[goose 2D]"
    require_nonempty_dir "goose_2d_val_tmp/images/val" "[goose 2D]"
    require_nonempty_dir "goose_2d_val_tmp/labels/val" "[goose 2D]"

    echo "[goose 2D] Validation passed. Moving into place..."
    mkdir -p images/val labels/val

    [ -f "goose_label_mapping.csv" ] || cp goose_2d_val_tmp/goose_label_mapping.csv .
    [ -f "CHANGELOG" ] || cp goose_2d_val_tmp/CHANGELOG . 2>/dev/null || true
    [ -f "LICENSE" ] || cp goose_2d_val_tmp/LICENSE . 2>/dev/null || true

    mv goose_2d_val_tmp/images/val/* images/val/
    mv goose_2d_val_tmp/labels/val/* labels/val/

    # Only reached if every step above succeeded -- set -e means any
    # failure (including a failed mv) stops the script here, before
    # cleanup and before the completion marker is written.
    rm -rf goose_2d_val_tmp goose_2d_val.zip
    touch .goose_2d_val_complete

    echo "[goose 2D] Done."
fi

# -----------------------------------------------------------------------
# 3D point clouds (validation split)
#
# Confirmed structure from a real download: the zip contains its own
# labels/val/ and lidar/val/ subfolders.
# -----------------------------------------------------------------------
if [ -f ".goose_3d_val_complete" ]; then
    echo "[goose 3D] Already present and validated, skipping download."
else
    echo "[goose 3D] Downloading validation split..."

    if [ ! -f "goose_3d_val.zip" ]; then
        wget "$GOOSE_3D_URL"
    fi

    echo "[goose 3D] Unzipping..."
    rm -rf goose_3d_val_tmp
    unzip -q goose_3d_val.zip -d goose_3d_val_tmp

    echo "[goose 3D] Validating extracted contents..."
    require_nonempty_dir "goose_3d_val_tmp/labels/val" "[goose 3D]"
    require_nonempty_dir "goose_3d_val_tmp/lidar/val" "[goose 3D]"

    echo "[goose 3D] Validation passed. Moving into place..."
    mkdir -p 3d/labels 3d/lidar
    mv goose_3d_val_tmp/labels/val 3d/labels/
    mv goose_3d_val_tmp/lidar/val 3d/lidar/

    rm -rf goose_3d_val_tmp goose_3d_val.zip
    touch .goose_3d_val_complete

    echo "[goose 3D] Done."
fi

echo ""
echo "GOOSE validation split ready under $DATA_DIR/"
echo "  2D: $DATA_DIR/images/val, $DATA_DIR/labels/val"
echo "  3D: $DATA_DIR/3d/labels/val, $DATA_DIR/3d/lidar/val"