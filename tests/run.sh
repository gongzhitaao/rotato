#!/usr/bin/env bash
# Run the rotato test suite (pytest) in the uv-managed environment.
# Equivalent to: uv run pytest
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
command -v uv >/dev/null || { echo "uv is required — https://docs.astral.sh/uv/" >&2; exit 1; }

exec uv run --project "$HERE/.." pytest "$HERE" "$@"
