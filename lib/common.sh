#!/usr/bin/env bash
# Shared rotation framework for rotato.
#
# rotato_run <secret_id> <rotate_fn>
#   1. reads the current secret value from Bitwarden Secrets Manager
#   2. calls rotate_fn "<old value>" which must print the NEW value to stdout
#      (the rotate_fn does whatever provider-specific dance is needed and is
#      responsible for actually issuing/minting the new credential)
#   3. writes the new value back to Bitwarden
#   4. verifies the store really has it — otherwise the new credential lives
#      nowhere. On verify failure it prints the new value to stderr (-> Cloud
#      Logging) as a break-glass so you can recover, then re-rotate.
#
# Requires: bws, jq, curl on PATH; BWS_ACCESS_TOKEN in the environment.

rotato_run() {
  local secret_id="$1" rotate_fn="$2"
  local old new check

  old=$(bws secret get "$secret_id" | jq -r '.value')
  if [ -z "$old" ] || [ "$old" = "null" ]; then
    echo "ERROR: could not read current value for ${secret_id}" >&2
    return 1
  fi

  new=$("$rotate_fn" "$old") || { echo "ERROR: ${rotate_fn} failed" >&2; return 1; }
  if [ -z "$new" ] || [ "$new" = "null" ]; then
    echo "ERROR: ${rotate_fn} produced no new value" >&2
    return 1
  fi

  bws secret edit "$secret_id" --value "$new" >/dev/null

  check=$(bws secret get "$secret_id" | jq -r '.value')
  if [ "$check" != "$new" ]; then
    echo "CRITICAL: write-back verify FAILED for ${secret_id}." >&2
    echo "CRITICAL: recover this value then re-rotate NOW: ${new}" >&2
    return 1
  fi

  echo "OK: rotated ${secret_id}"
}
