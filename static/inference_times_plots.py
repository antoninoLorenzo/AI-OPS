import json
import sys
from json import JSONDecodeError

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

if __name__ == "__main__":
    CASES = ['conversion', 'inference']  # inference == planning
    # GPUS = ['GTX-1660-Ti', 'RTX-3080']
    GPUS = ['RTX-3080']

    fig, axes = plt.subplots(nrows=len(CASES), ncols=len(GPUS), figsize=(16, 16))
    fig.suptitle('Inference Times')
    sns.set(style="whitegrid")

    times = {}
    max_time = 0
    for case in CASES:
        for gpu in GPUS:
            path = f'../test/test_acceptance/results/{case}_times_{gpu}.json'
            with open(path, 'r', encoding='utf-8') as fp:
                # load data
                try:
                    data = json.load(fp)
                except JSONDecodeError as err:
                    print(f'Failed extracting {path}\nError: {err}')
                    sys.exit(1)

                # store data and find max inference time
                t = [{'model': k, 'time': v['mean']} for k, v in data.items()]
                for item in t:
                    if item['time'] > max_time:
                        max_time = item['time']
                times[f'{case}_{gpu}'] = pd.DataFrame(t)

    # make subplots
    for i, case in enumerate(CASES):
        for j, gpu in enumerate(GPUS):
            df = times[f'{case}_{gpu}']
            if len(GPUS) > 1:
                ax = axes[i, j]
            else:
                ax = axes[i]
            sns.barplot(x='model', y='time', data=df, ax=ax)

            ax.set_title(f'{case[:1].upper()}{case[1:]} Times ({gpu})')
            ax.set_xlabel('Model')
            ax.set_ylabel('Time')
            ax.set_ylim([0, max_time + 10])
            ax.tick_params(axis='x', rotation=45)

    plt.savefig(
        './images/inference_times_plot_RTX.png',
        dpi=300,
        bbox_inches='tight'
    )

    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    plt.show()
