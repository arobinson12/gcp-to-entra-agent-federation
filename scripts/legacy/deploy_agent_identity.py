"""
Deploy Agent 1: Uses Native GCP Agent Identity on Vertex AI Agent Engine.

Prerequisites:
- Set environment variables in .env or your shell.
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
TARGET_SA = os.environ.get("GCP_FEDERATION_SERVICE_ACCOUNT")

if not PROJECT_ID or not STAGING_BUCKET or not TARGET_SA:
    print("Error: Missing required environment variables. Please check your .env file.")
    sys.exit(1)

os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import vertexai
from vertexai.agent_engines import _agent_engines

vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent_with_agent_identity"))
os.chdir(agent_dir)
sys.path.insert(0, agent_dir)

from agent_engine_app import adk_app

print(f"Deploying Agent 1 to Vertex AI Agent Engine (Native Agent Identity) in {PROJECT_ID}...")

# Note: Omitting service_account assigns a native GCP Agent Identity to the Reasoning Engine
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
    display_name="entra-agent-identity-client",
    description="GCP Native Agent Identity federated with Microsoft Entra Agent ID (Gemini 3.7 Flash)"
)

print("\n Deployment Successful!")
print(f"Agent Engine Resource Name: {remote_agent.resource_name}")
print("\nPost-Deployment Step:")
print("Run scripts/setup_agent_identity_iam.sh to grant required GCP IAM roles to the generated Agent Identity.")
