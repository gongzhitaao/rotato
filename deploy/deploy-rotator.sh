#!/usr/bin/env bash
# Deploy (or update) the single tag-driven rotation job: one Cloud Run job + one
# Cloud Scheduler trigger that, on each run, rotates EVERY secret whose note is
# tagged `#rotato=<type>` in the Bitwarden project. Adding a secret to rotation
# is then just tagging its note in Bitwarden -- no redeploy.
# Does NOT need BWS_ACCESS_TOKEN (the job reads it from Secret Manager).
# Usage: deploy/deploy-rotator.sh [env-file]   (default: deploy/rotato.env)
# Idempotent -- re-run to change schedule/env or after rebuilding the image.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
ENVFILE="${1:-$HERE/rotato.env}"
[ -f "$ENVFILE" ] || { echo "no env file: ${ENVFILE} (copy rotato.env.example)" >&2; exit 1; }
# shellcheck source=/dev/null
source "$ENVFILE"
: "${PROJECT_ID:?}"; : "${REGION:?}"; : "${REPO:?}"; : "${IMAGE_NAME:?}"
: "${SCHEDULE:?}"; : "${TIME_ZONE:?}"; : "${BWS_ORGANIZATION_ID:?}"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:latest"
JOB_SA="rotato-job@${PROJECT_ID}.iam.gserviceaccount.com"
SCHED_SA="rotato-sched@${PROJECT_ID}.iam.gserviceaccount.com"
JOB="rotato-rotate"
TRIGGER="rotato-rotate-trigger"

ENV_PAIRS="BWS_ORGANIZATION_ID=${BWS_ORGANIZATION_ID}"
ENV_PAIRS="${ENV_PAIRS},STALE_AFTER_DAYS=${STALE_AFTER_DAYS:-21}"

echo "== cloud run job: ${JOB} =="
# max-retries=0: retrying a half-completed rotation authenticates with the
# already-revoked old token and cannot recover -- it only hides the failure.
# Rotations run sequentially (~<=30s each), so task-timeout must scale with the
# number of enrolled secrets; raise it if a run risks exceeding 600s. A timeout
# mid-batch is safe -- already-rotated secrets are verified, the rest retry next
# run -- but marks the execution failed.
gcloud run jobs deploy "$JOB" --image="$IMAGE_URI" --region="$REGION" \
  --service-account="$JOB_SA" --max-retries=0 --task-timeout=600s \
  --args="refresh" \
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
