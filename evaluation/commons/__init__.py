import os

import google.generativeai as genai

from src.core.llm import LLM
from src.agent import Agent
from src.chat.service import build_agent_default_architecture
from src.utils import get_logger
from evaluation.commons.gemini import GeminiLLM

# disable deep eval telemetry
os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
os.environ['ERROR_REPORTING'] = 'YES'
logger = get_logger(__name__)


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

    AGENT = build_agent_default_architecture()
    # for _ in AGENT.query(0, 'Hi'):
    #     pass

    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    genai.configure(api_key=GEMINI_API_KEY)
    JUDGE = GeminiLLM()

    return AGENT, JUDGE

