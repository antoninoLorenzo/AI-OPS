
# Introduction

AI-OPS aims to empower penetration testing enthusiasts and professionals with an LLM-based solution. While this technology has demonstrated great capabilities, it’s important to recognize its limitations and maintain realistic expectations.

## Design Goals

Our main design goals for this project are:
- **Cost-Free Solution**: Penetration testing tools are free (most of them), so there’s no reason to pay for inference APIs or LLM-as-a-service. This is a challenge, but we hope you find it motivating rather than limiting.
- **Flexibility**: Penetration testers have their own preferences and workflows, so flexibility is key to delivering a quality tool.
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
3. **Run Tests**: Ensure that existing tests pass and add new tests if applicable.
4. **Commit Changes**: Write clear and concise commit messages.
    ```bash
    git commit -m "Describe the changes made"
    ```
5. **Push to GitHub**: Push your changes to your fork.
    ```bash
    git push origin branch-name
    ```

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

## Testing

### LLM Integration

- When integrating new LLM models, ensure they meet the existing acceptance tests and benchmarks. Validate that the new model performs as expected within the AI-OPS framework.

### RAG (Retrieval-Augmented Generation)

- For RAG system updates or modifications, ensure that the system continues to provide accurate and up-to-date information. Verify that new data integrations do not negatively impact performance.

## Code Style and Standards

- We use `pylint` to maintain a good coding baseline. Ensure your code passes pylint checks before submitting a pull request.
