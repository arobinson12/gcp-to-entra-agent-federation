"""ADK Application wrapper for Vertex AI Agent Engine deployment."""

from google.adk.apps import AdkApp
from agent import root_agent

adk_app = AdkApp(agent=root_agent)
