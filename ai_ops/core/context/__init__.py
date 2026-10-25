from ai_ops.core.context._checkpoint import CheckpointCompaction
from ai_ops.core.context._reasoning import ReasoningCompaction
from ai_ops.core.context._summary import SummarizationCompaction
from ai_ops.core.context._terminal import TerminalOutputCompaction
from ai_ops.core.context.transform import (
    DEFAULT_CONTEXT_TRANSFORMS,
    ContextTransform,
    ContextTransformSettings,
    ContextTransformType,
    build_context,
)

ContextTransformRegistry: dict[ContextTransformType, type[ContextTransform]] = {
    ContextTransformType.CHECKPOINT: CheckpointCompaction,
    ContextTransformType.REASONING: ReasoningCompaction,
    ContextTransformType.TERMINAL: TerminalOutputCompaction,
    ContextTransformType.SUMMARIZATION: SummarizationCompaction
}
