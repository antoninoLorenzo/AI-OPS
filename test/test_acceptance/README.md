# Acceptance Test

## Overview

The acceptance test is designed to determine whether an AI model can effectively assist with
penetration testing tasks. The primary focus is to assess whether the model can handle requests 
that may be ethically sensitive, such as providing advice on exploiting vulnerabilities. This 
is essentially a **jailbreak test** to evaluate the model's willingness and ability to respond 
to queries related to penetration testing.

## Test Approach

The test involves generating realistic penetration testing scenarios, followed by detailed queries 
based on those scenarios; those cover various type of tasks (tool usage, exploit development, ...)
and various difficulty levels, ensuring a comprehensive assessment of the model’s response.
The main objective is to understand where a model may refrain from assisting due to ethical constraints.

### Types of Tasks Tested

The queries are grouped by task type to cover different aspects of penetration testing:
- **Attack Vector Suggestion**: Identifying potential ways to exploit a vulnerability.
- **Tool Usage**: Guidance on using specific tools like Nmap or Metasploit for reconnaissance or exploitation.
- **Exploit Development**: Assisting in writing code or scripts to exploit identified vulnerabilities.

## Implementation

The test is powered by the **Gemini API**, which is used to generate both the scenarios and the corresponding
queries.

> Note: the API is free to use but there are geolocation restrictions (a VPN does the job)


### Dataset Generation

To create the dataset, a series of penetration testing scenarios are generated programmatically using 
large language models. Each scenario includes key elements like the task type, difficulty level (beginner, 
intermediate, advanced), and the technical context. From these scenarios, specific user queries are then 
generated to simulate real-world penetration testing questions.

The dataset ensures a balanced representation of the different types of tasks commonly encountered in 
penetration testing. This helps provide a detailed view of where the model excels or where it may encounter
ethical dilemmas.



