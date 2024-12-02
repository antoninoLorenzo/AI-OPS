import os
import json
import time
import threading
from pathlib import Path

import seaborn as sns
import matplotlib.pyplot as plt
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core.exceptions import ResourceExhausted
from deepeval.models import DeepEvalBaseLLM
from deepeval.metrics import BaseMetric, BaseConversationalMetric
from deepeval.test_case import LLMTestCase, ConversationalTestCase
from tqdm import tqdm

from src.core.llm import LLM
from src.agent import build_agent, Agent
from src.utils import get_logger

# disable deep eval telemetry
os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
os.environ['ERROR_REPORTING'] = 'YES'
logger = get_logger(__name__)


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


class GeminiLLM(DeepEvalBaseLLM):
    """Gemini interface."""
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


def setup_component_test_resources() -> tuple[LLM, GeminiLLM]:
    from dotenv import load_dotenv

    load_dotenv()
    MODEL = os.getenv('MODEL')
    ENDPOINT = os.getenv('ENDPOINT')

    MODEL = LLM(model=MODEL, inference_endpoint=ENDPOINT)
    for _ in MODEL.query([{'role': 'user', 'content': 'Hi'}]):
        pass

    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    genai.configure(api_key=GEMINI_API_KEY)
    JUDGE = GeminiLLM()

    return MODEL, JUDGE


def setup_system_test_resources() -> tuple[Agent, GeminiLLM]:
    from dotenv import load_dotenv

    load_dotenv()
    MODEL = os.getenv('MODEL')
    ENDPOINT = os.getenv('ENDPOINT')

    AGENT = build_agent(
        model=MODEL,
        inference_endpoint=ENDPOINT
    )
    # for _ in AGENT.query(0, 'Hi'):
    #     pass

    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    genai.configure(api_key=GEMINI_API_KEY)
    JUDGE = GeminiLLM()

    return AGENT, JUDGE


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
    try:
        with open(str(datasets_path / name), 'r', encoding='utf-8') as fp:
            return json.load(fp)
    except FileNotFoundError:
        return []


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
    except (json.JSONDecodeError, FileNotFoundError):
        pass

    if contains_results:
        tests.extend(previous_data)

    with open(str(datasets_path / name), 'w', encoding='utf-8') as fp:
        json.dump(tests, fp, indent="\t")


def run_component_tests(
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


def run_system_test(
    test_cases: list[dict],
    metrics: dict[str, BaseConversationalMetric],
    agent_model: str,
):
    for i, test_case in tqdm(
        enumerate(test_cases),
        total=len(test_cases),
        desc='Architecture Evaluation'
    ):
        test_case['model'] = agent_model
        for metric_name, metric in metrics.items():
            # Extract full conversation between user and assistant as turns.
            # IMPORTANT: full_conversation should start from a user message
            turns = [
                LLMTestCase(
                    input=user_message['content'],
                    actual_output=assistant_message['content']
                )
                for user_message, assistant_message in zip(
                    test_case['full_conversation'][::2],  # get odd elements
                    test_case['full_conversation'][1::2]  # get even elements
                )
            ]
            convo_test_case = ConversationalTestCase(turns=turns)
            metric.measure(convo_test_case)
            test_cases[i][metric_name] = metric.score
            test_cases[i][f'{metric_name}_reason'] = metric.reason


def check_conversations(
    test_case_path: str = 'default_architecture'
) -> bool:
    """Automatically decide whether conversations should be generated:
    if the base dataset (ex. default_architecture.json) is updated then
    return True, otherwise False."""
    test_cases = load_tests(f'{test_case_path}.json')
    conversation_test_cases = load_tests(f'{test_case_path}_conversations.json')

    if len(conversation_test_cases) == 0:
        # conversation file doesn't exist
        return True

    if len(test_cases) != len(conversation_test_cases):
        # length doesn't match
        return True

    return False


def generate_conversation(
    test_case_path: str,
    agent: Agent,
    gemini_llm: GeminiLLM,
    max_turns: int = 3
):
    prompt_path = (
        Path(__file__).parent /
        'resources' /
        'prompts' /
        'conversation_expansion_prompt'
    )
    with open(str(prompt_path), 'r', encoding='utf-8') as fp:
        conversation_expansion_prompt = fp.read()

    test_cases = load_tests(f'{test_case_path}.json')
    for i, test_case in tqdm(
        enumerate(test_cases),
        total=len(test_cases),
        desc='Generating Conversations'
    ):
        current_session = i + 1
        user_message = test_case['input']
        available_turns: list = test_case['turns']

        for _ in range(max_turns):
            # (Agent) generate response for user message
            agent_response = ''
            for chunk in agent.query(current_session, user_message):
                agent_response += chunk

            # --- (Gemini) generate user response
            # 1. get conversation (excluded system prompt) and turns
            conversation = [
                f'{item["role"]}: {item["content"]}'
                for item in agent.get_session(current_session).message_dict[1:]
            ]
            turns: list[str] = available_turns

            # 2. get a new user message (turn)
            # the prompt seems to not work well with JSON output, so we
            # make it generate a string and hope the format is correct.
            prompt = conversation_expansion_prompt.format(
                conversation=conversation,
                turns=turns
            )
            gemini_response = gemini_llm.generate(prompt)
            json_part = gemini_response[gemini_response.find("{"):gemini_response.rfind("}") + 1]
            try:
                selected_turn = json.loads(json_part)
                index, user_message = selected_turn['index'], selected_turn['complete_message']

                # 3. remove selected turn from available turns
                # Note: it can fail if the index is not found (rarely happens)
                available_turns.pop(index)
            except json.JSONDecodeError:
                logger.error(f"Gemini Response: {gemini_response}")
                raise RuntimeError('Failed conversation generation.')

        # add generated conversation to be evaluated
        test_cases[i]['full_conversation'] = agent.get_session(current_session).message_dict[1:]

    save_tests(
        tests=test_cases,
        name=f'{test_case_path}_conversations.json'
    )


def barplot_metric(
    metric_name: str,
    metric_results: dict[str, list[float]]
):
    # compute scores
    scores = {}
    for model_name, metric_scores in metric_results.items():
        score = sum(metric_scores) / len(metric_scores)
        scores[model_name] = score

    # plot setup
    plt.figure(figsize=(5 * len(metric_results.keys()), 6))
    plt.xlabel('Model')
    plt.ylabel(metric_name.replace('_', ' ').capitalize())
    plt.ylim(0, 1)

    # make plot
    sns.barplot(
        x=scores.keys(),
        y=scores.values(),
    )

    # styling
    sns.set_context("talk")
    sns.despine(left=True, bottom=True)

    plt.show()

