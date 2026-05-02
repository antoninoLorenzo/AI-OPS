from typing import Literal, Optional, Union, Dict, Annotated

from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool
from ai_ops.core.utils import get_logger

_logger = get_logger(__name__)


_WHITEBOARD_DESCRIPTION = """A structured in-memory notepad for persisting findings across reasoning steps.
Maintains a named index of findings (vulnerabilities, credentials, host info, etc.), each with a description and content.
Use 'w' to create or update a finding by name, and 'r' to retrieve a specific finding's full content.
Before performing a read, consult the whiteboard index provided in context to identify available finding names."""


class WhiteboardRequest(BaseModel):
    mode: Annotated[
        Literal['r', 'w'], 
        Field(description="'r' to read a finding's content, 'w' to create or update a finding (upsert semantics).")
    ]
    name: Annotated[
        str,
        Field(description="Unique identifier for the finding. Used as the index key.")
    ]
    description: Annotated[
        Optional[str],
        Field(description="One-sentence summary of the finding. Required for writes, used to build the index.")
    ]
    content: Annotated[
        Optional[str],
        Field(description="Full finding content. Required for writes, ignored on reads.")
    ]


class WhiteboardEntry(BaseModel):
    name: str
    description: str
    content: str


class WhiteboardResult(BaseModel):
    status: bool
    operation: Literal['r', 'w', 'undefined']
    result: Union[str, WhiteboardEntry]


class WhiteboardStore:
    def __init__(self):
        self.__store: Dict[str, Dict[str, WhiteboardEntry]] = {}

    def new_whiteboard(self, whiteboard_id: str):
        self.__store[whiteboard_id] = {}

    def get_index(self, whiteboard_id: str) -> Optional[str]:
        whiteboard = self.__store.get(whiteboard_id, None)
        if whiteboard is None:
            raise ValueError(f"No whiteboard with whiteboard_id={whiteboard_id}")
        
        if len(whiteboard) == 0:
            return None
        
        return "\n".join([
            f"{name}: {entry.description}" 
            for name, entry in whiteboard.items()
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
        
        old_entry = whiteboard.get(entry.name, None)
        if old_entry is None:
            raise ValueError(f"No entry {entry.name} in whiteboard")
        
        old_entry.description = entry.description
        old_entry.content = entry.content


_WHITEBOARD_STORE = None

def get_whiteboard_store() -> WhiteboardStore:
    global _WHITEBOARD_STORE
    if _WHITEBOARD_STORE is None:
        _WHITEBOARD_STORE = WhiteboardStore()
    return _WHITEBOARD_STORE


class Whiteboard(Tool[WhiteboardRequest, WhiteboardResult]):
    name = 'whiteboard'
    description = _WHITEBOARD_DESCRIPTION

    def __init__(self, whiteboard_id: str):
        self.whiteboard_id = whiteboard_id
        store = get_whiteboard_store()
        store.new_whiteboard(whiteboard_id)

    def __call__(self, tool_args: WhiteboardRequest) -> WhiteboardResult:
        store = get_whiteboard_store()
        entry = store.get_entry(self.whiteboard_id, tool_args.name)
        if entry is None:
            return WhiteboardResult(
                status=False,
                operation=tool_args.mode if tool_args.mode in ('r', 'w') else 'undefined',
                result=f"No entry for {tool_args.name} in whiteboard index"
            )
        
        if tool_args.mode == 'r':
            return WhiteboardResult(
                status=True,
                operation=tool_args.mode,
                result=entry
            )
        elif tool_args.mode == 'w':
            if tool_args.description is None or tool_args.content is None:
                _logger.error(
                    "write requires description and content: "
                    f"description={type(tool_args.description)} content={type(tool_args.content)}"
                )    
                return WhiteboardResult(
                    status=False,
                    operation=tool_args.mode,
                    result=f"description and content required for write"
                )
            
            store.upsert(self.whiteboard_id, WhiteboardEntry(
                name=tool_args.name,
                description=tool_args.description,
                content=tool_args.content
            ))
            
            return WhiteboardResult(
                status=True,
                operation=tool_args.mode,
                result=f"Wrote finding {tool_args.name}"
            )
        else:
            _logger.error(f"Invalid input mode={tool_args.mode}")
            return WhiteboardResult(
                status=False,
                operation='undefined',
                result=f"Invalid input mode={tool_args.mode}"
            )

    @staticmethod
    def format_result(whiteboard_result: WhiteboardResult) -> str:
        if whiteboard_result.status:
            return f"ERROR: {whiteboard_result.result}"
        return f"{whiteboard_result.result}"


    @property
    def index(self) -> Optional[str]:
        store = get_whiteboard_store()
        return store.get_index(whiteboard_id=self.whiteboard_id)
    
    