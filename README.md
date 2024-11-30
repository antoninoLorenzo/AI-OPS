
<div style="display:flex; gap: 8px">

[![unit test](https://img.shields.io/badge/Unit%20Test-passing-<COLOR>.svg)](https://shields.io/) ![pylint](https://img.shields.io/badge/PyLint-8.94-yellow) [![license](https://img.shields.io/badge/LICENSE-MIT-<COLOR>.svg)](https://shields.io/)

</div>


🚧 **Under Development** 🚧

> **Note:** AI-OPS is currently an experimental project. 
> 
# AI-OPS

### Table of Contents
1. [Overview](#-overview)
   - [Key Features](#key-features)
   - [Supported Models](#supported-models)
2. [Quickstart](#quickstart)
3. [Ethical and Legal Considerations](#-ethical-and-legal-considerations)

---

## 💡 Overview

AI-OPS is a **Penetration Testing AI Assistant** that leverages open-source Large Language Models (*LLMs*)
to explore the role of Generative AI in ethical hacking. With a focus on accessibility and practical use, it 
aims to bridge the gap between AI research and usage during real-world workflows.


### 🚀 Key Features

- 🎁 **Full Open-Source**: No need for third-party LLM providers; use any model you prefer with [Ollama](https://github.com/ollama/ollama).

<!--
### ▶️ Demo

TODO
-->


### Supported Models

AI-OPS supports virtually any LLM that can be hosted with Ollama, allowing you to tailor the assistant to your 
available resources; for detailed setup instructions, see [Configuration](./docs/user/2.Configuration.md).
While flexibility is key, note that performance may vary depending on the model used. Below is a list of currently implemented models.

| Name           | Implemented |
|----------------|-------------|
| **Mistral 7B** | &check;     | 

> *Note: AI-OPS prioritizes smaller, efficient LLMs like Mistral 7B to ensure accessibility and optimal performance, even on limited hardware.*

## Quickstart

**Requirements**
- Python (>= 3.11)
- Ollama (>= 0.3.0)
- Docker

```
# Clone Repository 
git clone https://github.com/antoninoLorenzo/AI-OPS.git

# Launch Ollama (...)
 
# Run `ai_ops_api.py` or build manually:
docker build -t ai-ops:api-dev --build-arg ollama_endpoint=ENDPOINT ollama_model=MODEL .
docker run -p 8000:8000 ai-ops:api-dev

# Install Client
pip install .

# Run Client
ai-ops-cli --api AI-OPS_API_ADDRESS
```

---

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