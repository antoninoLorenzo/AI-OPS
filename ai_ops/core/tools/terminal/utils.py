
import bashlex

from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)

# bash reserved (ex. conditionals, builtins) that never invoke an external
# program and have no security-relevant side effect on their own.
_NON_EXECUTABLE = frozenset({
    "[", "[[", "]", "]]", "test", ":", "true", "false", "continue", "break",
})

# TODO: wrapped commands (ex. `sudo docker ps`, `timeout 2 nmap`) are not
# unwrapped, only the wrapper is returned. bashlex flattens them into a single
# command node so the wrapped exec is just another word, and there's no clean
# generic way to find it: every wrapper has its own grammar (flags that eat a
# value like `sudo -u www`, leading positionals like timeout's duration) so
# it'd mean hardcoding each one. good enough for now since the wrapper itself
# is returned and gets checked against the allowlist anyway.


def extract_executables(command: str) -> set[str]:
    if len(command.strip()) == 0:
        return set()

    try:
        parts = bashlex.parse(command)
    except bashlex.errors.ParsingError as err:
        log_event(_logger, logging.WARNING, "failed to parse command", bashlex_error=str(err))
        return set()

    executables: set[str] = set()
    stack = list(parts)
    while stack:
        node = stack.pop()

        if node.kind == "command":
            if not node.parts:
                continue

            for index, part in enumerate(node.parts):
                if part.kind != "word":
                    stack.append(part)
                    continue

                if part.word not in _NON_EXECUTABLE:
                    executables.add(part.word)

                stack.extend(node.parts[index + 1:])
                break
        elif node.kind == "compound":
            stack.extend(node.list)
        elif node.kind in ("commandsubstitution", "processsubstitution"):
            stack.append(node.command)
        elif getattr(node, "parts", None):
            stack.extend(node.parts)

    return executables


