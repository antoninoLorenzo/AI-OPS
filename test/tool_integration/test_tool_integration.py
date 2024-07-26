"""
The tool documentations in `tools_settings` are LLM generated, to ensure
the correct JSON format is generated every time a new tool is added this
test verifies the tool can be correctly loaded.
> Discovering it when after building the Docker API is a pain in the ass
"""
import unittest
from pathlib import Path
from src.agent.tools.base import Tool


class TestToolIntegration(unittest.TestCase):
    BASE_PATH = Path('../../tools_settings')

    def test_load(self):
        """Try to load tool and fail if any exception is raised"""
        try:
            for path in Path(self.BASE_PATH).iterdir():
                if path.is_file() and path.suffix == '.json':
                    Tool.load_tool(str(path))
        except Exception as err:
            self.fail(f'Tool Integration failed.\n{err}')


if __name__ == "__main__":
    unittest.main()
