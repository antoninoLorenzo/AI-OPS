import time
import functools
from typing import Callable

import pytest

from ai_ops.core.tools.terminal.bash import BashSession, CommandOutput, CommandStatus


def output_expected(
    command_output: CommandOutput, 
    runtime: float, # seconds
    timeout: float,
    expected_status: CommandStatus, 
    should_timeout: bool,
    eps: float = 0.2
) -> bool:
    if command_output.status != expected_status:
        return False, f"status={command_output.status}; expected={expected_status}"
    if command_output.timed_out != should_timeout:
        return False, f"timed_out={command_output.timed_out}; should_timeout={should_timeout}"
    if (runtime >= timeout - eps) and not should_timeout:
        return False, f"runtime={runtime}; timeout={timeout}; should_timeout={should_timeout}"

    return True, ""


_BASH_SESSION_TESTS = [
    # check working directory is the expected
    {
       "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": "pwd"}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected, 
                    timeout=5.0,
                    expected_status=CommandStatus.OK,
                    should_timeout=False
                ),
                # we don't have access to tmp_dir there so instead of doing 
                # `assert out == exp` we have to do `assert output(out, exp) is True`
                "output": lambda out, exp: out == exp
            }
        ] 
    },
    # --- non interactive
    # command not found -> status not found, completes before timeout 
    {
        "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": "notexist"}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected, 
                    timeout=5.0,
                    expected_status=CommandStatus.NOT_FOUND,
                    should_timeout=False
                ),
                "output": None
            }
        ]
    },
    # custom timeout handling
    {
        "init_parameters": {"default_timeout": 30.0},
        "commands": [
            {"command": "sleep 30", "timeout": 3.0}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected, 
                    timeout=3.0,
                    expected_status=CommandStatus.KILLED,
                    should_timeout=True
                ),
                "output": None
            }
        ]
    },
    # timeout exceeded + command -> timeout + command result
    {
        "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": "sleep 30"},
            {"command": "echo 'Hello'"}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected,
                    timeout=5.0,
                    expected_status=CommandStatus.KILLED,
                    should_timeout=True
                ),
                "output": None
            },
            {
                "callback": functools.partial(
                    output_expected,
                    timeout=5.0,
                    expected_status=CommandStatus.OK,
                    should_timeout=False
                ),
                "output": "Hello"
            }
        ]
    },
    # --- interactive
    # interactive command improperly flagged + basic command -> timeout + expected output
    {
        "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": "sudo su"},
            {"command": "echo 'Hello'"}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected,
                    timeout=5.0,
                    expected_status=CommandStatus.KILLED,
                    should_timeout=True
                ),
                "output": None
            },
            {
                "callback": functools.partial(
                    output_expected,
                    timeout=5.0,
                    expected_status=CommandStatus.OK,
                    should_timeout=False
                ),
                "output": "Hello"
            }
        ]  
    },
    # exit from interactive command 
    {
        "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": f"echo 'Hello' > interactive"},
            {"command": "tail -f interactive", "interactive": True},
            {"command": "Ctrl+C"}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected,
                    timeout=5.0,
                    expected_status=CommandStatus.OK,
                    should_timeout=False
                ),
                "output": None
            },
            {
                "callback": functools.partial(
                    output_expected,
                    timeout=5.0,
                    expected_status=CommandStatus.UNKNOWN,
                    should_timeout=False # should/shouldn't?
                ),
                "output": "Hello"
            },
            {
                "callback": functools.partial(
                    output_expected,
                    timeout=5.0,
                    expected_status=CommandStatus.UNKNOWN,
                    should_timeout=False
                ),
                "output": None
            }
        ]
    },
    # command substitution
    {
        "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": "echo \"result: $(echo hello)\""}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected, timeout=5.0,
                    expected_status=CommandStatus.OK, should_timeout=False
                ),
                "output": "result: hello"
            }
        ]
    },
    # assignment via command substitution
    {
        "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": "R1=$(echo 404); echo \"Sample 1: $R1\""}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected, timeout=5.0,
                    expected_status=CommandStatus.OK, should_timeout=False
                ),
                "output": "Sample 1: 404"
            }
        ]
    },
    # multi-line for loop
    {
        "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": "for p in a b c; do\n  echo \"item: $p\"\ndone"}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected, timeout=5.0,
                    expected_status=CommandStatus.OK, should_timeout=False
                ),
                "output": "item: a\r\nitem: b\r\nitem: c\r\n"
            }
        ]
    },
    {
    "init_parameters": {"default_timeout": 5.0},
        "commands": [
            {"command": "echo one\necho two\necho three"}
        ],
        "expected": [
            {
                "callback": functools.partial(
                    output_expected, timeout=5.0,
                    expected_status=CommandStatus.OK, should_timeout=False
                ),
                "output": "one\r\ntwo\r\nthree"
            }
        ]
    },
]

@pytest.mark.parametrize("test_case", _BASH_SESSION_TESTS)
def test_bash_session(test_case, tmp_path):
    bash = BashSession(working_directory=str(tmp_path), **test_case["init_parameters"])

    print("\n### --- DEBUG")
    for command, expected in zip(test_case["commands"], test_case["expected"]):
        print(command["command"])
        
        s = time.monotonic()
        command_output = bash.run(**command)
        runtime = time.monotonic() - s

        print(command_output.output)

        callback = expected["callback"]
        if callback is not None:
            passed, err = callback(command_output=command_output, runtime=runtime)
            assert passed is True, err

        expected_output = expected["output"]
        if expected_output is not None:
            if isinstance(expected_output, str):
                # we could losen up if we check `expected_output in command_output.output`
                assert command_output.output.strip() == expected_output.strip()
            elif isinstance(expected_output, Callable):
                assert expected_output(command_output.output.strip(), str(tmp_path)) is True
