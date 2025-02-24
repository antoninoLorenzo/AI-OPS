from ollama import ResponseError

from src.core.llm import ProviderError


class MockOllamaClient:
    def __init__(self, host: str, valid_host = True):
        # valid_host is used to see how application handles Ollam not running on host
        self.__host = host
        if not valid_host:
            raise ProviderError('Ollama: invalid endpoint')

    def chat(
        self,
        model: str, 
        messages: list, 
        stream: bool = True, 
        options: dict | None = None,
        tools: list | None = None
    ):
        if not model or not messages:  
            raise ResponseError("Model and messages are required")  
        
        last_message = messages[-1]['content']
        response_message = f'response for: {last_message}\n'

        full_input_tokens, eval_count = 0, 0
        for i, char in enumerate(response_message): 
            # ollama sends token count only for last chunk in a stream
            if len(response_message) == i + 1:
                # count "tokens" (considering an average of 4 characters per token)
                for msg in messages:
                    full_input_tokens += int(len(msg['content']) / 4)
                
                # count output "tokens"
                eval_count += int(len(response_message) / 4)

            yield {
                'message': {'content': char},
                'prompt_eval_count': full_input_tokens, 
                'eval_count': eval_count
            }
