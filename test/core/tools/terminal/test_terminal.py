import functools

import pytest

import ai_ops.core.tools.terminal.terminal # to monkeypatch BashSession
from ai_ops.core.tools.terminal import TerminalRequest, TerminalResult, Terminal
from ai_ops.core.tools.terminal.bash import CommandStatus
from ai_ops.core.tools.terminal.policy import (
    CommandContext, 
    AllowListPolicy, 
    PolicyResult, 
    PolicyError
)
from ai_ops.core.tools.terminal.utils import extract_executables

from test.core.mocks.terminal import MockAdmissionPolicy, MockBashSession

_TERMINAL_CALL_TESTS = [
    # command policies result in deny -> command rejected
    {
        "init": { 
            "conversation_id": "1234", 
            "policies": (
                MockAdmissionPolicy(allowed=True),
                MockAdmissionPolicy(allowed=False)
            ),
            "working_directory": "/tmp"
        },
        "command": "nc -lnvp 4444",
        "call": TerminalRequest(command="nc -lnvp 4444", session_id="bash-1234"),
        "expected": TerminalResult(
            session_id="bash-1234", 
            command="nc -lnvp 4444", 
            allowed=False
        )
    },
    # command policies result in approval -> command executes
    {
        "init": { 
            "conversation_id": "1234", 
            "policies": (
                MockAdmissionPolicy(allowed=True),
                MockAdmissionPolicy(allowed=True)
            ),
            "working_directory": "/tmp"
        },
        "command": "ls -la",
        "call": TerminalRequest(command="ls -la", session_id="bash-1234"),
        "expected": TerminalResult(
            session_id="bash-1234", 
            command="ls -la", 
            allowed=True,
            output="Ran `ls -la`",
            status=CommandStatus.OK
        )
    },
    # session_id None -> command executes in new session
    {
        "init": { 
            "conversation_id": "1234", 
            "policies": (
                MockAdmissionPolicy(allowed=True),
                MockAdmissionPolicy(allowed=True)
            ),
            "working_directory": "/tmp"
        },
        "command": "ls -la",
        "call": TerminalRequest(command="ls -la"),
        # technically we should check whether it has a uuid session id
        "expected": lambda terminal_result: len(terminal_result.session_id) > 0
    },
    # session_id specified and existing session -> command executes in
    # existing session (how do you test it with mock bash)
]

@pytest.mark.parametrize("test_case", _TERMINAL_CALL_TESTS)
def test_terminal(test_case, monkeypatch):
    monkeypatch.setattr(
        target=ai_ops.core.tools.terminal.terminal,
        name="BashSession",
        value=functools.partial(
            MockBashSession, 
            output=f"Ran `{test_case['command']}`"
        )
    )

    terminal_tool = Terminal(**test_case["init"])
    terminal_result = terminal_tool(test_case["call"])
    expected = test_case["expected"]

    if isinstance(expected, TerminalResult): 
        assert terminal_result == expected
    else:
        assert expected(terminal_result) is True