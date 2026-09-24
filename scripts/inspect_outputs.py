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

from deformation.output_inspector import (
    KIND_LABELS,
    format_report,
    load_output_directory,
    load_output_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list", help="list known output files found under a directory as a table"
    )
    list_parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=Path("outputs"),
        help="directory to search (default: outputs)",
    )

    show_parser = subparsers.add_parser(
        "show", help="print a labelled report for one output file"
    )
    show_parser.add_argument("file", type=Path, help="path to an output JSON file")
    show_parser.add_argument(
        "--raw",
        action="store_true",
        help="print the full raw JSON instead of the formatted report",
    )

    return parser.parse_args()


def _shorten_path(path: Path, root: Path, max_len: int = 64) -> str:
    try:
        text = str(path.relative_to(root))
    except ValueError:
        text = str(path)

    if len(text) <= max_len:
        return text

    keep_end = max_len - 3
    return f"...{text[-keep_end:]}"


def _print_table(rows: list[tuple[str, str, str]]) -> None:
    headers = ("OUTPUT", "TYPE", "RESULT")
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(3)
    ]

    def format_row(row: tuple[str, str, str]) -> str:
        padded = [cell.ljust(widths[i]) for i, cell in enumerate(row[:-1])]
        return "  ".join([*padded, row[-1]])

    print(format_row(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(format_row(row))


def run_list(directory: Path) -> int:
    records = load_output_directory(directory)
    if not records:
        print(f"No known output files found under {directory}")
        return 0

    rows: list[tuple[str, str, str]] = []
    exit_code = 0
    for record in records:
        short_path = _shorten_path(record.path, directory)
        if record.ok:
            rows.append((short_path, KIND_LABELS.get(record.kind, record.kind), record.summary))
        else:
            exit_code = 1
            rows.append((short_path, "unreadable", f"WARNING: {record.error}"))

    _print_table(rows)
    return exit_code


def run_show(file: Path, raw: bool) -> int:
    record = load_output_file(file)
    if not record.ok:
        print(f"WARNING: {record.error}", file=sys.stderr)
        return 1

    if raw:
        print(json.dumps(record.data, indent=2, sort_keys=True))
    else:
        print(format_report(record))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "list":
        return run_list(args.directory)
    return run_show(args.file, args.raw)


if __name__ == "__main__":
    raise SystemExit(main())
