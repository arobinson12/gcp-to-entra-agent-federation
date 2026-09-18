#!/usr/bin/env bash
# ==============================================================================
# Post-Deployment IAM Setup for Agent 1 (Native GCP Agent Identity)
# ==============================================================================
set -euo pipefail

if [ -f .env ]; then
  source .env
else
  echo "Error: .env file not found. Copy .env.example to .env and populate your values."
  exit 1
fi

if [ $# -lt 1 ]; then
  echo "Usage: ./scripts/setup_agent_identity_iam.sh <REASONING_ENGINE_ID>"
  echo "Example: ./scripts/setup_agent_identity_iam.sh 5851967570151735296"
  exit 1
fi

RE_ID="$1"
PROJECT_NUMBER=$(gcloud projects describe "${GCP_PROJECT_ID}" --format="value(projectNumber)")
ORG_ID=$(gcloud projects describe "${GCP_PROJECT_ID}" --format="value(parent.id)")

# Determine native agent identity principal URI
AGENT_IDENTITY_PRINCIPAL="principal://agents.global.org-${ORG_ID}.system.id.goog/resources/aiplatform/projects/${PROJECT_NUMBER}/locations/${GCP_LOCATION}/reasoningEngines/${RE_ID}"

echo "Configuring IAM for Native Agent Identity:"
echo "${AGENT_IDENTITY_PRINCIPAL}"

# 1. Project level roles
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="${AGENT_IDENTITY_PRINCIPAL}" \
    --role="roles/aiplatform.user" \
    --condition=None

gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="${AGENT_IDENTITY_PRINCIPAL}" \
    --role="roles/serviceusage.serviceUsageConsumer" \
    --condition=None

# 2. Grant impersonation / token minting on the Federation Service Account
gcloud iam service-accounts add-iam-policy-binding "${GCP_FEDERATION_SERVICE_ACCOUNT}" \
    --project="${GCP_PROJECT_ID}" \
    --member="${AGENT_IDENTITY_PRINCIPAL}" \
    --role="roles/iam.serviceAccountOpenIdTokenCreator"

gcloud iam service-accounts add-iam-policy-binding "${GCP_FEDERATION_SERVICE_ACCOUNT}" \
    --project="${GCP_PROJECT_ID}" \
    --member="${AGENT_IDENTITY_PRINCIPAL}" \
    --role="roles/iam.serviceAccountTokenCreator"

echo " Native Agent Identity IAM permissions successfully configured!"
