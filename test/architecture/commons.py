import os
import json
import time
import threading
from pathlib import Path

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core.exceptions import ResourceExhausted
from deepeval.models import DeepEvalBaseLLM
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase
from tqdm import tqdm

from src.core.llm import LLM

# disable deep eval telemetry
os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
os.environ['ERROR_REPORTING'] = 'YES'


class Throttler:
    """A rate-limiter to avoid getting blocked by LLM providers (such as
    Gemini). Useful to scale up evaluation. """

    def __init__(self, requests_per_minute: int = 15):
        self.__quota = requests_per_minute
        self.__counter = 0
        self.__elapsed = 0
        self.__exceeded = False
        self.__lock = threading.Lock()

    @property
    def exceeded(self) -> bool:
        with self.__lock:
            return self.__exceeded

    @property
    def counter(self) -> int:
        with self.__lock:
            return self.__counter

    @counter.setter
    def counter(self, value: int):
        with self.__lock:
            self.__counter = value

    def run(self):
        while True:
            time.sleep(1)
            self.__elapsed += 1

            with self.__lock:
                if self.__counter >= self.__quota:
                    self.__exceeded = True
                else:
                    self.__exceeded = False

                # Reset after a minute
                if self.__elapsed == 60:
                    self.__elapsed = 0
                    self.__counter = 0


class GeminiJudgeLLM(DeepEvalBaseLLM):
    """Gemini interface to use as a judge for DeepEval metrics."""
    def __init__(self, *args, **kwargs):
        self.__llm = genai.GenerativeModel('gemini-1.5-flash')
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
        }
        self.generation_config = {
            'temperature': 0.5,
        }

        # avoid getting blocked and loosing computed metrics
        self.throttler = Throttler(requests_per_minute=15)
        self.__throttler_thread = threading.Thread(target=self.throttler.run, daemon=True)
        self.__throttler_thread.start()

        super().__init__(*args, **kwargs)

    def __generate(self, prompt: str) -> str:
        return self.__llm.generate_content(
            prompt,
            safety_settings=self.safety_settings,
            generation_config=self.generation_config
        ).text

    def generate(self, prompt: str) -> str:
        try:
            # increment number of requests, if maximum number of requests
            # is reached wait to restart.
            while self.throttler.exceeded:
                print("[!] Throttle limit exceeded. Waiting 60 seconds...")
                time.sleep(60)
            self.throttler.counter += 1

            return self.__generate(prompt)
        except ResourceExhausted as err:
            raise RuntimeError(f'[!] {err}')

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def load_model(self, *args, **kwargs):
        return self.__llm

    def get_model_name(self, *args, **kwargs) -> str:
        return 'gemini-1.5-flash'


def setup():
    from dotenv import load_dotenv

    load_dotenv()
    MODEL = os.getenv('MODEL')
    ENDPOINT = os.getenv('ENDPOINT')

    MODEL = LLM(model=MODEL, inference_endpoint=ENDPOINT)
    for _ in MODEL.query([{'role': 'user', 'content': 'Hi'}]):
        pass

    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    genai.configure(api_key=GEMINI_API_KEY)
    JUDGE = GeminiJudgeLLM()

    return MODEL, JUDGE


def load_prompt(name: str) -> str:
    """Get the prompt for a component in the default architecture."""
    current = str(Path(__file__))
    prompt_path = (
            Path(current[:current.find('test')])
            / 'src'
            / 'agent'
            / 'architectures'
            / 'default'
            / 'prompts'
    )
    with open(str(prompt_path / name), 'r', encoding='utf-8') as fp:
        return fp.read()


def load_tests(name: str) -> list[dict]:
    """Load JSON test cases for a component in the default architecture."""
    current = str(Path(__file__))
    datasets_path = (
            Path(current[:current.find('test')])
            / 'test'
            / 'architecture'
            / 'datasets'
    )
    with open(str(datasets_path / name), 'r', encoding='utf-8') as fp:
        return json.load(fp)


def save_tests(tests: list[dict], name: str):
    """Save (or add) the results for a component tests."""
    current = str(Path(__file__))
    datasets_path = (
            Path(current[:current.find('test')])
            / 'test'
            / 'architecture'
            / 'datasets'
    )

    # check if the file contains previous results (ex. other models)
    # if that's the case merge current results (tests) with previous ones
    contains_results = False
    try:
        with open(str(datasets_path / name), 'r', encoding='utf-8') as fp:
            previous_data: list[dict] = json.load(fp)
        contains_results = True
    except json.JSONDecodeError:
        pass

    if contains_results:
        tests.extend(previous_data)

    with open(str(datasets_path / name), 'w', encoding='utf-8') as fp:
        json.dump(tests, fp, indent="\t")


def run_tests(
        model: LLM,
        prompt: str,
        test_cases: list[dict],
        metrics: dict[str, BaseMetric]
) -> None:
    """Execute the evaluation test cases for a given architecture component.

    Note: Computed values (response, metrics etc.) are added in-place.

    :param model: an instance of a LLM client.
    :param prompt: the prompt of the architecture component.
    :param test_cases: a list of test cases for the architecture component.
    :param metrics: metrics to evaluate the architecture component.
    """
    # TODO: add some fault tolerance
    for i, test_case in tqdm(enumerate(test_cases), total=len(test_cases)):
        test_case['model'] = model.model
        # Generate response for current test case input
        messages = [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': test_case['input']}
        ]

        response = ""
        for chunk, _ in model.query(messages=messages):
            response += chunk
        test_cases[i]['response'] = response

        # compute metrics for generated response
        for metric_name, metric in metrics.items():
            expected_output = test_case['expected_output'] \
                if test_case['expected_output'] \
                else None

            metric.measure(
                LLMTestCase(
                    input=test_case['input'],
                    actual_output=response,
                    expected_output=expected_output
                )
            )

            test_cases[i][metric_name] = metric.score
            test_cases[i][f'{metric_name}_reason'] = metric.reason
