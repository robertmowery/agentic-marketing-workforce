#!/usr/bin/env bash
# Deploy the agent team to Cloud Run.
#
# Usage: deploy/deploy.sh [SERVICE_NAME] [SESSION_SERVICE_URI] [-- extra gcloud flags]
#
# The service is private: callers need an identity token and the run.invoker
# role. It runs as its own service account, which can call Gemini and write
# traces and nothing else.
#
# Needs GOOGLE_CLOUD_PROJECT (see .env.example). Region defaults to us-central1.
set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
REGION="${REGION:-us-central1}"
SERVICE="${1:-corvane-marketing-team}"
SESSIONS="${2:-memory://}"
shift $(( $# > 2 ? 2 : $# ))
[[ "${1:-}" == "--" ]] && shift
ACCOUNT="corvane-agent-runtime@${PROJECT}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$ACCOUNT" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create corvane-agent-runtime \
    --project "$PROJECT" --display-name "Corvane agent team runtime"
  sleep 15  # a new service account takes a moment to become visible to IAM
fi
# Granting a role the account already has changes nothing, so this is safe to repeat.
for role in roles/aiplatform.user roles/cloudtrace.agent roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT" --quiet --condition=None \
    --member "serviceAccount:${ACCOUNT}" --role "$role" >/dev/null
done

gcloud run deploy "$SERVICE" \
  --project "$PROJECT" --region "$REGION" --source . \
  --service-account "$ACCOUNT" \
  --no-allow-unauthenticated \
  --memory 1Gi --timeout 300 \
  --set-env-vars "GOOGLE_GENAI_USE_ENTERPRISE=TRUE,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=global,SESSION_SERVICE_URI=${SESSIONS},TRACE_TO_CLOUD=1" \
  "$@"

gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --format 'value(status.url)'
