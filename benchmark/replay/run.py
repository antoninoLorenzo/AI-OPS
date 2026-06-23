import os
from typing import List, Tuple, Type

import requests
import mlflow
from mlflow.entities import Trace, Span
from litellm import (
    ChatCompletionAssistantMessage,
    ChatCompletionSystemMessage,
    ChatCompletionToolMessage,
    ChatCompletionUserMessage,
)
from dotenv import load_dotenv

from ai_ops import API_BASE_ENV_NAME, API_KEY_ENV_NAME
from ai_ops.core.agent import orchestrator, AgentMode
from ai_ops.core.llm import ModelConfig, build_inference_client
from ai_ops.core.context_management import LayeredContextView
from ai_ops.core.conversation import (
    Message,
    Conversation,
    get_token_count,
    get_conversation_store
)
from ai_ops.core.tools import (
    Tool,
    ToolContext,
    ToolRegistry,
    LoadSkill, WhiteboardWrite, WhiteboardRead, ThinkTool
)
from ai_ops.core.tools.whiteboard import (
    WhiteboardWriteRequest, 
    WhiteboardEntry, 
    get_whiteboard_store
)
from ai_ops.core.tools.load_skill.skill import get_skill_registry

from benchmark.auto_pen_bench.tools import (
    SSHConnectTool,
    ExecuteBashTool,
    FileWriteTool,
    FinalAnswerTool
)
from benchmark.replay.patches.system_prompt import SYSTEM_PROMPT


_TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
_EXPERIMENT_ENV = "MLFLOW_EXPERIMENT_NAME"
_DEFAULT_EXPERIMENT = "AI-OPS"


def get_trace(session_id: str) -> Trace:
    trace = mlflow.search_traces(
        filter_string=f"metadata.`mlflow.trace.session` = '{session_id}'",
        max_results=1, 
        return_type='list', 
        include_spans=True
    )
    trace = trace[0] if len(trace) > 0 else None
    return trace


def completion_span_to_messages(span: Span) -> List[Message]:
    # where do inputs["tools"] go?
    raw_messages = []
    for msg in span.inputs["messages"]:
        if msg["role"] == "system":
            raw_messages.append(ChatCompletionSystemMessage(**msg))
        elif msg["role"] == "user":
            raw_messages.append(ChatCompletionUserMessage(**msg))
        elif msg["role"] == "assistant":
            raw_messages.append(ChatCompletionAssistantMessage(**msg))
        elif msg["role"] == "tool":
            raw_messages.append(ChatCompletionToolMessage(**msg))
    
    messages = [
        Message(message=message, token_count=get_token_count(message))
        for message in raw_messages
    ]
    response_dict = span.outputs["choices"][0]["message"]
    response = ChatCompletionAssistantMessage(**response_dict)
    messages.append(Message(message=response, token_count=get_token_count(response)))

    return messages


# great naming
def write_whiteboard_span_to_whiteboard_request(span: Span) -> WhiteboardWriteRequest:
    return WhiteboardWriteRequest(
        name=span.inputs["name"],
        description=span.inputs["description"],
        content=span.inputs["content"]
    )
    

def reconstruct_at_iteration(trace: Trace, iteration: int) -> Tuple[List[Message], List[WhiteboardWriteRequest]]:
    spans = sorted(trace.data.spans, key=lambda s: s.start_time_ns)    
    litellm_spans = [s for s in spans if s.name == 'litellm-completion']
    whiteboard_spans = [s for s in spans if s.name == 'write_whiteboard']
    
    if iteration >= len(litellm_spans):
        raise ValueError(f"Trace only has {len(litellm_spans)} iterations")
    
    target_span = litellm_spans[iteration]
    
    messages = completion_span_to_messages(target_span)
    whiteboard_writes = [
        write_whiteboard_span_to_whiteboard_request(s)
        for s in whiteboard_spans
        if s.start_time_ns < target_span.start_time_ns
    ]
    
    return messages, whiteboard_writes


def patch_system_prompt(messages: List[Message]) -> None:
    skill_registry = get_skill_registry()
    messages[0].message["content"] = SYSTEM_PROMPT.format(
        skill_index=skill_registry.get_index()
    )


def patch_skill(messages: List[Message], skill_name: str) -> None:
    pass


def patch_user_prompt(conversation_id: str, messages: List[Message]):
    whiteboard_store = get_whiteboard_store()
    wh_index = whiteboard_store.get_index(whiteboard_id=conversation_id)
    if wh_index is None:
        return
    
    last_usr_idx = next(
        (
            i for i in range(len(messages)-1, -1, -1)
            if messages[i].message.get("role", "") == "user"
        ),
        None
    )
    if last_usr_idx is None:
        return
    
    user_message = messages[last_usr_idx].message
    idx = user_message.get("content", "").find('# Whiteboard Index')
    if idx < 0:
        return
    
    task = user_message["content"][:idx]
    messages[last_usr_idx].message["content"] = task + wh_index


def main():
    # get input settings
    
    # AC VM0: After successfully finding the target in the network and the SSH credentials
    # Original: ... -> hydra (ok) -> write whiteboard -> load network-enumeration (you already did that) 
    # -> [nmap -> think -> nmap] (this block was wasted, already found) -> think (ok) -> ssh_connect -> ...
    # conversation_id = "ee61595c-ebaa-44db-828c-940d895a5d9b"
    # iteration = 11

    # AC VM1: After successfully finding the target in the network, what does it do
    # Original: ... -> SSH Connect (worked) -> write whiteboard -> load network-enumeration -> ssh connect (repeated) -> load privesc skill
    # conversation_id = "79175d1d-3c3f-419f-9c4a-dc5658c01a96"
    # iteration = 12

    # WEB VM3
    # Original: ... -> write whiteboard -> load net-enum -> load web-recon
    # conversation_id = "3c4a4777-64e4-4839-88fb-85eeb65156fd"
    # iteration = 7
    conversation_id = "9dbfcf60-ccb3-4284-a006-7e33a3326a09"
    iteration = 6

    # WEB VM5
    # conversation_id = "e880c1f9-0adc-47a7-8f4c-4a7f306fb727"
    # iteration = 4

    skills_to_patch = []
    
    tracking_uri = os.environ.get(_TRACKING_URI_ENV)
    experiment = os.environ.get(_EXPERIMENT_ENV, _DEFAULT_EXPERIMENT)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name=experiment)

    llm_api_base = os.environ.get(API_BASE_ENV_NAME, None)
    if llm_api_base:
        llm_api_base = llm_api_base.rstrip("/")
    
    llm_api_key = os.environ.get(API_KEY_ENV_NAME, None)

    # get trace
    trace: Trace | None = get_trace(session_id=conversation_id)
    if trace is None:
        print("Trace not found")
        return
    # model = trace.info.tags["model"] # provider is not registered
    # model = 'lightning-ai/gemma-4-31B-it'
    # model = 'lightning-ai/minimax-m2.5'
    # model = 'lightning-ai/glm-5'
    model = 'groq/qwen/qwen3-32b'
    messages, wh_writes = reconstruct_at_iteration(trace=trace, iteration=iteration)
    
    # build agent state from trace with patches
    conversation_store = get_conversation_store()
    whiteboard_store = get_whiteboard_store()

    patch_system_prompt(messages)
    for skill_name in skills_to_patch:
        patch_skill(messages=messages, skill_name=skill_name) # TODO: not implemented

    conversation_store.from_conversation(
        conversation_id=conversation_id, 
        conversation=Conversation(id=conversation_id, messages=messages)
    )

    whiteboard_store.new_whiteboard(whiteboard_id=conversation_id)
    for whiteboard_write in wh_writes:
        whiteboard_store.upsert(
            whiteboard_id=conversation_id, 
            entry=WhiteboardEntry(
                name=whiteboard_write.name,
                description=whiteboard_write.description,
                content=whiteboard_write.content
            )
        )
    # need this to validate new whiteboard index schema
    patch_user_prompt(conversation_id, messages)

    model_config = ModelConfig(model=model, api_base=llm_api_base, api_key=llm_api_key)
    inference_client = build_inference_client(models=[model_config])
    conversation = conversation_store.get_by_uuid(conversation_id=conversation_id)
    context_fn = LayeredContextView(
        max_window_tokens=16_384,
        terminal_alias=ExecuteBashTool.name,
        file_write_alias=FileWriteTool.name
    )
    
    available_tools: List[Type[Tool]] = [
        WhiteboardRead, WhiteboardWrite, LoadSkill, ThinkTool,
        ExecuteBashTool, FileWriteTool, SSHConnectTool, FinalAnswerTool
    ]
    ctx = ToolContext(
        conversation_id=conversation_id, 
        is_new_conversation=False,
        extra={"driver": None} # thx python
    )
    tools = {
        tool_cls.name: factory(ctx)
        for tool_cls in available_tools
        if (factory := ToolRegistry.get(tool_cls.name)) is not None
    }

    # run for one iteration and see what it generates
    for message in messages:
        print(f'{message.message["role"]}: {message.message["content"]}')
        
    event_stream = orchestrator(
        client=inference_client,
        conversation=conversation,
        tools=tools,
        context_fn=context_fn,
        mode=AgentMode.UNSUPERVISED,
        max_iterations=1
    )
    assistant_message = None
    for event in event_stream:
        if isinstance(event, Message):
            assistant_message = event
            break

    print(assistant_message.message)


if __name__ == "__main__":
    load_dotenv()
    main()
