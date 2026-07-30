#!/usr/bin/env bash
# One-time shared infrastructure for rotato. Idempotent — safe to re-run
# (e.g. after editing the Dockerfile/scripts, to rebuild the image).
# Usage: deploy/setup.sh [env-file]   (default: deploy/rotato.env)
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
ENVFILE="${1:-$HERE/rotato.env}"
[ -f "$ENVFILE" ] || { echo "no env file: ${ENVFILE} (copy rotato.env.example)" >&2; exit 1; }
# shellcheck source=/dev/null
source "$ENVFILE"
: "${PROJECT_ID:?}"; : "${REGION:?}"; : "${REPO:?}"; : "${IMAGE_NAME:?}"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:latest"
JOB_SA="rotato-job@${PROJECT_ID}.iam.gserviceaccount.com"
SCHED_SA="rotato-sched@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"

echo "== enabling APIs =="
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  monitoring.googleapis.com

echo "== artifact registry =="
gcloud artifacts repositories create "$REPO" --repository-format=docker \
  --location="$REGION" --description="rotato images" 2>/dev/null || true

echo "== build & push image =="
gcloud builds submit "$HERE/.." --tag "$IMAGE_URI"

echo "== bws access token secret (bootstrap) =="
gcloud secrets describe bws-access-token >/dev/null 2>&1 \
  || gcloud secrets create bws-access-token --replication-policy=automatic
if [ -n "${BWS_ACCESS_TOKEN:-}" ]; then
  # add a new version only if the value actually changed — keeps re-runs from
  # piling up identical secret versions.
  CUR=$(gcloud secrets versions access latest --secret=bws-access-token 2>/dev/null || true)
  if [ "$CUR" != "$BWS_ACCESS_TOKEN" ]; then
    printf '%s' "$BWS_ACCESS_TOKEN" | gcloud secrets versions add bws-access-token --data-file=-
    echo "  uploaded a new bws-access-token version"
  else
    echo "  bws-access-token unchanged; nothing to upload"
  fi
else
  gcloud secrets versions access latest --secret=bws-access-token >/dev/null 2>&1 \
    || { echo "ERROR: BWS_ACCESS_TOKEN is blank and no version exists yet" >&2; exit 1; }
  echo "  BWS_ACCESS_TOKEN blank; keeping existing Secret Manager version"
fi

echo "== service accounts =="
gcloud iam service-accounts create rotato-job   --display-name="rotato job"       2>/dev/null || true
gcloud iam service-accounts create rotato-sched --display-name="rotato scheduler" 2>/dev/null || true

# IAM service-account creation is eventually consistent — wait until each SA is
# visible before referencing it in a binding (avoids "does not exist", including
# when run.sh proceeds straight into add-rotator.sh).
for sa in "$JOB_SA" "$SCHED_SA"; do
  for _ in $(seq 1 15); do
    gcloud iam service-accounts describe "$sa" >/dev/null 2>&1 && break
    echo "  waiting for ${sa} to propagate..."
    sleep 2
  done
done

gcloud secrets add-iam-policy-binding bws-access-token \
  --member="serviceAccount:${JOB_SA}" --role="roles/secretmanager.secretAccessor"

echo
echo "setup complete. image: ${IMAGE_URI}"
echo "BWS_ACCESS_TOKEN is now in Secret Manager — you may blank it in ${ENVFILE}."
