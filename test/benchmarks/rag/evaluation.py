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
from test.benchmarks.rag.metrics import HuggingFaceLLM, ContextRecall, ContextPrecision, EVAL_PROMPTS


GEN_PROMPT = {
    'gemma:2b': {
        'sys': textwrap.dedent("""
            You are a Cybersecurity professional assistant, your job is to provide an answer to context specific questions.
            You will be provided with additional Context information to provide an answer.
        """),
        'usr': textwrap.dedent("""
            Question: {query}
            Context:
            {context}
        """)
    }
}


def init_knowledge_base(data: dict[str: list[Topic]]) -> Store:
    """Creates a connection to the Vector Database and
    uploads the data used to generate the synthetic dataset.
    :param data: {path to a JSON file : topic list}
    """
    store = Store()
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


def generate_evaluation_dataset(vdb: Store, qa_paths: list, model: str = 'gemma:2b'):
    """Uses the RAG pipeline to generate an evaluation dataset composed of
    questions and ground truths from Q&A dataset and context + answers from
    the RAG pipeline."""
    qa = pd.concat(
        [pd.read_json(path) for path in qa_paths],
        ignore_index=True
    )

    def gen_context_answer(question: str, llm: LLM):
        points = vdb.retrieve(question, 'owasp')
        context_list = [f'{p.payload["title"]}: {p.payload["text"]}' for p in points]
        context = '\n'.join(context_list)
        answer = llm.query(
            messages=[
                {'role': 'system', 'content': GEN_PROMPT[model]['sys']},
                {'role': 'user', 'content': GEN_PROMPT[model]['usr'].format(query=question, context=context)}
            ],
            stream=False
        )['message']['content']

        return context_list, answer

    generator = LLM(model=model)
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


def evaluate(vdb: Store, qa_paths: list,
             evaluation_api_key: str,
             generation_model: str = 'gemma:2b',
             evaluation_model: str = 'mistral:7b',
             eval_hf_url: str = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"):
    """Given the Vector Database and the synthetic Q&A dataset
    generated in `dataset_generation.ipynb` runs the evaluation
    process for the RAG pipeline.

    It consists of:

    - Retrieving the contexts and generating the answers for the questions.

    - Evaluating the full contexts-question-answer-ground_truths dataset.
    """
    eval_dataset = generate_evaluation_dataset(vdb, qa_paths, generation_model)

    # Setup evaluation metrics
    hf_llm = HuggingFaceLLM(eval_hf_url, evaluation_api_key)
    ctx_recall = ContextRecall(
        EVAL_PROMPTS[evaluation_model]['context_recall']['sys'],
        EVAL_PROMPTS[evaluation_model]['context_recall']['usr'],
        hf_llm
    )
    ctx_precision = ContextPrecision(
        EVAL_PROMPTS[evaluation_model]['context_precision']['sys'],
        EVAL_PROMPTS[evaluation_model]['context_precision']['usr'],
        hf_llm
    )

    # Run
    recall = []
    for i, item in tqdm(eval_dataset.iterrows(), total=len(eval_dataset), desc='Measuring Context Recall'):
        ctx = '\n\n'.join(item.contexts)
        ans = item.answer
        recall.append(ctx_recall.compute(ans, ctx))

    precision = []
    for i, item in tqdm(eval_dataset.iterrows(), total=len(eval_dataset), desc='Measuring Context Recall'):
        qst = item.question
        ctx = '\n\n'.join(item.contexts)
        ans = item.answer
        precision.append(ctx_precision.compute(qst, ans, ctx))

    return pd.DataFrame({
        'context_recall': recall,
        'context_precision': precision
    })


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
    hf_api_key = os.environ.get('HF_API_KEY')
    if not hf_api_key:
        raise RuntimeError('Missing HuggingFace API Key in .env')

    knowledge_base: Store = init_knowledge_base({
        '../../../data/json/owasp.json': [Topic.WebPenetrationTesting]
    })

    synthetic_qa_paths = [
        '../../../data/rag_eval/owasp_100.json',
        # '../../../data/rag_eval/owasp_100-200.json'
    ]

    eval_results_df = evaluate(knowledge_base, synthetic_qa_paths, hf_api_key)
    update_evaluation_plots(eval_results_df)
