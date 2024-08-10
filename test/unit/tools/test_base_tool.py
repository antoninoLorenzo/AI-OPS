import unittest


class TestBaseTool(unittest.TestCase):
    """Tests the Tool class in `src.agent.tools.base`.

    The implemented tests must answer the following questions:
    1. `load_tool`: create Tool object from json file

        - what happens if json schema is wrong?
        - what happens if the content of json fields is empty?
        - what happens if the provided path doesn't exist?

    2. `run`: executes a command

        - what happens if tool execution fails?
    """


if __name__ == "__main__":
    unittest.main()
