#!/usr/bin/env bash
# End-to-end: shared setup + deploy the rotator from a single env file.
# Usage: deploy/run.sh [env-file]   (default: deploy/rotato.env)
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
ENVFILE="${1:-$HERE/rotato.env}"

"$HERE/setup.sh"        "$ENVFILE"
"$HERE/add-rotator.sh"  "$ENVFILE"
"$HERE/add-alert.sh"    "$ENVFILE"
