# Multi-Cloud Agent Federation: Google Cloud Vertex AI to Microsoft Entra Agent ID

This repository demonstrates how to federate autonomous AI agents running in **Google Cloud Vertex AI Agent Runtime (Agent Engine)** with **Microsoft Entra ID** to access Microsoft APIs (Microsoft Graph and Azure Resource Manager) using **Entra Agent ID** and **Federated Identity Credentials (FIC)** — with zero hardcoded credentials, zero stored secrets, and **no intermediate Service Accounts**.

The agent is powered by **Gemini 3.7 Flash** (`gemini-3.7-flash`).

---

## 🌟 What's New: Direct SPIFFE ID Token Federation (Native Agent Identity)

GCP Agent Identity supports issuing Google-signed OIDC JWTs directly from the agent's native **SPIFFE ID**. 

<img width="818" height="433" alt="Screenshot 2026-09-17 at 8 58 45 PM" src="https://github.com/user-attachments/assets/15b3e909-817b-4833-a91c-1000ae9a0313" />

### 1: Auth Manager brokering (User Token - Tc)
Auth Manager initiates a 3-Legged OAuth (3LO) flow and retrieves the User Access Token (Tc), injecting it into the ADK Agent’s execution context.

### 2: Interactive Login
The user completes the interactive Entra ID login in their browser to authorize the agent.

### 3: Agent Auth via WIF (Exchange Token - T1)
The ADK Agent uses its Agent Identity SPIFFE ID (SVID) as a Federated Identity Credential (FIC) to request the Agent Exchange Token (T1) from Entra ID.

### 4: OBO Exchange (Resource Token - TR)
The ADK Agent performs an On-Behalf-Of (OBO) exchange, presenting both T1 and Tc to Entra ID to obtain the final Resource Access Token (TR).

### 5: Policy & Permission Validation
Entra ID validates the OBO exchange against the configured Agent Blueprint and Child Agent ID app registrations to ensure proper delegated permissions.

### 6: Resource API Call
The ADK Agent calls the target resource (e.g., MS Graph) using TR. It mathematically hashes the User ID and Agent ID into a deterministic UUIDv5, injecting it into the client-request-id HTTP header.

### 7: Dual-Identity Audit Trail (Cross-Cloud Correlation)
The ADK Agent writes a custom audit log to Cloud Logging containing the agent, user, API endpoint, and the UUIDv5 hash. Simultaneously, Microsoft natively records the same UUIDv5 in the Entra Graph Activity Logs, creating a mathematically provable link between the GCP execution and the Azure resource access.


### Previous vs. Current Architecture

- **Previous (Legacy):** Required creating and maintaining a GCP Service Account, configuring Google Cloud IAM impersonation bindings, and configuring the Entra Agent Blueprint FIC with the Service Account's numeric OAuth Client ID.
- **Current (Native SPIFFE ID):** The Vertex AI Agent Engine runtime directly mints a Google-signed OIDC JWT whose `sub` claim is the agent's native SPIFFE ID (`spiffe://agents.global.org-...`). Microsoft Entra ID validates this JWT directly against an FIC configured with the SPIFFE ID as the subject. **No Service Account is required.**

> 💡 *Looking for the earlier Service Account-based patterns? They are preserved under the [`legacy/`](./legacy/) directory. See [Legacy Patterns](#-legacy-patterns-service-account-based) below.*

---

## 🏗️ Architecture & How It Works

```
┌───────────────────────────────────────────────┐
│       Google Cloud Vertex AI Agent            │
│         (Native Agent Identity)               │
└───────────────────────┬───────────────────────┘
                        │ 1. Mint GCP OIDC ID Token with SPIFFE ID Subject
                        │    (Audience: api://AzureADTokenExchange)
                        ▼
┌───────────────────────────────────────────────┐
│         Entra Agent Blueprint (FIC)           │
│   (FIC Subject: spiffe://agents.global.org...)│
└───────────────────────┬───────────────────────┘
                        │ 2. Exchange for Proof-of-Authority Token (T1) using fmi_path
                        ▼
┌───────────────────────────────────────────────┐
│                Entra Agent ID                 │
└───────────────────────┬───────────────────────┘
                        │ 3. Exchange T1 for target resource access token
                        ▼
┌───────────────────────────────────────────────┐
│          Microsoft Graph / Azure ARM          │
└───────────────────────────────────────────────┘
```

The authentication flow executes in three steps:

1. **Mint Native Agent Identity JWT:** The agent calls `id_token.fetch_id_token(...)` from the ambient runtime with audience `api://AzureADTokenExchange`. The minted JWT contains:
   - **`iss`**: `https://sts.googleapis.com/v1/organizations/{ORG_ID}/locations/global/workloadIdentityPools/agents.global.org-{ORG_ID}.system.id.goog`
   - **`sub`**: `spiffe://agents.global.org-{ORG_ID}.system.id.goog/resources/aiplatform/projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}`
2. **Exchange for Blueprint Authority Token (T1):** The agent presents its SPIFFE JWT to Microsoft Entra's OAuth2 token endpoint (`/oauth2/v2.0/token`) targeting the **Agent Blueprint** with `fmi_path` set to the target **Entra Agent ID**. Entra validates the FIC and returns an intermediate `T1` token.
3. **Acquire Resource Token:** The agent presents `T1` to acquire an access token scoped to Microsoft Graph (`https://graph.microsoft.com/.default`) or Azure Resource Manager (`https://management.azure.com/.default`).

---

## 🚀 Step-by-Step Setup Guide

### 1. Prerequisites & Environment Setup

Clone this repository and install dependencies:

```bash
git clone https://github.com/arobinson12/gcp-to-entra-agent-federation.git
cd gcp-to-entra-agent-federation

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create your configuration file from template
cp .env.example .env
```

Fill in `.env` with your environment values:
```bash
# GCP Configuration
GCP_PROJECT_ID="your-gcp-project-id"
GCP_LOCATION="us-central1"
GCP_STAGING_BUCKET="gs://your-staging-bucket-name"

# Microsoft Entra Configuration
AZURE_TENANT_ID="00000000-0000-0000-0000-000000000000"
AZURE_BLUEPRINT_ID="11111111-1111-1111-1111-111111111111"       # Agent Blueprint Application ID
AZURE_AGENT_ID="22222222-2222-2222-2222-222222222222"           # Entra Agent ID Object ID
AZURE_SUBSCRIPTION_ID="33333333-3333-3333-3333-333333333333"    # Azure Subscription ID
```

---

### 2. Deploy Agent to Vertex AI Agent Engine

Deploy the agent with native Agent Identity:

```bash
python scripts/deploy.py
```

Note the **Reasoning Engine ID** from the deployment output (e.g., `5851967570151735296`).

---

### 3. Configure GCP IAM & Obtain SPIFFE ID

Run the setup script with your Reasoning Engine ID:

```bash
./scripts/setup_agent_identity_iam.sh <REASONING_ENGINE_ID>
```

This script:
1. Binds `roles/aiplatform.user` and `roles/serviceusage.serviceUsageConsumer` to the agent's native runtime principal.
2. Displays the exact **Issuer** and **Subject (SPIFFE ID)** to configure in Microsoft Entra ID.

---

### 4. Configure Microsoft Entra ID Federated Identity Credential (FIC)

1. **Add Federated Identity Credential to your Agent Blueprint (`Microsoft.Graph.AgentIdentityBlueprint`):**
   - **Credential type:** `Other issuer`
   - **Issuer:** `https://sts.googleapis.com/v1/organizations/<ORG_ID>/locations/global/workloadIdentityPools/agents.global.org-<ORG_ID>.system.id.goog`
   - **Subject:** `spiffe://agents.global.org-<ORG_ID>.system.id.goog/resources/aiplatform/projects/<PROJECT_NUMBER>/locations/<LOCATION>/reasoningEngines/<REASONING_ENGINE_ID>`
   - **Audience:** `api://AzureADTokenExchange`
   - **Name:** `gcp-agent-<REASONING_ENGINE_ID>`
2. **Assign Permissions to the Child Entra Agent ID (`Microsoft.Graph.AgentIdentity`):**
   - **Microsoft Graph:** Assign Entra Directory Role `Directory Readers` (allows user and directory lookups).
   - **Azure Resource Manager:** Assign Azure RBAC role `Reader` on target subscriptions or resource groups.

---

### 5. Validate & Test

Test your deployed agent by invoking the test script:

```bash
python scripts/test_agent.py <REASONING_ENGINE_ID>
```

The agent will execute `query_microsoft_graph_users` and `list_azure_resource_groups` using the direct SPIFFE ID token federation flow and stream back live results from Microsoft Entra and Azure!

---

## 🗄️ Legacy Patterns (Service Account-Based)

For environments or architectures that still require using Google Cloud Service Accounts as the identity bridge, the previous patterns are preserved in the [`legacy/`](./legacy/) directory:

- **Legacy Option 1 ([`legacy/agent_with_agent_identity/`](./legacy/agent_with_agent_identity/)):** 
  The agent runs with native GCP Agent Identity and impersonates a designated GCP Service Account via the IAM Credentials API (`generateIdToken`) to authenticate with Entra ID.
  - Deploy script: [`scripts/legacy/deploy_agent_identity.py`](./scripts/legacy/deploy_agent_identity.py)
  - IAM script: [`scripts/legacy/setup_agent_identity_iam.sh`](./scripts/legacy/setup_agent_identity_iam.sh)
- **Legacy Option 2 ([`legacy/agent_with_service_account/`](./legacy/agent_with_service_account/)):** 
  A custom user-managed GCP Service Account is directly attached to the Agent Engine runtime (`spec.service_account`). The service account mints its own OIDC ID token directly.
  - Deploy script: [`scripts/legacy/deploy_service_account.py`](./scripts/legacy/deploy_service_account.py)
  - IAM script: [`scripts/legacy/setup_gcp_iam.sh`](./scripts/legacy/setup_gcp_iam.sh)

---

## 📂 Repository Structure

```
gcp-to-entra-agent-federation/
├── agent/                         # Native GCP Agent Identity (SPIFFE ID) pattern ⭐
│   ├── agent.py                   # ADK Agent definition with Gemini 3.7 Flash & direct SPIFFE JWT
│   └── agent_engine_app.py        # AdkApp wrapper
├── legacy/                        # Legacy Service Account-based federation patterns
│   ├── agent_with_agent_identity/ # Option 1: Agent Identity impersonating a Service Account
│   └── agent_with_service_account/# Option 2: Service Account attached directly to runtime
├── docs/
│   └── architecture.md            # Sequence diagrams and deep-dive technical details
├── scripts/
│   ├── deploy.py                  # Deploys native SPIFFE Agent to Vertex AI Agent Engine
│   ├── setup_agent_identity_iam.sh# Configures IAM and prints Entra FIC parameters
│   ├── test_agent.py              # Invokes and tests deployed agents
│   └── legacy/                    # Deployment scripts for legacy SA patterns
│       ├── deploy_agent_identity.py
│       ├── deploy_service_account.py
│       ├── setup_agent_identity_iam.sh
│       └── setup_gcp_iam.sh
├── .env.example                   # Environment configuration template
├── requirements.txt               # Python dependencies
└── README.md                      # Documentation and quickstart guide
```
