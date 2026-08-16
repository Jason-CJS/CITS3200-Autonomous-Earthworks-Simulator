#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(dirname "$script_dir")"
work_dir="$(dirname "$repo_dir")"

chrono_lib="$work_dir/chrono-install-graphics/lib"
irrlicht_lib="$work_dir/irrlicht-1.8.5/lib/Linux"
glut_lib="$work_dir/glut-runtime/usr/lib/x86_64-linux-gnu"

if [[ "${1:-}" == "excavator" ]]; then
    shift
fi

case "$#" in
    0) demo_args=() ;;
    1)
        if [[ "$1" != "--calibrate" ]]; then
            echo "Usage: $0 [excavator] [--capture OUTPUT.png | --calibrate | --capture-calibration OUTPUT.png]" >&2
            exit 2
        fi
        demo_args=("$1")
        ;;
    2)
        if [[ "$1" != "--capture" && "$1" != "--capture-calibration" ]]; then
            echo "Usage: $0 [excavator] [--capture OUTPUT.png | --calibrate | --capture-calibration OUTPUT.png]" >&2
            exit 2
        fi
        demo_args=("$1" "$2")
        ;;
    *)
        echo "Usage: $0 [excavator] [--capture OUTPUT.png | --calibrate | --capture-calibration OUTPUT.png]" >&2
        exit 2
        ;;
esac

demo="$repo_dir/build-graphics/excavator_demo"
if [[ ! -x "$demo" ]]; then
    echo "The graphics demo is not built yet: $demo" >&2
    echo "Build the graphics target before running this script." >&2
    exit 1
fi

export LD_LIBRARY_PATH="$chrono_lib:$irrlicht_lib:$glut_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$demo" "${demo_args[@]}"
