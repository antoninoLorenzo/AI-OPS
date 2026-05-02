from typing import List, Optional, Dict, Type, Iterator, Any

import litellm
from litellm import (
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage,
    ChatCompletionAssistantMessage,
    ChatCompletionToolMessage
)

from ai_ops.core.agent import orchestrator
from ai_ops.core.schema import (
    AgentConfig, 
    AgentMode, 
    Event, EventType,
    UserMessageEvent,
    TextEvent,
    ToolCallEvent, ToolResultEvent,
    StopEvent
)
from ai_ops.core.llm import ModelConfig, InferenceClient, build_inference_client
from ai_ops.core.conversation import Conversation, Message, get_conversation_store
from ai_ops.core.tools import (
    Tool, ToolContext,
    ToolRegistry, ToolFactory,
    LoadSkill, 
    get_skill_registry,
    Whiteboard,
    get_whiteboard_store
)
from ai_ops.core.prompt import BASE_PROTOTYPE_PROMPT, SKILL_PROTOTYPE_PROMPT
from ai_ops.core.context_management import ContextView
from ai_ops.core.utils import get_logger

_logger = get_logger(__name__)



class AgentRunner:
    def __init__(
        self,
        conversation_id: str,
        client: InferenceClient,
        tools: List[str],
        context_fn: ContextView,
        extra_tool_ctx: Optional[Dict[str, Any]] = None
    ):
        self.conversation_id = conversation_id
        self.client = client
        self.context_fn = context_fn
        self._conversation_store = get_conversation_store()

        ctx = ToolContext(conversation_id=conversation_id, extra=extra_tool_ctx)
        self.tools = {
            name: factory(ctx)
            for name in tools
            if (factory := ToolRegistry.get(name)) is not None
        }
        self._user_stopped = False
    
    def run(
        self, 
        user_message: UserMessageEvent,
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: Optional[int] = None
    ) -> Iterator[Event]:
        self._append_user_message(user_message.content)

        conversation = self._conversation_store.get(conversation_id=self.conversation_id)
        event_stream = orchestrator(
            client=self.client,
            conversation=conversation,
            tools=self.tools,
            context_fn=self.context_fn,
            mode=mode,
            max_iterations=max_iterations
        )

        for event in event_stream:
            if isinstance(event, Message):
                self._conversation_store.append(
                    conversation_id=self.conversation_id, message=event
                )
                yield TextEvent(chunk=event.message["content"])
                continue
            
            if isinstance(event, ToolResultEvent):
                self._conversation_store.append(
                    conversation_id=self.conversation_id, 
                    message=Message(
                        message=ChatCompletionToolMessage(
                            role="tool",
                            content=str(event.result),
                            tool_call_id=event.call_id
                        ),
                        token_count=litellm.token_counter(text="")
                    )
                )
            elif isinstance(event, StopEvent):
                yield event
                break

            yield event

            if self._user_stopped:
                break
            

    def send(self, user_event: UserMessageEvent | StopEvent):
        if isinstance(user_event, UserMessageEvent):
            self._append_user_message(user_event.content)
        elif isinstance(user_event, StopEvent):
            self._user_stopped = True


    def _append_user_message(self, content: str):
        self._conversation_store.append(
            conversation_id=self.conversation_id,
            message=Message(
                message=ChatCompletionUserMessage(role="user", content=content),
                token_count=litellm.token_counter(text=content)
            )
        )

class AgentFactory:
    def __init__(
        self, 
        agent_config: AgentConfig,
        model_config: ModelConfig | List[ModelConfig],
        extra_tool_ctx: Optional[Dict[str, Any]] = None
    ):
        if isinstance(model_config, ModelConfig):
            model_config = [model_config]

        self._inference_client = build_inference_client(model_config)
        self._conversation_store = get_conversation_store()
        self._context_strategy = agent_config.context_fn
        self._tools: Dict[str, Type[Tool]] = {
            tool.name: tool 
            for tool in agent_config.tools
        }
        self._extra_tool_context = extra_tool_ctx
        
        self._system_prompt = BASE_PROTOTYPE_PROMPT
        if agent_config.system_prompt:
            self._system_prompt = agent_config.system_prompt
        
        _logger.info(f"Available tools: {list(self._tools.keys())}")
        self._whiteboard_store = None
        if Whiteboard.name in self._tools:
            self._whiteboard_store = get_whiteboard_store()
        
        if LoadSkill.name in self._tools:
            skill_registry = get_skill_registry()
            self._system_prompt += SKILL_PROTOTYPE_PROMPT.format(skill_index=skill_registry.get_index())
    
    def create(self, conversation_id: Optional[str] = None) -> AgentRunner:
        # if given a conversation_id resumes
        if conversation_id:
            conversation = self._conversation_store.get(conversation_id)
        else:
            conversation = self._conversation_store.create(self._system_prompt)
        
        return AgentRunner(
            conversation_id=conversation.id,
            client=self._inference_client,
            tools=list(self._tools.keys()),
            context_fn=self._context_strategy,
            extra_tool_ctx=self._extra_tool_context
        )
    
