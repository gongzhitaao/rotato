#!/usr/bin/env bash
# Deploy (or update) one rotator: a Cloud Run job + a Cloud Scheduler trigger.
# Does NOT need BWS_ACCESS_TOKEN — the job reads it from Secret Manager.
# Usage: deploy/add-rotator.sh [env-file]   (default: deploy/rotato.env)
# Idempotent — re-run to change schedule/env or after rebuilding the image.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
ENVFILE="${1:-$HERE/rotato.env}"
[ -f "$ENVFILE" ] || { echo "no env file: ${ENVFILE} (copy rotato.env.example)" >&2; exit 1; }
# shellcheck source=/dev/null
source "$ENVFILE"
: "${PROJECT_ID:?}"; : "${REGION:?}"; : "${REPO:?}"; : "${IMAGE_NAME:?}"
: "${ROTATOR:?}"; : "${SCHEDULE:?}"; : "${TIME_ZONE:?}"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:latest"
JOB_SA="rotato-job@${PROJECT_ID}.iam.gserviceaccount.com"
SCHED_SA="rotato-sched@${PROJECT_ID}.iam.gserviceaccount.com"
JOB="rotato-${ROTATOR}"
TRIGGER="rotato-${ROTATOR}-trigger"

# Assemble --set-env-vars from ROTATOR plus each var named in ROTATOR_ENV.
ENV_PAIRS="ROTATOR=${ROTATOR}"
for k in "${ROTATOR_ENV[@]}"; do
  ENV_PAIRS="${ENV_PAIRS},${k}=${!k}"
done

echo "== cloud run job: ${JOB} =="
# max-retries=0: retrying a half-completed rotation authenticates with the
# already-revoked old token and cannot recover — it only hides the failure.
gcloud run jobs deploy "$JOB" --image="$IMAGE_URI" --region="$REGION" \
  --service-account="$JOB_SA" --max-retries=0 --task-timeout=120s \
  --args="${ROTATOR}" \
  --set-env-vars="${ENV_PAIRS}" \
  --set-secrets="BWS_ACCESS_TOKEN=bws-access-token:latest"

gcloud run jobs add-iam-policy-binding "$JOB" --region="$REGION" \
  --member="serviceAccount:${SCHED_SA}" --role="roles/run.invoker"

echo "== cloud scheduler: ${TRIGGER} =="
if gcloud scheduler jobs describe "$TRIGGER" --location="$REGION" >/dev/null 2>&1; then
  VERB=update
else
  VERB=create
fi
gcloud scheduler jobs "$VERB" http "$TRIGGER" --location="$REGION" \
  --schedule="$SCHEDULE" --time-zone="$TIME_ZONE" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run" \
  --http-method=POST --oauth-service-account-email="$SCHED_SA"

echo
echo "deployed ${JOB} on '${SCHEDULE}' (${TIME_ZONE})"
echo "test now: gcloud run jobs execute ${JOB} --region ${REGION} --wait"
