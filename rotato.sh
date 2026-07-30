#!/usr/bin/env bash
# rotato entrypoint / dispatcher.
# Usage: rotato.sh <rotator-name>   (or set ROTATOR in the environment)
# Runs rotators/<name>.sh, which must define a rotato_main function.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib/common.sh
source "$HERE/lib/common.sh"

name="${1:-${ROTATOR:-}}"
[ -n "$name" ] || { echo "usage: rotato.sh <rotator-name>  (or set ROTATOR)" >&2; exit 1; }

script="$HERE/rotators/${name}.sh"
[ -f "$script" ] || { echo "unknown rotator: ${name}" >&2; exit 1; }
# shellcheck source=/dev/null
source "$script"

command -v rotato_main >/dev/null || { echo "rotator ${name} defines no rotato_main" >&2; exit 1; }
rotato_main
