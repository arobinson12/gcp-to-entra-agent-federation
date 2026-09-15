"""
Interactive test script to invoke a deployed Vertex AI Agent Engine.

Usage:
    python scripts/test_agent.py <REASONING_ENGINE_RESOURCE_NAME_OR_ID>
"""

import os
import sys
import certifi
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

if len(sys.argv) < 2:
    print("Usage: python scripts/test_agent.py <REASONING_ENGINE_RESOURCE_NAME_OR_ID>")
    print("Example: python scripts/test_agent.py 5851967570151735296")
    sys.exit(1)

agent_id = sys.argv[1]
if not agent_id.startswith("projects/"):
    resource_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{agent_id}"
else:
    resource_name = agent_id

os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import vertexai
from vertexai.agent_engines import _agent_engines

vertexai.init(project=PROJECT_ID, location=LOCATION)

print(f"Connecting to Agent Engine: {resource_name}...")
remote_agent = _agent_engines.AgentEngine(resource_name)

prompt = "Please query Microsoft Graph users and list Azure resource groups using your tools."
print(f"\nSending Prompt: '{prompt}'\n")

for event in remote_agent.stream_query(
    message=prompt,
    user_id="customer-test-user@example.com"
):
    if "content" in event:
        parts = event["content"].get("parts", [])
        for part in parts:
            if "text" in part:
                print(part["text"], end="", flush=True)
            elif "function_call" in part:
                print(f"\n[Tool Call] -> {part['function_call']['name']}({part['function_call'].get('args', {})})")
            elif "function_response" in part:
                print(f"[Tool Response] -> {part['function_response']['response']}\n")
print("\n\nFinished stream.")
