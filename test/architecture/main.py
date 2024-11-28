import os

import pandas as pd
import google.generativeai as genai
import deepeval
from deepeval.test_case import LLMTestCase, ConversationalTestCase
from deepeval.metrics import (
    BaseMetric,
    AnswerRelevancyMetric,
    ConversationCompletenessMetric
)
from tqdm import tqdm
from dotenv import load_dotenv

from src.agent import build_agent
from test.evaluation.utils import JudgeLLM

load_dotenv()
MODEL = os.getenv('MODEL')
ENDPOINT = os.getenv('ENDPOINT')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

AGENT = build_agent(
    model=MODEL,
    inference_endpoint=ENDPOINT
)

deepeval.telemetry_opt_out()

# pre-load LLM
for ch in AGENT.query(0, 'Hi'):
    pass


if __name__ == "__main__":
    print('[+] Loading test cases')
    df = pd.read_json('./test_cases.json')
    # does initializing new columns this way make sense?
    df['response'] = ''
    df['relevancy'] = 0
    df.head()
    test_cases = list(df['input'])

    judge_llm = JudgeLLM()
    metrics: dict[str: BaseMetric] = {
        'relevancy': AnswerRelevancyMetric(
            threshold=0.7,
            model=judge_llm,
            include_reason=True
        ),
        'conversation_completeness': ConversationCompletenessMetric(
            threshold=0.7,
            model=judge_llm,
            include_reason=True
        )
    }

    # how would this work for conversation instead of simple response
    # some error management there?
    for i, test_case_input in tqdm(enumerate(test_cases), total=len(test_cases)):
        test_response = ''
        for chunk in AGENT.query(i+1, test_case_input):
            test_response += chunk

        deep_eval_test_case = LLMTestCase(
            input=test_case_input,
            actual_output=test_response
        )

        for metric_name, metric in metrics.items():
            # example of "fuck it, it works"
            if metric_name.startswith('conversation'):
                convo_test_case = ConversationalTestCase(
                    turns=[deep_eval_test_case]
                )
                metric.measure(convo_test_case)
            else:
                metric.measure(deep_eval_test_case)

            df.loc[i, 'response'] = test_response
            df.loc[i, metric_name] = metric.score

    print('[+] Saving Results')
    df.to_json('./test_output.json')
    print('[+] Done')
