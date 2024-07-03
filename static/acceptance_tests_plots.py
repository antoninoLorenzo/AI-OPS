import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

if __name__ == "__main__":
    with open('../test/tests/results/conversion_times.json', 'r', encoding='utf-8') as fp:
        data = json.load(fp)

    inference_times_conv = [{'model': k, 'time': v['mean']} for k, v in data.items()]
    df_conv = pd.DataFrame(inference_times_conv)

    plt.figure(figsize=(12, 12))
    sns.set(style="whitegrid")
    sns.barplot(x='model', y='time', data=df_conv)
    plt.xlabel('Model')
    plt.ylabel('Mean Time')
    plt.title('Mean Conversion Times per Model')
    plt.xticks(rotation=45)

    plt.show()
