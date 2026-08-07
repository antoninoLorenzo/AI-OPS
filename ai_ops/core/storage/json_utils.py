import json
from collections.abc import Iterator
from pathlib import Path

from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)

def read_jsonl(file: Path) -> Iterator[dict]:
    with open(str(file), 'r', encoding='utf-8') as fp:
        for line_no, line in enumerate(fp, start=1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError as err:
                log_event(
                    _logger, logging.DEBUG, "Error parsing JSONL line, skipping.",
                    jsonl_file=str(file), error=err
                )


def append_jsonl(file: Path, raw: str):
    with open(str(file), 'a', encoding='utf-8') as fp:
        fp.write(raw + "\n")
