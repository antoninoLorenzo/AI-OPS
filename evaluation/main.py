import sys
import argparse

from evaluation.pipeline import Orchestrator
from evaluation.pipeline.stage import InferenceSettings, EvaluationSettings
from src.utils import get_logger


LOGGER = get_logger('pipeline')


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--models',
        type=str,
        required=True
    )

    parser.add_argument(
        '--inference-endpoint',
        type=str,
        required=True
    )

    parser.add_argument(
        '--architecture',
        type=str,
        default='default',
        required=False
    )

    parser.add_argument(
        '--judge',
        type=str,
        default='gemini-2.0-flash',
        required=False
    )

    parser.add_argument(
        '--metrics',
        type=str,
        default='hallucination',
        required=False
    )

    arguments = parser.parse_args(sys.argv[1:])

    inference_settings = InferenceSettings(
        architecture=arguments.architecture,
        models=[model.strip() for model in arguments.models.split(',')],
        inference_endpoint=arguments.inference_endpoint
    )
    LOGGER.debug(f'inference settings: {inference_settings}')

    evaluation_settings = EvaluationSettings(
        judge_model=arguments.judge,
        metrics=[metric.strip() for metric in arguments.metrics.split(',')]
    )
    LOGGER.debug(f'evaluation settings: {evaluation_settings}')

    orchestrator = Orchestrator(inference_settings, evaluation_settings)
    orchestrator.run()


if __name__ == "__main__":
    # example: 
    # python -m evaluation.main --models mistral:7b-instruct-v0.3-q8_0 --inference-endpoint http://localhost:8080
    try:
        main()
    except KeyboardInterrupt:
        pass
