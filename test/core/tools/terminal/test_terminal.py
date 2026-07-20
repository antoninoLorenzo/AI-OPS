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


# --- admission (evaluate)
# Policy evaluation is split from execution: `evaluate` returns True when the
# command is blocked (any policy denies) and must go through the confirmation
# path, False when it can execute directly.
_TERMINAL_EVALUATE_TESTS = [
    # any policy denies -> blocked
    {
        "init": {
            "conversation_id": "1234",
            "policies": (
                MockAdmissionPolicy(allowed=True),
                MockAdmissionPolicy(allowed=False)
            ),
        },
        "call": TerminalRequest(command="nc -lnvp 4444", session_id="bash-1234"),
        "blocked": True
    },
    # all policies allow -> not blocked
    {
        "init": {
            "conversation_id": "1234",
            "policies": (
                MockAdmissionPolicy(allowed=True),
                MockAdmissionPolicy(allowed=True)
            ),
        },
        "call": TerminalRequest(command="ls -la", session_id="bash-1234"),
        "blocked": False
    },
    # no policies -> not blocked
    {
        "init": {
            "conversation_id": "1234",
            "policies": (),
        },
        "call": TerminalRequest(command="ls -la", session_id="bash-1234"),
        "blocked": False
    },
]


@pytest.mark.parametrize("test_case", _TERMINAL_EVALUATE_TESTS)
def test_terminal_evaluate(test_case, tmp_path):
    terminal_tool = Terminal(working_directory=tmp_path, **test_case["init"])
    assert terminal_tool.evaluate(test_case["call"]) is test_case["blocked"]


def test_terminal_requires_confirmation():
    assert Terminal.requires_confirmation is True


def test_terminal_not_admitted_result(tmp_path):
    terminal_tool = Terminal(
        working_directory=tmp_path,
        conversation_id="1234",
        policies=(MockAdmissionPolicy(allowed=False),)
    )
    call = TerminalRequest(command="nc -lnvp 4444", session_id="bash-1234")
    assert terminal_tool.not_admitted_result(call) == TerminalResult(
        session_id="bash-1234",
        command="nc -lnvp 4444",
        allowed=False
    )


# --- execution (__call__)
# `__call__` assumes the call was already admitted, so it no longer consults the
# policies; it just runs the command in the (new or reused) session.
_TERMINAL_CALL_TESTS = [
    # explicit session_id -> command executes in that session
    {
        "init": { "conversation_id": "1234", "policies": () },
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
    # session_id None -> command executes in a new session
    {
        "init": { "conversation_id": "1234", "policies": () },
        "command": "ls -la",
        "call": TerminalRequest(command="ls -la"),
        # technically we should check whether it has a uuid session id
        "expected": lambda terminal_result: len(terminal_result.session_id) > 0
    },
    # a policy that would deny is irrelevant to __call__ (admission is `evaluate`'s
    # job) -> the command still executes
    {
        "init": {
            "conversation_id": "1234",
            "policies": (MockAdmissionPolicy(allowed=False),)
        },
        "command": "nc -lnvp 4444",
        "call": TerminalRequest(command="nc -lnvp 4444", session_id="bash-1234"),
        "expected": TerminalResult(
            session_id="bash-1234",
            command="nc -lnvp 4444",
            allowed=True,
            output="Ran `nc -lnvp 4444`",
            status=CommandStatus.OK
        )
    },
]


@pytest.mark.parametrize("test_case", _TERMINAL_CALL_TESTS)
def test_terminal(test_case, monkeypatch, tmp_path):
    monkeypatch.setattr(
        target=ai_ops.core.tools.terminal.terminal,
        name="BashSession",
        value=functools.partial(
            MockBashSession,
            output=f"Ran `{test_case['command']}`"
        )
    )

    terminal_tool = Terminal(working_directory=tmp_path, **test_case["init"])
    terminal_result = terminal_tool(test_case["call"])
    expected = test_case["expected"]

    if isinstance(expected, TerminalResult):
        assert terminal_result == expected
    else:
        assert expected(terminal_result) is True
