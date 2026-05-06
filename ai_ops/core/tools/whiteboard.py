from typing import Annotated, Dict, Optional, Union

from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool

_WHITEBOARD_DESCRIPTION = """A structured in-memory notepad for persisting findings across reasoning steps.
Maintains a named index of findings (vulnerabilities, credentials, host info, etc.), each with a description and content."""

_WHITEBOARD_READ_DESCRIPTION = """Perform a read operation on the whiteboard by specifying the name of a finding.
Findings are provided under `# Whiteboard Index`, if any, as `name: description`."""

_WHITEBOARD_WRITE_DESCRIPTION = """Perform a write operation on the whiteboard by specifying: the name of the \
finding, the description and the content. The description should be short and include only the necessary information \
that will be included in the Whiteboard Index, the content contains a more detailed overview of the finding, including \
the process that lead to the finding (ex. what commands you executed and why).
"""


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
        
        return "# Whiteboard Index\n" + "\n".join([
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

        whiteboard[entry.name] = entry


_WHITEBOARD_STORE = None

def get_whiteboard_store() -> WhiteboardStore:
    global _WHITEBOARD_STORE
    if _WHITEBOARD_STORE is None:
        _WHITEBOARD_STORE = WhiteboardStore()
    return _WHITEBOARD_STORE


class WhiteboardRead(Tool[WhiteboardReadRequest, WhiteboardResult]):
    name = 'read_whiteboard'
    description = _WHITEBOARD_DESCRIPTION + _WHITEBOARD_READ_DESCRIPTION

    def __init__(self, whiteboard_id: str):
        self.whiteboard_id = whiteboard_id
        store = get_whiteboard_store()
        store.new_whiteboard(whiteboard_id)

    def __call__(self, tool_args: WhiteboardReadRequest) -> WhiteboardResult:
        store = get_whiteboard_store()

        try:
            entry = store.get_entry(self.whiteboard_id, tool_args.name)
        except ValueError:
            return WhiteboardResult(
                status=False,
                operation='r',
                result=f"No entry for {tool_args.name} in whiteboard"
            )

        return WhiteboardResult(
            status=True,
            operation='r',
            result=entry
        )

    @staticmethod
    def format_result(whiteboard_result: WhiteboardResult) -> str:
        if whiteboard_result.status:
            return f"{whiteboard_result.result}"
        return f"ERROR: {whiteboard_result.result}"


    @property
    def index(self) -> Optional[str]:
        store = get_whiteboard_store()
        return store.get_index(whiteboard_id=self.whiteboard_id)
    

class WhiteboardWrite(Tool[WhiteboardWriteRequest, WhiteboardResult]):
    name = 'write_whiteboard'
    description = _WHITEBOARD_DESCRIPTION + _WHITEBOARD_WRITE_DESCRIPTION

    def __init__(self, whiteboard_id: str):
        self.whiteboard_id = whiteboard_id
        store = get_whiteboard_store()
        store.new_whiteboard(whiteboard_id)

    def __call__(self, tool_args: WhiteboardReadRequest) -> WhiteboardResult:
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
                operation='r',
                result=str(err)
            )

        return WhiteboardResult(
            status=True,
            operation='w',
            result=f"Wrote finding {tool_args.name}"
        )

    @staticmethod
    def format_result(whiteboard_result: WhiteboardResult) -> str:
        if whiteboard_result.status:
            return f"{whiteboard_result.result}"
        return f"ERROR: {whiteboard_result.result}"