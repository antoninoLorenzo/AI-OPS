"""Assistant tools"""

from tool_parse import ToolRegistry
from src.core.tools.schema import ToolCall
from src.core.tools.web_search import Search
from src.core.tools.parsing import get_tool_call

TOOL_REGISTRY = ToolRegistry()
SEARCH = Search(max_results=1)


@TOOL_REGISTRY.register(description=SEARCH.usage)
def search_web(search_query: str):
    return SEARCH.run(search_query)

