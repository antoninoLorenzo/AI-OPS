

class MockCLIInput:
    def __init__(self, mock_input: str):
        self.user_input = mock_input

    def prompt(self):
        return self.user_input


def build_input_mock(user_input):
    return MockCLIInput(user_input)

