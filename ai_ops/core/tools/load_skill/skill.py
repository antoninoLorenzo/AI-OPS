import re
from pathlib import Path
from typing import List, Optional, Annotated, Dict, Union

import yaml
from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool
from ai_ops.core.prompt import get_prompt
from ai_ops.core.log import get_logger, log_event, logging


BUNDLED_SKILLS = Path(__file__).parent / 'bundled'
FRONTMATTER_REGEX = r"(?s)^---\s*\n(?P<frontmatter>.*?)\n---\s*(?P<instructions>.*)"

_logger = get_logger(__name__)


class Skill(BaseModel):
    name: str
    description: str
    content: str
    requirements: Optional[List[str]] = None


def verify_installed(dependency: Union[str, List[str]]):
    # verifies whether or not binary (ex. curl) is installed on the system, if not
    # it raises a RuntimeError.
    # The reason is to avoid having the agent being cock-blocked when it tries to run
    # a command but the command is not installed; the agent itself shouldn't be able 
    # to install binaries
    pass


def fetch_skill(skill_path: Path) -> Skill | None:
    # path to parent folder of SKILL.md
    if not skill_path.is_dir():
        return None

    skill_file_path = skill_path / 'SKILL.md'
    if not skill_file_path.exists():
        _logger.error(f"{skill_file_path} doesn't exist")
        return None
    
    with open(str(skill_file_path), 'r') as fp:
        content = fp.read()
    
    match = re.match(pattern=FRONTMATTER_REGEX, string=content, flags=re.MULTILINE)
    if match is None:
        _logger.warning(f"Invalid format for {skill_file_path}")
        return None
    
    frontmatter = match.group('frontmatter')
    instructions = match.group('instructions').strip()
    if not instructions:
        _logger.warning(f"skipping skill with no instructions at {skill_file_path}")
        return None
    
    skill_specs = yaml.safe_load(frontmatter)
            
    skill_name = skill_specs.get('name', None)
    skill_desc = skill_specs.get('description', None)
    skill_meta = skill_specs.get('metadata', None)

    if skill_name is None or skill_desc is None:
        _logger.warning(f'skipping skill at {skill_file_path}, missing name and/or description')
        return None

    # skill with no requirements is allowed
    requirements = []
    if skill_meta is not None:
        requirements = skill_meta.get('requirements', [])
        if len(requirements) > 0:
            verify_installed(requirements)
    
    return Skill(
        name=skill_name, 
        description=skill_desc, 
        content=str(instructions), 
        requirements=requirements
    )
    

class SkillRegistry:
    def __init__(self, skills: Optional[Path] = None):
        self._skill_registry: Dict[str, Skill] = {}
        for skill_path in BUNDLED_SKILLS.iterdir():
            skill = fetch_skill(skill_path)
            if skill:
                self._skill_registry[skill.name] = skill
        
        # extend bundled skills with other skills, conflicting name resolution
        # gets resolved as overloading (user skills overwrite bundled).
        if skills:
            if not skills.is_dir():
                log_event(
                    _logger, logging.ERROR, 
                    "Extended skill path not a directory", 
                    extended_skills_path=skills
                )
            else:
                for skill_path in skills.iterdir():
                    skill = fetch_skill(skill_path)
                    if skill is None:
                        continue
                    
                    if skill.name in self._skill_registry:
                        log_event(
                            _logger, logging.WARNING, 
                            f"Overriding bundled skill {skill.name}"
                        )
                    
                    self._skill_registry[skill.name] = skill

    def get_index(self) -> str:
        return "\n".join([
            f"{name}: {skill.description}\n"
            for name, skill in self._skill_registry.items()
        ])

    def get_available(self) -> List[str]:
        return self._skill_registry.keys()
    
    def get_skill(self, name: str) -> Skill | None:
        return self._skill_registry.get(name, None)


_SKILL_REGISTRY = None

def get_skill_registry() -> SkillRegistry:
    global _SKILL_REGISTRY
    if _SKILL_REGISTRY is None:
        _SKILL_REGISTRY = SkillRegistry()
    return _SKILL_REGISTRY


class LoadSkillRequest(BaseModel):
    skill_id: Annotated[
        str, 
        Field(description="Unique name identifier of skill to load.")
    ]


class LoadSkillResult(BaseModel):
    skill: Skill | None


class LoadSkill(Tool[LoadSkillRequest, LoadSkillResult]):
    name = "load_skill"
    description = None

    def __init__(self, model: str | None = None):
        registry = get_skill_registry()
        self.description = get_prompt(name=LoadSkill.name, kind="tool", model=model)
        self.description = self.description.format(skill_index=registry.get_index())

    def __call__(self, skill_request: LoadSkillRequest) -> LoadSkillResult:
        registry = get_skill_registry()
        
        skill_id = skill_request.skill_id.lower().strip()
        if not skill_id in registry.get_available():
            log_event(
                _logger, logging.WARNING,
                f"Skill not found", skill_id=skill_id
            )
            return LoadSkillResult(skill=None)
        
        return LoadSkillResult(skill=registry.get_skill(skill_id))
    
    @staticmethod
    def format_result(skill_result: LoadSkillResult) -> str:
        if skill_result.skill is None:
            return "Skill not found"
        return f"{skill_result.skill.name}\n{skill_result.skill.content}"
