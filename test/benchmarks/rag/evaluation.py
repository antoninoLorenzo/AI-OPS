"""
Gets executed by GitHub Actions, loads the synthetic dataset generated in `dataset_generation.ipynb`
into the Qdrant vector database, performs evaluation of the RAG pipeline and outputs the results
as plots in `rag_evaluation_out`; the plots are then added to the relevant EVALUATION.md file.
"""
import os
import json
import textwrap
from pathlib import Path
from tqdm import tqdm

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from dotenv import load_dotenv

from src.agent.llm import LLM
from src.agent.knowledge import Store, Collection, Document, Topic
from test.benchmarks.rag.metrics import (
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

    generator = LLM(model=model, client_url=client_url)
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
             evaluation_model: str = 'gemma2:9b'):
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
    llm = LLM(model='gemma2:9b', client_url=endpoint)
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
    eval_dataset = generate_evaluation_dataset(
        vdb=vdb,
        qa_paths=qa_paths,
        model=generation_model,
        client_url=endpoint
    )

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


def update_evaluation_plots(results_df: pd.DataFrame):
    # Load the evaluation history
    with open('../../../data/rag_eval/results/results.json', 'r+', encoding='utf-8') as fp:
        content: list = json.load(fp)
        res = results_df.mean()
        content.append({'context_precision': res.context_precision, 'context_recall': res.context_recall})
        fp.seek(0)
        json.dump(content, fp, indent=4)
    history = pd.DataFrame(content)

    def plot_eval(plot_df: pd.DataFrame, name: str):
        """Create a plot for an evaluation metric, the columns should be named 'x' and 'y'"""
        sns.lineplot(data=plot_df, x='x', y='y', zorder=0)
        plt.scatter(
            plot_df.iloc[1:]['x'],
            plot_df.iloc[1:]['y'],
            color='#000000',
            s=15,
            zorder=1
        )

        plt.ylim(0, 1)
        plt.xticks(range(0, len(plot_df)))

        plt.title(f'RAG Evaluation: {name}')
        plt.ylabel(name)
        plt.xlabel('')
        return plt

    # Output the updated evaluation plots
    plots = {}
    for col in history.columns:
        values = history[col].to_list()
        plots[col] = [{'x': i, 'y': val} for i, val in enumerate(values)]

    ctx_precision_df = pd.DataFrame(plots['context_precision'])
    ctx_recall_df = pd.DataFrame(plots['context_recall'])

    plt_ctx_precision = plot_eval(ctx_precision_df, 'Context Precision')
    plt_ctx_precision.savefig('../../../data/rag_eval/results/plots/context_precision.png')

    plt_ctx_recall = plot_eval(ctx_recall_df, 'Context Recall')
    plt_ctx_recall.savefig('../../../data/rag_eval/results/plots/context_recall.png')


if __name__ == '__main__':
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

    metrics_df, eval_output_dataset = evaluate(
        metrics=['context_precision', 'context_recall'],
        vdb=knowledge_base,
        qa_paths=synthetic_qa_paths,
        endpoint=OLLAMA_ENDPOINT
    )
    print(metrics_df.head())
    metrics_df.to_json('./tmp_metrics.json')
    eval_output_dataset.to_json('./tmp_eval_ds.json')

    # eval_results_df = pd.read_json('./tmp.json')

    update_evaluation_plots(metrics_df)
