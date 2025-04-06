import re

from src.core.tools.schema import ToolCall

# identifies a JSON block until the text ends with JSON
JSON_REGEX = r"\s*({[^}]*(?:{[^}]*})*[^}]*}|\[[^\]]*(?:\[[^\]]*\])*[^\]]*\])\s*$"
# identifies a markdown (json) block at any point of the text 
MARKDWON_JSON_BLOCK = r'\s*```json\s*([\s\S]*?)\s*```$'


def get_tool_call(text: str) -> ToolCall:
    """
    Extract a tool call from LLM JSON response.
    :param text: string that contains JSON ToolCall
    :returns: a valid ToolCall or None
    """
    try:
        json_str = None
        # handle markdown tool call
        if '```json' in text:
            md_block = re.search(MARKDWON_JSON_BLOCK, text)
            if md_block is not None:
                json_str = md_block.group(1)
        
        # extract json string
        if json_str is not None:
            js_match = re.search(JSON_REGEX, json_str)
        else:
            js_match = re.search(JSON_REGEX, text)
        
        if js_match is not None:
            json_str = js_match.group(1)
        
        # the text is not a valid json string
        if json_str is None:
            return None
        
        json_str = json_str.replace("'", '"').strip()
        json_str = json_str.replace('""', '"') # \" fucks itself in the process
        
        # note: pydantic doesn't accept trailing commas, so the following is invalid
        # {"name": "function_name", "arguments": {"param1": "content of param1",}}
        return ToolCall.model_validate_json(json_str)
    except Exception:
        return None
    