#!/usr/bin/env bash
# Run the rotato test suite. Installs bats globally via npm if it is missing.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")

if ! command -v bats >/dev/null 2>&1; then
  echo "bats not found — installing via 'npm install -g bats' ..."
  npm install -g bats
fi

command -v jq >/dev/null 2>&1 || { echo "these tests require jq on PATH" >&2; exit 1; }

exec bats "$HERE"
