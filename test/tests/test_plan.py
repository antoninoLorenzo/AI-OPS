import textwrap
import unittest

from src.agent import Agent
from src.agent.tools import Terminal
from src.agent.plan import Plan, Task, TaskStatus


class TestPlan(unittest.TestCase):

    NL_PLANS = [
        textwrap.dedent("""
I completely agree with you! Let's refine our plan and use the tools more efficiently.

**Step 1: DNS Information**

Using `dig`, we'll gather DNS information about the target domain:

<TOOL>terminal dig example.com</TOOL>

This will provide us with valuable information, such as MX records, NS records, and potential subdomains.

**Step 2: Port Scan (nmap -sV)**

We can skip scanning specific ports since `nmap -sV` already scans the common ports (80, 21, 22, and 443). This will give us a comprehensive view of open ports and services:

<TOOL>nmap -sV example.com</TOOL>

**Step 3: NSE Scripting**

To gather more information, we can use nmap's NSE (Nmap Scripting Engine) to run scripts that scan for vulnerabilities, check for common web servers, and identify potential issues. For example:

<TOOL>nmap --script=http-title,http-open-proxy,http-methods,http-robots.txt example.com</TOOL>

This will help us identify potential vulnerabilities, open proxies, and other information.

**Step 4: Operating System Identification**

Using `nmap -O`, we can determine the operating system running on the target machine:

<TOOL>terminal nmap -O example.com</TOOL>

This will help us narrow down potential attack vectors or identify specific vulnerabilities.

By refining our plan, we can gather more information about the target host and services without attempting to exploit any vulnerabilities. What do you think?
        """),
        textwrap.dedent("""
        **Plan for Reconnaissance Phase:**

**Target System:** 154.142.1.1 (IP Camera).
**Objective:** Gather information about the operating system, services, data transmission, and potential vulnerabilities.
**Tasks:**

1. **Nmap Scan**: Use Nmap to gather information about the IP Camera's operating system, services, and open ports.
   - Execute the following command: `nmap -O -sV 154.142.1.1`
2. **Operating System Detection**: Identify the operating system running on the IP Camera using Nmap's `-O` option.
3. **Service Detection**: Identify any services or protocols being used by the IP Camera, such as HTTP, FTP, or SSH, using Nmap's `-sV` option.
4. **Data Transmission Analysis**: Use Nmap's `-A` option to analyze data transmission patterns and identify any potential issues.
5. **SSH and FTP Vulnerability Scan**: Run a vulnerability scan for SSH and FTP protocols using Nmap's `--script` option with the following commands:
   - `nmap --script sshvuln 154.142.1.1`
   - `nmap --script ftp-vuln 154.142.1.1`

Please let me know if you'd like to proceed with this plan or if you have any specific requirements or concerns.
        """),
    ]

    def test_execute(self):
        tasks = [
            Task(thought="Get directory content", tool=Terminal, command="ls"),
            Task(thought="Get machine host name", tool=Terminal, command="hostname")
        ]

        plan = Plan(tasks)
        for output in plan.execute():
            print('---------------------------------')
            for i, task_overview in enumerate(output):
                print(f'{i+1}. {task_overview}')
                if task_overview.status == TaskStatus.DONE:
                    print(f'Output:\n{task_overview.output}')

    def test_from_response(self):
        agent = Agent(model='llama3')
        for plan_nl in TestPlan.NL_PLANS:
            plan = agent.extract_plan(plan_nl)
            print(plan)
            self.assertIsNotNone(plan)

    # def test_should_timeout(self):
    #     pass

    # def test_multi_step_task(self):
    #     pass


if __name__ == "__main__":
    unittest.main()
