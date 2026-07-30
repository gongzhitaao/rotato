#!/usr/bin/env bash
# One-time shared infrastructure for rotato. Idempotent — safe to re-run
# (e.g. after changing the Dockerfile/scripts, to rebuild the image).
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
# shellcheck source=/dev/null
source "$HERE/config.env"

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

echo "== bws access token secret =="
gcloud secrets describe bws-access-token >/dev/null 2>&1 \
  || gcloud secrets create bws-access-token --replication-policy=automatic
read -rsp 'Paste rotato BWS_ACCESS_TOKEN (read+write machine account): ' BWS_TOKEN; echo
printf '%s' "$BWS_TOKEN" | gcloud secrets versions add bws-access-token --data-file=-
unset BWS_TOKEN

echo "== service accounts =="
gcloud iam service-accounts create rotato-job   --display-name="rotato job"       2>/dev/null || true
gcloud iam service-accounts create rotato-sched --display-name="rotato scheduler" 2>/dev/null || true
gcloud secrets add-iam-policy-binding bws-access-token \
  --member="serviceAccount:${JOB_SA}" --role="roles/secretmanager.secretAccessor"

echo
echo "setup complete. image: ${IMAGE_URI}"
echo "next: deploy/add-rotator.sh deploy/rotators/<name>.env"
