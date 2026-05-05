# AutoPenBench benchmark execution code.
import os
import abc
import uuid
import json
import argparse
from datetime import datetime
from enum import StrEnum
from typing import List, Dict, ClassVar, Literal
from pathlib import Path

from dotenv import load_dotenv

from pydantic import BaseModel

from autopenbench.driver import PentestDriver
from autopenbench.utils import load_data, load_milestones

from ai_ops import API_BASE_ENV_NAME, API_KEY_ENV_NAME
from ai_ops.core import (
    ModelConfig, AgentConfig,
    AgentFactory, AgentRunner,
    Event, 
    TextEvent, 
    UserMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    StopEvent,
    LoadSkill, Whiteboard
)
from ai_ops.core.llm import build_inference_client
from ai_ops.core.conversation import get_conversation_store
from ai_ops.core.tools.load_skill.skill import get_skill_registry
from ai_ops.core.prompt import BASE_PROTOTYPE_PROMPT, SKILL_PROTOTYPE_PROMPT
from ai_ops.core.utils import get_logger

from benchmark.tools import (
    ExecuteBashTool, 
    SSHConnectTool, 
    FileWriteTool, 
    FinalAnswerTool
)
from benchmark.evaluator import Evaluator


_logger = get_logger(__name__)

_OUTPUT_PATH = Path(__file__).parent / "results_autopenbench"
_OUTPUT_PATH.mkdir(exist_ok=True)


_CVE_TASKS = [
    "cve-2024-36401",
    "cve-2024-23897",
    "cve-2022-22965",
    "cve-2021-3156",
    "cve-2021-42013",
    "cve-2021-43798",
    "cve-2021-25646",
    "cve-2021-44228",
    "cve-2019-16113",
    "cve-2017-7494",
    "cve-2014-0160",
]
_IN_VITRO_CATEGORIES = ["access_control", "cryptography", "network_security", "web_security"]

class InVitroCategories(StrEnum):
    AccessControl = "access_control"
    WebSecurity = "web_security"
    NetworkSecurity = "network_security"
    Cryptography = "cryptography"


class InVitroTaskSet(BaseModel):
    enabled: bool = True
    tasks: Dict[InVitroCategories, List[str]] = {
        InVitroCategories.AccessControl: [
            "in-vitro_access_control_vm0",
            "in-vitro_access_control_vm1",
            "in-vitro_access_control_vm2",
            "in-vitro_access_control_vm3",
            "in-vitro_access_control_vm4"
        ],
        InVitroCategories.WebSecurity: [
            "in-vitro_web_security_vm0",
            "in-vitro_web_security_vm1",
            "in-vitro_web_security_vm2",
            "in-vitro_web_security_vm3",
            "in-vitro_web_security_vm4",
            "in-vitro_web_security_vm5",
            "in-vitro_web_security_vm6"
        ],
        InVitroCategories.NetworkSecurity: [
            "in-vitro_network_security_vm0",
            "in-vitro_network_security_vm1",
            "in-vitro_network_security_vm2",
            "in-vitro_network_security_vm3",
            "in-vitro_network_security_vm4",
            "in-vitro_network_security_vm5"
        ],
        InVitroCategories.Cryptography: [
            "in-vitro_cryptography_vm0",
            "in-vitro_cryptography_vm1",
            "in-vitro_cryptography_vm2",
            "in-vitro_cryptography_vm3"
        ]
    }


class RealWorldTaskSet(BaseModel):
    enabled: bool = True
    tasks: List[str] = _CVE_TASKS


class AutoPenBenchRun(BaseModel):
    model: str
    judge: str
    in_vitro: InVitroTaskSet
    real_world: RealWorldTaskSet
    dry_run: bool = False


def get_run_settings() -> AutoPenBenchRun:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "model", type=str,
        help="Specify model id as <provider>/<model>. Use `hosted_vllm/model` for vLLM."
    )

    # here the assumption is that they have the same provider (the case for me, for now)
    parser.add_argument("judge", type=str)

    parser.add_argument("--output-path", type=str, default=_OUTPUT_PATH)

    # want to be able to specify a subset of benchmark tasks to run, by default all run
    parser.add_argument(
        "--difficulty", 
        nargs="*",
        choices=["in-vitro", "real-world"],
        default=["in-vitro", "real-world"]
    )

    parser.add_argument(
        "--in-vitro-categories",
        nargs="*",
        choices=_IN_VITRO_CATEGORIES,
        default=_IN_VITRO_CATEGORIES,
    )

    parser.add_argument(
        "--access-control",
        nargs="*",
        choices=["0", "1", "2", "3", "4"],
        default=["0", "1", "2", "3", "4"]
    )

    parser.add_argument(
        "--cryptography",
        nargs="*",
        choices=["0", "1", "2", "3"],
        default=["0", "1", "2", "3"]
    )

    parser.add_argument(
        "--network-security",
        nargs="*",
        choices=["0", "1", "2", "3", "4", "5"],
        default=["0", "1", "2", "3", "4", "5"]
    )

    parser.add_argument(
        "--web-security",
        nargs="*",
        choices=["0", "1", "2", "3", "4", "5", "6"],
        default=["0", "1", "2", "3", "4", "5", "6"]
    )

    parser.add_argument(
        "--real-world-cve",
        nargs="*",
        choices=_CVE_TASKS,
        default=_CVE_TASKS
    )

    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="skip agent execution, basically ensures benchmark containers are available"
    )

    args = parser.parse_args()

    in_vitro_enabled = "in-vitro" in args.difficulty
    real_world_enabled = "real-world" in args.difficulty

    category_to_indices: Dict[InVitroCategories, List[str]] = {
        InVitroCategories.AccessControl: args.access_control,
        InVitroCategories.Cryptography: args.cryptography,
        InVitroCategories.NetworkSecurity: args.network_security,
        InVitroCategories.WebSecurity: args.web_security,
    }

    default_tasks = InVitroTaskSet().tasks
    filtered_tasks = {
        cat: [
            task for task in default_tasks[cat]
            if task.split("_vm")[-1] in category_to_indices[cat]
        ]
        for cat in InVitroCategories
        if cat.value in args.in_vitro_categories
    }

    return AutoPenBenchRun(
        model=args.model,
        judge=args.judge,
        in_vitro=InVitroTaskSet(
            enabled=in_vitro_enabled, 
            tasks=filtered_tasks
        ),
        real_world=RealWorldTaskSet(
            enabled=real_world_enabled,
            tasks=args.real_world_cve
        ),
        dry_run=args.dry_run
    )


class Task(abc.ABC, BaseModel):
    difficulty: ClassVar[Literal["in-vitro", "real-world"]]
    task: str
    flag: str
    target: str
    vulnerability: str
    command_milestones: List[str]
    stage_milestones: List[str]


class InVitroTask(Task, BaseModel):
    difficulty: ClassVar[Literal["in-vitro", "real-world"]] = "in-vitro"
    category: Literal["access_control", "web_security", "network_security", "cryptography"]


class RealWorldTask(Task, BaseModel):
    difficulty: ClassVar[Literal["in-vitro", "real-world"]] = "real-world"
    alias: str


def load_tasks(settings: AutoPenBenchRun) -> List[Task]:
    data = {}
    if settings.in_vitro.enabled:
        data["in-vitro"] = load_data("in-vitro")
    if settings.real_world.enabled:
        data["real-world"] = load_data("real-world")
    
    task_list = []
    for category in data.get("in-vitro", []):
        if category not in settings.in_vitro.tasks:
            continue

        for idx, task in enumerate(data["in-vitro"][category]):
            if task["target"] not in settings.in_vitro.tasks[category]:
                continue

            command_milestones = load_milestones("command", "in-vitro", category, idx)
            stage_milestones = load_milestones("stage", "in-vitro", category, idx)
            task_list.append(
                InVitroTask(
                    category=category,
                    task=task["task"],
                    flag=task["flag"],
                    target=task["target"],
                    vulnerability=task["vulnerability"],
                    command_milestones=command_milestones,
                    stage_milestones=stage_milestones
                )
            )
    
    for idx, task in enumerate(data.get("real-world", {"cve": []})["cve"]):
        if task["vulnerability"] not in settings.real_world.tasks:
            continue

        command_milestones = load_milestones("command", "real-world", "cve", idx)
        stage_milestones = load_milestones("stage", "real-world", "cve", idx)
        task_list.append(
            RealWorldTask(
                task=task["task"],
                flag=task["flag"],
                target=task["target"],
                vulnerability=task["vulnerability"],
                alias=task["alias"],
                command_milestones=command_milestones,
                stage_milestones=stage_milestones
            )
        )

    return task_list


def run_task(
    task: Task,
    agent_config: AgentConfig,
    agent_model: ModelConfig,
    judge_model: ModelConfig,
    output_path: Path
):
    _logger.info(f"Starting AutoPenBench run {task.task}")
    
    driver = PentestDriver(task.task, task.flag, task.target)
    observation, _ = driver.reset()

    system_prompt = BASE_PROTOTYPE_PROMPT
    if LoadSkill.name in [tool.name for tool in agent_config.tools]:
        skill_registry = get_skill_registry()
        system_prompt += SKILL_PROTOTYPE_PROMPT.format(skill_index=skill_registry.get_index())

    conversation_store = get_conversation_store()
    conversation = conversation_store.create(system_prompt=system_prompt)
    run_id = datetime.now().strftime("%d-%m-%Y_%H:%M") + conversation.id

    agent = AgentRunner(
        conversation_id=conversation.id,
        client=build_inference_client(models=[agent_model]),
        tools=[tool.name for tool in agent_config.tools],
        context_fn=agent_config.context_fn,
        extra_tool_ctx={"driver": driver}
    )

    judge = Evaluator(
        judge_llm=judge_model,
        command_milestones=task.command_milestones,
        stage_milestones=task.stage_milestones
    )

    progress = {
        "complete": False,
        "command_progress": [False] * len(task.command_milestones),
        "stage_progress": [False] * len(task.stage_milestones)
    }
    event_stream = agent.run(user_message=UserMessageEvent(content=task.task))
    for event in event_stream:
        if isinstance(event, TextEvent):
            print(f"Assistant: {event.chunk}")
        elif isinstance(event, ToolCallEvent):
            print(f"ToolCallEvent: {event.name}({event.args})")
        elif isinstance(event, ToolResultEvent):
            step = f"{event.name}({event.args})\n{event.result}"
            print(f"ToolResultEvent: {step}")

            progress = judge.evaluate_step(step=step)
            command_complete = list(filter(None, progress["command_progress"]))
            stage_complete = list(filter(None, progress["stage_progress"]))
        
            print(
                f"complete          : {progress['complete']}\n"
                f"command_progress  : {len(command_complete)}/{len(progress['command_progress'])}\n"
                f"stage_progress    : {len(stage_complete)}/{len(progress['stage_progress'])}\n"
            )
        elif isinstance(event, StopEvent):
            print(f"StopEvent: reason={event.reason}, max_iteration={event.max_iteration}")
    
    command_complete = list(filter(None, progress["command_progress"]))
    stage_complete = list(filter(None, progress["stage_progress"]))

    result = {
        "run_id": run_id,
        "model": agent_model.model,
        "judge": judge_model.model,
        "target": task.target,
        "vulnerability": task.vulnerability,
        "difficulty": task.difficulty,
        "complete": progress["complete"],
        "command_progress_reached": len(command_complete),
        "command_progress_total": len(progress["command_progress"]),
        "stage_progress_reached": len(stage_complete),
        "stage_progress_total": len(progress["stage_progress"]),
    }

    with open(str(output_path), "w") as fp:
        json.dump(result, fp, indent=4)

    _logger.info(f"Results saved to {output_path}")
    return result


def main():
    api_base = os.environ.get(API_BASE_ENV_NAME, None)
    if api_base:
        api_base = api_base.rstrip("/")
    
    api_key = os.environ.get(API_KEY_ENV_NAME, None)

    run_settings = get_run_settings()
    tasks = load_tasks(settings=run_settings)
    if run_settings.dry_run:
        print(f'Dry Run')
        for task in tasks:
            driver = PentestDriver(task.task, task.flag, task.target)
            observation, _ = driver.reset()
        return

    agent_config = AgentConfig(
        tools=[
            Whiteboard, LoadSkill, 
            ExecuteBashTool, FileWriteTool, SSHConnectTool, FinalAnswerTool
        ]
    )
    agent_model = ModelConfig(model=run_settings.model, api_base=api_base, api_key=api_key)
    judge_model = ModelConfig(model=run_settings.judge, api_base=api_base, api_key=api_key)
    
    # one directory per benchmark run, so results from different runs don't mix
    model_slug = run_settings.model.replace("/", "_")
    run_timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
    run_dir = _OUTPUT_PATH / f"{run_timestamp}_{model_slug}"
    run_dir.mkdir(exist_ok=True)

    results = []
    for task in tasks:
        _logger.info(f"Target: {task.target} | Vulnerability: {task.vulnerability}")
        output_path = run_dir / f"{task.target}.json"
        try:
            result = run_task(
                task=task,
                agent_config=agent_config,
                agent_model=agent_model,
                judge_model=judge_model,
                output_path=output_path
            )
            results.append(result)
        except Exception as e:
            _logger.error(f"Task {task.target} failed: {e}")
            results.append({
                "target": task.target,
                "vulnerability": task.vulnerability,
                "difficulty": task.difficulty,
                "error": str(e)
            })

    # aggregate summary across all tasks in this run
    summary_path = run_dir / "summary.json"
    with open(str(summary_path), "w") as fp:
        json.dump(results, fp, indent=4)
    _logger.info(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    load_dotenv()
    main()
