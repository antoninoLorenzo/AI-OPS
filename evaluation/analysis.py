from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from evaluation.commons.visualization import (
    barplot_metric,
    extract_activity_scores,
    score_activity_boxplot
)

PATH_EVALUATION_RESULTS = Path('.') / 'datasets'
PATH_EVALUATION_PLOTS = Path('.') / 'resources' / 'plots'

# --- ARCHITECTURE EVALUATION

# load results
architecture_eval_df = pd.read_json(
    str(
        PATH_EVALUATION_RESULTS /
        'default_architecture_out.json'
    )
)

# compute overall scores
architecture_eval_scores: pd.DataFrame = architecture_eval_df[[
    'model',
    'conversation_relevancy',
    'conversation_completeness'
]].groupby('model', as_index=False).mean().set_index('model')

architecture_eval_scores['overall'] = architecture_eval_scores[
    ['conversation_relevancy', 'conversation_completeness']
].mean(axis=1)
architecture_eval_scores = architecture_eval_scores.sort_values(
    by='overall',
    ascending=False
)[['overall']]

# make pretty table
ARCHITECTURE_EVAL_TABLE = architecture_eval_scores.style \
    .format('{:.2f}') \
    .bar(
        align="left",
        vmin=0, vmax=1,
        cmap=plt.colormaps['RdYlGn'],
    ) \
    .set_properties(**{
        'color': 'black',
    }) \
    .set_table_styles(
        [
            {
                "selector": "thead th",
                "props": [("color", "#2c7fb8"), ("font-weight", "bold"), ("text-align", "left")]
            },
            {
                "selector": "tbody td",
                "props": [("text-align", "left"), ("font-family", "monospace")]
            },
        ]
    )

# boxplot system metrics
activity_conversation_completeness = extract_activity_scores(
    df=architecture_eval_df,
    metric_name='conversation_completeness'
)
ARCHITECTURE_BOXPLOT_COMPLETENESS = score_activity_boxplot(
    activity_conversation_completeness,
    metric_name='conversation_completeness'
)
ARCHITECTURE_BOXPLOT_COMPLETENESS.savefig(
    str(PATH_EVALUATION_PLOTS / f'architecture_boxplot_completeness.svg'),
    format='svg'
)

activity_conversation_relevancy = extract_activity_scores(
    df=architecture_eval_df,
    metric_name='conversation_relevancy'
)
ARCHITECTURE_BOXPLOT_RELEVANCY = score_activity_boxplot(
    activity_conversation_completeness,
    metric_name='conversation_relevancy'
)
ARCHITECTURE_BOXPLOT_RELEVANCY.savefig(
    str(PATH_EVALUATION_PLOTS / f'architecture_boxplot_relevancy.svg'),
    format='svg'
)

# --- ROUTER EVALUATION

# load results
router_eval_df = pd.read_json(
    str(
        PATH_EVALUATION_RESULTS /
        'default_architecture_router_out.json'
    )
)

# get router barplots
router_alignment_results: dict[str, list[float]] = {model: [] for model in set(list(router_eval_df['model']))}
for _, router_eval_row in router_eval_df.iterrows():
    router_alignment_results[router_eval_row['model']].append(router_eval_row['prompt_alignment'])
ROUTER_BARPLOT_ALIGNMENT = barplot_metric(
    'prompt_alignment',
    router_alignment_results
)
ROUTER_BARPLOT_ALIGNMENT.savefig(
    str(PATH_EVALUATION_PLOTS / f'router_barplot_alignment.svg'),
    format='svg'
)

router_index_correctness_results: dict[str, list[float]] = {model: [] for model in set(list(router_eval_df['model']))}
for _, router_eval_row in router_eval_df.iterrows():
    router_index_correctness_results[router_eval_row['model']].append(router_eval_row['assistant_index_correctness'])
ROUTER_BARPLOT_CORRECTNESS = barplot_metric(
    'prompt_index_correctness',
    router_index_correctness_results
)
ROUTER_BARPLOT_CORRECTNESS.savefig(
    str(PATH_EVALUATION_PLOTS / f'router_barplot_correctness.svg'),
    format='svg'
)

# get router box plots
router_activity_correctness_scores = extract_activity_scores(
    df=router_eval_df,
    metric_name='assistant_index_correctness',
    skip_activity=()
)
ROUTER_BOXPLOT_CORRECTNESS = score_activity_boxplot(
    activity_scores=router_activity_correctness_scores,
    metric_name='assistant_index_correctness'
)
ROUTER_BOXPLOT_CORRECTNESS.savefig(
    str(PATH_EVALUATION_PLOTS / f'router_boxplot_correctness.svg'),
    format='svg'
)

# --- TOOL EVALUATION

# load results
tool_eval_df = pd.read_json(
    str(
        PATH_EVALUATION_RESULTS /
        'default_architecture_tool_out.json'
    )
)

# get tool plots
tool_relevance_results: dict[str, list[float]] = {model: [] for model in set(list(tool_eval_df['model']))}
for _, tool_eval_row in tool_eval_df.iterrows():
    tool_relevance_results[tool_eval_row['model']].append(tool_eval_row['tool_relevance'])
TOOL_BARPLOT_RELEVANCE = barplot_metric('tool_relevance', tool_relevance_results)
TOOL_BARPLOT_RELEVANCE.savefig(
    str(PATH_EVALUATION_PLOTS / f'tool_barplot_relevance.svg'),
    format='svg'
)

tool_activity_scores = extract_activity_scores(
    df=tool_eval_df,
    metric_name='tool_relevance'
)
TOOL_BOXPLOT_RELEVANCE = score_activity_boxplot(
    tool_activity_scores,
    'tool_relevance'
)
TOOL_BOXPLOT_RELEVANCE.savefig(
    str(PATH_EVALUATION_PLOTS / f'tool_boxplot_relevance.svg'),
    format='svg'
)
