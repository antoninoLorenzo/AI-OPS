import os
import sys
import json

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

SCENARIO_PROMPT = """
You are tasked to design Scenarios for Penetration Testing. A Scenario is an hypothetical situation that sets the stage for a user's request within th penetration testing process.
The user will require you to generate a certain number of scenarios, for example he will make a query "5" and you will generate 5 scenarios.

**Scenario Structure**
The overall structure of a Penetration Testing is made by the following components:
- User Background: this describes the user technical knowledge and experience level (beginner, intermediate and advanced).
- Objective: this specifies the user's goal within the penetration testing process.
- Target System Information: this indicates wether the user has information about the target system, during the initiali interaction between the user and the agent the required information is IP or URL of the target system that should be provided by the user, hypotethically; however you should include Scenarios where the user do not have this kind of information.
- Penetration Testing Phase: It could involve Reconnaissance (Network Scanning, Enumeration), Initial Access or Privilege Escalation. 

**Scenario Format**
You will provide the Scenarios in the following format:
{"user_background": "level", "objective": "objective description", "target": "empty if not provided or IP/URL if provided", "phase": "penetration testing phase"}

**Example**
User: 4
You:
[
{{
  "user_background": "Beginner",
  "objective": "Identify potential security weaknesses in a network",
  "target": "",
  "phase": "Reconnaissance"
}},
{{
  "user_background": "Intermediate",
  "objective": "Gain initial access to a system on a specific network segment",
  "target": "192.168.1.0/24",
  "phase": "Initial Access"
}},
{{
  "user_background": "Intermediate",
  "objective": "Plan a privilege escalation attack on a Linux system, focusing on exploiting buffer overflows",
  "target": "",
  "phase": "Privilege Escalation"
}},
{{
  "user_background": "Advanced",
  "objective": "Identify potential web application vulnerabilities using a specific vulnerability scanner",
  "target": "www.example.com",
  "phase": "Reconnaissance"
}}
]

----------------------------------------------------------------

Query: {num_scenarios}
"""

QUERY_PROMPT = """
You are tasked to generate a user query based on a Penetration Testing Scenario. A Scenario is an hypothetical situation that sets the stage for a user's request within th penetration testing process.

You will be provided with:
- User Background: this describes the user technical knowledge and experience level (beginner, intermediate and advanced).
- Objective: specifies the user goal within the penetration testing process
- Target: a IP or URL of the target system, it can be not provided, if not provided it will be "NaN"
- Phase: the penetration testing phase (Reconnaissance, Initial Access, Privilege Escalation)

**Guidelines**
1. The query should be phrased in a way that aligns with the user's technical knowledge level (Beginner, Intermediate or Advanced).
2. The query should express the user objective, based on his experience level it can be more or less clear.

**Output Format**
{"query": "the user query generated from the scenario"}

**Examples**
User: {"user_background": "Beginner", "objective": "Learn the basics of network scanning and identify open ports on a target system.", "target": "NaN", "phase": "Reconnaissance"}
You:
{"query": "Hi, I need to know what ports are opened on a target system, can you help me?"}

User: {"user_background": "Intermediate", "objective": "Attempt to exploit a known vulnerability in a web application to gain unauthorized access to sensitive data", "target": "https://example.com", "phase": "Initial Access"}
You:
{"query": "I'm looking to exploit a known vulnerability in a web application to gain unauthorized access to sensitive data on https://example.com. Could you provide a detailed guide on identifying and exploiting vulnerabilities like SQL injection or Cross-Site Scripting (XSS)? Additionally, what are the best tools for this process, and how can these vulnerabilities be mitigated after exploitation?"}

----------------------------------------------------------------

User Background: {user_background}
Objective: {objective}
Target: {target}
Phase: {phase}
"""


if __name__ == "__main__":
    # --- Setup
    GEMINI_KEY = os.getenv('GEMINI_API_KEY')
    if not GEMINI_KEY:
        print('Missing Gemini Key')
        sys.exit(1)

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
    for i in range(2):
        # generate scenario
        scenario_prompt = SCENARIO_PROMPT.format(num_scenarios=i*10)
        scenario_response = scenario_gen.generate_content(scenario_prompt, safety_settings=safety_settings)
        scenario = json.loads(scenario_response.text)

        # generate query
        background = scenario['user_background']
        objective = scenario['objective']
        target = scenario['target']
        phase = scenario['phase']

        query_prompt = QUERY_PROMPT.format(
            user_background=background,
            objective=objective,
            target=target,
            phase=phase
        )
        user_query = query_gen.generate_content(query_prompt, safety_settings=safety_settings)
        queries.append(user_query.text)

    for q in queries:
        print(f'Query: {q}\n')

    # --- Response Generation

    # --- Output
