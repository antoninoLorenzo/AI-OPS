

class MockSearch:

    usage: str = "Make an online search using a query string."

    def __init__(
        self, 
        headers: dict = None,
        max_results: int = 3,
        num_threads: int = 3,
        search_result: str = '',
        should_fail: bool = False
    ):
        self.headers = headers
        self.max_results = max_results
        self.num_threads = num_threads

        # search result tells mock search what should be returned
        self.search_result = search_result

        # should fail is used to make the tool execution raise an Exception
        self.should_fail = should_fail

    def run(self, search_query: str) -> str:
        if self.should_fail:
            raise Exception('tool execution failed')
        results = []
        for i in range(): 
            results.append(f'{search_query}\n{self.search_result}')
        return '\n'.join(results)
