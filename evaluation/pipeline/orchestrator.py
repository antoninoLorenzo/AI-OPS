import sys
import json
import time
import threading
from pathlib import Path
from typing import List

from pydantic import BaseModel

from evaluation.core import QueueStream, get_judge, get_metrics
from evaluation.pipeline.stage import (
    InferenceSettings,
    InferenceExecutor,
    AssistantFactory,
    ConversationType,
    InferenceTask,
    Inference,
    EvaluationSettings,
    EvaluationTask,
    Evaluation,
    get_assistant_factory
)
from src.core import Conversation, Message, Role
from src.utils import get_logger


LOGGER = get_logger(__name__)


class Item(BaseModel):
    evaluation_id: str
    conversation_name: str
    user_input: str
    context: List[str]


Dataset = List[Item]


class Orchestrator:

    def __init__(
        self, 
        inference_settings: InferenceSettings, 
        evaluation_settings: EvaluationSettings
    ):
        try:
            # initialize dataset
            current_path = str(Path(__file__))
            self.dataset_path = (
                Path(current_path[:current_path.find('evaluation')])
                / 'evaluation'
                / 'resources'
                / 'dataset.json'
            )
            with open(str(self.dataset_path), 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                self.dataset = [Item.model_validate(item) for item in data]
            
            # specify output path to pass in Evaluation Stage
            self.output_path = (
                Path(current_path[:current_path.find('evaluation')])
                / 'evaluation'
                / 'resources'
                / 'results.json'
            )

            # initialize inference related resources
            self.__factory : AssistantFactory = get_assistant_factory(inference_settings.architecture)()
            # An assistant for each specified model is created, in order to compare models.
            # Note: in that case we assume a AssistantFactory takes in input the parameters
            # model and inference_endpoint, however for some other architecture/configuration
            # it may not be true -> TODO: solve design issue
            self.__assistants : List[InferenceExecutor] = []
            for model in inference_settings.models:
                self.__assistants.append(
                    self.__factory.build_assistant(
                        model=model, 
                        inference_endpoint=inference_settings.inference_endpoint
                    )
                )

            # initialize evaluation related resources
            self.__judge_llm = get_judge(evaluation_settings.judge_model)
            self.__metrics = get_metrics(evaluation_settings.metrics, {'model': self.__judge_llm})
        except Exception as err:
            print(f'failed initializing pipeline: {err}')
            sys.exit(1)

    def run(self):
        # initialize components
        inference_runner = Inference()
        inference_task_stream = QueueStream()

        evaluation = Evaluation(str(self.output_path))
        evaluation_task_stream = QueueStream()

        # start the inference task producer 
        # note: it should be pretty fast since there's no actual overhead
        threading.Thread(
            target=self.__inference_task_producer, 
            args=(inference_task_stream,), 
            daemon=True
        ).start()
        LOGGER.debug('started inference task producer thread')

        # start the evaluation task producer
        threading.Thread(
            target=self.__evaluation_task_producer,
            args=(inference_runner, inference_task_stream, evaluation_task_stream),
            daemon=True
        ).start()
        LOGGER.debug('started evaluation task producer thread')
        
        # a mechanism to start the evaluation stage only when at least one result 
        # from the inference stage is available is needed -> TODO: design issue :(
        time.sleep(15)
        LOGGER.debug('starting evaluation stage')
        evaluation.run(evaluation_task_stream)

    def __inference_task_producer(self, stream: QueueStream):
        current = str(Path(__file__))
        log_path = (
            Path(current[:current.find('evaluation')])
            / 'evaluation'
            / 'logs'
            / 'inference.log'
        )
        inference_logger = get_logger(__name__, output_file=log_path)
        inference_logger.info('loaded inference task producer')

        # each assistant configuration should be tested against each input test case
        for assistant in self.__assistants:
            inference_logger.debug(
                f'inference tasks for {assistant.architecture_name}[{assistant.model}]'
            )

            for idx, item in enumerate(self.dataset):
                conversation = Conversation(
                    conversation_id=idx,
                    name=item.conversation_name,
                    messages=[Message(role=Role.USER, content=item.user_input)]
                )
                
                inference_task = InferenceTask(
                    assistant=assistant,
                    conversation=conversation,
                    conversation_type=ConversationType.SingleTurn
                )

                stream.send(inference_task)
                inference_logger.info(
                    f'sent task to inference stage: {conversation.conversation_id}_'
                    f'{inference_task.assistant.architecture_name}[{assistant.model}]'
                )

        # puts a None sentinel in the queue so the inference stage knows when should stop
        stream.stop()
        inference_logger.debug('sent stop signal to inference stream')

    def __evaluation_task_producer(
        self, 
        inference_runner: Inference, 
        inference_task_stream: QueueStream,
        evaluation_task_stream = QueueStream
    ):
        # setup logging
        current = str(Path(__file__))
        log_path = (
            Path(current[:current.find('evaluation')])
            / 'evaluation'
            / 'logs'
            / 'evaluation.log'
        )
        evaluation_logger = get_logger(__name__, output_file=log_path)
        evaluation_logger.info('loaded evaluation task producer')

        # fetch generated conversations and send evaluation tasks to Evaluation stage
        evaluation_logger.debug('starting inference stage')
        try:
            for conversation in inference_runner.run(inference_task_stream):
                evaluation_logger.debug(f'sending conversation {conversation.conversation_id} to evaluation stage')

                dataset_item = self.dataset[conversation.conversation_id]
                for metric_name, metric in self.__metrics.items():
                    task = EvaluationTask(
                        conversation=conversation,
                        metric=metric,
                        metric_name=metric_name,
                        test_case_parameters={'context': dataset_item.context},
                        metadata={
                            'evaluation_id': dataset_item.evaluation_id
                        }
                    )   

                    evaluation_task_stream.send(task)
                    evaluation_logger.info(
                        f'sent task to evaluation stage: '
                        f'{task.conversation.conversation_id}_{task.metric_name}'
                    )
        except RuntimeError as err:
            LOGGER.error(f'stopping evaluation task producer: {err}')
            
        evaluation_task_stream.stop()
        evaluation_logger.debug('sent stop signal to evaluation stream.')

