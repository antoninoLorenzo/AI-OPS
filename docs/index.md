# AI-OPS Documentation

**What is AI-OPS**

AI-OPS is a completely open agent for penetration-testing and cybersecurity tasks. 
You run the agent behind an HTTP API, in a container with the offensive tooling preinstalled, and drive it from a terminal client. 

It can also be used directly as a Python library (see [Run the Agent Programmatically](how-to/run-the-agent-programmatically.md)) for use-cases such as benchmarking or automation.

**What AI-OPS isn't**

A banana.

## Start here

New to AI-OPS? [**Getting Started**](getting-started.md) takes you from nothing to a running API with the CLI connected, and your first task sent.

## Deploy and operate

For running AI-OPS and using it day to day.

- [**Getting Started**](getting-started.md): deploy the API from source and connect the CLI.
- [**Run the API Server**](how-to/run-the-api-server.md): configuration, exposing beyond localhost, driving the API without the CLI.
- [**Use the CLI**](how-to/use-the-cli.md): flags, config file, in-app keys, slash commands, modes, resume.
- [**Model Selection**](model_selection.md): choose a model that works, including self-hosted and OpenAI-compatible endpoints.
- [**Configuration**](configuration.md): every API, CLI, and agent setting.
- [**Command Policies**](command-policy.md): allow-list what the terminal tool may execute.

## Extend

For adding capabilities or embedding the agent in your own code.

- [**Add a Tool**](how-to/add-a-tool.md): give the agent a new action.
- [**Add a Skill**](how-to/add-a-skill.md): give the agent task-specific instructions on demand.
- [**Add a Command Policy**](how-to/add-a-command-policy.md): write a custom terminal admission rule.
- [**Run the Agent Programmatically**](how-to/run-the-agent-programmatically.md): use `ai_ops.core` directly, including the synchronous execution model for benchmarks and prompt optimization.

## Reference

- [**API Reference**](reference/api.md): endpoints, events, schemas, configuration, auth.
- [**Built-in Tools**](reference/tools.md): the tools the agent can be given.
- [**Context Management**](reference/context-management.md): how the context window is compacted.
- [**Storage Layout**](reference/storage.md): the base directory, sessions, and the session store.
- [**Bundled Skills**](reference/skills.md): the skills that ship with AI-OPS.
