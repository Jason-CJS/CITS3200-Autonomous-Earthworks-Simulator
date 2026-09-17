#!/bin/bash
#
# Downloads the GOOSE-Ex (ALICE) 3D point cloud validation split needed
# for the GOOSE terrain generation pipeline. Replaces the earlier base
# GOOSE download -- superseded per team decision (client meeting,
# GOOSE-Ex confirmed as the single environment going forward).
#
# Scoped to 3D only: the terrain pipeline this feeds only consumes
# point clouds + labels, not 2D images. GOOSE-Ex 2D download is
# deferred to the separate labels/manifest export issue if/when that's
# picked up -- not needed here.
#
# Output structure is deliberately flat (matching what the terrain
# pipeline's build_heightmap.py / goose_to_heightmaps.py already expect
# internally, just rooted here instead of under environments/goose/data/):
#
#   data/goose/
#     goose_label_mapping.csv
#     lidar/val/<scenario>/*.bin
#     labels/val/<scenario>/*.label
#
# Confirmed from a real download: the zip contains its own top-level
# gooseEx_3d_val/ folder (not flat), with goose_label_mapping.csv,
# lidar/val/, and labels/val/ inside that.
#
# NOTE: the download URL below (gooseEx_3d_val.zip) is inferred by
# analogy and was confirmed working via a real successful download.
#
# Data license: CC BY-SA 4.0 (attribution + share-alike required).
# See data/goose/README.md for full citation and license details.
#
# Usage: bash scripts/download_goose_dataset.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$REPO_ROOT/data/goose"

GOOSE_EX_3D_URL="https://goose-dataset.de/storage/gooseEx_3d_val.zip"

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

# require_nonempty_dir <path> <description>
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
# GOOSE-Ex 3D point clouds (validation split)
# -----------------------------------------------------------------------
if [ -f ".gooseEx_3d_val_complete" ]; then
    echo "[gooseEx 3D] Already present and validated, skipping download."
else
    echo "[gooseEx 3D] Downloading validation split..."

    if [ ! -f "gooseEx_3d_val.zip" ]; then
        wget "$GOOSE_EX_3D_URL"
    fi

    echo "[gooseEx 3D] Unzipping..."
    rm -rf gooseEx_3d_val_tmp
    unzip -q gooseEx_3d_val.zip -d gooseEx_3d_val_tmp

    # Confirmed from a real extraction: the zip contains its own
    # gooseEx_3d_val/ subfolder rather than extracting flat -- i.e. the
    # real content sits at gooseEx_3d_val_tmp/gooseEx_3d_val/..., not
    # gooseEx_3d_val_tmp/... directly.
    EXTRACTED="gooseEx_3d_val_tmp/gooseEx_3d_val"

    echo "[gooseEx 3D] Validating extracted contents..."
    require_file "$EXTRACTED/goose_label_mapping.csv" "[gooseEx 3D]"
    require_nonempty_dir "$EXTRACTED/lidar/val" "[gooseEx 3D]"
    require_nonempty_dir "$EXTRACTED/labels/val" "[gooseEx 3D]"

    echo "[gooseEx 3D] Validation passed. Moving into place..."
    # Clear any leftover partial move targets from a prior interrupted
    # run before moving -- reaching this point means the completion
    # marker is missing, so anything already at these paths is from an
    # unvalidated attempt and shouldn't block a clean retry.
    rm -rf lidar/val labels/val
    mkdir -p lidar labels

    [ -f "goose_label_mapping.csv" ] || cp "$EXTRACTED/goose_label_mapping.csv" .
    [ -f "CHANGELOG" ] || cp "$EXTRACTED/CHANGELOG" . 2>/dev/null || true
    [ -f "LICENSE" ] || cp "$EXTRACTED/LICENSE" . 2>/dev/null || true

    mv "$EXTRACTED/lidar/val" lidar/
    mv "$EXTRACTED/labels/val" labels/

    # Only reached if every step above succeeded -- set -e means any
    # failure stops the script here, before cleanup and before the
    # completion marker is written.
    rm -rf gooseEx_3d_val_tmp gooseEx_3d_val.zip
    touch .gooseEx_3d_val_complete

    echo "[gooseEx 3D] Done."
fi

echo ""
echo "GOOSE-Ex 3D validation split ready under $DATA_DIR/"
echo "  $DATA_DIR/lidar/val, $DATA_DIR/labels/val"
echo "  $DATA_DIR/goose_label_mapping.csv"