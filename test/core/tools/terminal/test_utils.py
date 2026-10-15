import pytest

from ai_ops.core.tools.terminal.utils import extract_executables


_EXTRACT_EXECUTABLE_TESTS = [
    {
        "command": "echo $(cat secret)",
        "expected": {"echo", "cat"}
    },
    {
        "command": "cat names.txt | grep -i smith | wc -l",
        "expected": {"cat", "grep", "wc"}
    },
    {
        "command": "mkdir build && cd build && cmake .. || echo 'Build failed'",
        "expected": {"mkdir", "cd", "cmake", "echo"}
    },
    {
        "command": "echo \"Today is `date`\"",
        "expected": {"echo", "date"}
    },
    {
        # 'grep' is inside a literal string, not executed
        "command": "echo 'grep pattern file.txt'",  
        "expected": {"echo"}
    },
    {
        # process substitution
        "command": "echo <(ls -l $(cat file.txt))",
        "expected": {"echo", "ls", "cat"}
    },
    {
        "command": "sudo docker ps -a",
        "expected": {"sudo", "docker"}
    },
    {
        "command": "   sudo   systemctl restart $(cat service_name)   ",
        "expected": {"sudo", "systemctl", "cat"}
    },
    {
        "command": "sudo -l",
        "expected": {"sudo"}
    },
    {
        # the bug this fixes: without special-casing `sudo` (and the
        # other transparent wrapper commands), only `sudo` was ever
        # extracted here, so the allowlist policy never saw `rm` at all
        # and a blocked command could be smuggled straight through it.
        "command": "sudo rm -rf /",
        "expected": {"sudo", "rm"}
    },
    {
        "command": "doas whoami",
        "expected": {"doas", "whoami"}
    },
    {
        # a duration-taking wrapper's own positional argument must not
        # be mistaken for the wrapped command -- flagging it would
        # require confirmation on every ordinary use of `timeout`, not
        # just malicious ones.
        "command": "timeout 10 nmap -sS 10.0.0.1",
        "expected": {"timeout"}
    }
]

@pytest.mark.parametrize("test_case", _EXTRACT_EXECUTABLE_TESTS)
def test_extract_executables(test_case):
    assert extract_executables(test_case["command"]) == test_case["expected"]
        