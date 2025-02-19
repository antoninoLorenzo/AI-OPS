"""Core component of the system"""
from src.core import (
    LLM,
    AVAILABLE_PROVIDERS,
    TOOL_REGISTRY,
)
from src.agent.agent import Agent, Architecture
from src.agent.architectures import init_default_architecture


init = {
    'default': init_default_architecture
}


def build_agent(
    model: str,
    inference_endpoint: str,
    architecture_name: str = 'default',
    provider: str = 'ollama',
    provider_key: str = ''
) -> Agent:
    if provider not in AVAILABLE_PROVIDERS.keys():
        raise RuntimeError(f'{provider} not supported.')
    llm_provider = AVAILABLE_PROVIDERS[provider]['class']
    key_required = AVAILABLE_PROVIDERS[provider]['key_required']

    if key_required and len(provider_key) == 0:
        raise RuntimeError(
            f'Missing PROVIDER_KEY environment variable for {provider}.'
        )

    llm = LLM(
        model=model,
        inference_endpoint=inference_endpoint,
        provider=llm_provider,
        api_key=provider_key
    )
    architecture = init[architecture_name](
        llm=llm,
        tool_registry=TOOL_REGISTRY
    )
    return Agent(architecture)

