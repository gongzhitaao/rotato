#!/usr/bin/env bats
#
# Unit tests for the rotato framework. Stubs for bws/curl live in test/bin and
# are put ahead of the real tools on PATH; jq is used for real.

setup() {
  ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  PATH="$BATS_TEST_DIRNAME/bin:$PATH"
  export PATH
  export BWS_STORE="$BATS_TEST_TMPDIR/store"
  # shellcheck source=/dev/null
  source "$ROOT/lib/common.sh"
}

# ---- rotato_run (framework) ------------------------------------------------

@test "rotato_run: happy path stores and verifies the new value" {
  printf 'OLDVAL' >"$BWS_STORE"
  _new() { echo "NEWVAL"; }
  run rotato_run "sid" _new
  [ "$status" -eq 0 ]
  [ "$(cat "$BWS_STORE")" = "NEWVAL" ]
  [[ "$output" == *"OK: rotated sid"* ]]
}

@test "rotato_run: fails when the current value cannot be read" {
  : >"$BWS_STORE"   # empty
  _new() { echo "NEWVAL"; }
  run rotato_run "sid" _new
  [ "$status" -ne 0 ]
  [[ "$output" == *"could not read current value"* ]]
}

@test "rotato_run: fails when rotate_fn errors" {
  printf 'OLDVAL' >"$BWS_STORE"
  _new() { return 1; }
  run rotato_run "sid" _new
  [ "$status" -ne 0 ]
  [[ "$output" == *"_new failed"* ]]
}

@test "rotato_run: fails when rotate_fn yields an empty value" {
  printf 'OLDVAL' >"$BWS_STORE"
  _new() { echo ""; }
  run rotato_run "sid" _new
  [ "$status" -ne 0 ]
  [[ "$output" == *"no new value"* ]]
}

@test "rotato_run: fails loudly (break-glass) when write-back does not persist" {
  printf 'OLDVAL' >"$BWS_STORE"
  export BWS_STUB_READONLY=1
  _new() { echo "NEWVAL"; }
  run rotato_run "sid" _new
  [ "$status" -ne 0 ]
  [[ "$output" == *"verify FAILED"* ]]
  [[ "$output" == *"NEWVAL"* ]]   # new value printed for manual recovery
}

# ---- gitlab-pat rotator ----------------------------------------------------

@test "gitlab-pat: rotate returns the token from the API response" {
  # shellcheck source=/dev/null
  source "$ROOT/rotators/gitlab-pat.sh"
  export CURL_STUB_MODE=ok
  run _gitlab_pat_rotate "OLDTOKEN"
  [ "$status" -eq 0 ]
  [ "$output" = "NEWTOKEN" ]
}

@test "gitlab-pat: rotate fails when the API call fails" {
  # shellcheck source=/dev/null
  source "$ROOT/rotators/gitlab-pat.sh"
  export CURL_STUB_MODE=fail
  run _gitlab_pat_rotate "OLDTOKEN"
  [ "$status" -ne 0 ]
}

@test "gitlab-pat: rotato_main rotates end to end with stubs" {
  # shellcheck source=/dev/null
  source "$ROOT/rotators/gitlab-pat.sh"
  printf 'OLDTOKEN' >"$BWS_STORE"
  export CURL_STUB_MODE=ok GITLAB_PAT_SECRET_ID=sid
  run rotato_main
  [ "$status" -eq 0 ]
  [ "$(cat "$BWS_STORE")" = "NEWTOKEN" ]
}

# ---- dispatcher ------------------------------------------------------------

@test "dispatcher: rejects an unknown rotator" {
  run "$ROOT/rotato.sh" definitely-not-a-rotator
  [ "$status" -ne 0 ]
  [[ "$output" == *"unknown rotator"* ]]
}
