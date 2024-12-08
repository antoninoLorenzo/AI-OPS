import os
import time
import threading

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core.exceptions import ResourceExhausted
from deepeval.models import DeepEvalBaseLLM

from src.utils import get_logger

# disable deep eval telemetry
os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
os.environ['ERROR_REPORTING'] = 'YES'
logger = get_logger(__name__)


class Throttler:
    """A rate-limiter to avoid getting blocked by LLM providers (such as
    Gemini). Useful to scale up evaluation. """

    def __init__(self, requests_per_minute: int = 15):
        self.__quota = requests_per_minute - 1  # from 0 to 14
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
                time.sleep(61)  # for the sake of waiting an additional second
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
