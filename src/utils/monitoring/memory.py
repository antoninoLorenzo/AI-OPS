import time
import threading
import logging
import psutil

from src.utils.log import get_logger, LOGS_PATH

logger = get_logger(__name__)


class MemoryUsageLogger(threading.Thread):
    """A background thread that monitors and logs the memory usage of the
    current process. It to periodically check the resident set size (RSS)
    memory usage of the process using the `psutil` library.

    It can log memory usage data to a file and optionally update an external
    gauge metric from Prometheus Gauge, for real-time monitoring.
    """

    def __init__(
        self,
        memory_gauge=None,
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.memory_gauge = memory_gauge
        self.process = psutil.Process()

        self.logger = logging.Logger('memory_logger')
        formatter = logging.Formatter('%(asctime)s: %(name)s: %(message)s')

        logger_handler = logging.FileHandler(
            filename=f'{str(LOGS_PATH)}/memory_usage.log',
            mode='a',
            encoding='utf-8'
        )
        logger_handler.setLevel(logging.DEBUG)
        logger_handler.setFormatter(formatter)

        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logger_handler)

    def run(self):
        steps = 0
        while True:
            try:
                time.sleep(2)

                memory_info = self.process.memory_info()
                # memory in GB
                memory: float = memory_info.rss / 1_073_741_824
                if self.memory_gauge is not None:
                    self.memory_gauge.set(memory)

                steps += 1
                if steps == 5:
                    steps = 0
                    self.logger.info(f'Usage: {memory:.2f} GB')
            except Exception as err:
                logger.error(f'Unexpected error in {self.__name__}: {str(err)}')
                time.sleep(5)
