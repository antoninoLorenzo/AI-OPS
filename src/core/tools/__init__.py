"""Assistant tools"""

from tool_parse import ToolRegistry
from src.core.tools.web_search import Search

TOOL_REGISTRY = ToolRegistry()
SEARCH = Search()


@TOOL_REGISTRY.register(description=SEARCH.usage)
def search_web(search_query: str):
    return SEARCH.run(search_query)

