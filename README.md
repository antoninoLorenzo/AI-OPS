![pylint](https://img.shields.io/badge/PyLint-7.10-orange?logo=python&logoColor=white)

# AI-OPS

### Table of Contents
1. [Overview](#-overview)

    - [Key Features](#key-features)
2. [Install](#-install)

    - [End-User](#end-user)
    - [Development](#development)
3. [Tools](#tools)

    - [Available Tools](#available-tools)
    - [Add a Tool](#add-a-tool)
4. [Knowledge](#-knowledge-)

    - [Available Collections](#available-collections)
    - [Add a Collection](#add-a-collection)

## 💡 Overview

- **AI** powered: uses a LLM AI-Agent to assist and automate
- **O**pen-source: full open-source solution (even the LLM)
- **P**entesting **S**uite: includes several tools for various use cases


The objective of **AI-OPS** is to enhance Penetration Testing operations with an *AI Agent*
capable of planning and executing tasks, whether that's about automating the **Reconnaisance**,
the **Exploitation**, generating a **Report** or just getting another point of view on a target system.

<ins>AI-OPS objective is not replacing human Pentesters</ins>, it is an AI Agent with *human-in-the-loop*
by design, think it as follows: AI will not replace programmers, it makes bad programmers job worse, but 
it enhances great programmers and make them more productive; that's the same objective of AI-OPS.


### Key Features

**TODO:** *LLM integrations, Knowledge, Collections, Tools etc.*

## 💻 Install

### End-User
**Requirements**
- Ollama
- Docker

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
