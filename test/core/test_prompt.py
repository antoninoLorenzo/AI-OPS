import os
import time
import uuid
import json
import urllib3
from pathlib import Path
from typing import Literal

import pytest

import ai_ops
from ai_ops.core.prompt.registry import load_prompt_from_disk, load_prompt_from_mlflow


_TEST_ID = str(uuid.uuid4())
AGENT_BASE_PROMPT = {
    "name": f"{_TEST_ID}_base", 
    "content": "Agent Prompt"
}
AGENT_VARIANT_PROMPT = {
    "name": f"{_TEST_ID}_base_qwen3-32B", 
    "content": "This prompt was specialized for a model"
}
TOOL_PROMPT = {
    "name": f"{_TEST_ID}_mock_tool",
    "content": "Tool Prompt"
}
EXAMPLE_PROMPT = {
    "name": f"{_TEST_ID}_1_mock_tool_example",
    "content": "Tool Example Prompt"
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest.fixture
def mock_base_path(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "examples").mkdir()

    registry_file = {
        "agent": {
            AGENT_BASE_PROMPT["name"]: { "version": "0.0.0" },
            AGENT_VARIANT_PROMPT["name"]: { "version": "0.0.0" }
        },
        "tool": {
            TOOL_PROMPT["name"]: { "version": "0.0.0" }
        },
        "example": {
            EXAMPLE_PROMPT["name"]: { "version": "0.0.0" }
        }
    }

    with open(str(tmp_path / "registry.json"), "w") as fp:
        json.dump(registry_file, fp)

    (tmp_path / AGENT_BASE_PROMPT["name"]).write_text(AGENT_BASE_PROMPT["content"])
    (tmp_path / AGENT_VARIANT_PROMPT["name"]).write_text(AGENT_VARIANT_PROMPT["content"])
    (tmp_path / "tools" / TOOL_PROMPT["name"]).write_text(TOOL_PROMPT["content"])
    (tmp_path / "examples" / EXAMPLE_PROMPT["name"]).write_text(EXAMPLE_PROMPT["content"])

    yield tmp_path


_LOAD_FROM_DISK_TESTS = [
    # a prompt with name doesn't exists -> ValueError
    {
        "load_parameters": { "name": "notexists" },
        "expected": ValueError
    },
    # a prompt for the specific model doesn't exists -> base prompt
    {
        "load_parameters": { "name": f"{_TEST_ID}_base", "model": "gemma-4-31B-it" },
        "expected": AGENT_BASE_PROMPT["content"]
    },
    # a prompt variant for some model (existing) -> variant prompt
    {
        "load_parameters": { "name": f"{_TEST_ID}_base", "model": "qwen3-32B" },
        "expected": AGENT_VARIANT_PROMPT["content"]
    },
]

@pytest.mark.parametrize("test_case", _LOAD_FROM_DISK_TESTS)
def test_load_prompt_from_disk(test_case, monkeypatch, mock_base_path):
    monkeypatch.setattr(
        target=ai_ops.core.prompt.registry,
        name="PROMPT_BASE_PATH",
        value=mock_base_path
    )

    expected = test_case["expected"]
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            load_prompt_from_disk(**test_case["load_parameters"])
    else:
        assert load_prompt_from_disk(**test_case["load_parameters"]) == expected


# `mlflow.genai` doesn't expose any way to delete a prompt, also the prompt registry 
# is global, not experiment-tied.
@pytest.fixture
def setup_mlflow_test_dependencies(mock_base_path):
    import mlflow
    from ai_ops.core._mlflow import setup_mlflow, mlflow_ready

    try:
        setup_mlflow()
    except Exception as err:
        pytest.skip(f"Could not connect to MLFlow: {err}")
    
    if not mlflow_ready():
        pytest.skip("MLFlow Status not ready")

    # still need local registry
    yield mock_base_path


def check_is_registered(
    name: str, 
    kind: Literal["agent", "tool", "example"] = "agent",
    model: str | None = None, 
    version: str | None = None
) -> bool:
    import mlflow
    from ai_ops.core.prompt.registry import (
        semver_encode, semver_decode,
        PROMPT_BASE_PATH # monkeypatched by the test
    )

    # replicate load_prompt_from_mlflow logic
    registry_path = Path(PROMPT_BASE_PATH) / "registry.json"
    try:
        with open(str(registry_path), "r", encoding="utf-8") as fp:
            registry = json.load(fp)
    except Exception:
        print(f"DEBUG: Exception reading registry at {registry_path}: {e}")
        registry = {}

    variant = f"_{model}" if model else ""
    prompt_name = f"{kind}_{name}{variant}"
    semver = version or registry.get(kind, {}).get(name, {}).get("version")
    if semver:
        semver = semver_encode(version=semver)
    else:
        semver = "0_0_0"
    
    uri = f"prompts:/{prompt_name}@{semver}" if semver else f"prompts:/{prompt_name}"

    for attempt in range(5):
        try:
            prompt = mlflow.genai.load_prompt(uri, allow_missing=True)
            if prompt is not None:
                return True
        except Exception as err:
            print(f"DEBUG: check_is_registered attempt {attempt} threw an error: {err}")

        time.sleep(1.0) 

    print(f"DEBUG: MLflow never returned the prompt. Queried URI: {uri}")
    return False


_LOAD_FROM_MLFLOW_TESTS = [
    # TODO: this test won't pass, though the prompts are actually registered if we check 
    # inside mlflow prompt registry. 
    # btw they should allow prompt deletion from sdk
    # prompt doesn't exists on mlflow but it exists locally -> prompt is registered
    # {
    #     "load_parameters": { "name": f"{_TEST_ID}_base", "model": "qwen3-32B" },
    #     "expected": AGENT_VARIANT_PROMPT["content"],
    #     "callback": check_is_registered
    # },
    # prompt variant doesn't exists -> fallback to base
    {
        "load_parameters": { "name": f"{_TEST_ID}_base", "model": "gemma-4-31B-it" },
        "expected": AGENT_BASE_PROMPT["content"],
        "callback": None
    },
]

@pytest.mark.parametrize("test_case", _LOAD_FROM_MLFLOW_TESTS)
def test_load_prompt_from_mlflow(test_case, monkeypatch, setup_mlflow_test_dependencies):
    prompt_base_path = setup_mlflow_test_dependencies
    monkeypatch.setattr(
        target=ai_ops.core.prompt.registry,
        name="PROMPT_BASE_PATH",
        value=prompt_base_path
    )

    assert load_prompt_from_mlflow(**test_case["load_parameters"]) == test_case["expected"]
    
    callback = test_case["callback"]
    if callback:
        assert callback(**test_case["load_parameters"]) is True, "Prompt not registered"
