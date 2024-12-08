from deepeval.metrics import BaseMetric, PromptAlignmentMetric, GEval
from deepeval.test_case import LLMTestCaseParams

from evaluation.commons import setup_component_test_resources
from evaluation.commons.executors import (
    load_prompt,
    load_tests,
    run_component_tests,
    save_tests
)


def run_router_test(
    agent,
    judge,
    test_case_path: str = 'default_architecture_router',
):
    print('[+] Loading router evaluation resources')
    router_prompt = load_prompt('router')
    test_cases = load_tests(f'{test_case_path}.json')

    # defined metrics evaluate:
    # - the router component capability of following routing instructions
    # - the router capability of choosing a good assistant (component)
    router_metrics: dict[str, BaseMetric] = {
        'prompt_alignment': PromptAlignmentMetric(
            prompt_instructions=[router_prompt],
            model=judge,
            include_reason=True
        ),
        'assistant_index_correctness': GEval(
            name='AssistantIndexCorrectness',
            model=judge,
            criteria="Determine whether the assistant index in 'expected_output' aligns with the index in 'actual_output'",
            evaluation_steps=[
                "Analyze the user intent in 'input'",
                "Consider the assistant index in 'expected_output' (1: General, 2: Reasoning, 3: Function Calling)",
                "Determine if the user intent, expressed by 'expected_output' aligns with 'actual_output'",
                "Heavily Penalize 'actual_output' if: it is 1 and 'expected_output' is 2'; it is 3 and 'expected_output' is 1.",
                "Slightly Penalize 'actual_output' if: it is 3 and 'expected_output' is 2."
            ],
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT
            ]
        )
    }

    print('[+] Running router evaluation')
    run_component_tests(
        model=agent,
        prompt=router_prompt,
        test_cases=test_cases,
        metrics=router_metrics
    )

    print('[+] Saving results')
    save_tests(
        tests=test_cases,
        name=f'{test_case_path}_out.json'
    )


if __name__ == '__main__':
    print('[+] Loading LLMs')
    AGENT, JUDGE = setup_component_test_resources()
    run_router_test(AGENT, JUDGE)
