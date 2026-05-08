import pytest

from ai_ops.core.context_management import raw_context_view
from ai_ops.core.conversation import Message


def test_raw_context_view_deep_copy():
    messages = [
        Message(message={"role": "system", "content": "U're a good boy"}),
        Message(message={"role": "user", "content": "Wyd u up?"})
    ]

    context = raw_context_view(messages)
    context[1].message["content"] += "Ephemeral info"

    assert "Ephemeral info" not in messages[1].message["content"]
    
