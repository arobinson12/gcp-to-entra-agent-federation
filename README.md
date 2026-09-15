# Multi-Cloud Agent Federation: Google Cloud Vertex AI to Microsoft Entra Agent ID

This repository demonstrates how to federate autonomous AI agents running in **Google Cloud Vertex AI Agent Runtime (Agent Engine)** with **Microsoft Entra ID** to access Microsoft APIs (Microsoft Graph and Azure Resource Manager) using **Entra Agent ID** and **Federated Identity Credentials (FIC)** — with zero hardcoded credentials or API keys.

Both agents use **Gemini 3.7 Flash** (`gemini-3.7-flash`).

---

## 🏗️ Architecture & How It Works

The solution uses a **2-step token exchange** flow:

```
┌───────────────────────────────┐
│ Google Cloud Vertex AI Agent  │
│ (Agent Identity or Custom SA) │
└──────────────┬────────────────┘
               │ 1. Mint Google OIDC ID Token (Audience: api://AzureADTokenExchange)
               ▼
┌───────────────────────────────┐
│  Entra Agent Blueprint (FIC)  │
└──────────────┬────────────────┘
               │ 2. Exchange for Proof-of-Authority Token (T1) using fmi_path
               ▼
┌───────────────────────────────┐
│        Entra Agent ID         │
└──────────────┬────────────────┘
               │ 3. Exchange T1 for target resource access token
               ▼
┌───────────────────────────────┐
│ Microsoft Graph / Azure ARM   │
└───────────────────────────────┘
```

### Two Agent Patterns

1. **Agent 1 (`agent_with_agent_identity/`) — Native GCP Agent Identity**
   - Deployed with native GCP Agent Identity (`spec.identity_type = AGENT_IDENTITY`).
   - The ambient Agent Identity calls the GCP IAM Credentials API to mint an OIDC token for a designated Federation Service Account, which then authenticates to Entra Agent ID.
2. **Agent 2 (`agent_with_service_account/`) — Attached Custom Service Account**
   - Deployed with a user-managed GCP Service Account attached directly to the Agent Engine runtime (`spec.service_account`).
   - The attached Service Account mints its own OIDC token directly to authenticate to Entra Agent ID.

---

## 🚀 Step-by-Step Setup Guide

### 1. Prerequisites & Environment Setup

Clone this repository and install the dependencies:

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
GCP_FEDERATION_SERVICE_ACCOUNT="entra-federation-sa@your-gcp-project-id.iam.gserviceaccount.com"

# Microsoft Entra Configuration
AZURE_TENANT_ID="00000000-0000-0000-0000-000000000000"
AZURE_BLUEPRINT_ID="11111111-1111-1111-1111-111111111111"       # Agent Blueprint Application ID
AZURE_AGENT_ID="22222222-2222-2222-2222-222222222222"           # Entra Agent ID Object ID
AZURE_SUBSCRIPTION_ID="33333333-3333-3333-3333-333333333333"    # Azure Subscription ID
```

---

### 2. Configure GCP IAM

Run the GCP setup script to create the Federation Service Account and assign base permissions:

```bash
./scripts/setup_gcp_iam.sh
```

> **Important:** Save the **Service Account Unique Numeric ID** printed at the end of the script (e.g., `100639696541006854251`). You will need this for the Azure FIC configuration.

---

### 3. Configure Microsoft Entra ID

1. **Create an Agent Identity Blueprint (`Microsoft.Graph.AgentIdentityBlueprint`):**
   - Create a Federated Identity Credential (FIC) on the Blueprint with:
     - **Issuer:** `https://accounts.google.com`
     - **Subject:** `<GCP_SERVICE_ACCOUNT_UNIQUE_NUMERIC_ID>`
     - **Audience:** `api://AzureADTokenExchange`
2. **Create an Entra Agent ID (`Microsoft.Graph.AgentIdentity`):**
   - Link it to the Blueprint Application ID (`AZURE_BLUEPRINT_ID`).
   - Assign Entra Directory Role: **Directory Readers** (for Microsoft Graph user lookups).
   - Assign Azure Subscription Role: **Reader** on target subscription (`AZURE_SUBSCRIPTION_ID`).

---

### 4. Deploy the Agents to Vertex AI Agent Engine

#### Option A: Deploy Agent 1 (Native Agent Identity)

```bash
python scripts/deploy_agent_identity.py
```
Once deployed, run the post-deployment script to grant IAM roles to the generated Agent Identity:
```bash
./scripts/setup_agent_identity_iam.sh <REASONING_ENGINE_ID>
```

#### Option B: Deploy Agent 2 (Attached Service Account)

```bash
python scripts/deploy_service_account.py
```

---

### 5. Validate & Test

Test your deployed agent by invoking the test script:

```bash
python scripts/test_agent.py <REASONING_ENGINE_ID_OR_RESOURCE_NAME>
```

The agent will execute `query_microsoft_graph_users` and `list_azure_resource_groups` using the 2-step Entra Agent ID token exchange and stream back the live results.

---

## 📂 Repository Structure

```
gcp-to-entra-agent-federation/
├── agent_with_agent_identity/    # Agent 1: Native GCP Agent Identity pattern
│   ├── agent.py                  # ADK Agent definition with Gemini 3.7 Flash & Entra tools
│   └── agent_engine_app.py       # AdkApp wrapper
├── agent_with_service_account/   # Agent 2: Custom Service Account pattern
│   ├── agent.py                  # ADK Agent definition with Gemini 3.7 Flash & Entra tools
│   └── agent_engine_app.py       # AdkApp wrapper
├── docs/
│   └── architecture.md           # Sequence diagram and deep-dive technical details
├── scripts/
│   ├── deploy_agent_identity.py  # Deploys Agent 1 to Vertex AI Agent Engine
│   ├── deploy_service_account.py # Deploys Agent 2 to Vertex AI Agent Engine
│   ├── setup_gcp_iam.sh          # Sets up GCP Service Account and IAM bindings
│   ├── setup_agent_identity_iam.sh # Configures post-deployment IAM for Agent 1
│   └── test_agent.py             # Invokes and tests deployed agents
├── .env.example                  # Environment configuration template
├── requirements.txt              # Python dependencies
└── README.md                     # Setup and architecture documentation
```
