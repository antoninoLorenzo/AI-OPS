"""
Script to generate tool documentation for AI-OPS agent.

Documentation generation requires a "Tool Documentation" json file in the following format:
[
    {
        "title": "Documentation page title",
        "content": "Page content"
    }
]

Documentation generation requires a Gemini API key; Google provides free inference
for 'gemini-1.5-flash', however it is a service limited to some countries. (a VPN does the job)

------------------------------------------------------------------------------------------------
The tool documentation generation process is inspired by:
EASYTOOL: Enhancing LLM-based Agents with Concise Tool Instruction (https://arxiv.org/abs/2401.06201)
"""
import sys
import os
import json
import argparse
import textwrap
from textwrap import dedent

from tqdm import tqdm
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from dotenv import load_dotenv


PROMPTS = {
    'summarization': textwrap.dedent("""Your job is to create a concise and effective tool usage description based on the tool documentation. 
        You should ensure the description only contains the purposes of the tool without irrelevant information. 
        You will be provided with several pages of documentation, there is a lot of information that is not useful to use the tool.
        
        IMPORTANT: 
        - Your output should include command examples.
        - Do not include links to the documentation.
        
        Tool Documentation:
        {tool_documentation}
    """),
    'scenario': textwrap.dedent("""Your task is to create the scenario that will use the tool. You are given a tool with its purpose and its parameters list. 
        The scenario should adopt the parameters in the list.
        
        Consider the following example:
        Input: ‘Ebay’ can get products from Ebay in a specific country. ‘Product Details’ in ‘Ebay’ can get the product details for a given product id and a specific country.
        Scenario: if you want to know the details of the product with product ID 1954 in Germany from Ebay
        
        Tool Documentation:
        {tool_documentation}
    """),
    'output': textwrap.dedent("""Your job is to provide tool usage guidelines for a Large Language Model based on the input provided. 
        The input provided is composed by Tool Documentation and Tool Scenarios.
        The Tool Scenarios are used to provide more detailed information in "args_description" field.

        Your output should be in the following JSON format:
        {{
            "name": "tool name",
            "tool_description": "Short description.",
            "args_description": [
                "This is line one of tool arguments description.\n",
                "This is line two of tool arguments description.\n"
            ]
        }}

        IMPORTANT: The output will be provided as guidelines for a Large Language Model, you should make the descriptions coincise to limit the context length, however you should ensure high quality information is provided.
        
        Tool Documentation:
        {tool_documentation}
        
        Tool Scenarios:
        {tool_scenarios}
    """)
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}


def parse_arguments(argv: list):
    """Parsing command line arguments"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--tool-name",
        required=True,
        help="The name of the tool"
    )

    parser.add_argument(
        "--docs-path",
        required=True,
        help="The path to the JSON documentation file"
    )

    parser.add_argument(
        "--api-key",
        required=True,
        help="API key for Gemini"
    )

    parser.add_argument(
        "--output-path",
        help="Specifies the path for tool guidelines"
    )

    arguments = parser.parse_args(argv)
    print(arguments)

    return {
        'tool_name': arguments.tool_name,
        'docs_path': arguments.docs_path,
        'api_key': arguments.api_key
    }


def load_tool_docs(path: str, tool_name: str) -> str:
    """Get the full tool documentation from a json file.
    Tool Documentation is a JSON list containing pages, each
    page contains a "title" field and a "content field".

    :param path: tool documentation path
    :param tool_name: the tool name
    """
    if not os.path.exists(path):
        raise RuntimeError(f"Path don't exists: {path}")
    print('Loading tool documentation')

    out = f'# {tool_name}\n\n'
    with open(path, 'r', encoding='utf-8') as fp:
        data = json.load(fp)

        if len(data) == 0:
            raise RuntimeError(f"Empty documentation")

        for page in data:
            if not ('title' in page and 'content' in page):
                print('[!] Skipped page: "title" or "content" not found')
                continue
            out += f'## {page["title"]}\n{page["content"]}\n\n'

    return out


def generate_summary(full_docs: str) -> str:
    """Generates the summary of the tool documentation"""
    print('Generating summary')
    llm = genai.GenerativeModel('gemini-1.5-flash')
    prompt = PROMPTS['summarization'].format(tool_documentation=full_docs)
    response = llm.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
    return response.text


def generate_scenarios(docs_summary: str,
                       num_scenarios: int = 3) -> list[str]:
    """Generates usage scenarios based on the summarized tool documentation"""
    print('Generating Scenarios')
    llm = genai.GenerativeModel('gemini-1.5-flash')
    prompt = PROMPTS['scenario'].format(tool_documentation=docs_summary)

    scenarios = []
    for i in range(num_scenarios):
        response = llm.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
        scenarios.append(f'[{i}]\n{response.text}\n')
    return scenarios


def generate_tool_documentation(path: str, tool_name) -> dict:
    """Generates the tool documentation dictionary"""
    tool_docs = load_tool_docs(path, tool_name)

    tool_docs_summary = generate_summary(tool_docs)
    scenarios = generate_scenarios(tool_docs_summary)

    llm = genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
    prompt = PROMPTS['output'].format(
        tool_documentation=tool_docs_summary,
        tool_scenarios='\n'.join(scenarios)
    )

    print('Generating tool documentation')
    response = llm.generate_content(prompt, safety_settings=SAFETY_SETTINGS)
    tool_guidelines = json.loads(response.text)

    return tool_guidelines


if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])

    genai.configure(api_key=args['api_key'])
    output = generate_tool_documentation(args['docs_path'], args['tool_name'])
    print(output)


