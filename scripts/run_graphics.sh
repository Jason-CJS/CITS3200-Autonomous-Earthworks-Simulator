#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(dirname "$script_dir")"
python_command="${AES_PYTHON:-${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}}"
python_command="${python_command:-python3}"

vehicle="excavator"
if [[ "$#" -gt 0 && ("$1" == "excavator" || "$1" == "bulldozer") ]]; then
    vehicle="$1"
    shift
fi

case "$#" in
    0) demo_args=() ;;
    1)
        if [[ "$1" != "--calibrate" ]]; then
            echo "Usage: $0 [excavator|bulldozer] [capture option]" >&2
            exit 2
        fi
        if [[ "$vehicle" == "bulldozer" ]]; then
            echo "Bulldozer does not have a calibration mode; use --capture OUTPUT.png." >&2
            exit 2
        fi
        demo_args=("$1")
        ;;
    2)
        if [[ "$vehicle" == "bulldozer" ]]; then
            case "$1" in
                --capture|--capture-front|--capture-side|--capture-opposite) ;;
                *)
                    echo "Bulldozer captures: --capture-front, --capture-side, or --capture-opposite OUTPUT.png." >&2
                    exit 2
                    ;;
            esac
        elif [[ "$1" != "--capture" && "$1" != "--capture-calibration" ]]; then
            echo "Excavator captures: --capture or --capture-calibration OUTPUT.png." >&2
            exit 2
        fi
        demo_args=("$1" "$2")
        ;;
    *)
        echo "Usage: $0 [excavator|bulldozer] [capture option]" >&2
        exit 2
        ;;
esac

if ! "$python_command" -c "import pychrono, pychrono.irrlicht, pychrono.vehicle" >/dev/null 2>&1; then
    echo "PyChrono is unavailable to $python_command. Create and activate environment.yml first." >&2
    exit 1
fi

cd "$repo_dir"
exec "$python_command" -m "src.${vehicle}_main" "${demo_args[@]}"
