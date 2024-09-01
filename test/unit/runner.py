import unittest
from test.unit.llm import test_ollama_provider
from test.unit.store import test_collection, test_store
from test.unit.tools import test_base_tool


def suite():
    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()

    test_suite.addTests(test_loader.loadTestsFromModule(test_ollama_provider))
    test_suite.addTests(test_loader.loadTestsFromModule(test_collection))
    test_suite.addTests(test_loader.loadTestsFromModule(test_store))
    test_suite.addTests(test_loader.loadTestsFromModule(test_base_tool))

    return test_suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=3)
    result = runner.run(suite())
