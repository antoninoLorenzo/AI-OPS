from typing import Set

import bashlex

from ai_ops.core.log import get_logger, log_event, logging


_logger = get_logger(__name__)


def extract_executables(command: str) -> Set[str]:
    # TODO: fix `sudo` edge case, it's either `sudo [command]` and the fn returns
    # {sudo, command, ...} or `sudo [params]` and it returns {sudo, ...}, however 
    # I can't find any clean way to handle this since we have no way to discriminate 
    # between the second word node (node.kind == "command") being a `sudo` parameter 
    # or another executable. 
    if len(command.strip()) == 0:
        return set()

    try:
        parts = bashlex.parse(command)
    except bashlex.errors.ParsingError as err:
        log_event(_logger, logging.WARNING, bashlex_error=str(err))
        return {}

    ast = parts[0]
    
    stack = [ast]
    executables = []
    while stack:
        node = stack.pop()

        if node.kind == 'command':
            if not node.parts:
                continue

            executables.append(node.parts[0].word)
            stack.extend(
                arg for arg in node.parts[1:] 
                if getattr(arg, "parts", None) and arg.parts
            )
                    
        elif node.kind == 'compound':
            stack.extend(node.list)
        elif node.kind == 'commandsubstitution':
            stack.append(node.command)
        elif hasattr(node, 'parts'):
            for child in node.parts:
                stack.append(child)

    return set(executables)
