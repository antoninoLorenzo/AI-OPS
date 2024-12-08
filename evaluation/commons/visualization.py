import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt


def barplot_metric(
    metric_name: str,
    metric_results: dict[str, list[float]]
):
    # compute scores
    scores = {}
    for model_name, metric_scores in metric_results.items():
        score = sum(metric_scores) / len(metric_scores)
        scores[model_name] = score

    # plot setup
    plt.figure(figsize=(5 * len(metric_results.keys()), 6))
    plt.xlabel('Model')
    plt.ylabel(metric_name.replace('_', ' ').capitalize())
    plt.ylim(0, 1)

    # make plot
    sns.barplot(
        x=scores.keys(),
        y=scores.values(),
    )

    # styling
    sns.set_context("talk")
    sns.despine(left=True, bottom=True)

    return plt


def extract_activity_scores(
    df: pd.DataFrame,
    metric_name: str,
    skip_activity: tuple = ('general',)
) -> dict[str, dict[str, list]]:
    """
    :return: 'model_name': {'activity_name': [scores...]}
    """
    df_scores: dict[str, dict[str, list]] = {}
    for _, row in df.iterrows():
        activity_name = row['activity']
        if activity_name in skip_activity:
            continue

        model_name = row['model']
        score = row[metric_name]

        if model_name not in df_scores:
            df_scores[model_name] = {}

        if activity_name not in df_scores[model_name]:
            df_scores[model_name][activity_name] = []

        df_scores[model_name][activity_name].append(score)

    # Exclude activities with a mean score of 1.0
    for model_name, activities in df_scores.items():
        for activity_name, scores in list(activities.items()):
            if np.mean(scores) == 1.0:
                del activities[activity_name]

    return df_scores


def score_activity_boxplot(
    activity_scores: dict[str, dict[str, list]],
    metric_name: str,
):
    """
    :param activity_scores: 'model_name': {'activity_name': [scores...]}
    :param metric_name:
    """
    metric_capitalized_name = metric_name.replace("_", " ").capitalize()

    plt.figure(figsize=(12, 12))
    for i, model in enumerate(activity_scores.keys(), 1):
        plt.subplot(2, 2, i)

        x = list(activity_scores[model].keys())
        y = list(activity_scores[model].values())

        x_full = [
            val
            for i, sublist in enumerate(y)
            for val in [x[i]] * len(sublist)
        ]
        y_flat = [
            value
            for sublist in y
            for value in sublist
        ]

        sns.boxplot(x=x_full, y=y_flat)

        plt.title(f'{metric_capitalized_name} for {model}', fontsize=10)
        plt.xlabel('Activity', fontsize=8)
        plt.xticks(rotation=45, ha='right')
        plt.ylabel(metric_capitalized_name, fontsize=8)
        plt.ylim(0, 1)

    plt.tight_layout()
    return plt
