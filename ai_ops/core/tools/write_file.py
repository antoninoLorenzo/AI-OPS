import os
from pathlib import Path
from enum import StrEnum, auto
from typing import Annotated

from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool
from ai_ops.core.prompt import get_prompt
from ai_ops.core.log import get_logger, log_event, logging


_logger = get_logger(__name__)


# Note: this makes a one-to-one mapping between requested paths and
# the actual paths, so the client knows what's the name of file being 
# written on the fs (that's no bueno in path traversal).
def resolve_path(base_dir: Path, requested_path: Path) -> Path | None:
    path = base_dir.joinpath(requested_path)
    if base_dir not in path.resolve().parents:
        return None

    return path


def tree_view(base: str):
    view = f"{base}/\n"

    # the amount of over-engineering I was going to do to implement this is an 
    # absolute shame... 
    # So I stole this: https://github.com/kddnewton/tree/blob/main/tree.py
    # I tried to reimplement with Path.walk(), however it was noticeably slower, 
    # idk if pathlib made it slower or I just suck (probably the latter).
    def walk(directory, prefix = ""):
        nonlocal view

        filepaths = sorted([filepath for filepath in os.listdir(directory)])

        for index in range(len(filepaths)):
            if filepaths[index][0] == ".":
                continue

            absolute = os.path.join(directory, filepaths[index])

            if index == len(filepaths) - 1:
                view += prefix + "└── " + filepaths[index] + "\n"
                if os.path.isdir(absolute):
                    walk(absolute, prefix + "    ")
            else:
                view += prefix + "├── " + filepaths[index] + "\n"
                if os.path.isdir(absolute):
                    walk(absolute, prefix + "│   ")

    walk(base)

    return view


# I'm not sure I want to keep the enum though, it kind of filters out 
# error information, the question is whether or not we want the agent 
# to see the info or just log it.
class WriteFileError(StrEnum):
    NOT_AUTHORIZED = auto() # outside of workspace
    OS_ERROR = auto()   # stuff like path too long


class WriteFileInput(BaseModel):
    path: Annotated[
        str,
        Field(description="Relative path from the workspace root, ex. script.py")
    ]
    content: Annotated[
        str,
        Field(description="Full text content to write. Overwrites the file if it already exists.")
    ]


class WriteFileOutput(BaseModel):
    tree_view: str | None = None
    error: WriteFileError | None = None


class WriteFile(Tool[WriteFileInput, WriteFileOutput]):
    name = 'write_file'
    description = None

    def __init__(self, working_directory: Path):
        self.description = get_prompt(name="write_file", kind="tool")
        self.working_directory = working_directory
        if not self.working_directory.exists():
            self.working_directory.mkdir(parents=True, exist_ok=True)

    def __call__(self, tool_args: WriteFileInput) -> WriteFileOutput:
        path = resolve_path(self.working_directory, tool_args.path)
        if path is None:
            return WriteFileOutput(error=WriteFileError.NOT_AUTHORIZED)

        if not path.parent.exists():
            path.parent.mkdir()
            
        try:
            path.write_text(tool_args.content)        
        except OSError as os_err:
            return WriteFileOutput(error=WriteFileError.OS_ERROR)
        except Exception as err:
            return WriteFileOutput(error=str(err))

        return WriteFileOutput(
            tree_view=tree_view(str(self.working_directory))
        )

    @staticmethod
    def format_result(tool_result: WriteFileOutput) -> str:
        if tool_result.error is not None:
            return f"write_file error: {tool_result.error}"
        else:
            return f"Workspace Content:\n{tool_result.tree_view}"
