import os
from evaluation.stage.examples import evaluation_stage_example, inference_stage_example
from evaluation.perf.performance import PerfEval

def inference_stage():
    inference_performance = PerfEval(func=inference_stage_example, num_iterations=10)
    inference_performance.run(print_results=True)


def evaluation_stage():
    os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
    evaluation_performance = PerfEval(func=evaluation_stage_example, num_iterations=10)
    evaluation_performance.run(print_results=True)


if __name__ == "__main__":    
    inference_stage()
