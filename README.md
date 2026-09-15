# Multi-Cloud Agent Federation: Google Cloud Vertex AI & Microsoft Entra Agent ID

This repository provides production-ready implementations of **Google Cloud Agent Development Kit (ADK)** agents deployed to **Vertex AI Agent Engine** powered by **`gemini-3.7-flash`**, authenticated to **Microsoft Entra ID** using **Federated Identity Credentials (FIC)** and **Entra Agent IDs** (Agent Blueprints).

---

##  What is Included

Two sanitized, production-ready agent implementations:

1. **`agent_with_agent_identity/` (Agent 1):**
   - Deployed with a **native GCP Agent Identity** (`spec.identity_type = AGENT_IDENTITY`).
   - The ambient Agent Identity securely impersonates a designated GCP Service Account to mint OIDC tokens for Entra federation.
2. **`agent_with_service_account/` (Agent 2):**
   - Deployed with a **custom Service Account attached directly** to the Agent Engine runtime (`spec.service_account`).
   - The attached Service Account directly mints OIDC tokens for Entra federation.

Both agents perform a **2-step Entra Agent ID Token Exchange** (Blueprint $\to$ Intermediate Proof-of-Authority T1 Token $\to$ Entra Agent ID Access Token) to securely call **Microsoft Graph API** and **Azure Resource Manager (ARM)** without hardcoded secrets.

---

## 🚀 Quickstart & Setup

### 1. Clone & Configure Environment

```bash
git clone <YOUR_REPO_URL>
cd gcp-entra-agent-federation

# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create your environment file from template
cp .env.example .env
```

Edit `.env` and fill in your details:
```bash
GCP_PROJECT_ID="your-gcp-project-id"
GCP_LOCATION="us-central1"
GCP_STAGING_BUCKET="gs://your-staging-bucket-name"
GCP_FEDERATION_SERVICE_ACCOUNT="entra-federation-sa@your-gcp-project-id.iam.gserviceaccount.com"

AZURE_TENANT_ID="your-entra-tenant-id"
AZURE_BLUEPRINT_ID="your-agent-blueprint-app-id"
AZURE_AGENT_ID="your-entra-agent-id-object-id"
AZURE_SUBSCRIPTION_ID="your-azure-subscription-id"
```

---

### 2. Configure GCP IAM

Run the GCP IAM configuration script:
```bash
./scripts/setup_gcp_iam.sh
```
*Note down the **Service Account Unique Numeric ID** printed at the end of the script (e.g. `100639696541006854251`).*

---

### 3. Configure Microsoft Entra ID

1. **Create an Agent Identity Blueprint (`Microsoft.Graph.AgentIdentityBlueprint`):**
   - Add a Federated Identity Credential (FIC) on the Blueprint:
     - **Issuer:** `https://accounts.google.com`
     - **Subject:** `<GCP_SERVICE_ACCOUNT_UNIQUE_NUMERIC_ID>`
     - **Audience:** `api://AzureADTokenExchange`
2. **Create an Entra Agent ID (`Microsoft.Graph.AgentIdentity`):**
   - Link it to the Blueprint Application ID (`AZURE_BLUEPRINT_ID`).
   - Assign Entra Directory Role: **Directory Readers**.
   - Assign Azure Subscription Role: **Reader** on target subscription (`AZURE_SUBSCRIPTION_ID`).

---

### 4. Deploying the Agents

#### Option A: Deploy Agent 1 (Native GCP Agent Identity)

```bash
python scripts/deploy_agent_identity.py
```
After deployment completes, configure IAM permissions for the newly minted Agent Identity principal:
```bash
./scripts/setup_agent_identity_iam.sh <REASONING_ENGINE_ID>
```

#### Option B: Deploy Agent 2 (Attached GCP Service Account)

```bash
python scripts/deploy_service_account.py
```

---

### 5. Test Agent Execution

Invoke either agent using the test script:
```bash
python scripts/test_agent.py <REASONING_ENGINE_ID_OR_RESOURCE_NAME>
```

---

## 📐 Architecture & Details

For an in-depth sequence diagram and technical breakdown of the 2-step Entra Agent ID exchange, see [docs/architecture.md](docs/architecture.md).
