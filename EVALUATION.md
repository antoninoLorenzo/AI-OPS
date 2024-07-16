**Table of Contents**
1. [Agent Evaluation](#agent-evaluation)
2. [RAG Evaluation](#rag-evaluation)
   1. [Introduction](#introduction)
   2. [Results](#results)
      
      3. [Context Precision](#context-precision)
      4. [Context Recall](#context-recall)

# 📈Agent Evaluation

**TODO**

# 📊RAG Evaluation

## Introduction

Our objective is to monitor and improve the RAG pipeline for **AI-OPS**, that requires context-specific data from 
*Cybersecurity* and *Penetration Testing* fields.

The evaluation workflow is split in two steps:

1. **Dataset Generation** ([dataset_generation.ipynb](./test/benchmarks/rag/dataset_generation.ipynb)):
uses Gemini free API and the data that is ingested into Qdrant (RAG Vector Database) to generate *question* and *ground truth* 
 (Q&A dataset).

2. **Evaluation** ([evaluation.py](./test/benchmarks/rag/evaluation.py)):
builds the RAG pipeline with the same used to generate the synthetic Q&A dataset, leverages the pipeline to provide
 an *answer* to the questions (given *contex*), then performs evaluation of the full evaluation dataset using LLM as a
judge. Here everything related to generation is done via Ollama with the same models integrated in **AI-OPS**.

## Results

![Context Precision Plot](data/rag_eval/results/plots/plot.png)
