#!/usr/bin/env bash
# Run the rotato test suite. Only test deps (pytest, httpx) are installed — not
# the Bitwarden SDK, which is imported lazily and mocked out in tests.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
ROOT="$HERE/.."

if command -v uv >/dev/null 2>&1; then
  # --no-project: don't build/install rotato (skips the Bitwarden SDK dep).
  PYTHONPATH="$ROOT" exec uv run --no-project --with pytest --with httpx \
    python -m pytest "$HERE" "$@"
fi

# Fallback: stdlib venv (needs the python3-venv package).
VENV="$ROOT/.venv"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" -q install --upgrade pip pytest httpx
PYTHONPATH="$ROOT" exec "$VENV/bin/python" -m pytest "$HERE" "$@"
