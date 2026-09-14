#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(dirname "$script_dir")"
python_command="${AES_PYTHON:-${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}}"
python_command="${python_command:-python3}"

if ! "$python_command" -c "import pychrono" >/dev/null 2>&1; then
    echo "PyChrono is unavailable to $python_command. Create and activate environment.yml first." >&2
    exit 1
fi

cd "$repo_dir"
exec "$python_command" -m unittest discover -s tests -v
