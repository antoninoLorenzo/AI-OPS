import os
import argparse

from dotenv import load_dotenv

from ai_ops import API_BASE_ENV_NAME, API_KEY_ENV_NAME
from ai_ops.core import (
    ModelConfig, AgentConfig,
    AgentFactory, AgentRunner,
    Event, 
    TextEvent, 
    UserMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    StopEvent,
    LoadSkill, Whiteboard
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "model", type=str,
        help="Specify model id as <provider>/<model>. Use `hosted_vllm/model` for vLLM."
    )
    args = parser.parse_args()
    api_base = os.environ.get(API_BASE_ENV_NAME, None)
    if api_base:
        api_base = api_base.rstrip("/")
    
    api_key = os.environ.get(API_KEY_ENV_NAME, None)


    agent_factory = AgentFactory(
        agent_config=AgentConfig(tools=[Whiteboard, LoadSkill]),
        model_config=ModelConfig(model=args.model, api_base=api_base, api_key=api_key)
    )

    agent = agent_factory.create()

    stream = agent.run(user_message=UserMessageEvent(content="What skills are available?"))
    for event in stream:
        if isinstance(event, TextEvent):
            print(event.chunk)
        elif isinstance(event, ToolCallEvent):
            print(f"called tool: {event.name}({event.args})")
        elif isinstance(event, ToolResultEvent):
            print(f"tool result: {event.result}")
        elif isinstance(event, StopEvent):
            print(f"done: reason={event.reason}")

if __name__ == "__main__":
    load_dotenv()
    main()
