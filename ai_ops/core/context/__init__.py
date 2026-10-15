from ai_ops.core.context._checkpoint import CheckpointCompaction
from ai_ops.core.context._reasoning import ReasoningCompaction
from ai_ops.core.context._terminal import TerminalOutputCompaction
from ai_ops.core.context.transform import (
    DEFAULT_CONTEXT_TRANSFORMS,
    ContextTransform,
    ContextTransformType,
    ContextTransformSettings,
    build_context,
)

ContextTransformRegistry: dict[ContextTransformType, type[ContextTransform]] = {
    ContextTransformType.CHECKPOINT: CheckpointCompaction,
    ContextTransformType.REASONING: ReasoningCompaction,
    ContextTransformType.TERMINAL: TerminalOutputCompaction
}
