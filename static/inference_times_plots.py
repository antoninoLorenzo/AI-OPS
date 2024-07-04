import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

if __name__ == "__main__":
    with open('../test/tests/results/conversion_times.json', 'r', encoding='utf-8') as fp:
        data_conv = json.load(fp)

    with open('../test/tests/results/inference_times.json', 'r', encoding='utf-8') as fp:
        data_plan = json.load(fp)

    inference_times_conv = [{'model': k, 'time': v['mean']} for k, v in data_conv.items()]
    inference_times_plan = [{'model': k, 'time': v['mean']} for k, v in data_conv.items()]

    df_conv = pd.DataFrame(inference_times_conv)
    df_plan = pd.DataFrame(inference_times_plan)

    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(16, 16))
    fig.suptitle('Inference Times')
    sns.set(style="whitegrid")

    ax_plan = axes[0, 0]
    sns.barplot(x='model', y='time', data=df_plan, ax=ax_plan)
    ax_plan.set_title('Planning Times')
    ax_plan.set_xlabel('Model')
    ax_plan.set_ylabel('Time')
    ax_plan.xticks(rotation=45)

    ax_conv = axes[0, 1]
    sns.barplot(x='model', y='time', data=df_conv, ax=ax_conv)
    ax_plan.set_title('Conversion Times')
    ax_plan.set_xlabel('Model')
    ax_plan.set_ylabel('Time')
    ax_plan.xticks(rotation=45)

    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    plt.show()
