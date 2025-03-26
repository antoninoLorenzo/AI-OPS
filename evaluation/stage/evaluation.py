from pathlib import Path
from typing import Any, Dict, Union

from deepeval.metrics import BaseConversationalMetric, BaseMetric
from pydantic import ConfigDict

from evaluation.core import (JSONFileStream, QueueStream, Stage, Task,
                             conversation_to_test_case)
from src.core.memory import Conversation
from src.utils import get_logger

LOGGER = get_logger(__name__)


class EvaluationTask(Task):
    """
    Represents the input for the Evaluation Stage. 

    :param conversation: the Conversation to evaluate.
    :param metric: the DeepEval metric to use for evaluation.
    :param metric_name: the name of the DeepEval metric.
    :param test_case_parameters: additional parameters for the DeepEval LLMTestCase metric.
    :param metadata: data to add in the output (not relly defined)
    """
    conversation: Conversation
    metric: Union[BaseMetric, BaseConversationalMetric]
    # this is required because DeepEval doesn't provide any way to 
    # determine a metric name from BaseMetric or BaseConversationalMetric
    metric_name: str    
    test_case_parameters: Dict[str, Any]
    metadata: Dict[str, Any]

    # BaseMetric and BaseConversationalMetric aren't allowed as 
    # parameters for a BaseModel subclass, thanks DeepEval.
    model_config = ConfigDict(arbitrary_types_allowed=True)


class Evaluation(Stage):
    """
    Implements the Evaluation Stage execution logic.
    """
    def __init__(self, output_path: str):
        self.output_path = Path(output_path)

    def run(self, task_stream: QueueStream):
        with JSONFileStream(output_path=self.output_path) as output_stream:
            try:
                for task in task_stream:
                    if not isinstance(task, EvaluationTask):
                        raise ValueError(f'expected EvaluationTask: got {type(task)}')
                    
                    # run metric evaluation
                    test_case = conversation_to_test_case(
                        conversation=task.conversation,
                        **task.test_case_parameters
                    )
                    metric = task.metric
                    metric.measure(test_case)

                    # write output to json file
                    output = {
                        'metric_name': task.metric_name,
                        'score': metric.score,
                        'reason': metric.reason
                    }
                    output.update(task.metadata)
                    
                    # note: JSONStream takes in input a list of dicitonaries
                    output_stream.send([output])
            except Exception as err:
                # if (when...) measuring a metric fails, for example because of rate limiting
                # from Gemini, we want (1) fail gracefully (2) avoid computing metrics again; 
                # the metrics are saved as they are computed, also the try/catch is inside the 
                # with block, this way the stream is closed properly and no data is lost.
                LOGGER.error(f'exit: error in the Evaluation Stage: {err}')
