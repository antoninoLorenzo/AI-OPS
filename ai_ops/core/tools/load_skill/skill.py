import re
from pathlib import Path
from typing import List, Optional, Annotated, Dict, Union

import yaml
from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool
from ai_ops.core.utils import get_logger


BUNDLED_SKILLS = Path(__file__).parent / 'bundled'

_SKILL_DESCRIPTION = """Load the full instructions for one or more skills before executing them.

Skills are step-by-step procedural guides for specific offensive security tasks \
(e.g. http-reconnaissance, sql-injection). Each skill contains tool usage, \
command sequences, and decision logic tailored to the task.

Always call this tool before attempting any task that maps to a known skill. \
Do not rely on general knowledge when a skill is available — skill instructions \
are authoritative and must be followed.

If a requested skill is not found it will be silently skipped, so only request \
skill names that appear in the skill index.\
"""

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
                _logger.error(f"{skills} is not a directory")
            else:
                for skill_path in skills.iterdir():
                    skill = fetch_skill(skill_path)
                    if skill is None:
                        continue
                    
                    if skill.name in self._skill_registry:
                        _logger.warning(f"Overrding bundled skill {skill.name}")
                    
                    self._skill_registry[skill.name] = skill

    def get_index(self) -> str:
        return "\n".join([
            f"{name}: {skill.description}"
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
    skill_ids: Annotated[
        List[str], 
        Field(description="List of unique skill names")
    ]


class LoadSkillResult(BaseModel):
    skills: List[Skill]


class LoadSkill(Tool[LoadSkillRequest, LoadSkillResult]):
    name = "load_skill"
    description = _SKILL_DESCRIPTION

    def __call__(self, skill_request: LoadSkillRequest) -> LoadSkillResult:
        registry = get_skill_registry()
        
        skill_ids = [sk_id.lower().strip() for sk_id in skill_request.skill_ids]
        skill_ids = set(skill_ids)
        
        available_skill_ids = skill_ids.intersection(set(registry.get_available()))
        not_found_ids = skill_ids.difference(available_skill_ids)
        if len(not_found_ids) > 0:
            _logger.warning(f'Skills not found: {not_found_ids}')
        
        return LoadSkillResult(skills=[
            registry.get_skill(sk_id)
            for sk_id in available_skill_ids
        ])
    
    @staticmethod
    def format_result(skill_result: LoadSkillResult) -> str:
        return "\n".join([
            f"{skill.name}\n{skill.content}" for skill in skill_result.skills
        ])

