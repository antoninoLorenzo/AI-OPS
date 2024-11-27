"""
Initializes all the necessary dependencies for the API.
"""
from src.config import AGENT_SETTINGS
from src.agent import Agent, build_agent


agent: Agent = build_agent(
    model=AGENT_SETTINGS.MODEL,
    inference_endpoint=AGENT_SETTINGS.ENDPOINT,
    provider=AGENT_SETTINGS.PROVIDER,
    provider_key=AGENT_SETTINGS.PROVIDER_KEY
)


def get_agent():
    """Expose agent for Dependency Injection"""
    return agent

