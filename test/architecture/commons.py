import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from deepeval.models import DeepEvalBaseLLM


class JudgeLLM(DeepEvalBaseLLM):

    def __init__(self, *args, **kwargs):
        self.__llm = genai.GenerativeModel('gemini-1.5-flash')
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
        }
        self.generation_config = {
            'temperature': 0.5,
        }
        super().__init__(*args, **kwargs)

    def generate(self, prompt: str) -> str:
        return self.__llm.generate_content(
            prompt,
            safety_settings=self.safety_settings,
            generation_config=self.generation_config
        ).text

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def load_model(self, *args, **kwargs):
        return self.__llm

    def get_model_name(self, *args, **kwargs) -> str:
        return 'gemini-1.5-flash'

