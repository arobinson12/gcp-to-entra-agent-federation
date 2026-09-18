"""
Deploy Native GCP Agent Identity to Vertex AI Agent Engine.

This deploys the agent with a native GCP Agent Identity (SPIFFE ID).
No custom service account or impersonation is required.
"""

import os
import sys
import certifi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("GCP_STAGING_BUCKET")

if not PROJECT_ID or not STAGING_BUCKET:
    print("Error: Missing required environment variables (GCP_PROJECT_ID, GCP_STAGING_BUCKET). Please check your .env file.")
    sys.exit(1)

os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import vertexai
from vertexai.agent_engines import _agent_engines

vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent"))
os.chdir(agent_dir)
sys.path.insert(0, agent_dir)

from agent_engine_app import adk_app

print(f"Deploying Agent to Vertex AI Agent Engine with Native Agent Identity in {PROJECT_ID} ({LOCATION})...")

# Deploying without a service_account parameter assigns a native GCP Agent Identity (SPIFFE ID)
remote_agent = _agent_engines.AgentEngine.create(
    adk_app,
    requirements=[
        "google-cloud-aiplatform[adk,agent_engines]",
        "requests>=2.31.0",
        "google-auth>=2.30.0",
        "certifi>=2024.2.2",
        "python-dotenv>=1.0.0"
    ],
    extra_packages=["agent.py", "agent_engine_app.py"],
    display_name="native-spiffe-entra-agent",
    description="GCP Native Agent Identity (SPIFFE ID) federated directly with Microsoft Entra Agent ID (Gemini 3.7 Flash)"
)

print("\n Deployment Successful!")
print(f"Agent Engine Resource Name: {remote_agent.resource_name}")

# Extract reasoning engine ID
re_id = remote_agent.resource_name.split("/")[-1]
print(f"\nNext Steps:")
print(f"1. Run ./scripts/setup_agent_identity_iam.sh {re_id} to bind base Vertex AI permissions to the Agent Identity.")
print(f"2. Add the Agent's SPIFFE ID as a Federated Identity Credential (FIC) on your Microsoft Entra Agent Blueprint.")
