#!/usr/bin/env bash
# Create (idempotently) an email alert that fires when a rotator's Cloud Run job
# records a failed execution. No-op if ALERT_EMAIL is blank.
# Usage: deploy/add-alert.sh [env-file]   (default: deploy/rotato.env)
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
ENVFILE="${1:-$HERE/rotato.env}"
[ -f "$ENVFILE" ] || { echo "no env file: ${ENVFILE}" >&2; exit 1; }
# shellcheck source=/dev/null
source "$ENVFILE"
: "${PROJECT_ID:?}"; : "${ROTATOR:?}"

if [ -z "${ALERT_EMAIL:-}" ]; then
  echo "ALERT_EMAIL blank; skipping alert setup"
  exit 0
fi

gcloud config set project "$PROJECT_ID" >/dev/null

JOB="rotato-${ROTATOR}"
POLICY_NAME="rotato-${ROTATOR} failed"

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

echo "== alert policy =="
EXISTING=$(gcloud alpha monitoring policies list \
  --filter="displayName='${POLICY_NAME}'" \
  --format="value(name)" 2>/dev/null | head -n1)
if [ -n "$EXISTING" ]; then
  echo "  policy already exists: ${EXISTING} (skipping)"
  exit 0
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
cat >"$TMP" <<JSON
{
  "displayName": "${POLICY_NAME}",
  "combiner": "OR",
  "conditions": [{
    "displayName": "${JOB} execution failed",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB}\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\" AND metric.labels.result=\"failed\"",
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

gcloud alpha monitoring policies create --policy-from-file="$TMP"
echo "  created policy: ${POLICY_NAME}"
