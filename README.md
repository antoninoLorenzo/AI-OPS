![pylint](https://img.shields.io/badge/PyLint-7.19-orange?logo=python&logoColor=white)

# AI-OPS

### Table of Contents
1. [Overview](#-overview)
   
   2. [Key Features](#key-features)
   3. [Components](#components)
3. [Install](#-install)
   
   3. [End-User](#end-user)
   4. [Development](#development)
5. [Tools](#-tools)
   
   4. [Available Tools](#available-tools)
   5. [Add a Tool](#add-a-tool)
7. [Knowledge](#-knowledge)
   
   5. [Available Collections](#available-collections)
   6. [Add a Collection](#add-a-collection)

## 💡 Overview

- **AI** powered: uses a LLM AI-Agent to assist and automate
- **O**pen-source: full open-source solution (even the LLM)
- **P**entesting **S**uite: includes several tools for various use cases


The objective of **AI-OPS** is to enhance Penetration Testing operations with an *AI Agent*
capable of planning and executing tasks, whether that's about automating the **Reconnaissance**,
the **Exploitation**, generating a **Report** or just getting another point of view on a target system.

<ins>AI-OPS objective is not replacing human Pentesters</ins>, it is an AI Agent with *human-in-the-loop*
by design, think it as follows: AI will not replace programmers, it makes bad programmers job worse, but 
it enhances great programmers and make them more productive; that's the same objective of AI-OPS.


### Key Features

- 🎁 **Full Open-Source** : this project do not require any subscription to third party LLM providers, we use 
[Ollama](https://github.com/ollama/ollama) as main LLM provider, meaning that you can use <ins>whatever model you 
want</ins>.
- 🔧 **Tool Integration** : the agent can execute Penetration Testing tools, not only the most common tools are 
available (see [Available Tools](#available-tools)), but you can integrate <ins>whatever tool you want</ins> without 
knowing how to code in Python (see [Add a Tool](#add-a-tool)).
- 📚 **Up-to-date Knowledge** : the agent won't leverage only training information, there is a `RAG` system available 
that enables the agent to get up-to-date knowledge, and you can add <ins>whatever document you want</ins> (see 
[Add a Collection](#add-a-collection)).
- ⚙️ **Scalability** : every component of the agent is independently deployable, meaning that you can leverage <ins>
whatever hardware setup</ins> you have available (see [Components](#components) and [End-User](#end-user) installation).


### Components
![Deployment Diagram](static/images/deployment_diagram.svg)

| Component                                  | Description                                                             |
|--------------------------------------------|-------------------------------------------------------------------------|
| Frontend                                   | Web interface for the AI Agent built in `React`                         |
| AI Agent                                   | The implementation of the AI Agent exposed to `Frontend` with `FastAPI` |
| [Qdrant](https://github.com/qdrant/qdrant) | Vector Database                                                         |
| [Ollama](https://github.com/ollama/ollama)                              | LLM Provider                                                            | 


## 💻 Install

### End-User
**Requirements**
- Ollama
- Docker
- Minimum hardware requirements to-be-defined


1. **TODO:** *work in progress*

### Development

**Requirements**
- Ollama
- Linux
- Python
- Node
- Docker

1. **TODO:** *work in progress*
2. Install `requirements` and `dev-requirements`
```
pip install -r requirements.txt
```
```
pip install -r dev-requirements.txt
```
2. Install spacy `en_core_web_lg`
```
python -m spacy download en_core_web_lg
```

## 🛠️Tools

### Available Tools

| Name        | Use Case                         | Implemented         |
|-------------|----------------------------------|---------------------|
| nmap        | Scanning/Network Exploitation    | &check;             |
| hashcat     | Password Cracking                | &cross;             |
| SQLmap      | SQL Injection                    | &cross;             | 
| Metasploit  | Exploitation                     | &cross;             |

### Add a Tool

Most Penetration Testing tools are 'simple' CLI programs, so the Agent only needs a Terminal and 
instructions to use the tool, however there are more advanced tools (such as `Metasploit`) that 
need a specific class to be integrated; for this reason there are two ways of adding a tool:
1. **JSON Instructions**: create a file with instructions for the Agent and add it to 
`/home/YOUR_USERNAME/.aiops/tools` (or `../Users/YOUR_USERNAME/.aiops/tools`); all available tools 
that use JSON Instructions are available in `tools_settings`.
```json
{
    "name": "...",
    "tool_description": "...",
    "args_description": [
        "Multiline JSON\n",
        "instructions\n",
        "..."
    ],
    "examples": [
        "<THOUGHT>reason to execute (thought process) </THOUGHT>\n",
        "<TOOL>command (ex. nmap -sV 127.0.0.1)</TOOL>\n"
    ]
}
```

2. **Custom Class**: tools that require more advanced usage can be implemented extending the class
`Tool` at `src.agent.tools.base`; you're welcome to **open an issue** for a tool request/proposal.


## 📚 Knowledge 

**TODO**

### Available Collections

**TODO**


### Add a Collection

**TODO**
