import re
import json
from pathlib import Path
from typing import Literal

from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core._mlflow import mlflow_ready


PROMPT_BASE_PATH = Path(__file__).parent / "local"
BASE_PROMPT_NAME = "react"

_logger = get_logger(__name__)


def _normalize_model_name(model: str | None) -> str | None:
    if not model:
        return None
    # strips case-insensitive suffixes like -AWQ, -GGUF, extend the regex
    return re.sub(re.compile(r"-(awq|gguf)$", re.IGNORECASE), "", model)


def build_prompt(
    model: str | None = None,
    prompt_extension: str | None = None
) -> str:
    system_prompt = get_prompt(name=BASE_PROMPT_NAME, model=model)
    
    if prompt_extension:
        system_prompt += prompt_extension
    
    return system_prompt
    
def get_prompt(
    name: str, 
    kind: Literal["agent", "tool", "example"] = "agent",
    model: str | None = None, 
    version: str | None = None
) -> str:
    """Load a prompt template by name, kind and optionally model and/or version.

    On disk, the prompt identifier is `{name}_{model}` for prompt variants, otherwise 
    just the name. For MLFlow the identifier is `{kind}_{name}_{model}`.

    Versioning uses SemVer strings (`X.Y.Z`):
    * `X`: Major agent architectural changes
    * `Y`: Minor changes such as tool schemas.
    * `Z`: Text optimization and changes in wording.
    Only the latest version lives inside the repository (technically not though), 
    versioning is enabled by a prompt registry (currently MLFlow), so the versioning 
    parameter is ignored if a backend is not setup.

    > Note: currently this only loads template strings, attaching inference configs \
    such as temperature per prompt would be a desirable future feature. (it would be \
    attached only to the "agent" prompts though). Skill versioning could also be a \
    future functionality.

    Examples:
    >>> # get the react agent prompt
    >>> get_prompt("react")
    >>> # get the load_skill tool description tuned towards gemma-4
    >>> get_prompt("load_skill", kind="tool", model="gemma-4-31B-it")
    """
    if mlflow_ready():
        return load_prompt_from_mlflow(
            name=name, kind=kind, 
            model=_normalize_model_name(model), 
            version=version
        )
    else:
        return load_prompt_from_disk(
            name=name, kind=kind, 
            model=_normalize_model_name(model)
        )


def load_prompt_from_disk(
    name: str, 
    kind: Literal["agent", "tool", "example"] = "agent", 
    model: str | None = None
):
    base_path = PROMPT_BASE_PATH
    if kind == "tool":
        base_path = Path(base_path / 'tools')
    if kind == "example":
        base_path = Path(base_path / 'examples')

    prompt_path = Path(base_path / name)
    if not prompt_path.exists():
        raise ValueError(f"Prompt {name} doesn't exists.")

    if model:
        # how to handle same model different `model_id` (ex. gemma-4-31B-it vs gemma-4-31B-it-AWQ) ???
        _prompt_path = Path(base_path / f"{name}_{model}")
        if _prompt_path.exists():
            prompt_path = _prompt_path
        else:
            # does this kind of silent fail with fallback make sense ???
            log_event(
                _logger, logging.WARNING, 
                f"Prompt {name} not found for {model}, defaulting to base."
            )
    
    with open(str(prompt_path), 'r', encoding='utf-8') as fp:
        prompt = fp.read()

    return prompt


def semver_encode(version: str) -> str:
    return version.replace('.', '_')


def load_prompt_from_mlflow(
    name: str, 
    kind: Literal["agent", "tool", "example"] = "agent",
    model: str | None = None, 
    version: str | None = None
) -> str:
    # if the prompt doesn't exist it needs to be registered, the version lives in 
    # "local/registry.json". There are two "versioning" systems in place, one is the 
    # prompt living in the repo, the other is MLFlow storage, porting a version from 
    # MLFlow to GitHub is manual; in the other direction (for example a clean MLFlow 
    # instance) this method pushed the on disk prompts to MLFlow. 
    import mlflow

    with open(str(Path(PROMPT_BASE_PATH / "registry.json")), "r", encoding="utf-8") as fp:
        registry = json.load(fp)

    variant = f"_{model}" if model else ""
    prompt_name = f"{kind}_{name}{variant}"

    # MLFlow uses sequential 1...N versioning but we can use aliases to "version" it.
    # semver is used as the alias; if no version is passed, fall back to registry.json,
    # and if that's also missing, load whatever MLFlow considers latest.
    semver = version or registry.get(kind, {}).get(name, {}).get("version")
    if semver:
        # MLFlow doesn't accept dots in alias names 
        semver = semver_encode(version=semver)
    
    uri = f"prompts:/{prompt_name}@{semver}" if semver else f"prompts:/{prompt_name}"

    prompt = mlflow.genai.load_prompt(uri, allow_missing=True)
    if prompt is not None:
        return prompt.template

    # variant doesn't exist? fall back to base
    if model:
        base_prompt_name = f"{kind}_{name}"
        base_uri = f"prompts:/{base_prompt_name}@{semver}" if semver else f"prompts:/{base_prompt_name}"
        prompt = mlflow.genai.load_prompt(base_uri, allow_missing=True)
        if prompt is not None:
            log_event(
                _logger, logging.WARNING,
                f"Prompt {name} not found for {model}, defaulting to {base_uri}."
            )
            return prompt.template

    log_event(
        _logger, logging.INFO,
        f"Prompt {prompt_name} not found, bootstrapping from disk."
    )
    local_prompt = load_prompt_from_disk(name=name, kind=kind, model=model)
    try:
        version_obj = mlflow.genai.register_prompt(name=prompt_name, template=local_prompt)
        if semver:
            mlflow.genai.set_prompt_alias(name=prompt_name, alias=semver, version=version_obj.version)
        return local_prompt
    except Exception as e:
        raise RuntimeError(
            f"Prompt not found at {uri} and automated MLflow registration failed: {e}"
        )