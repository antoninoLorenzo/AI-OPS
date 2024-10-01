import os
import sys
import json
import time

import google.api_core.exceptions
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from tqdm import tqdm
from dotenv import load_dotenv

from src.agent.tools import TOOLS

load_dotenv()

SCENARIO_PROMPT = """
You are tasked to design Scenarios for Penetration Testing. A Scenario is an hypothetical situation that sets the stage for a user's request within th penetration testing process.
The user will require you to generate a certain number of scenarios, for example he will make a query "5" and you will generate 5 scenarios.

**Scenario Structure**
The overall structure of a Penetration Testing Scenario is made by the following components:
- Task: the context of the Penetration Testing situation
- Type of Task (ToT)
- Difficulty: experience level required to solve the task (beginner, intermediate and advanced).

**Possible Type of Task (ToT)**
- Attack Vector Suggestion
- Tool Usage, for example "provide a command to do X" or "why command X gives output Y"
- Exploit Development

**Scenario Format**
You will provide the Scenarios in the following format:
{{"task": "...", "difficulty": "level", "ToT": "type of task"}}

**Example**
User: 3
You:
[
{{
  "task": "The user needs a reverse shell and provides some specific constraints about the program used to get it.",
  "ToT": "Attack Vector Suggestion",
  "difficulty": "Intermediate",
}},
{{
  "task": "The user provides a hydra command that speifies how to perform a brute force attack on a http form using a user list and a password list; he needs to understand how the success of the attack is defined in the hydra command.",
  "ToT": "Tool Usage",
  "difficulty": "Beginner",
}},
{{
  "task": "The user is writing the code to exploit a Linux server running a custom network service with no ASLR or stack canaries; the goal is to achieve root access via a heap overflow vulnerability.",
  "ToT": "Exploit Development",
  "difficulty": "Advanced",
}},
]

----------------------------------------------------------------

Query: {num_scenarios}
"""

QUERY_PROMPT = """
You are tasked to generate a user query based on a Penetration Testing Scenario. 
A Scenario is an hypothetical situation that sets the stage for a user's request within th penetration testing process.

You will be provided with:
- Task
- Type of Task (ToT)
- Difficulty: experience level required to solve the task (beginner, intermediate and advanced).

**Guidelines**
1. The query should be phrased in a way that aligns with the user's technical knowledge level (Beginner, Intermediate or Advanced).
2. The query should express the user objective, based on his experience level it can be more or less clear.
3. The query should contain additional details that are not provided in the scenario, in order to make it even more specific.

**Output Format**
{{"query": "the user query generated from the scenario"}}

**Examples**
{{"task": "The user wants to use Nmap to scan a network for open ports and services. They need to understand the different scan types available and how to customize the scan for specific needs.", "ToT": "Tool Usage", "difficulty": "Beginner"}}
You:
{{"query": "Using nmap I need to scan the network 192.168.1.1 to gain information about exposed services, however I don't know how to adjust the scan to make it stealth."}}

----------------------------------------------------------------

Task: {task}
ToT: {type_of_task}
Difficulty: {difficulty}
"""


if __name__ == "__main__":
    # --- Setup
    GEMINI_KEY = os.getenv('GEMINI_API_KEY')
    if not GEMINI_KEY:
        print('Missing Gemini Key')
        sys.exit(-1)
    genai.configure(api_key=GEMINI_KEY)

    scenario_gen = genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
    query_gen = genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
    safety_settings = {
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
    }

    # --- Query Generation
    queries = []
    n_scenarios = 10
    for i in tqdm(range(1, n_scenarios), total=n_scenarios, desc='Generating Scenarios'):
        try:
            # generate scenario
            scenario_prompt = SCENARIO_PROMPT.format(num_scenarios=n_scenarios)
            scenario_response = scenario_gen.generate_content(scenario_prompt, safety_settings=safety_settings)
            scenarios = json.loads(scenario_response.text)

            # generate query
            for scenario in scenarios:
                task = scenario['task']
                type_of_task = scenario['ToT']
                difficulty = scenario['difficulty']

                query_prompt = QUERY_PROMPT.format(
                    task=task,
                    type_of_task=type_of_task,
                    difficulty=difficulty
                )
                user_query = query_gen.generate_content(query_prompt, safety_settings=safety_settings)
                query = json.loads(user_query.text)
                queries.append(query['query'])
                time.sleep(1)
        except google.api_core.exceptions.ResourceExhausted:
            time.sleep(15)  # that way could potentially skip an iteration or part of it

    # Export Planning Test Cases
    with open('test_cases/acceptance.json', 'w+', encoding='utf-8') as fp:
        json.dump([{'query': q} for q in queries], fp)
