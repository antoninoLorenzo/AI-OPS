### Table of Contents

1. [Introduction](#introduction)
2. [Design Goals](#design-goals)
3. [How to Contribute](#how-to-contribute)
   - [Submitting Changes](#submitting-changes)
     - [General Contribution Process](#general-contribution-process)
     - [For New Features](#for-new-features)
4. [Install](#install)
5. [Testing](#testing)
   - [LLM Integration](#llm-integration)
   - [RAG (Retrieval-Augmented Generation)](#rag-retrieval-augmented-generation)
6. [Code Style and Standards](#code-style-and-standards)

# Introduction

AI-OPS aims to empower penetration testing enthusiasts and professionals with an LLM-based solution. 
While this technology has demonstrated great capabilities, it’s important to recognize its limitations 
and maintain realistic expectations.

## Design Goals

Our main design goals for this project are:
- **Cost-Free Solution**: Penetration testing tools are free (most of them), so **there’s no reason to pay for inference** APIs or LLM-as-a-service. This is a challenge, but we hope you find it motivating rather than limiting.
- **Flexibility**: Penetration testers have their own preferences and workflows, so flexibility is key to deliver a quality tool.
- **Human In the Loop**: This solution is not meant to automate the entire penetration testing process. It’s designed to provide another perspective on a problem, acting on your instructions, but AI will never replace experience.

# How to Contribute

Use [GitHub Issues](https://github.com/antoninoLorenzo/AI-OPS/issues) to report bugs or request features. 
Provide as much detail as possible to help reproduce the issue or understand the feature request.

## Submitting Changes

You can contribute in various ways:
- **Documentation**: Improve or update documentation.
- **Bug Fixes**: Address issues and bugs reported in the repository.
- **New Features**: Add new features or enhancements.

### General Contribution Process

1. **Fork the Repository**: Create a personal fork of the repository on GitHub.
2. **Make Your Changes**: Implement your changes in your fork.
3. **Commit Changes**: Write clear and concise commit messages.
    ```bash
    git commit -m "Describe the changes made"
    ```
4. **Push to GitHub**: Push your changes to your fork.
    ```bash
    git push origin branch-name
    ```
5. **Open a Pull Request**

### For New Features

1. **Create a Feature Branch**: Create a new branch for your feature.
    ```bash
    git checkout -b feature/your-feature-name
    ```
2. **Implement Your Feature**: Make the necessary changes in the feature branch.
3. **Push to GitHub**: Push your feature branch to your fork.
    ```bash
    git push origin feature/your-feature-name
    ```
4. **Create a Pull Request**: Open a pull request against the `main` branch of the original repository.

## Install

1. **Setup**
- Clone Repository `git clone https://github.com/antoninoLorenzo/AI-OPS.git`
- Install Python requirements `pip install -r requirements.txt`
- Install spacy model `python -m spacy download en_core_web_lg`


2. **Ollama**
- Set remote origins environment variable:  `OLLAMA_ORIGINS=1.2.3.4,...` *(Optional)*
- Set host environment variable: `OLLAMA_HOST=0.0.0.0:11434` *(Optional)*
- Run ollama: `ollama serve`


3. **Agent API**
- Launch Agent API (*in development*): `fastapi.exe dev ./src/api.py`
  
  -  Access from other machines: `fastapi.exe dev --host 0.0.0.0 ./src/api.py`
  -  Additional Settings in `.env` file:
  ```
  MODEL=model_name
  ENDPOINT=ollama_url
  ```
  *Note: the tools that require root would require also the API to be runned as root*

4. **Setup Tools** (*first time only*)
- move the content of `tools_settings` to `<user home>/.aiops/tools`.

5. **CLI Client**
- Run Client
  ```
  python ai-ops-cli.py --api AGENT_API_ADDRESS
  ```

## Testing

<h3 id="llm-integration">LLM Integration</h2>

- When integrating new LLM models, ensure they meet the existing acceptance tests ([planning](./test/test_acceptance/test_planning.py) and [conversion](./test/test_acceptance/test_conversion.py)). Validate that the new model performs as expected within the AI-OPS framework.
<!-- TODO: test_acceptance.md -->

### RAG (Retrieval-Augmented Generation)

- For RAG system updates or modifications, ensure that the system continues to provide good results, to know more go to [benchmark](./test/benchmarks/rag)). Verify that new data integrations do not negatively impact performance.
  <!-- TODO: benchmark.md -->

## Code Style and Standards

- We use `pylint` to maintain a good coding baseline. Ensure your code passes pylint checks before submitting a pull request.
