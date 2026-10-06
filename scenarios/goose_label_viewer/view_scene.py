"""Save colour-coded fine/coarse label previews with a legend."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True, help="generated scene.json")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/goose_label_viewer"))
    parser.add_argument("--map", dest="selection", choices=("fine", "coarse", "both"), default="both")
    parser.add_argument("--overlay", action="store_true", help="blend labels over the saved heightmap")
    parser.add_argument("--alpha", type=float, default=0.55, help="overlay label opacity, 0..1 (default: 0.55)")
    parser.add_argument("--dpi", type=int, default=150, help="PNG resolution, 50..600 (default: 150)")
    parser.add_argument("--fine-map", type=Path, help="explicit fine raster, relative to the working directory")
    parser.add_argument("--coarse-map", type=Path, help="explicit coarse raster, relative to the working directory")
    parser.add_argument("--legend", type=Path, help="explicit legend JSON, relative to the working directory")
    parser.add_argument("--heightmap", type=Path, help="explicit heightmap for --overlay")
    args = parser.parse_args(argv)
    if args.heightmap is not None and not args.overlay:
        parser.error("--heightmap requires --overlay")
    if not 0 <= args.alpha <= 1:
        parser.error("--alpha must be between 0 and 1")
    if not 50 <= args.dpi <= 600:
        parser.error("--dpi must be between 50 and 600")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        from .viewer import ViewerError, load_scene, render_previews
    except ImportError as error:
        print(
            f"Label viewer dependency unavailable: {error}. "
            "Update and activate the project Conda environment (NumPy, Pillow, Matplotlib).",
            file=sys.stderr,
        )
        return 2
    try:
        scene = load_scene(
            args.scene, selection=args.selection, fine_map=args.fine_map,
            coarse_map=args.coarse_map, legend_path=args.legend,
            overlay=args.overlay, heightmap_path=args.heightmap,
        )
        result = render_previews(scene, args.output_dir, alpha=args.alpha, dpi=args.dpi)
    except (ViewerError, OSError, ImportError) as error:
        print(f"Cannot view scene: {error}", file=sys.stderr)
        return 2
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for path in result.paths:
        print(f"Saved: {path}")
    print("Open the saved PNG files in your image viewer to inspect the maps and legends.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
