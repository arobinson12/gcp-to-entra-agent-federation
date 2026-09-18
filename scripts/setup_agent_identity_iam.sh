#!/usr/bin/env bash
# ==============================================================================
# Setup IAM and Output SPIFFE ID for Native GCP Agent Identity
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

# Determine native agent identity principal URI and SPIFFE ID
AGENT_IDENTITY_PRINCIPAL="principal://agents.global.org-${ORG_ID}.system.id.goog/resources/aiplatform/projects/${PROJECT_NUMBER}/locations/${GCP_LOCATION}/reasoningEngines/${RE_ID}"
AGENT_SPIFFE_ID="spiffe://agents.global.org-${ORG_ID}.system.id.goog/resources/aiplatform/projects/${PROJECT_NUMBER}/locations/${GCP_LOCATION}/reasoningEngines/${RE_ID}"
STS_ISSUER="https://sts.googleapis.com/v1/organizations/${ORG_ID}/locations/global/workloadIdentityPools/agents.global.org-${ORG_ID}.system.id.goog"

echo "=============================================================================="
echo "Configuring GCP IAM for Native Agent Identity:"
echo "${AGENT_IDENTITY_PRINCIPAL}"
echo "=============================================================================="

# Project level roles for Agent Runtime execution
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="${AGENT_IDENTITY_PRINCIPAL}" \
    --role="roles/aiplatform.user" \
    --condition=None

gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="${AGENT_IDENTITY_PRINCIPAL}" \
    --role="roles/serviceusage.serviceUsageConsumer" \
    --condition=None

echo ""
echo " Native Agent Identity IAM permissions successfully configured!"
echo ""
echo "=============================================================================="
echo " Microsoft Entra ID - Federated Identity Credential (FIC) Settings"
echo "=============================================================================="
echo "Configure the Federated Identity Credential on your Entra Agent Blueprint with:"
echo ""
echo "  Credential type: Other issuer"
echo "  Issuer:          ${STS_ISSUER}"
echo "  Subject:         ${AGENT_SPIFFE_ID}"
echo "  Audience:        api://AzureADTokenExchange"
echo "  Name:            gcp-agent-${RE_ID}"
echo "=============================================================================="
