#!/usr/bin/env bash
# ==============================================================================
# GCP IAM Setup Script for Entra ID Agent Federation
# ==============================================================================
set -euo pipefail

if [ -f .env ]; then
  source .env
else
  echo "Error: .env file not found. Copy .env.example to .env and populate your values."
  exit 1
fi

echo "Setting up GCP IAM for Service Account: ${GCP_FEDERATION_SERVICE_ACCOUNT} in Project: ${GCP_PROJECT_ID}..."

# 1. Create the Service Account if it does not already exist
gcloud iam service-accounts create "${GCP_FEDERATION_SERVICE_ACCOUNT%%@*}" \
    --project="${GCP_PROJECT_ID}" \
    --display-name="Entra ID Federation Service Account" || true

# 2. Grant project-level roles required by the agent runtime
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${GCP_FEDERATION_SERVICE_ACCOUNT}" \
    --role="roles/aiplatform.user" \
    --condition=None

gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${GCP_FEDERATION_SERVICE_ACCOUNT}" \
    --role="roles/serviceusage.serviceUsageConsumer" \
    --condition=None

# 3. Allow the Service Account to mint tokens for itself
gcloud iam service-accounts add-iam-policy-binding "${GCP_FEDERATION_SERVICE_ACCOUNT}" \
    --project="${GCP_PROJECT_ID}" \
    --member="serviceAccount:${GCP_FEDERATION_SERVICE_ACCOUNT}" \
    --role="roles/iam.serviceAccountOpenIdTokenCreator"

# 4. Grant Vertex AI Agent Engine Service Agent access to act as the SA (for Agent 2)
PROJECT_NUMBER=$(gcloud projects describe "${GCP_PROJECT_ID}" --format="value(projectNumber)")
AI_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

gcloud iam service-accounts add-iam-policy-binding "${GCP_FEDERATION_SERVICE_ACCOUNT}" \
    --project="${GCP_PROJECT_ID}" \
    --member="serviceAccount:${AI_SERVICE_AGENT}" \
    --role="roles/iam.serviceAccountUser" || true

echo " GCP IAM Setup Complete!"
echo "Service Account Unique ID:"
gcloud iam service-accounts describe "${GCP_FEDERATION_SERVICE_ACCOUNT}" --format="value(uniqueId)"
