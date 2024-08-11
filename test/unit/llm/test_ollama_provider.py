import unittest


class TestOllamaProvider(unittest.TestCase):
    """Tests the Ollama class from `src.agent.llm.llm`

    1. [ ] `query`: returns a generator for the response tokens (chunks)

        - what happens if message list is empty?
        - what happens if message list is malformed?

            -  case wrong roles
            -  case wrong format (not "role": "", "content": "")
            -  case empty role/content

        - what happens if Ollama is down?

    2. [ ] `tool_query`: returns something that I knew when I wrote the code :|
    """


if __name__ == '__main__':
    unittest.main()
