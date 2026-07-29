# --- Security Notes (TODO: move to documentation)
# 
# The API is bound to 127.0.0.1 by default.
#
# The API enforces the `Host` header is correctly set to the expected host (set in the `AI_OPS_HOST` 
# environment variable).
# 
# The API authenticates requests with an api key provided through `X-AI-OPS-ApiKey` header. The token 
# is given during deployment using `AI_OPS_AUTH_TOKEN` environment variable.
# API Key Authentication is opt-in *only* if the API is bound to localhost, otherwise it's mandatory. 
# 

# TODO: logging here should bind to the fastapi logger
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterable, Dict

from fastapi import FastAPI, APIRouter, Depends, Request, HTTPException, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import StreamingResponse

from ai_ops.api.config import get_settings, build_agent_config
from ai_ops.api.auth import handle_api_key

from ai_ops.core.schema import Event, UserMessageEvent, ToolConfirmationEvent
from ai_ops.core.runner import AgentRunner, AgentConfig
from ai_ops.core.agent import AgentMode
from ai_ops.core.conversation import Conversation, ConversationStore
from ai_ops.core.conversation import get_conversation_store as _core_get_conversation_store
from ai_ops.core.llm import InferenceClient, ModelMetadata, ModelConfig, build_inference_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    agent_config = build_agent_config()
    inference_client = build_inference_client(config=ModelConfig(
        model=settings.model,
        api_base=settings.llm_provider_base,
        api_key=settings.llm_provider_key
    ))
    # TODO: impl. startup client check 

    app.state.inference_client = inference_client
    app.state.agent_config = agent_config
    app.state.runner_map: Dict[int, AgentRunner] = {}
    
    # call get_conversation_store once with the intended strategy (pay init cost 
    # at startup since the JSONL strategy init does disk i/o).
    _ = _core_get_conversation_store(strategy=settings.storage_strategy)

    yield


assert handle_api_key is not None, "Impl. error: `ai_ops.api.setup_auth` not called before app creation."

app = FastAPI(
    lifespan=lifespan, 
    dependencies=[Depends(handle_api_key)]
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[get_settings().host])

conversation_router = APIRouter(prefix="/conversation")


async def get_inference_client(request: Request) -> InferenceClient:
    return request.app.state.inference_client

async def get_conversation_store() -> ConversationStore:
    return _core_get_conversation_store()


async def get_runner_map(request: Request) -> Dict[int, AgentRunner]:
    return request.app.state.runner_map


async def get_agent_config(request: Request) -> AgentConfig:
    return request.app.state.agent_config


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/model")
async def get_model(
    inference_client: Annotated[InferenceClient, Depends(get_inference_client)]
) -> ModelMetadata:
    return inference_client.metadata


@conversation_router.post("") # POST /conversation
async def create_conversation(
    conversation_store: Annotated[ConversationStore, Depends(get_conversation_store)],
    inference_client: Annotated[InferenceClient, Depends(get_inference_client)],
    runner_map: Annotated[Dict[int, AgentRunner], Depends(get_runner_map)],
    agent_config: Annotated[AgentConfig, Depends(get_agent_config)]
) -> Conversation:
    """Creates a conversation and initalizes the agent."""
    conversation = conversation_store.create()

    runner = AgentRunner(
        conversation_id=conversation.uuid,
        client=inference_client,
        config=agent_config
    )

    runner_map[conversation.short_id] = runner

    return conversation


@conversation_router.get("/{short_id}")
async def load_conversation(
    short_id: int,
    conversation_store: Annotated[ConversationStore, Depends(get_conversation_store)],
    inference_client: Annotated[InferenceClient, Depends(get_inference_client)],
    runner_map: Annotated[Dict[int, AgentRunner], Depends(get_runner_map)],
    agent_config: Annotated[AgentConfig, Depends(get_agent_config)]
) -> Conversation:
    try:
        conversation = conversation_store.get_by_short_id(short_id=short_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    runner = runner_map.get(short_id)
    if runner is None:
        runner = AgentRunner(
            conversation_id=conversation.uuid,
            client=inference_client,
            config=agent_config,
            is_new_conversation=False
        )
        runner_map[conversation.short_id] = runner

    return conversation


@conversation_router.post("/{short_id}")
async def start_agent(
    short_id: int,
    content: str,
    mode: AgentMode,
    runner_map: Annotated[Dict[int, AgentRunner], Depends(get_runner_map)]
) -> StreamingResponse:
    runner = runner_map.get(short_id)
    if runner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # `arun` raises before returning the async iterator, so resolving the stream here lets 
    # us surface errors as proper status codes before the streaming response starts. 
    try:
        event_stream = runner.arun(user_message=UserMessageEvent(content=content), mode=mode)
    except RuntimeError:
        # here we assume `RuntimeError` is raised only because the agent is already running
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    except ValueError:
        # here we assume `ValueError` is raised because the conversation format is invalid,
        # that is an implementation error somewhere in conversation management.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    async def event_generator() -> AsyncIterable[str]:
        async for event in event_stream:
            yield event.model_dump_json() + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    
@conversation_router.delete("/{short_id}")
async def delete_agent(
    short_id: int,
    runner_map: Annotated[Dict[int, AgentRunner], Depends(get_runner_map)]
):
    """Close the agent instance on CLI-exit."""
    # note: duplicated of `stop_agent`
    runner = runner_map.get(short_id)
    if runner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # technically it will keep running until end of last event because stop is 
    # non-preemptive and doesn't tell us when it's done.
    if runner.running:
        runner.stop()

    runner_map.pop(short_id, None)


@conversation_router.post("/{short_id}/stop")
async def stop_agent(
    short_id: int,
    runner_map: Annotated[Dict[int, AgentRunner], Depends(get_runner_map)]
):
    runner = runner_map.get(short_id)
    if runner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # technically it will keep running until end of last event because stop is 
    # non-preemptive and doesn't tell us when it's done.
    if runner.running:
        runner.stop()


@conversation_router.post("/{short_id}/confirmation/{tool_call_id}")
async def confirm_tool_call(
    short_id: int, 
    tool_call_id: str, 
    approved: bool,
    runner_map: Annotated[Dict[int, AgentRunner], Depends(get_runner_map)]
):
    runner = runner_map.get(short_id)
    if runner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        runner.confirm(confirmation=ToolConfirmationEvent(call_id=tool_call_id, approved=approved))
    except RuntimeError:
        # here we assume `RuntimeError` is raised because `tool_call_id` doesn't match any existing 
        # pending tool call.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)


@conversation_router.get("/{short_id}/usage")
async def get_usage(
    short_id: int,
    inference_client: Annotated[InferenceClient, Depends(get_inference_client)],
    conversation_store: Annotated[ConversationStore, Depends(get_conversation_store)]
):
    try:
        conversation = conversation_store.get_by_short_id(short_id=short_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    total = sum((
        message.token_count 
        for message in conversation.messages 
        if message.token_count is not None
    ))
    max_context_length = inference_client.metadata.max_context_length

    return {
        "total_tokens": total,
        "max_context_length": max_context_length
    }


app.include_router(conversation_router)
