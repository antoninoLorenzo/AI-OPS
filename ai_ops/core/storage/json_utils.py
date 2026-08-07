import json
from typing import Iterator
from pathlib import Path


def read_jsonl(file: Path) -> Iterator[dict]:
    with open(str(file), 'r', encoding='utf-8') as fp:
        for line_no, line in enumerate(fp, start=1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                pass


def append_jsonl(file: Path, raw: str):
    with open(str(file), 'a', encoding='utf-8') as fp:
        fp.write(raw + "\n")
