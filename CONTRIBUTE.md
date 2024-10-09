### Table of Contents

1. [How to Contribute](#how-to-contribute)
   - [Design Goals](#design-goals)
   - [General Contribution Process](#general-contribution-process)
4. [Development Installation](#development-installation)
5. [Testing](#testing)
   - [LLM Integration](#llm-integration)
   - [Tool Integration]()
   - [RAG (Retrieval-Augmented Generation)](#rag-retrieval-augmented-generation)
6. [Code Style and Standards](#code-style-and-standards)

# How to Contribute

I highly appreciate any contribution to the project, you can:
- Report Bugs
- Request a feature
- Request the integration of a model
- Provide Feedback
- etc.

## Design Goals

Our main design goals for the project are:
- **Cost-Free Solution**: Penetration Testing tools are free (most of them), so will be AI-OPS; this means that *no paid models will be integrated*.
- **Flexibility**: Penetration testers have their own preferences and workflows, so flexibility is key to deliver a quality tool.
- **Human In the Loop**: This solution is not meant to automate the entire penetration testing process. It’s designed to provide another perspective on a problem, acting on your instructions, but AI will never replace experience.

## General Contribution Process

1. **Fork the Repository**: Create a personal fork of the repository on GitHub.
2. **Make Your Changes**: Implement your changes in your fork. (***Important**: For new features create a new branch.*)
3. **Commit Changes**: Write clear and concise commit messages.
    ```bash
    git commit -m "Describe the changes made"
    ```
4. **Push to GitHub**: Push your changes to your fork.
    ```bash
    git push origin branch-name
    ```
5. **Open a Pull Request**

# Development Installation

1. **Setup**
- Clone Repository `git clone https://github.com/antoninoLorenzo/AI-OPS.git`
- Install Python requirements `pip install -r requirements.txt`
- Install spacy model `python -m spacy download en_core_web_md`


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

### Tool Integration

- When integrating a new tool run the test `test/tool_integration/test_tool_integration.py` to ensure it doesn't break
when starting the API. Anyway there is a GitHub Actions Workflow that will ensure the test passes.

### RAG (Retrieval-Augmented Generation)

- For RAG system updates or modifications, ensure that the system continues to provide good results, to know more go to [benchmark](./test/benchmarks/rag)). Verify that new data integrations do not negatively impact performance.
  <!-- TODO: benchmark.md -->

## Code Style and Standards

- We use `pylint` to maintain a good coding baseline. Ensure your code passes pylint checks before submitting a pull request.
