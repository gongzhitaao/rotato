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
: "${BWS_ACCESS_TOKEN:?set BWS_ACCESS_TOKEN in ${ENVFILE} (bootstrap secret)}"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:latest"
JOB_SA="rotato-job@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"

echo "== enabling APIs =="
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

echo "== artifact registry =="
gcloud artifacts repositories create "$REPO" --repository-format=docker \
  --location="$REGION" --description="rotato images" 2>/dev/null || true

echo "== build & push image =="
gcloud builds submit "$HERE/.." --tag "$IMAGE_URI"

echo "== bws access token secret (bootstrap) =="
gcloud secrets describe bws-access-token >/dev/null 2>&1 \
  || gcloud secrets create bws-access-token --replication-policy=automatic
printf '%s' "$BWS_ACCESS_TOKEN" | gcloud secrets versions add bws-access-token --data-file=-

echo "== service accounts =="
gcloud iam service-accounts create rotato-job   --display-name="rotato job"       2>/dev/null || true
gcloud iam service-accounts create rotato-sched --display-name="rotato scheduler" 2>/dev/null || true
gcloud secrets add-iam-policy-binding bws-access-token \
  --member="serviceAccount:${JOB_SA}" --role="roles/secretmanager.secretAccessor"

echo
echo "setup complete. image: ${IMAGE_URI}"
echo "BWS_ACCESS_TOKEN is now in Secret Manager — you may blank it in ${ENVFILE}."
