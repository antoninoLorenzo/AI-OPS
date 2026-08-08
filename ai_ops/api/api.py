# TODO: logging here should bind to the fastapi logger
from collections.abc import AsyncIterable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import StreamingResponse

from ai_ops.api.auth import handle_api_key
from ai_ops.api.config import build_agent_config, get_settings
from ai_ops.api.model import StartAgentRequest
from ai_ops.core.llm import (
    InferenceClient,
    ModelConfig,
    ModelMetadata,
    build_inference_client,
)
from ai_ops.core.runner import AgentConfig, AgentRunner
from ai_ops.core.schema import Event, ToolConfirmationEvent, UserMessageEvent
from ai_ops.core.storage import Session, SessionStore
from ai_ops.core.storage import get_session_store as _core_get_session_store
from ai_ops.core.tracing import configure_tracing
from ai_ops.core.log import get_logger, log_event, logging


_logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing()

    settings = get_settings()
    log_event(
        _logger, logging.INFO, "Loaded API Settings",
        host=settings.host,
        storage_strategy=settings.storage_strategy,
        model=settings.model,
        llm_provider_base=settings.llm_provider_base
    )

    agent_config = build_agent_config()
    
    inference_client = build_inference_client(config=ModelConfig(
        model=settings.model,
        api_base=settings.llm_provider_base,
        api_key=settings.llm_provider_key
    ))
    # TODO: impl. startup client check 
    log_event(
        _logger, logging.DEBUG, "Done build_inference_client"
    )

    app.state.inference_client = inference_client
    app.state.agent_config = agent_config
    app.state.runner_map: dict[int, AgentRunner] = {}
    
    # call get_session_store once with the intended strategy (pay init cost
    # at startup since the JSONL strategy init does disk i/o).
    _ = _core_get_session_store(strategy=settings.storage_strategy)

    yield


assert handle_api_key is not None, "Impl. error: `ai_ops.api.setup_auth` not called before app creation."

app = FastAPI(
    lifespan=lifespan, 
    dependencies=[Depends(handle_api_key)],
    docs_url=None, redoc_url=None, openapi_url=None
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[get_settings().host])

conversation_router = APIRouter(prefix="/conversation")


async def get_inference_client(request: Request) -> InferenceClient:
    return request.app.state.inference_client

async def get_store() -> SessionStore:
    return _core_get_session_store()

async def get_runner_map(request: Request) -> dict[int, AgentRunner]:
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
    store: Annotated[SessionStore, Depends(get_store)],
    inference_client: Annotated[InferenceClient, Depends(get_inference_client)],
    runner_map: Annotated[dict[int, AgentRunner], Depends(get_runner_map)],
    agent_config: Annotated[AgentConfig, Depends(get_agent_config)]
) -> Session:
    """Creates a session and initalizes the agent."""
    session = store.create_session()

    runner = AgentRunner(
        session_id=session.uuid,
        client=inference_client,
        config=agent_config
    )

    runner_map[session.short_id] = runner

    return session


# response_model=None: the return is List[Event] (an ABC, not a pydantic field),
# so let jsonable_encoder serialize the concrete event instances directly.
@conversation_router.get("/{short_id}", response_model=None)
async def load_conversation(
    short_id: int,
    store: Annotated[SessionStore, Depends(get_store)],
    inference_client: Annotated[InferenceClient, Depends(get_inference_client)],
    runner_map: Annotated[dict[int, AgentRunner], Depends(get_runner_map)],
    agent_config: Annotated[AgentConfig, Depends(get_agent_config)]
) -> list[Event]:
    try:
        session_id = store.get_session_uuid(short_id=short_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    runner = runner_map.get(short_id)
    if runner is None:
        runner = AgentRunner(
            session_id=session_id,
            client=inference_client,
            config=agent_config,
            is_new_conversation=False
        )
        runner_map[short_id] = runner

    try:
        return store.get_events_by_uuid(session_id=session_id)
    except RuntimeError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@conversation_router.post("/{short_id}")
async def start_agent(
    short_id: int,
    body: StartAgentRequest,
    runner_map: Annotated[dict[int, AgentRunner], Depends(get_runner_map)]
) -> StreamingResponse:
    runner = runner_map.get(short_id)
    if runner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # `arun` raises before returning the async iterator, so resolving the stream here lets 
    # us surface errors as proper status codes before the streaming response starts. 
    try:
        event_stream = runner.arun(user_message=UserMessageEvent(content=body.content), mode=body.mode)
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


@conversation_router.post("/{short_id}/send")
async def send_message(
    short_id: int,
    runner_map: Annotated[dict[int, AgentRunner], Depends(get_runner_map)],
    content: str = Body(..., embed=True),
):
    runner = runner_map.get(short_id)
    if runner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) 
    
    if not runner.send(UserMessageEvent(content=content)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)

    return {"enqueued": True}

    
@conversation_router.delete("/{short_id}")
async def delete_agent(
    short_id: int,
    runner_map: Annotated[dict[int, AgentRunner], Depends(get_runner_map)]
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
    runner_map: Annotated[dict[int, AgentRunner], Depends(get_runner_map)]
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
    runner_map: Annotated[dict[int, AgentRunner], Depends(get_runner_map)]
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
    store: Annotated[SessionStore, Depends(get_store)]
):
    try:
        session_id = store.get_session_uuid(short_id=short_id)
        session = store.get_session_by_uuid(session_id=session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    total = sum(
        message.token_count
        for message in session.messages
        if message.token_count is not None
    )

    return {
        "total_tokens": total,
        "max_context_length": inference_client.metadata.max_context_length
    }


app.include_router(conversation_router)
