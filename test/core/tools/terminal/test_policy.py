import pytest

import ai_ops.core.tools.terminal.policy # to monkeypatch extract_executables
from ai_ops.core.tools.terminal.policy import (
    CommandContext, 
    AllowListPolicy, 
    PolicyResult, 
    PolicyError
)

from test.core.mocks.terminal import MockAdmissionPolicy



_ALLOW_LIST_POLICY_TESTS = [
    # both allowed and not -> block
    {
        "allowlist": ["cat"],
        "executables": {"export", "cat"},
        "call": CommandContext(session_id="1", command="export VAR=$(cat secret)"),
        "expected": PolicyResult(allowed=False, blocked={"export"})
    },
    # none allowed -> block
        {
        "allowlist": [],
        "executables": {"nc"},
        "call": CommandContext(session_id="1", command="nc -lnvp 4444"),
        "expected": PolicyResult(allowed=False, blocked={"nc"})
    },
    # allowed -> pass
        {
        "allowlist": ["ls"],
        "executables": {"ls"},
        "call": CommandContext(session_id="1", command="ls -la"),
        "expected": PolicyResult(allowed=True)
    }
]

@pytest.mark.parametrize("test_case", _ALLOW_LIST_POLICY_TESTS)
def test_allow_list_policy(test_case, monkeypatch):
    monkeypatch.setattr(
        target=ai_ops.core.tools.terminal.policy,
        name="extract_executables",
        value=lambda _: test_case["executables"]
    )

    policy = AllowListPolicy(allowlist=test_case["allowlist"])
    assert policy(test_case["call"]) == test_case["expected"]

