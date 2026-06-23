# Starts the kali container + task container and waits for Ctrl+C.
# Used to manually interact with the environment for exploration purposes.
from dotenv import load_dotenv

from autopenbench.driver import PentestDriver
from autopenbench.utils import load_data

from benchmark.auto_pen_bench.run import get_parser, get_run_settings, load_tasks
from benchmark.auto_pen_bench.schema import AutoPenBenchRun, Task


def main():
    # technically this will take the same arguments of the benchmark harness
    # i.e more than one task, intended to use with only one, however will only
    # load the first one if more than one is supplied.
    parser = get_parser()
    args = parser.parse_args()
    settings = get_run_settings(args)
    tasks = load_tasks(settings)

    task = tasks[0]
    driver = PentestDriver(task.task, task.flag, task.target)
    _ = driver.reset()

    try:
        print("Running")
        while True:
            pass
    except KeyboardInterrupt:
        print(f"Stopping {task.task}")


if __name__ == "__main__":
    load_dotenv()
    main()