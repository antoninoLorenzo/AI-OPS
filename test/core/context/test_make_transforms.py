from ai_ops.core.context.transform import ContextTransform
import pytest

from ai_ops.core.runner import AgentSpec
from ai_ops.core.context import (
    ContextTransformType, 
    ContextTransformSettings, 
    ContextTransform,
    ContextTransformRegistry,
    CheckpointCompaction,
    TerminalOutputCompaction,
    ReasoningCompaction,
    DEFAULT_CONTEXT_TRANSFORMS
)
from ai_ops.core.context._terminal import TerminalOutputCompactionConfig

_INIT_SETTINGS = [
    {
        "context_transforms": [
            {"kind": str(ctx_settings.kind), "config": ctx_settings.config.model_dump()} 
            for ctx_settings in DEFAULT_CONTEXT_TRANSFORMS
        ],
        "raises": None
    },
    {
        "context_transforms": [
            {"kind": str(ContextTransformType.REASONING)},
            {
                "kind": str(ContextTransformType.TERMINAL), 
                "config": TerminalOutputCompactionConfig(terminal_alias="my-term").model_dump()
            }
        ],
        "raises": None
    },
    {
        "context_transforms": [
            {"kind": "not-exists"}
        ],
        "raises": ValueError
    }
]

@pytest.mark.parametrize("test_case", _INIT_SETTINGS)
def test_initialize_transforms(test_case):  
    agent_spec = AgentSpec(context_transforms=test_case["context_transforms"])

    if test_case["raises"]:
        with pytest.raises(test_case["raises"]):
            agent_spec.build_config()
        return
    agent_config = agent_spec.build_config()

    context_transforms = []
    for ctx_settings in agent_config.context_transforms:
        assert isinstance(ctx_settings, ContextTransformSettings)

        ctx_cls = ContextTransformRegistry[ctx_settings.kind]
        assert issubclass(ctx_cls, ContextTransform)

        config_cls = ctx_cls.config_schema()
        if config_cls is not None and ctx_settings.config is not None:
            ctx_config = ctx_settings.config.model_dump()
        else:
            ctx_config = {}
        
        if ctx_cls.requires_state:
            ctx_config["tools"] = ["not-a-tool"]
        
        context_transforms.append(ctx_cls(**ctx_config))


