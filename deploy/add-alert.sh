#!/usr/bin/env bash
# Create (idempotently) the email alerts for the rotation job. No-op if
# ALERT_EMAIL is blank. Two policies, since a tag-driven job fails silently in
# ways a plain "job failed" alert can't see:
#   1. failed      - the Cloud Run job execution failed (a rotation errored).
#   2. STALE       - an enrolled secret's value is older than its cadence, i.e. a
#                    rotation has been silently failing (matches the job's
#                    "rotato-alert STALE" log line).
# Usage: deploy/add-alert.sh [env-file]   (default: deploy/rotato.env)
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
ENVFILE="${1:-$HERE/rotato.env}"
[ -f "$ENVFILE" ] || { echo "no env file: ${ENVFILE}" >&2; exit 1; }
# shellcheck source=/dev/null
source "$ENVFILE"
: "${PROJECT_ID:?}"

if [ -z "${ALERT_EMAIL:-}" ]; then
  echo "ALERT_EMAIL blank; skipping alert setup"
  exit 0
fi

gcloud config set project "$PROJECT_ID" >/dev/null

JOB="rotato-rotate"

echo "== notification channel =="
CHANNEL=$(gcloud beta monitoring channels list \
  --filter="type='email' AND labels.email_address='${ALERT_EMAIL}'" \
  --format="value(name)" 2>/dev/null | head -n1)
if [ -z "$CHANNEL" ]; then
  CHANNEL=$(gcloud beta monitoring channels create \
    --display-name="rotato alerts (${ALERT_EMAIL})" --type=email \
    --channel-labels="email_address=${ALERT_EMAIL}" \
    --format="value(name)")
  echo "  created channel: ${CHANNEL}"
else
  echo "  reusing channel: ${CHANNEL}"
fi

# Create a policy from a JSON body on stdin, skipping if one with the same
# displayName already exists.
create_policy() {
  local name="$1" body="$2"
  local existing
  existing=$(gcloud alpha monitoring policies list \
    --filter="displayName='${name}'" --format="value(name)" 2>/dev/null | head -n1)
  if [ -n "$existing" ]; then
    echo "  policy already exists: ${name} (skipping)"
    return 0
  fi
  local tmp
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' RETURN
  printf '%s' "$body" >"$tmp"
  gcloud alpha monitoring policies create --policy-from-file="$tmp"
  echo "  created policy: ${name}"
}

RUN_FILTER="resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB}\""

echo "== alert policy: ${JOB} failed =="
create_policy "rotato-rotate failed" "$(cat <<JSON
{
  "displayName": "rotato-rotate failed",
  "combiner": "OR",
  "conditions": [{
    "displayName": "${JOB} execution failed",
    "conditionThreshold": {
      "filter": "${RUN_FILTER} AND metric.type=\"run.googleapis.com/job/completed_execution_count\" AND metric.labels.result=\"failed\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "0s",
      "aggregations": [{ "alignmentPeriod": "3600s", "perSeriesAligner": "ALIGN_SUM" }],
      "trigger": { "count": 1 }
    }
  }],
  "notificationChannels": ["${CHANNEL}"],
  "alertStrategy": { "autoClose": "604800s" }
}
JSON
)"

echo "== alert policy: rotato stale secret =="
create_policy "rotato stale secret" "$(cat <<JSON
{
  "displayName": "rotato stale secret",
  "combiner": "OR",
  "conditions": [{
    "displayName": "a tagged secret is overdue for rotation",
    "conditionMatchedLog": {
      "filter": "${RUN_FILTER} AND textPayload:\"rotato-alert STALE\""
    }
  }],
  "notificationChannels": ["${CHANNEL}"],
  "alertStrategy": { "notificationRateLimit": { "period": "3600s" }, "autoClose": "604800s" }
}
JSON
)"
