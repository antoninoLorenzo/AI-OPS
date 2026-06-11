import os
import pytest

from ai_ops.core.tools.write_file import (
    WriteFileInput, 
    WriteFileOutput,
    WriteFileError,
    WriteFile
)


@pytest.fixture
def mock_workspace(tmp_path):
    (tmp_path / "agent_workspace").mkdir()

    yield tmp_path / "agent_workspace"


def check_content(path: str, content: str):
    with open(path, "r") as fp:
        return content == fp.read()


# note: empty path/content are not allowed by BaseModel no reason to 
_WRITE_FILE_TESTS = [
    # cover that case
    # path traversal
    {
        "call": WriteFileInput(path="../etc/passwd", content="jomama"),
        "expected": lambda out: out.error and out.error == WriteFileError.NOT_AUTHORIZED
    },
    # path length
    {
        "call": WriteFileInput(
            path="a"*os.pathconf("/", "PC_PATH_MAX") + ".txt",
            content="jopapa"
        ),
        "expected": lambda out: out.error and out.error == WriteFileError.OS_ERROR
    },
    # parent dir not exists
    {
        "call": WriteFileInput(path="dir/file.txt", content="deez"),
        "expected": lambda out: out.tree_view and "file.txt" in out.tree_view
    },
    # overwrite (allowed within workspace)
    {
        "call": [
            WriteFileInput(path="tmp.txt", content="asd"),
            WriteFileInput(path="tmp.txt", content="1234")
        ],
        "expected": [
            check_content,
            check_content
        ]
    }
]


@pytest.mark.parametrize("test_case", _WRITE_FILE_TESTS)
def test_write_file(test_case, mock_workspace):
    write_file = WriteFile(working_directory=mock_workspace)

    if isinstance(test_case["call"], list):
        for tool_args, expected_fn in zip(test_case["call"], test_case["expected"]):
            tool_out = write_file(tool_args)

            if expected_fn.__name__ == "check_content":
                check_content(
                    path=str(mock_workspace / tool_args.path), 
                    content=tool_args.content
                )
    else:
        tool_args = test_case["call"]
        expected_fn = test_case["expected"]
        tool_out = write_file(tool_args)
        assert expected_fn(tool_out) is True, f"tool_out: {tool_out}"