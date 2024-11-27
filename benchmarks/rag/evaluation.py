"""
Gets executed by GitHub Actions, loads the synthetic dataset generated in `dataset_generation.ipynb`
into the Qdrant vector database, performs evaluation of the RAG pipeline and outputs the results
as plots in `rag_evaluation_out`; the plots are then added to the relevant EVALUATION.md file.
"""
import os
import json
from pathlib import Path
from tqdm import tqdm

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from dotenv import load_dotenv

from src.agent.llm import LLM
from src.agent.knowledge import Store, Collection, Document, Topic
from benchmarks.rag.metrics import (
    ContextRecall,
    ContextPrecision,
    ContextRelevancy,
    Metric,
    EVAL_PROMPTS
)

GEN_PROMPT = {
    'gemma2:9b': {
        'sys': """
You are a Cybersecurity professional assistant, your job is to provide an answer to context specific questions.
You will be provided with additional Context information to provide an answer.""",
        'usr': """Question: {query}
Context:
{context}"""
    }
}

METRICS = {
    'context_precision': ContextPrecision,
    'context_recall': ContextRecall,
    'context_relevancy': ContextRelevancy
}


def init_knowledge_base(data: dict[str: list[Topic]], embedding_url: str) -> Store:
    """Creates a connection to the Vector Database and
    uploads the data used to generate the synthetic dataset.
    :param data: {path to a JSON file : topic list}
    :param embedding_url: llm endpoint
    """
    store = Store(in_memory=True, embedding_url=embedding_url)
    i = 0
    for p, topics in data.items():
        path = Path(p)
        if not (path.exists() and path.is_file() and path.suffix == '.json'):
            raise ValueError(f'Invalid file {p}. Should be an existing JSON file.')

        # create collection
        collection = Collection(
            i,
            path.name.split('.')[0],
            documents=[],
            topics=topics
        )

        store.create_collection(collection)

        # upload data
        with open(str(path), 'r', encoding='utf-8') as file:
            json_data = json.load(file)

        for doc in tqdm(json_data, total=len(json_data), desc=f'Uploading {path.name}'):
            store.upload(
                Document(name=doc['title'], content=doc['content'], topic=None),
                collection.title
            )

        i += 1

    return store


def generate_evaluation_dataset(vdb: Store, qa_paths: list, client_url: str,
                                model: str = 'gemma2:9b'):
    """Uses the RAG pipeline to generate an evaluation dataset composed of
    questions and ground truths from Q&A dataset and context + answers from
    the RAG pipeline."""
    qa = pd.concat(
        [pd.read_json(path) for path in qa_paths],
        ignore_index=True
    )

    def gen_context_answer(question: str, llm: LLM):
        points = vdb.retrieve_from(question, 'owasp')
        context_list = [f'{p.payload["title"]}: {p.payload["text"]}' for p in points]
        context = '\n'.join(context_list)
        response = llm.query(
            messages=[
                {'role': 'system', 'content': GEN_PROMPT[model]['sys']},
                {'role': 'user', 'content': GEN_PROMPT[model]['usr'].format(query=question, context=context)}
            ],
        )
        answer = ''
        for chunk in response:
            answer += chunk

        return context_list, answer

    generator = LLM(model=model, inference_endpoint=client_url)
    eval_data = []
    for i, items in tqdm(qa.iterrows(), total=len(qa), desc='Retrieving context and generating answers.'):
        ctx, ans = gen_context_answer(items.question, generator)
        eval_data.append({
            'contexts': ctx,
            'question': items.question,
            'answer': ans,
            'ground_truth': items.ground_truth
        })
    return pd.DataFrame(eval_data)


def evaluate(vdb: Store, qa_paths: list, endpoint: str, metrics: list,
             generation_model: str = 'gemma2:9b',
             evaluation_model: str = 'gemma2:9b',
             eval_dataset_cache: bool = True):
    """Given the Vector Database and the synthetic Q&A dataset
    generated in `dataset_generation.ipynb` runs the evaluation
    process for the RAG pipeline.

    It consists of:

    - Retrieving the contexts and generating the answers for the questions.

    - Evaluating the full contexts-question-answer-ground_truths dataset.
    """
    if len(metrics) == 0:
        raise ValueError('No metrics specified.')

    # Setup evaluation metrics
    llm = LLM(model='gemma2:9b', inference_endpoint=endpoint)
    eval_metrics: dict[Metric] = {}
    for metric in metrics:
        if metric not in METRICS.keys():
            raise ValueError(f'Invalid metric: {metric}.')

        m = METRICS[metric](
            EVAL_PROMPTS[evaluation_model][metric]['sys'],
            EVAL_PROMPTS[evaluation_model][metric]['usr'],
            llm
        )
        eval_metrics[metric] = m

    # Evaluation Dataset
    eval_dataset_path = f'../../../data/rag_eval/cache/eval_dataset.json'
    if eval_dataset_cache and os.path.exists(eval_dataset_path):
        print(f'Loaded evaluation dataset from cache.')
        eval_dataset = pd.read_json(eval_dataset_path)
    else:
        eval_dataset = generate_evaluation_dataset(
            vdb=vdb,
            qa_paths=qa_paths,
            model=generation_model,
            client_url=endpoint
        )
        eval_dataset.to_json(eval_dataset_path)

    # Run Evaluation
    results = {}
    for metric_name, m in eval_metrics.items():
        results[metric_name] = []
        for i, item in tqdm(eval_dataset.iterrows(), total=len(eval_dataset), desc=f'evaluating {metric_name}'):
            ctx = ''
            for idx, chunk in enumerate(item.contexts):
                ctx += f"[{idx}]: {chunk}\n\n"

            data = {
                'context': ctx,
                'question': item.question,
                'answer': item.answer,
                'ground_truth': item.ground_truth
            }
            results[metric_name].append(m.compute(data))

    metrics = pd.DataFrame(results)
    return metrics, eval_dataset


def update_evaluation_plots(results_df: pd.DataFrame, metrics: list,
                            modified=True,
                            rows: int = 1,
                            cols: int = 3):
    if len(metrics) == 0:
        raise ValueError('No metrics specified.')

    for metric in metrics:
        if metric not in METRICS.keys():
            raise ValueError(f'Invalid metric: {metric}.')

    # Load the evaluation history and add new results
    if modified:
        with open('../../../data/rag_eval/results/results.json', 'r+', encoding='utf-8') as fp:
            content: list[dict] = json.load(fp)

            # Initialize metric if never computed
            for metric in metrics:
                if metric not in content[0].keys():
                    for prev_results in content:
                        prev_results[metric] = 0

            # Add new results
            res: pd.Series = results_df.mean()
            new_results = {
                metric_name: res[metric_name] if metric_name in res else content[len(content) - 1][metric_name]
                for metric_name in content[0].keys()}
            content.append(new_results)

            fp.seek(0)
            json.dump(content, fp, indent=4)
        history = pd.DataFrame(content)
    else:
        history = results_df

    # Ensure the grid has enough space for all metrics
    total_metrics = len(metrics)
    if rows * cols < total_metrics:
        raise ValueError(f'Grid size ({rows}x{cols}) is too small for {total_metrics} metrics.')

        # Create a single plot with subplots for each metric
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 5))
    axes = axes.flatten()  # Flatten in case of a single row or column

    def plot_eval(ax, plot_df: pd.DataFrame, name: str):
        """Create a plot for an evaluation metric, the columns should be named 'x' and 'y'"""
        sns.lineplot(data=plot_df, x='x', y='y', ax=ax, zorder=0)
        ax.scatter(
            plot_df.iloc[1:]['x'],
            plot_df.iloc[1:]['y'],
            color='#000000',
            s=15,
            zorder=1
        )
        ax.set_ylim(0, 1)
        ax.set_xticks(range(0, len(plot_df)))
        ax.set_title(f'RAG Evaluation: {name}')
        ax.set_ylabel(name)
        ax.set_xlabel('')

    # Output the updated evaluation plots
    for i, col in enumerate(history.columns):
        values = history[col].to_list()
        metric_plot_df = pd.DataFrame([{'x': i, 'y': val} for i, val in enumerate(values)])
        plot_eval(axes[i], metric_plot_df, col)

    # Hide any unused subplots
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    plt.tight_layout()
    plt.savefig(f'../../../data/rag_eval/results/plots/plot.png')
    plt.close()


def main(plot_only=False):
    if plot_only and os.path.exists('../../../data/rag_eval/results/results.json'):
        current = pd.read_json('../../../data/rag_eval/results/results.json')
        update_evaluation_plots(
            current,
            list(current.columns),
            modified=False
        )
    else:
        load_dotenv()
        OLLAMA_ENDPOINT = os.environ.get('ENDPOINT')
        if not OLLAMA_ENDPOINT:
            raise RuntimeError('Missing environment variable "ENDPOINT"')

        knowledge_base: Store = init_knowledge_base({
            '../../../data/json/owasp.json': ['Web Pentesting'],
        }, embedding_url=OLLAMA_ENDPOINT)

        synthetic_qa_paths = [
            '../../../data/rag_eval/owasp_50.json',
        ]

        # computed_metrics = ['context_precision', 'context_recall']
        computed_metrics = ['context_relevancy']
        metrics_df, eval_output_dataset = evaluate(
            metrics=computed_metrics,
            vdb=knowledge_base,
            qa_paths=synthetic_qa_paths,
            endpoint=OLLAMA_ENDPOINT
        )
        update_evaluation_plots(metrics_df, computed_metrics)


if __name__ == '__main__':
    main(plot_only=True)
