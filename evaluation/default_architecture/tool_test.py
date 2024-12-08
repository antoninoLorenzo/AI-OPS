import json
from pathlib import Path
from typing import Dict

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from pydantic import BaseModel
from deepeval.test_case import LLMTestCase
from deepeval.metrics import BaseMetric, JsonCorrectnessMetric

from evaluation.commons import setup_component_test_resources
from evaluation.commons.executors import (
    load_prompt,
    load_tests,
    run_component_tests,
    save_tests
)


class ToolSchema(BaseModel):
    name: str
    parameters: Dict[str, str]


class ToolRelevanceMetric(BaseMetric):
    """Measures how relevant the tool call is to the user query."""
    SCORES = {
        "RELEVANT": 1.0,
        "MISLEADING": 0.5,
        "IRRELEVANT": 0.0
    }

    def __init__(
        self,
        threshold: float = 0.5,
        include_reason: bool = True,
        strict_mode: bool = True,
        async_mode: bool = True
    ):
        self.threshold = threshold
        self.include_reason = include_reason
        self.strict_mode = strict_mode
        self.async_mode = async_mode

        # since setup() is called at start, api key is available
        self.__llm = genai.GenerativeModel('gemini-1.5-flash')
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
        }
        self.generation_config = {
            'temperature': 0.5,
            "response_mime_type": "application/json"
        }

        # load prompt
        prompt_path = (
            Path(__file__).parent.parent /
            'resources' /
            'prompts' /
            'tool_relevance_prompt'
        )
        with open(str(prompt_path), 'r', encoding='utf-8') as fp:
            self.__eval_prompt = fp.read()

    @property
    def __name__(self):
        return "ToolRelevanceMetric"

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        try:
            evaluation = self.__generate_evaluation(test_case=test_case)
            self.score, self.reason = evaluation['score'], evaluation['reason']
            self.success = self.score >= self.threshold
            return self.score
        except Exception as e:
            self.error = str(e)
            raise

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        if self.error is not None:
            self.success = False
        else:
            return self.success

    def __generate_evaluation(self, test_case: LLMTestCase):
        user_query = test_case.input
        tool_call = test_case.actual_output

        prompt = self.__eval_prompt.format(
            user_query=user_query,
            response=tool_call
        )
        evaluation_text = self.__llm.generate_content(
            prompt,
            safety_settings=self.safety_settings,
            generation_config=self.generation_config
        ).text

        evaluation_json = json.loads(evaluation_text)
        return {
            'score': self.SCORES[evaluation_json['label']],
            'reason': evaluation_json['reason']
        }


def run_tool_test(
    agent,
    judge,
    test_case_path: str = 'default_architecture_tool',
):
    print('[+] Loading tool evaluation resources')
    tool_prompt = load_prompt('tool')
    test_cases = load_tests(f'{test_case_path}.json')

    # defined metrics involve:
    # - evaluating the tool component can produce correct json
    # - evaluating the tool component provide meaningful tool calls
    tool_metrics: dict[str, BaseMetric] = {
        'json_correctness':  JsonCorrectnessMetric(
            expected_schema=ToolSchema,
            model=judge,
            include_reason=True,
            strict_mode=True
        ),
        'tool_relevance': ToolRelevanceMetric(
            threshold=0.7,
            include_reason=True
        )
    }

    print('[+] Running tool evaluation')
    run_component_tests(
        model=agent,
        prompt=tool_prompt,
        test_cases=test_cases,
        metrics=tool_metrics
    )

    print('[+] Saving results')
    save_tests(
        tests=test_cases,
        name=f'{test_case_path}_out.json'
    )


if __name__ == '__main__':
    print('[+] Loading LLMs')
    AGENT, JUDGE = setup_component_test_resources()
    run_tool_test(AGENT, JUDGE)
