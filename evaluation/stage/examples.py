import os
import threading
import time
from datetime import datetime

import google.generativeai as genai
from deepeval.metrics import HallucinationMetric
from dotenv import load_dotenv

from evaluation.core import GeminiLLM, QueueStream
from evaluation.stage.evaluation import Evaluation, EvaluationTask
from evaluation.stage.inference import (ConversationType,
                                        DefaultAssistantFactory, Inference,
                                        InferenceTask)
from src.core.memory import Conversation, Message, Role
from src.utils import get_logger

LOGGER = get_logger(__name__)


def inference_stage_example():
    load_dotenv()
    INFERENCE_ENDPOINT = os.environ.get('ENDPOINT', None)
    if INFERENCE_ENDPOINT is None:
        raise RuntimeError('missing ENDPOINT environment variable.')
    

    # setup task resources
    default_assistant = DefaultAssistantFactory().build_assistant(
        model='mistral:7b-instruct-v0.3-q8_0',
        inference_endpoint=INFERENCE_ENDPOINT
    )
    conversation = Conversation(
        conversation_id=1,
        name='untitled',
        messages=[Message(role=Role.USER, content='what is CSRF?')]
    )
    
    task = InferenceTask(
        assistant=default_assistant,
        conversation=conversation,
        conversation_type=ConversationType.SingleTurn
    )

    # setup the task producer
    def producer(stream: QueueStream):
        tasks = [task]
        for t in tasks:
            stream.send(t)
            time.sleep(3)
        stream.stop()

    queue_stream = QueueStream()
    threading.Thread(target=producer, args=(queue_stream,), daemon=True).start()
    LOGGER.info('task producer is running')

    # run the inference stage
    inference_runner = Inference()
    for output_conversation in inference_runner.run(queue_stream):
        print(
            f'{output_conversation.conversation_id}: {output_conversation.name}\n'
            '------------------------------------------------------------------\n'
        )
        for message in output_conversation.messages:
            print(f'{message.role}: {message.content}')


def evaluation_stage_example():
    # setup gemini
    load_dotenv()
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    genai.configure(api_key=GEMINI_API_KEY)
    judge = GeminiLLM()

    # setup the task
    conversation = Conversation(
        conversation_id=1,
        name='untitled',
        messages=[
            Message(role=Role.SYS, content='you are an useful AI Assistant'),
            Message(role=Role.USER, content='What is 2 + 2?'),
            Message(role=Role.ASSISTANT, content='that\'s 4 man')
        ]
    )

    metric = HallucinationMetric(model=judge)

    task = EvaluationTask(
        conversation=conversation,
        metric=metric,
        metric_name='hallucination',
        test_case_parameters={'context': ['the result of 2 + 2 is 4']},
        metadata={
            'evaluation-id': f'001_{datetime.today().strftime("%d-%m-%Y")}'
        }
    )

    # setup task producer
    def producer(stream: QueueStream):
        tasks = [task]
        for t in tasks:
            stream.send(t)
            time.sleep(3)
        stream.stop()

    queue_stream = QueueStream()
    threading.Thread(target=producer, args=(queue_stream,), daemon=True).start()
    # LOGGER.info('task producer is running')

    # setup evaluation stage
    evaluation_runner = Evaluation('output.json')
    evaluation_runner.run(task_stream=queue_stream)


if __name__ == "__main__":
    evaluation_stage_example()
