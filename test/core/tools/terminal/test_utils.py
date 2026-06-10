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
    # TODO: fix this edge case (see core.tools.utils)
    # {
    #     "command": "sudo docker ps -a",
    #     "expected": {"sudo", "docker"}
    # },
    # {
    #     "command": "   sudo   systemctl restart $(cat service_name)   ",
    #     "expected": {"sudo", "systemctl", "cat"}
    # },
    # {
    #     "command": "sudo -l",
    #     "expected": {"sudo"}
    # }
]

@pytest.mark.parametrize("test_case", _EXTRACT_EXECUTABLE_TESTS)
def test_extract_executables(test_case):
    assert extract_executables(test_case["command"]) == test_case["expected"]
    if test_case["command"] == "sudo -l":
        pytest.fail(reason="jomama")
        