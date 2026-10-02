
import bashlex

from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)

# Commands whose first non-flag positional argument is the command they
# run, given as a plain word rather than shell-syntax (so bashlex sees it
# as just another WORD on the same `command` node, not something with its
# own `.parts` to recurse into). `sudo docker ps -a` parses as a single
# `command` node {sudo, docker, ps, -a}; without special-casing these,
# only `sudo` ever reaches the allowlist check and the command it
# elevates is invisible to policy enforcement entirely.
# https://gtfobins.org/ documents many of these as well-known sandbox/
# restricted-shell escapes for exactly this reason.
#
# Deliberately excludes wrappers whose first positional argument is NOT
# the wrapped command (`timeout <seconds> <command>`, `nice -n <level>
# <command>`, `xargs <command>`) -- flagging those would misidentify the
# duration/level/etc. as the wrapped command and require confirmation on
# every ordinary use of the wrapper, not just malicious ones.
TRANSPARENT_WRAPPER_COMMANDS = frozenset({
    'sudo', 'doas', 'su', 'nohup', 'setsid', 'unshare', 'chroot', 'time',
})


def extract_executables(command: str) -> set[str]:
    if len(command.strip()) == 0:
        return set()

    try:
        parts = bashlex.parse(command)
    except bashlex.errors.ParsingError as err:
        log_event(_logger, logging.WARNING, bashlex_error=str(err))
        return set()

    ast = parts[0]

    stack = [ast]
    executables = []
    while stack:
        node = stack.pop()

        if node.kind == 'command':
            if not node.parts:
                continue

            head = node.parts[0].word
            executables.append(head)
            stack.extend(
                arg for arg in node.parts[1:]
                if getattr(arg, "parts", None) and arg.parts
            )
            if head in TRANSPARENT_WRAPPER_COMMANDS:
                # The wrapped command is the first non-flag positional
                # argument (`sudo -l` has none, so nothing is added).
                wrapped = next(
                    (
                        arg.word for arg in node.parts[1:]
                        if getattr(arg, "word", None) and not arg.word.startswith('-')
                    ),
                    None,
                )
                if wrapped:
                    executables.append(wrapped)

        elif node.kind == 'compound':
            stack.extend(node.list)
        elif node.kind == 'commandsubstitution' or node.kind == 'processsubstitution':
            stack.append(node.command)
        elif hasattr(node, 'parts'):
            stack.extend(node.parts)

    return set(executables)
