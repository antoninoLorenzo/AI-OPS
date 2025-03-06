<div align="center">

  <img src="./static/logo_nobg.png" style="width:100px" alt="AI-OPS-logo">
  <h1>AI-OPS</h1>
  <p><strong>AI-OPS is a Penetration Testing AI Assistant based on open source LLMs.</strong></p>
  
  [![license](https://img.shields.io/badge/LICENSE-MIT-<COLOR>.svg)](https://shields.io/)
  ![GitHub last commit (branch)](https://img.shields.io/github/last-commit/antoninoLorenzo/AI-OPS/main)
  ![pylint](https://img.shields.io/badge/Code%20Quality-8.52-yellow) 
  ![Code Coverage](https://img.shields.io/badge/coverage-61%25-yellow)


</div>

---

### Table of Contents

- [Overview](#overview)
  - [Key Features](#key-features)
  - [Supported Models](#supported-models)
- [Quickstart](#quickstart)
  - [Requirements](#requirements)
  - [Get Started](#get-started)
  - [Additional Information](#additional-information)
- [⚖️ Ethical and Legal Considerations](#️-ethical-and-legal-considerations)
  - [Disclaimer](#disclaimer)

> 💡 ***Note:** AI-OPS is currently an experimental project.*

---

## Overview

AI-OPS is a **Penetration Testing AI Assistant** that leverages open-source Large Language Models (*LLMs*)
to explore the role of Generative AI in ethical hacking. With a focus on accessibility and practical use, it  
aims to accelerate common tasks in pentesting such as exploit development, vulnerability research, and code analysis.

**Disclaimer**: AI-OPS goal is to support human operators rather than automate penetration testing activities entirely,  
ensuring that AI remains a supplementary tool during real-world workflows. As any other automation tool, it doesn't  
replace operator competence, neither knowledge: AI won't do the work for you, but it may help in the process.

In the current iteration, AI-OPS does not  directly interact with target systems. Instead, it serves as an assistive tool that aids in tasks like generating 
proof-of-concept (PoC) exploits, researching security vulnerabilities in specific technologies, and analyzing code for potential flaws.

### Key Features

- 🚀 **Full Open-Source**: There is no reliance on third-party LLM providers; use any model you prefer with [Ollama](https://github.com/ollama/ollama).
- 🔍 **Web Search**: The AI assistant delivers up-to-date responses by performing online searches via Google.

<!--
### ▶️ Demo

TODO

-->

### Supported Models

AI-OPS supports virtually any LLM that can be hosted with Ollama, allowing you to tailor the assistant to your  
available resources; for detailed setup instructions, see [Configuration](./docs/user/2.Configuration.md).
While flexibility is key, note that performance may vary depending on the model used. Below is a list of currently implemented models.

| Name            | Notes                                                                                              |
|-----------------|----------------------------------------------------------------------------------------------------|
| **DeepSeek-r1** | New integration.                                                                                    |
| **Mistral 7B**  | Using non quantized mistral `mistral:7b-instruct-v0.3-q8_0` gives better results in exploit tasks. |
| **Gemma2**      | Better compared to mistral in vulnerability research tasks.                                        |

> *Note: AI-OPS prioritizes smaller, efficient LLMs to ensure accessibility and optimal performance, even on limited hardware.*

---

## Quickstart

### Requirements

To get started with AI-OPS, ensure you have the following dependencies installed:

- **Python** (*>= 3.11*): for AI-OPS CLI interface. 
- **Ollama** (*>= 0.3.0*): for LLM inference.
- **Docker** : for AI-OPS API.

### Get Started

Start by cloning the repository:

```bash
git clone https://github.com/antoninoLorenzo/AI-OPS.git
cd AI-OPS
```

Then configure Ollama, you can refer to their [documentation](https://github.com/ollama/ollama/blob/main/docs/README.md) for additional
details:

```bash
ollama run MODEL
```

> 💡 ***Tip:** If you lack mid/high-end GPUs to run LLMs locally you can follow [my guide](https://github.com/antoninoLorenzo/Ollama-on-Colab-with-ngrok) on how to run Ollama on Google Colab.*

Build and run the Docker container for the AI-OPS API using the following command. Replace `ENDPOINT` with the URL of your 
Ollama instance and `MODEL` with the name of the model you wish to use (e.g., Mistral 7B):

```bash
docker build -t ai-ops:api-dev --build-arg ollama_endpoint=ENDPOINT ollama_model=MODEL .
docker run -p 8000:8000 ai-ops:api-dev
```

To start interacting with AI-OPS, install and run the `ai-ops-cli` command-line client. Make sure to 
replace `AI-OPS_API_ADDRESS` with the address of your running Docker container (e.g., http://localhost:8000):

```bash
pip install .
ai-ops-cli --api AI-OPS_API_ADDRESS
```

### Additional Information

**User Documentation**

1. [Usage](./docs/user/1.Usage.md)
2. [Configuration](./docs/user/2.Configuration.md)

**Developer Documentation**

1. [Project Structure](./docs/development/1.Project%20Structure.md)

---

## ⚖️ Ethical and Legal Considerations

**AI-OPS** is designed as a penetration testing tool intended for academic and educational purposes only. Its primary goal is to assist cybersecurity professionals and enthusiasts in enhancing their understanding and skills in penetration testing through the use of AI-driven automation and tools.

### Disclaimer

The creators and contributors of **AI-OPS** are not responsible for any misuse of this tool. By using **AI-OPS**, you agree to take full responsibility for your actions and to use the tool in a manner that is ethical, legal, and in accordance with the intended purpose.

This project is provided "as-is" without any warranties, express or implied. The creators are not liable for any damages or legal repercussions resulting from the use of this tool.

> Yes, this section is generated with AI.
