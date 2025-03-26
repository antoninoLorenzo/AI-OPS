import json
import queue
from contextlib import ContextDecorator
from pathlib import Path
from typing import Dict, List

from evaluation.core.schema import Stream
from src.utils.log import get_logger

LOGGER = get_logger(__name__)


class JSONFileStream(Stream, ContextDecorator):
    """
    Writes data to a JSON file as the data arrive from a Stage.
    """
    
    def __init__(self, output_path: Path):
        self.output = output_path
        self.__buffer = []
        self.__output_file = None

        if not self.output.exists():
            with open(str(self.output), 'w+'):
                pass

    def __enter__(self):
        self.__output_file = open(str(self.output), 'r+', encoding='utf-8')

        # load any saved data
        buffer = None
        try:
            buffer: List[Dict] = json.load(self.__output_file)
        except json.decoder.JSONDecodeError:
            pass
        self.__buffer = buffer if buffer is not None else []

        return self

    def __exit__(self, *exc):
        self.__output_file.close()
        return False

    def send(self, result: List[Dict]):
        # store result inside the buffer
        self.__buffer.extend(result)

        # delete current content to avoid duplication
        self.__output_file.truncate(0)
        self.__output_file.seek(0)

        # write the entire buffer in the file
        # LOGGER.debug(f'writing {self.__buffer} to {self.output}')
        json.dump(self.__buffer, self.__output_file)
        self.__output_file.flush()


class QueueStream(Stream):
    """
    A queue-based comunication channel to process tasks between pipeline stages.

    The producer must explicitly call `stop` to stop the iteration in the consumer.
    """

    def __init__(self, timeout: int = 180):
        """
        :param timeout: set in seconds, ensures that QueueStream doesn't run indefinetly
        """
        self.__stream = queue.Queue()
        self.__stop = False
        self.__timeout = timeout 

    def __iter__(self):
        return self

    def __next__(self):
        if self.__stop:
            raise StopIteration()
        try:
            item = self.__stream.get(timeout=self.__timeout)
            if item is None:
                raise StopIteration()
            return item
        except queue.Empty:
            # LOGGER.error(f'queue stream timed out after {self.__timeout}s: shutting down')
            raise StopIteration()

    def send(self, result):
        self.__stream.put(result)

    def stop(self):
        self.__stop = True
        # when stop is set after the consumer called __next__ it will wait indefinetly because
        # the stop flag is already checked, so a None sentinel value is put to stop the iteration
        self.__stream.put(None)


def json_output_example():
    import time
    to_write = [
        [{'name': 'Antonino'},{'name': 'Lorenzo'}],
        [{'name': 'Lorenzo'}, {'name': 'Antonino'}]
    ]
    with JSONFileStream(output_path=Path('output_file.json')) as output_stream:
        for res in to_write:
            output_stream.send(res)
            time.sleep(3)


def generator_output_example():
    import threading
    import time

    def producer(stream: QueueStream):
        to_write = [
            [{'name': 'Antonino'},{'name': 'Lorenzo'}],
            [{'name': 'Lorenzo'}, {'name': 'Antonino'}]
        ]
        for res in to_write:
            time.sleep(2)
            stream.send(res)
        stream.stop()
    
    out_stream = QueueStream()
    threading.Thread(target=producer, args=(out_stream,), daemon=True).start()
    
    for item in out_stream:
        print(item)

if __name__ == "__main__":
    generator_output_example()
