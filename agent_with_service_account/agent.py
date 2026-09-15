"""
Agent 2: Direct GCP Service Account with Entra ID Federation.

Architecture:
1. Deployed to Vertex AI Agent Engine with a dedicated Service Account attached directly to the runtime (`spec.service_account = GCP_FEDERATION_SERVICE_ACCOUNT`).
2. The runtime's ambient Service Account credentials generate a signed GCP OIDC ID token directly.
3. Exchanges the GCP OIDC token with the Microsoft Entra Agent Identity Blueprint for an intermediate T1 token.
4. Uses the T1 token to request access tokens under the Entra Agent ID to query Microsoft Graph and Azure ARM APIs.
"""

import os
import requests
import google.auth
import google.auth.transport.requests
from google.adk.agents import Agent

# ==============================================================================
# Configuration Loaded from Environment Variables
# ==============================================================================
ATTACHED_SERVICE_ACCOUNT = os.environ.get("GCP_FEDERATION_SERVICE_ACCOUNT", "entra-federation-sa@your-gcp-project-id.iam.gserviceaccount.com")
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
AZURE_BLUEPRINT_ID = os.environ.get("AZURE_BLUEPRINT_ID", "11111111-1111-1111-1111-111111111111")
AZURE_AGENT_ID = os.environ.get("AZURE_AGENT_ID", "22222222-2222-2222-2222-222222222222")
AZURE_SUBSCRIPTION_ID = os.environ.get("AZURE_SUBSCRIPTION_ID", "33333333-3333-3333-3333-333333333333")

# ==============================================================================
# Token Federation & Exchange Logic
# ==============================================================================
def _get_entra_token(scope: str) -> str:
    """Generates a GCP OIDC ID Token using the agent's attached Service Account and exchanges it for an Entra Agent ID Access Token."""
    # 1. Obtain ambient credentials of the attached Service Account in Agent Engine
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    # 2. Generate a signed GCP OIDC ID Token for the attached Service Account
    oidc_url = f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{ATTACHED_SERVICE_ACCOUNT}:generateIdToken"
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json"
    }
    body = {
        "audience": "api://AzureADTokenExchange",
        "includeEmail": True
    }
    resp = requests.post(oidc_url, headers=headers, json=body)
    resp.raise_for_status()
    gcp_id_token = resp.json()["token"]

    # 3. Step 1: Exchange GCP OIDC token with the Entra Agent Blueprint for intermediate proof-of-authority token (T1)
    entra_token_url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
    t1_data = {
        "grant_type": "client_credentials",
        "client_id": AZURE_BLUEPRINT_ID,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": gcp_id_token,
        "scope": "api://AzureADTokenExchange/.default",
        "fmi_path": AZURE_AGENT_ID
    }
    t1_resp = requests.post(entra_token_url, data=t1_data)
    t1_resp.raise_for_status()
    t1_token = t1_resp.json()["access_token"]

    # 4. Step 2: Use T1 token to acquire the final resource access token under the Entra Agent ID
    agent_data = {
        "grant_type": "client_credentials",
        "client_id": AZURE_AGENT_ID,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": t1_token,
        "scope": scope
    }
    agent_resp = requests.post(entra_token_url, data=agent_data)
    agent_resp.raise_for_status()
    return agent_resp.json()["access_token"]

# ==============================================================================
# Agent Tools
# ==============================================================================
def query_microsoft_graph_users() -> str:
    """Tool: Authenticates as Entra Agent ID to query Microsoft Graph API and retrieve directory users."""
    try:
        token = _get_entra_token("https://graph.microsoft.com/.default")
        resp = requests.get(
            "https://graph.microsoft.com/v1.0/users?$top=5",
            headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        users = resp.json().get("value", [])
        if not users:
            return "Successfully queried Microsoft Graph API via Entra Agent ID, but no users were found."
        
        output = [f"Successfully queried Microsoft Graph API via Entra Agent ID (found {len(users)} users):"]
        for u in users:
            output.append(f"- DisplayName: {u.get('displayName')} | UPN: {u.get('userPrincipalName')} | Mail: {u.get('mail')}")
        return "\n".join(output)
    except Exception as e:
        return f"Error querying Microsoft Graph API: {e}"

def list_azure_resource_groups() -> str:
    """Tool: Authenticates as Entra Agent ID to query Azure Resource Manager and list resource groups."""
    try:
        token = _get_entra_token("https://management.azure.com/.default")
        url = f"https://management.azure.com/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourcegroups?api-version=2021-04-01"
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        groups = resp.json().get("value", [])
        if not groups:
            return f"Successfully queried Azure ARM via Entra Agent ID, but no resource groups were found in subscription {AZURE_SUBSCRIPTION_ID}."
        
        output = [f"Successfully queried Azure Resource Manager via Entra Agent ID (found {len(groups)} resource group(s)):"]
        for rg in groups:
            output.append(f"- Name: {rg.get('name')} | Location: {rg.get('location')} | State: {rg.get('properties', {}).get('provisioningState')}")
        return "\n".join(output)
    except Exception as e:
        return f"Error querying Azure Resource Manager: {e}"

# ==============================================================================
# Root Agent Definition with Gemini 3.7 Flash
# ==============================================================================
root_agent = Agent(
    name="EntraDirectSAClient",
    model="gemini-3.7-flash",
    description="Multi-cloud AI agent running under a custom GCP Service Account and Microsoft Entra Agent ID Blueprint Federation.",
    instruction=(
        "You are an enterprise AI assistant running on Google Cloud Vertex AI Agent Runtime with an attached Service Account. "
        "You authenticate to Microsoft Entra ID using your attached GCP Service Account federated through an Agent Blueprint and Entra Agent ID. "
        "When asked about Microsoft Graph users or Azure cloud resources, use your specialized tools to query Microsoft APIs and present the results clearly."
    ),
    tools=[query_microsoft_graph_users, list_azure_resource_groups]
)
