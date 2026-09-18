"""
Native GCP Agent Identity (SPIFFE ID) with Microsoft Entra Agent ID Federation.

Architecture:
1. Deployed to Vertex AI Agent Engine with native Agent Identity (identity_type = AGENT_IDENTITY).
2. The runtime's ambient GCP Agent Identity generates an OIDC ID token directly from its
   native SPIFFE ID identity without needing any intermediate Service Account or impersonation.
3. The minted JWT ID token contains:
   - sub: spiffe://agents.global.org-{ORG_ID}.system.id.goog/resources/aiplatform/projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}
   - iss: https://sts.googleapis.com/v1/organizations/{ORG_ID}/locations/global/workloadIdentityPools/agents.global.org-{ORG_ID}.system.id.goog
   - aud: api://AzureADTokenExchange
4. Exchanges this native Agent Identity JWT directly with Microsoft Entra ID Agent Identity Blueprint
   using a Federated Identity Credential (FIC) configured with the agent's SPIFFE ID as the Subject.
5. Uses the resulting T1 token to acquire the final resource access token under the child Entra Agent ID
   to query Microsoft Graph and Azure Resource Manager (ARM) APIs.
"""

import os
import requests
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.adk.agents import Agent

# ==============================================================================
# Configuration Loaded from Environment Variables
# ==============================================================================
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
AZURE_BLUEPRINT_ID = os.environ.get("AZURE_BLUEPRINT_ID", "11111111-1111-1111-1111-111111111111")
AZURE_AGENT_ID = os.environ.get("AZURE_AGENT_ID", "22222222-2222-2222-2222-222222222222")
AZURE_SUBSCRIPTION_ID = os.environ.get("AZURE_SUBSCRIPTION_ID", "33333333-3333-3333-3333-333333333333")

# ==============================================================================
# Direct SPIFFE ID Token Generation & Entra Federation
# ==============================================================================
def _get_agent_identity_jwt(audience: str = "api://AzureADTokenExchange") -> str:
    """Generates a signed OIDC JWT directly from the native GCP Agent Identity (SPIFFE ID).

    In Vertex AI Agent Engine, the ambient runtime identity provides an identity token
    with the agent's SPIFFE ID as the subject ('sub') claim.
    """
    auth_req = Request()
    # fetch_id_token acquires the Google-signed OIDC JWT for the target audience
    # directly from the runtime environment / metadata server
    return id_token.fetch_id_token(auth_req, audience)

def _get_entra_token(scope: str) -> str:
    """Exchanges native GCP Agent Identity JWT for an Entra Agent ID Access Token."""
    # 1. Obtain native GCP Agent Identity JWT directly (Audience: api://AzureADTokenExchange)
    gcp_spiffe_jwt = _get_agent_identity_jwt("api://AzureADTokenExchange")

    # 2. Step 1: Exchange GCP SPIFFE JWT with Entra Agent Blueprint for intermediate proof-of-authority token (T1)
    entra_token_url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
    t1_data = {
        "grant_type": "client_credentials",
        "client_id": AZURE_BLUEPRINT_ID,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": gcp_spiffe_jwt,
        "scope": "api://AzureADTokenExchange/.default",
        "fmi_path": AZURE_AGENT_ID
    }
    t1_resp = requests.post(entra_token_url, data=t1_data)
    t1_resp.raise_for_status()
    t1_token = t1_resp.json()["access_token"]

    # 3. Step 2: Use T1 token to acquire the final resource access token under the child Entra Agent ID
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
    """Tool: Authenticates as Entra Agent ID via native GCP SPIFFE ID federation to query Microsoft Graph API and retrieve directory users."""
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
    """Tool: Authenticates as Entra Agent ID via native GCP SPIFFE ID federation to query Azure Resource Manager and list resource groups."""
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
    name="NativeEntraAgentIdentityClient",
    model="gemini-3.7-flash",
    description="Multi-cloud AI agent utilizing direct GCP Native Agent Identity (SPIFFE ID) and Microsoft Entra Agent ID Blueprint Federation.",
    instruction=(
        "You are an enterprise AI assistant running on Google Cloud Vertex AI Agent Runtime. "
        "You authenticate directly to Microsoft Entra ID using your native GCP Agent Identity SPIFFE ID federated through an Agent Blueprint and Entra Agent ID. "
        "When asked about Microsoft Graph users or Azure cloud resources, use your specialized tools to query Microsoft APIs and present the results clearly."
    ),
    tools=[query_microsoft_graph_users, list_azure_resource_groups]
)
