from typing import Annotated

from pydantic import BaseModel, Field

from ai_ops.core.prompt import get_prompt
from ai_ops.core.schema import Event, ToolCallEvent
from ai_ops.core.tools.base import Tool


class WhiteboardEntry(BaseModel):
    name: str
    description: str
    content: str


class WhiteboardReadRequest(BaseModel):
    name: Annotated[
        str,
        Field(description="Finding name / index key. Required for both read and write.")
    ] 

class WhiteboardWriteRequest(BaseModel):
    name: Annotated[
        str,
        Field(description="Finding name / index key. Required for both read and write.")
    ]
    description: Annotated[
        str,
        Field(description="Required when mode='w'. One-sentence summary used for the whiteboard index. Omit when mode='r'.")
    ]
    content: Annotated[
        str,
        Field(description="Required when mode='w'. Full finding content. Omit when mode='r'.")
    ]


class WhiteboardResult(BaseModel):
    status: bool
    result: str | WhiteboardEntry


class WhiteboardStore:
    def __init__(self):
        self.__store: dict[str, dict[str, WhiteboardEntry]] = {}

    def new_whiteboard(self, whiteboard_id: str):
        self.__store[whiteboard_id] = {}

    def get_index(self, whiteboard_id: str) -> str:
        whiteboard = self.__store.get(whiteboard_id, None)
        if whiteboard is None:
            raise ValueError(f"No whiteboard with whiteboard_id={whiteboard_id}")
        
        if len(whiteboard) == 0:
            return "\n# Whiteboard Index\n (empty)"
        
        return "\n# Whiteboard Index\n" + "\n".join([
            f"## {entry.name}\n**Description**: {entry.description}\n### Content\n{entry.content}" 
            for _, entry in whiteboard.items()
        ])

    def get_entry(self, whiteboard_id: str, name: str) -> WhiteboardEntry:
        whiteboard = self.__store.get(whiteboard_id, None)
        if whiteboard is None:
            raise ValueError(f"No whiteboard with whiteboard_id={whiteboard_id}")
        
        entry = whiteboard.get(name, None)
        if entry is None:
            raise ValueError(f"No entry {name} in whiteboard")
        return entry

    def upsert(self, whiteboard_id: str, entry: WhiteboardEntry):
        whiteboard = self.__store.get(whiteboard_id, None)
        if whiteboard is None:
            raise ValueError(f"No whiteboard with whiteboard_id={whiteboard_id}")

        whiteboard[entry.name] = entry


_WHITEBOARD_STORE = None

def get_whiteboard_store() -> WhiteboardStore:
    global _WHITEBOARD_STORE
    if _WHITEBOARD_STORE is None:
        _WHITEBOARD_STORE = WhiteboardStore()
    return _WHITEBOARD_STORE


class WhiteboardRead(Tool[WhiteboardReadRequest, WhiteboardResult]):
    name = 'read_whiteboard'
    description = get_prompt(name="read_whiteboard", kind="tool")

    def __init__(
        self, 
        whiteboard_id: str, 
        new_whiteboard: bool = True,
        model: str | None = None
    ):
        self.whiteboard_id = whiteboard_id
        store = get_whiteboard_store()
        if new_whiteboard:
            store.new_whiteboard(whiteboard_id)

    def __call__(self, tool_args: WhiteboardReadRequest) -> WhiteboardResult:
        store = get_whiteboard_store()

        try:
            entry = store.get_entry(self.whiteboard_id, tool_args.name)
        except ValueError:
            return WhiteboardResult(
                status=False,
                result=f"No entry for {tool_args.name} in whiteboard"
            )

        return WhiteboardResult(
            status=True,
            result=entry
        )

    @staticmethod
    def format_result(whiteboard_result: WhiteboardResult) -> str:
        if whiteboard_result.status:
            return f"{whiteboard_result.result}"
        return f"ERROR: {whiteboard_result.result}"


    @property
    def index(self) -> str | None:
        store = get_whiteboard_store()
        return store.get_index(whiteboard_id=self.whiteboard_id)


class WhiteboardWrite(Tool[WhiteboardWriteRequest, WhiteboardResult]):
    name = 'write_whiteboard'
    description = get_prompt(name="write_whiteboard", kind="tool")

    def __init__(
        self, 
        whiteboard_id: str, 
        new_whiteboard: bool = True, 
        model: str | None = None
    ):
        self.whiteboard_id = whiteboard_id
        store = get_whiteboard_store()
        if new_whiteboard:
            store.new_whiteboard(whiteboard_id)

    def __call__(self, tool_args: WhiteboardWriteRequest) -> WhiteboardResult:
        store = get_whiteboard_store()

        try:
            store.upsert(
                self.whiteboard_id,
                WhiteboardEntry(
                    name=tool_args.name,
                    description=tool_args.description,
                    content=tool_args.content
                )
            )
        except ValueError as err:
            return WhiteboardResult(
                status=False,
                result=str(err)
            )

        return WhiteboardResult(
            status=True,
            result=f"Wrote finding {tool_args.name}"
        )

    @staticmethod
    def format_result(whiteboard_result: WhiteboardResult) -> str:
        if whiteboard_result.status:
            return f"{whiteboard_result.result}"
        return f"ERROR: {whiteboard_result.result}"

    def post_compaction_state(self) -> str | None:
        return self.index

    @property
    def index(self) -> str | None:
        store = get_whiteboard_store()
        return store.get_index(whiteboard_id=self.whiteboard_id)


def replay_whiteboard(whiteboard_id: str, events: list[Event]) -> None:
    """Reconstruct a whiteboard's state from a resumed session's events.

    :param whiteboard_id: Corresponds to `session_id`
    :param events: event list used to reconstruct the `WhiteboardStore` state
    """
    store = get_whiteboard_store()
    store.new_whiteboard(whiteboard_id)  # create empty, then re-apply writes
    for event in events:
        if isinstance(event, ToolCallEvent) and event.name == WhiteboardWrite.name:
            args = event.args
            store.upsert(
                whiteboard_id,
                WhiteboardEntry(
                    name=args.name,
                    description=args.description,
                    content=args.content
                )
            )