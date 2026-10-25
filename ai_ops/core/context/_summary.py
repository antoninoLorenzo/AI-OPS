import json

from pydantic import BaseModel

from ai_ops.core.context.transform import ContextTransform
from ai_ops.core.conversation import Message, get_token_count
from ai_ops.core.llm import InferenceClient, query
from ai_ops.core.prompt import get_prompt
from ai_ops.core.schema import ChatCompletionEvent, SummaryRecord
from ai_ops.core.storage import get_session_store

SUMMARIZATION_AGENT_ID = "summarization"
DEFAULT_CONTEXT_BOUND = 64_000
DEFAULT_CONTEXT_THRESHOLD = 0.9
DEFAULT_MAX_SUMMARY_TOKENS = 8_000


class SummarizationConfig(BaseModel):
    context_bound: int = DEFAULT_CONTEXT_BOUND
    context_threshold: float = DEFAULT_CONTEXT_THRESHOLD
    max_summary_tokens: int = DEFAULT_MAX_SUMMARY_TOKENS


class SummarizationCompaction(ContextTransform):
    """
    Replaces the trajectory (everything after [system, user]) with an LLM-generated
    summary once the estimated context size crosses the threshold (bound*threshold).

    The transform is stateful: it remembers the last summary and how many leading
    session messages it already folded (`session.messages` is append-only, so the
    fold boundary is a stable index). Each turn the produced context is therefore

        [system, user, <last summary>, <messages appended since the fold>]

    and the summarizer LLM is only re-invoked when that view again crosses the
    threshold, at which point the previous summary and the new tail are folded into a
    fresh summary. State is recovered on resume from the persisted `SummaryRecord`s,
    so a reloaded session continues from the last summary instead of re-summarizing.
    """
    required_state = ("session_id", "client")

    @classmethod
    def config_schema(cls) -> type[BaseModel] | None:
        return SummarizationConfig

    def __init__(
        self,
        session_id: str,
        client: InferenceClient,
        context_bound: int = DEFAULT_CONTEXT_BOUND,
        context_threshold: float = DEFAULT_CONTEXT_THRESHOLD,
        max_summary_tokens: int = DEFAULT_MAX_SUMMARY_TOKENS
    ):
        self.session_id = session_id
        self.client = client
        self.max_summary_tokens = max_summary_tokens
        self.summarization_prompt = get_prompt(name=SUMMARIZATION_AGENT_ID)

        self._threshold = context_bound * context_threshold
        self._store = get_session_store()

        # compaction state; recovered from persisted summaries on resume.
        # _folded is the number of leading session messages represented by
        # _summary_msg ([0] and [1] are kept verbatim as system/user, [2:_folded]
        # are folded into the summary).
        self._summary_msg: Message | None = None
        self._folded = 0
        self.__recover_state()

    def __recover_state(self):
        try:
            session = self._store.get_session_by_uuid(self.session_id)
        except ValueError:
            return

        records = session.summarization_events
        if not records:
            return

        last = records[-1]
        self._summary_msg = self.__summary_to_message(last.event)
        self._folded = last.boundary

    def __call__(self, messages: list[Message]) -> list[Message]:
        # note: token_count sums are an approximation of the real context size; to be
        # exact we'd read prompt tokens from the last chat completion event, this is
        # good enough to drive compaction.
        if self._summary_msg is None:
            tail = messages[2:]
            if sum(m.token_count for m in tail) < self._threshold:
                return messages
            return self.__summarize(messages, prev_summary=None, fold_from=2)

        tail = messages[self._folded:]
        if not tail:
            # nothing new since the last fold, reuse the summary as-is
            return [messages[0], messages[1], self._summary_msg]

        context_size = self._summary_msg.token_count + sum(m.token_count for m in tail)
        if context_size < self._threshold:
            return [messages[0], messages[1], self._summary_msg, *tail]

        return self.__summarize(messages, prev_summary=self._summary_msg, fold_from=self._folded)

    def __summarize(
        self,
        messages: list[Message],
        prev_summary: Message | None,
        fold_from: int,
    ) -> list[Message]:
        trajectory = self.__format_trajectory(messages[fold_from:])
        if prev_summary is not None:
            trajectory = (
                "<previous_summary>\n"
                + prev_summary.message["content"]
                + "\n</previous_summary>\n"
                + trajectory
            )

        summarizer_messages = [
            {"role": "system", "content": self.summarization_prompt},
            {"role": "user", "content": trajectory}
        ]

        # note: llm call is sync because transforms are not async, good enough for now
        response = query(
            client=self.client, messages=summarizer_messages,
            max_completion_tokens=self.max_summary_tokens
        )

        event = ChatCompletionEvent.from_model_response(
            session_id=self.session_id, response=response
        )
        summary_msg = self.__summary_to_message(event)
        boundary = len(messages)

        self._store.append_summary(
            session_id=self.session_id,
            summary=SummaryRecord(event=event, boundary=boundary)
        )
        self._summary_msg = summary_msg
        self._folded = boundary

        return [messages[0], messages[1], summary_msg]

    def __summary_to_message(self, event: ChatCompletionEvent) -> Message:
        raw = {"role": "user", "content": event.message["content"]}
        return Message(
            message=raw,
            agent_id=SUMMARIZATION_AGENT_ID,
            token_count=get_token_count(raw)
        )

    def __format_trajectory(self, messages: list[Message]) -> str:
        user_prompt = ""
        for message in messages:
            msg = message.message
            role = msg["role"]
            user_prompt += f"<{role}>\n"

            if role == "assistant" and msg.get("reasoning_content") is not None:
                user_prompt += f"<reasoning>{msg['reasoning_content']}</reasoning>\n"

            user_prompt += (msg.get("content") or "") + "\n"

            if role == "assistant" and len(msg.get("tool_calls") or []) > 0:
                user_prompt += "<tool_calls>\n"
                for tc in msg['tool_calls']:
                    user_prompt += json.dumps(tc["function"])
                user_prompt += "</tool_calls>\n"

            user_prompt += f"</{role}>\n"

        return user_prompt
