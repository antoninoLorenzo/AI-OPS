from pathlib import Path
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Union, List

from deepeval.metrics import BaseConversationalMetric, BaseMetric
from pydantic import ConfigDict

from evaluation.core import (
    JSONFileStream, 
    QueueStream, 
    Stage, 
    Task,
    conversation_to_test_case
)
from src.core.memory import Conversation
from src.utils import get_logger

current = str(Path(__file__))
log_path = (
    Path(current[:current.find('evaluation')])
    / 'evaluation'
    / 'logs'
    / 'evaluation.log'
)
LOGGER = get_logger(__name__, output_file=log_path)


@dataclass
class EvaluationSettings:
    judge_model: str
    metrics: List[str]

    def __str__(self):
        mtrcs = ', '.join(self.metrics)
        return (
            f"model: {self.judge_model}; "
            f"metrics: {mtrcs}"
        )


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
                    output = {}
                    output.update(task.metadata)
                    output.update({
                        'metric_name': task.metric_name,
                        'score': metric.score,
                        'reason': metric.reason,
                        'conversation': task.conversation.model_dump()
                    })
                    
                    # note: JSONStream takes in input a list of dicitonaries
                    output_stream.send([output])
                    
                    identifier = f'{task.conversation.conversation_id}_{task.conversation.name}'
                    LOGGER.info(
                        f'completed {task.metric_name}_{identifier} evaluation'
                    )
            except Exception as err:
                LOGGER.error(f'exit: error in the Evaluation Stage: {err}')
