"""Inspect previously-generated simulation output files without re-running them.

Reads the JSON files already produced by the project's exporters
(deformation summaries, hole-fill summaries, GOOSE scene manifests) so they
can be listed and reviewed independently of the simulation that produced
them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deformation.output_inspector import load_output_directory, load_output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list", help="list known output files found under a directory"
    )
    list_parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=Path("outputs"),
        help="directory to search (default: outputs)",
    )

    show_parser = subparsers.add_parser(
        "show", help="print the full contents of one output file"
    )
    show_parser.add_argument("file", type=Path, help="path to an output JSON file")

    return parser.parse_args()


def run_list(directory: Path) -> int:
    records = load_output_directory(directory)
    if not records:
        print(f"No known output files found under {directory}")
        return 0

    exit_code = 0
    for record in records:
        if record.ok:
            print(f"{record.path}\n  {record.summary}")
        else:
            exit_code = 1
            print(f"{record.path}\n  WARNING: {record.error}", file=sys.stderr)
    return exit_code


def run_show(file: Path) -> int:
    record = load_output_file(file)
    if not record.ok:
        print(f"WARNING: {record.error}", file=sys.stderr)
        return 1

    print(f"kind: {record.kind}")
    print(f"format_version: {record.format_version}")
    print(f"summary: {record.summary}")
    print(json.dumps(record.data, indent=2, sort_keys=True))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "list":
        return run_list(args.directory)
    return run_show(args.file)


if __name__ == "__main__":
    raise SystemExit(main())
