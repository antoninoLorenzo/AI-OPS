"""
Gets executed by GitHub Actions, loads the synthetic dataset generated in `dataset_generation.ipynb`
into the Qdrant vector database, performs evaluation of the RAG pipeline and outputs the results
as plots in `rag_evaluation_out`; the plots are then added to the relevant EVALUATION.md file.
"""

