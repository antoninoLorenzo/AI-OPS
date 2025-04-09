import os
from typing import List, Dict

import google.generativeai as genai
from dotenv import load_dotenv
from deepeval.metrics import (
    HallucinationMetric, 
    BaseConversationalMetric, 
    BaseMetric
)

from evaluation.core.judge import GeminiLLM
from evaluation.core.schema import Stage, Stream, Task
from evaluation.core.stream import JSONFileStream, QueueStream
from evaluation.core.utils import (
    conversation_to_test_case, 
    gen_checkpoint_id, 
    verify_checkpoint_id
)

os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'

SUPPORTED_METRICS = {
    'hallucination': HallucinationMetric
}

SUPPORTED_JUDGES = ('gemini',)

def get_judge(model: str):
    if 'gemini' in model:
        # setup api key for gemini
        load_dotenv()
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        genai.configure(api_key=GEMINI_API_KEY)
        
        return GeminiLLM(model=model)
    raise NotImplementedError(f'model {model} is not supported.')


def get_metrics(
    metrics: List[str], 
    settings: Dict[str, any]
) -> Dict[str, BaseMetric | BaseConversationalMetric]:
    result = {}
    
    for metric in metrics:
        if metric not in SUPPORTED_METRICS.keys():
            raise NotImplementedError(f'metric {metric} is not supported.')
        Metric = SUPPORTED_METRICS[metric]
        result[metric] = Metric(**settings)
    
    return result


__all__ = [
    "Task",
    "Stream",
    "Stage",
    "JSONFileStream",
    "QueueStream",
    "GeminiLLM",
    "conversation_to_test_case",
    "get_judge",
    "get_metrics"
    "gen_checkpoint_id", 
    "verify_checkpoint_id"
]