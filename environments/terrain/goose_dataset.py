"""Discover labelled GOOSE frames without loading NumPy or PyChrono."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


SPLITS = ("val", "train", "test")
CLOUD_DIRECTORIES = {"lidar", "velodyne"}


def frame_name_for(pointcloud: Path) -> str:
    for suffix in ("_pcl.bin", "_vls128.bin", ".bin"):
        if pointcloud.name.endswith(suffix):
            return pointcloud.name[: -len(suffix)]
    raise ValueError(f"Expected a .bin point cloud: {pointcloud}")


def sequence_matches(pointcloud: Path, sequence: str | None) -> bool:
    if sequence is None:
        return True
    number = sequence.removeprefix("sequence")
    if not number.isdecimal():
        raise ValueError("--sequence must be a number, such as 07 or sequence07")
    return re.search(rf"(?:^|_)sequence0*{int(number)}(?=_|$)", pointcloud.stem) is not None


def matching_label(pointcloud: Path, label_dir: Path) -> Path | None:
    prefix = frame_name_for(pointcloud)
    for name in (f"{prefix}_goose.label", f"{prefix}.label", f"{pointcloud.stem}.label"):
        label = label_dir / name
        if label.is_file():
            return label
    return None


@dataclass(frozen=True)
class Scenario:
    data_root: Path
    cloud_dir: Path
    label_dir: Path
    split: str
    name: str
    clouds: tuple[Path, ...]

    def pairs(self, sequence: str | None = None) -> list[tuple[Path, Path]]:
        pairs = []
        for cloud in self.clouds:
            if sequence_matches(cloud, sequence):
                label = matching_label(cloud, self.label_dir)
                if label is not None:
                    pairs.append((cloud, label))
        return pairs


@dataclass(frozen=True)
class SelectedFrame:
    dataset_root: Path
    scenario: Scenario
    pointcloud: Path
    label: Path
    mapping: Path | None
    changelog: Path | None
    selection_index: int


@dataclass(frozen=True)
class FrameMetadata:
    name: str
    sequence: str | None
    frame_number: int | None
    timestamp: int | None


def parse_frame_metadata(pointcloud: Path) -> FrameMetadata:
    """Extract stable frame fields from the documented GOOSE file name."""
    name = frame_name_for(pointcloud)
    sequence_match = re.search(r"(?:^|_)sequence(\d+)(?=_|$)", name)
    trailing_numbers = re.search(r"_(\d+)_(\d+)$", name)
    return FrameMetadata(
        name=name,
        sequence=sequence_match.group(1) if sequence_match else None,
        frame_number=int(trailing_numbers.group(1)) if trailing_numbers else None,
        timestamp=int(trailing_numbers.group(2)) if trailing_numbers else None,
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_scenarios(dataset_root: Path) -> list[Scenario]:
    """Find flat archives and nested 3d/<split> layouts, excluding 2D data."""
    root = dataset_root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(
            f"Dataset directory does not exist: {root}. "
            "Pass the prepared dataset directory with --dataset."
        )
    scenarios = []

    def on_error(error: OSError) -> None:
        raise error

    for directory, subdirectories, _ in os.walk(root, onerror=on_error):
        current = Path(directory)
        if current.name in CLOUD_DIRECTORIES:
            for split in SPLITS:
                split_root = current / split
                if not split_root.is_dir():
                    continue
                for cloud_dir in sorted(split_root.iterdir()):
                    if not cloud_dir.is_dir():
                        continue
                    clouds = tuple(sorted(path for path in cloud_dir.glob("*.bin") if path.is_file()))
                    if clouds:
                        scenarios.append(Scenario(
                            data_root=current.parent,
                            cloud_dir=cloud_dir,
                            label_dir=current.parent / "labels" / split / cloud_dir.name,
                            split=split,
                            name=cloud_dir.name,
                            clouds=clouds,
                        ))
            subdirectories[:] = []
        else:
            subdirectories[:] = sorted(
                name for name in subdirectories
                if not name.startswith(".")
                and name not in {"images", "labels", "generated", "outputs", "__pycache__"}
            )
    return sorted(scenarios, key=lambda item: (
        SPLITS.index(item.split), item.name, str(item.cloud_dir)
    ))


def mapping_for(data_root: Path, dataset_root: Path) -> Path | None:
    """Prefer the selected archive's map, then a shared map up to dataset_root."""
    current = data_root
    while current.is_relative_to(dataset_root):
        mapping = current / "goose_label_mapping.csv"
        if mapping.is_file():
            return mapping
        if current == dataset_root:
            break
        current = current.parent
    return None


def changelog_for(data_root: Path, dataset_root: Path) -> Path | None:
    """Locate version information distributed with a GOOSE archive."""
    candidates = (
        "CHANGELOG",
        "CHANGELOG.md",
        "CHANGELOG.txt",
        "changelog",
        "changelog.md",
        "changelog.txt",
    )
    current = data_root
    while current.is_relative_to(dataset_root):
        for name in candidates:
            changelog = current / name
            if changelog.is_file():
                return changelog
        if current == dataset_root:
            break
        current = current.parent
    return None


def frame_source_fingerprints(frame: SelectedFrame) -> dict[str, str | None]:
    """Hash all source files that can affect generated scene outputs."""
    return {
        "pointcloud_sha256": file_sha256(frame.pointcloud),
        "labels_sha256": file_sha256(frame.label),
        "mapping_sha256": file_sha256(frame.mapping) if frame.mapping else None,
        "changelog_sha256": file_sha256(frame.changelog) if frame.changelog else None,
    }


def dataset_version_fingerprint(
    frame: SelectedFrame,
    fingerprints: dict[str, str | None] | None = None,
) -> str:
    """Return a reproducible version ID even when an archive has no version file."""
    if fingerprints is None:
        fingerprints = frame_source_fingerprints(frame)
    dataset_evidence = {
        "changelog_sha256": fingerprints["changelog_sha256"],
        "mapping_sha256": fingerprints["mapping_sha256"],
    }
    if not any(dataset_evidence.values()):
        dataset_evidence.update({
            "pointcloud_sha256": fingerprints["pointcloud_sha256"],
            "labels_sha256": fingerprints["labels_sha256"],
        })
    encoded = json.dumps(
        dataset_evidence, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def scenario_listing(scenarios: list[Scenario]) -> str:
    lines = []
    for scenario in scenarios:
        pairs = scenario.pairs()
        lines.append(
            f"{scenario.split}  {scenario.name}  "
            f"{len(pairs)}/{len(scenario.clouds)} labelled frames  {scenario.cloud_dir}"
        )
    return "\n".join(lines)


def no_clouds_message(root: Path) -> str:
    return (
        f"No 3D .bin point clouds found under {root}. Expected "
        "lidar/<split>/<scenario>/ or velodyne/<split>/<scenario>/, "
        "possibly inside 3d/<split>/ or an extracted archive folder. "
        "2D images and PNG labels alone cannot produce a LiDAR heightmap. "
        "Pass the directory containing the prepared 3D data with --dataset."
    )


def select_frame(
    dataset_root: Path,
    split: str = "auto",
    scenario: str | None = None,
    sequence: str | None = None,
    frame_index: int = 0,
) -> SelectedFrame:
    root = dataset_root.expanduser().resolve()
    if split not in ("auto", *SPLITS):
        raise ValueError(f"Unsupported split {split!r}; choose auto, val, train or test")
    if frame_index < 0:
        raise IndexError("--frame-index must be zero or greater")
    if sequence is not None:
        sequence_matches(Path("frame.bin"), sequence)  # Validate even an empty selection.
    discovered = discover_scenarios(root)
    if not discovered:
        raise FileNotFoundError(no_clouds_message(root))
    candidates = [
        item for item in discovered
        if (split == "auto" or item.split == split)
        and (scenario is None or item.name == scenario)
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No scenario matches split={split!r}, scenario={scenario!r}.\n"
            f"Available 3D data:\n{scenario_listing(discovered)}"
        )
    usable = [(item, item.pairs(sequence)) for item in candidates]
    usable = [(item, pairs) for item, pairs in usable if pairs]
    if not usable:
        raise FileNotFoundError(
            f"3D point clouds were found, but no matching .label files for "
            f"split={split!r}, scenario={scenario!r}, sequence={sequence!r}. "
            "Labels must be under labels/<split>/<scenario>/ beside the selected "
            "lidar/ or velodyne/ directory and have the same frame prefix. "
            "PNG image labels cannot be used. An unlabelled test split is not "
            "sufficient; use a labelled split.\n"
            f"Available 3D data:\n{scenario_listing(candidates)}"
        )
    # Auto chooses a labelled validation scenario first, then train, then test.
    chosen, pairs = usable[0]
    duplicates = [item for item, _ in usable if item.split == chosen.split and item.name == chosen.name]
    if len(duplicates) > 1:
        locations = "\n".join(str(item.data_root) for item in duplicates)
        raise ValueError(
            f"More than one copy of {chosen.split}/{chosen.name} was found. "
            f"Pass a more specific --dataset directory:\n{locations}"
        )
    if frame_index >= len(pairs):
        raise IndexError(
            f"Frame index {frame_index} is outside 0..{len(pairs) - 1} for "
            f"labelled frames in {chosen.split}/{chosen.name}"
        )
    pointcloud, label = pairs[frame_index]
    return SelectedFrame(
        root,
        chosen,
        pointcloud,
        label,
        mapping_for(chosen.data_root, root),
        changelog_for(chosen.data_root, root),
        frame_index,
    )
