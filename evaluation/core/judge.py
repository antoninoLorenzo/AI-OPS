import json
import re

import google
import google.api_core
import google.api_core.exceptions
import google.generativeai as genai
from backoff import expo, on_exception
from deepeval.models import DeepEvalBaseLLM
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from pydantic import BaseModel, ValidationError
from ratelimit import RateLimitException, limits

from src.utils import get_logger

LOGGER = get_logger(__name__)
MINUTE = 60
JSON_MARKDWON = r'^```json\s*([\s\S]*?)\s*```$'


def backoff_ratelimit_logger(details):
    LOGGER.warning(
        '{target}: RateLimitException: backoff {wait:0.1f}s; tries={tries}'.format(**details)
    )


def backoff_parsing_logger(details):
    LOGGER.warning(
        '{target}: ValueError: backoff {wait:0.1f}s; tries={tries}'.format(**details)
    )


@on_exception(
    expo,
    exception=RateLimitException,
    # if it has to try more than ten times it means that a minute from the
    # last request has passed -> the daily quota is exceeded (without subscription)
    max_tries=10,
    on_backoff=backoff_ratelimit_logger,
)
@on_exception(
    expo,
    exception=ValueError,
    # don't expect it to work if it failed JSON more than three times
    max_tries=3,    
    on_backoff=backoff_parsing_logger
)
@limits(calls=15, period=MINUTE, raise_on_limit=True)
def gemini_query(
    model: genai.GenerativeModel, 
    prompt: str,
    response_schema: BaseModel,
    **model_settings
) -> BaseModel:
    """
    Makes a query to Gemini API with rate limiting and validation of response schema.
    """
    try:
        response = model.generate_content(prompt, **model_settings)
    except google.api_core.exceptions.ClientError as request_err:
        LOGGER.error(f'failed request to Gemini: {request_err}')
        raise RateLimitException from request_err

    # extract evaluation result
    content = response.text
    try:
        # gemini usually outputs json with "```json (...) ```"
        json_markdwon_match = re.match(JSON_MARKDWON, response.text)
        if json_markdwon_match:
            content = json_markdwon_match.group(1)

        # extract json and create BaseModel from response_schema
        evaluation_result = json.loads(content)        
        evaluation_result = response_schema(**evaluation_result)
        return evaluation_result
    except (ValidationError, json.JSONDecodeError) as parsing_error:
        LOGGER.error(f'failed parsing: {content}')
        raise ValueError from parsing_error


class GeminiLLM(DeepEvalBaseLLM):
    """
    Implement a wrapper to Google Gemini LLM that is used as judge for evaluation.
    """
    def __init__(self, *args, **kwargs):
        self.model_name = 'gemini-2.0-flash'

        # needed to perform evaluation of hacking related content
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
        }
        self.generation_config = {
            'temperature': 0.5,
        }

        self.model = genai.GenerativeModel(self.model_name)

    def load_model(self):
        return self.model

    def generate(self, prompt: str, schema: BaseModel) -> BaseModel:
        return gemini_query(
            model=self.load_model(),
            prompt=prompt,
            response_schema=schema,
            safety_settings=self.safety_settings,
            generation_config=self.generation_config
        )

    async def a_generate(self, prompt: str, schema: BaseModel) -> BaseModel:
        raise NotImplementedError()

    def get_model_name(self):
        return self.model_name
