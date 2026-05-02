from typing import Set

import bashlex


def extract_executables(command: str) -> Set[str]:
    if len(command.strip()) == 0:
        return {}
    
    try:
        parts = bashlex.parse(command)
    except bashlex.errors.ParsingError:
        return {}

    bashlex.errors
    ast = parts[0]
    
    stack = [ast]
    executables = []
    while stack:
        node = stack.pop()

        if node.kind == 'command':
            if not node.parts:
                continue
        
            executables.append(node.parts[0].word)
            stack.extend(arg for arg in node.parts[1:] if arg.parts)
                    
        elif node.kind == 'compound':
            stack.extend(node.list)
        elif node.kind == 'commandsubstitution':
            stack.append(node.command)
        elif hasattr(node, 'parts'):
            for child in node.parts:
                stack.append(child)

    return set(executables)
