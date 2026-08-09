<div align="center">

  <img src="./static/logo_nobg.png" style="width:100px" alt="AI-OPS-logo">
  <h1>AI-OPS</h1>
  <p><strong>LLM-assisted penetration-testing agent. Bring your own LLM, run the API, drive it from the CLI.</strong></p>

  [![license](https://img.shields.io/badge/LICENSE-MIT-green.svg)](./LICENSE)
  [![CI](https://github.com/antoninoLorenzo/AI-OPS/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/antoninoLorenzo/AI-OPS/actions/workflows/ci.yml)
  ![GitHub last commit](https://img.shields.io/github/last-commit/antoninoLorenzo/AI-OPS/main)
  ![coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/antoninoLorenzo/5c765b19faeae31f45f4b6b13e8c1f1c/raw/coverage.json)

</div>

---

### Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quickstart](#quickstart)
  - [Requirements](#requirements)
  - [Run the API](#run-the-api)
  - [Connect the CLI](#connect-the-cli)
- [Supported Models](#supported-models)
- [Documentation](#documentation)
- [Use as a Library](#use-as-a-library)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [License](#license)

> 💡 ***Note:** AI-OPS is an active research prototype.*

---

## Overview

AI-OPS is an open agent for penetration-testing and cybersecurity tasks. You run the agent behind an HTTP API, in a container with the offensive tooling preinstalled, and drive it from a terminal client.

It is built to be model-agnostic: it uses [`litellm`](https://github.com/BerriAI/litellm/) under the hood, so you can point it at a hosted provider, an OpenAI-compatible endpoint, or a self-hosted model. The design targets medium-sized LLMs, so it stays usable without frontier-scale hardware.

> This is mostly an experiment tool, don't expect it to replace any actual competence in pentesting/cybersecurity.

## Features

- **Bring your own LLM.** Any provider `litellm` supports, including OpenAI-compatible and self-hosted endpoints.
- **Skills.** Reusable, bundled playbooks the agent can load for common tasks. Can extend with your own.
- **Guarded command execution.** A terminal tool runs commands under configurable allow-list policies, with confirmation for anything not on the list.
- **Context management.** Layered context views keep long sessions within a model's window (under analysis).
- **Observability.** Optional tracing through MLflow.
- **Two ways to use it.** Drive it interactively from the CLI, or call the API (and the Python library) directly for automation and benchmarking.

## Architecture

AI-OPS has two parts:

- **API**: a containerized HTTP server that owns the agent, the tools, and conversation state. This is what you deploy.
- **CLI**: a terminal client that connects to the API and gives you an interactive session.

The LLM is external and yours to choose.

## Quickstart

### Requirements

- **Docker** to run the API.
- The **CLI**, either the prebuilt binary or Node 22+ to run it from source.

### Run the API

Pull and run the image, passing your model configuration as environment variables:

```bash
docker run --rm -p 8000:8000 -e AI_OPS_MODEL=openai/your-model -e LLM_API_BASE=http://your-endpoint/v1 -e LLM_API_KEY=your-key -v ai_ops_data:/home/aiops/.local/share/ai_ops ghcr.io/antoninolorenzo/ai-ops:latest
```

- `AI_OPS_MODEL` is the only required setting (a fully-qualified `litellm` model id). `LLM_API_BASE` and `LLM_API_KEY` are optional and depend on your provider.
- The volume persists conversation history across runs.
- Bound to `127.0.0.1` the API runs without auth for local use. If you expose it on a network, set `AI_OPS_AUTH_TOKEN`. See [Run the API Server](https://antoninolorenzo.github.io/AI-OPS/how-to/run-the-api-server/) for more details.

### Connect the CLI

Download the latest `ai-ops-cli` from [Releases](https://github.com/antoninoLorenzo/AI-OPS/releases), then:

```bash
chmod +x ai-ops-cli
./ai-ops-cli --base-url http://127.0.0.1:8000
```

Flags, the config file, slash commands, and resume are covered in [Use the CLI](https://antoninolorenzo.github.io/AI-OPS/how-to/use-the-cli/).

## Documentation

Full documentation lives at **[antoninolorenzo.github.io/AI-OPS](https://antoninolorenzo.github.io/AI-OPS/)**:

- [Getting Started](https://antoninolorenzo.github.io/AI-OPS/getting-started/)
- [Run the API Server](https://antoninolorenzo.github.io/AI-OPS/how-to/run-the-api-server/)
- [Use the CLI](https://antoninolorenzo.github.io/AI-OPS/how-to/use-the-cli/)
- [Configuration](https://antoninolorenzo.github.io/AI-OPS/configuration/)
- [Extending AI-OPS](https://antoninolorenzo.github.io/AI-OPS/how-to/add-a-tool/) (tools, skills, policies)

## Use as a Library

The agent can be driven directly from Python for automation or benchmarking, without the API. See [Run the Agent Programmatically](https://antoninolorenzo.github.io/AI-OPS/how-to/run-the-agent-programmatically/).

## Contributing

Contributions are welcome. See [CONTRIBUTE.md](./CONTRIBUTE.md) for setup, testing, and documentation guidelines.

## Disclaimer

**AI-OPS** is designed as an ethical hacking tool intended for academic and educational purposes only.

The creators and contributors of **AI-OPS** are not responsible for any misuse of this tool. By using **AI-OPS**, you agree to take full responsibility for your actions and to use the tool in a manner that is ethical, legal, and in accordance with the intended purpose. The creators are not liable for any damages or legal repercussions resulting from the use of this tool.

## License

Released under the [MIT License](./LICENSE).
