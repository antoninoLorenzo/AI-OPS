import os

from evaluation.pipeline.stage.evaluation import Evaluation, EvaluationTask, EvaluationSettings
from evaluation.pipeline.stage.inference import (
    InferenceSettings,
    AssistantFactory, 
    ConversationType,
    DefaultAssistant,                                
    DefaultAssistantFactory, 
    Inference,                               
    InferenceExecutor, 
    InferenceTask
)

os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'


SUPPORTED_ARCHITECTURES = {
    'default': DefaultAssistantFactory
}

def get_assistant_factory(architecture: str) -> AssistantFactory:
    if architecture == 'default':
        return SUPPORTED_ARCHITECTURES['default']
    raise NotImplementedError(f'{architecture} architecture is not supported.')


__all__ = [
    "InferenceSettings",
    "InferenceExecutor",
    "AssistantFactory",
    "DefaultAssistant",
    "DefaultAssistantFactory",
    "ConversationType",
    "InferenceTask",
    "Inference",
    "EvaluationSettings",
    "EvaluationTask", 
    "Evaluation",
    "get_assistant_factory"
]
