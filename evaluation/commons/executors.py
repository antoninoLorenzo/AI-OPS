import json
from pathlib import Path

from deepeval.metrics import BaseMetric, BaseConversationalMetric
from deepeval.test_case import LLMTestCase, ConversationalTestCase
from tqdm import tqdm

from src.core.llm import LLM
from src.agent import Agent
from src.utils import get_logger
from evaluation.commons.gemini import GeminiLLM

logger = get_logger(__name__)


def load_prompt(name: str) -> str:
    """Get the prompt for a component in the default architecture."""
    current = str(Path(__file__))
    prompt_path = (
            Path(current[:current.find('evaluation')])
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
        Path(current[:current.find('evaluation')])
        / 'evaluation'
        / 'resources'
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
        Path(current[:current.find('evaluation')])
        / 'resources'
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
    for i, test_case in tqdm(
        enumerate(test_cases),
        total=len(test_cases),
        desc=f'{model.model}'
    ):
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
                if 'expected_output' in test_case and test_case['expected_output'] \
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
    test_case_path: str = 'default_architecture',
    model: str = 'mistral:7b-instruct-v0.3-q8_0'
) -> bool:
    """Automatically decide whether conversations should be generated:
    if the base dataset (ex. default_architecture.json) is updated then
    return True, otherwise False."""
    test_cases = load_tests(f'{test_case_path}.json')
    conversation_test_cases = load_tests(f'{test_case_path}_conversations.json')

    if len(conversation_test_cases) == 0:
        # conversation file doesn't exist
        return True

    # the number of test cases for model X should match the
    # number of generated conversations for the same model
    conversational_test_cases_for_model = list(filter(
        lambda d: d.get("model") == model, conversation_test_cases
    ))

    if len(conversational_test_cases_for_model) == 0 or \
            len(conversational_test_cases_for_model) != len(test_cases):
        return True

    return False


def generate_conversation(
    test_case_path: str,
    agent: Agent,
    gemini_llm: GeminiLLM,
    max_turns: int = 3
):
    current = str(Path(__file__))
    prompt_path = (
        Path(current[:current.find('evaluation')])
        / 'evaluation'
        / 'resources'
        / 'prompts'
        / 'conversation_expansion_prompt'
    )

    with open(str(prompt_path), 'r', encoding='utf-8') as fp:
        conversation_expansion_prompt = fp.read()

    test_cases = load_tests(f'{test_case_path}.json')
    for i, test_case in tqdm(
        enumerate(test_cases),
        total=len(test_cases),
        desc='Generating Conversations'
    ):
        test_case['model'] = agent.agent.model
        current_session = i + 1
        user_message = test_case['input']
        available_turns: list = test_case['turns']

        for t in range(max_turns):
            logger.info(f'turn {t}')

            # (Agent) generate response for user message
            agent_response = ''
            for chunk in agent.query(current_session, user_message):
                agent_response += chunk
            logger.info(f'assistant generated response.')

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
            # TODO: should still handle if the resource gets exhausted
            #   in the case Throttle fails
            gemini_response = gemini_llm.generate(prompt)
            logger.info(f'gemini selected next turn.')

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

