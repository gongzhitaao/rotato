#!/usr/bin/env bash
# Rotator: GitLab personal access token (self-rotation).
#
# Env:
#   GITLAB_PAT_SECRET_ID  (required) UUID of the BWS secret holding the PAT
#   GITLAB_HOST           (optional) default https://gitlab.com
#   EXPIRY_DAYS           (optional) new token lifetime, default 30
#
# The PAT must carry `api` scope (or `self_rotate` on GitLab >= 17.7),
# otherwise the self-rotate endpoint returns 403.

_gitlab_pat_rotate() {
  local old="$1" expires_at resp new
  expires_at=$(date -u -d "+${EXPIRY_DAYS:-30} days" +%F)
  resp=$(curl -sS --fail-with-body --request POST \
    --header "PRIVATE-TOKEN: ${old}" \
    --url "${GITLAB_HOST:-https://gitlab.com}/api/v4/personal_access_tokens/self/rotate" \
    --data "expires_at=${expires_at}") \
    || { echo "gitlab rotate call failed: ${resp}" >&2; return 1; }
  echo "$resp" | jq -r '.token'
}

rotato_main() {
  : "${GITLAB_PAT_SECRET_ID:?GITLAB_PAT_SECRET_ID is required}"
  rotato_run "$GITLAB_PAT_SECRET_ID" _gitlab_pat_rotate
}
