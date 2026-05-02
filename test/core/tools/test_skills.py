from pathlib import Path
from functools import partial
from typing import Optional, List, Dict

import pytest
from ai_ops.core.tools.load_skill.skill import SkillRegistry, LoadSkill, Skill, LoadSkillRequest, fetch_skill


_FETCH_SKILL_TEST_PARAMETERS = [
    # T1_SKIP No Frontmatter
    {
        'id': 'SK_T1_SKIP', 
        'expected': None,
        'content': """# This is a skill with no frontmatter""",
    },
    # T2_SKIP Empty Frontmatter
    {
        'id': 'SK_T2_SKIP', 
        'expected': None,
        'content': """---
---
Where's the frontmatter?""",
    },
    # T3_SKIP Empty Instructions 
    {
        'id': 'SK_T3_SKIP', 
        'expected': None,
        'content': """---
name: some-skill
description: Does something
metadata:
  requirements:
  - cat
--- 
""",
    },
    # T4_SKIP Frontmatter not YAML
    {
        'id': 'SK_T4_SKIP', 
        'expected': None,
        'content': """---
{"content": "wasn't json?"}
---
# some instructions
""",
    },
    # T5_SKIP No SKILL.md
    {
        'id': 'SK_T5_SKIP', 
        'expected': None
    },
    # T1_ERR Requirement not found (RuntimeError)
    # {
    #     'id': 'SK_T1_ERR',
    #     'expected': RuntimeError,
    #     'content': """---
# name: some-skill
# description: Does something
# metadata:
#   requirements:
#   - somedependency
# --- 
# skill instructions
# """,
#     },
    # T1_OK Follows https://agentskills.io/specification
    {
        'id': 'SK_T1_OK',
        'expected': Skill,
        'content': """---
name: some-skill
description: Does something
metadata:
  requirements:
  - cat
--- 
Everything's fine
""",
    },
    # T2_OK No requirements
    {
        'id': 'SK_T2_OK', 
        'expected': Skill,
        'content': """---
name: some-skill
description: Does something
--- 
Maybe those are just instructions.
""",
    }
]

@pytest.mark.parametrize("test_case", _FETCH_SKILL_TEST_PARAMETERS)
def test_fetch_skill(tmp_path, test_case):
    skill_dir = tmp_path / test_case.get('id', 'undefined')
    skill_content = test_case.get('content')
    test_expected = test_case['expected']

    skill_dir.mkdir()
    if skill_content:
        skill_path = skill_dir / 'SKILL.md'
        with open(str(skill_path), 'w') as fp:
            fp.write(skill_content)

    if test_expected is None:
        assert fetch_skill(skill_dir) is None
    else:
        assert isinstance(fetch_skill(skill_dir), Skill)



_LOAD_SKILL_TEST_PARAMETERS = [
    # no matching skills -> return empty list
    {
        "available_skills": None,
        "skill_request": LoadSkillRequest(skill_ids=["skill_a"]),
        "expected": []
    },
    # some skill matching, other not -> return what was found
    {
        "available_skills": {
            "skill_a": Skill(name="skill_a", description="Agagagaga", content="Gagaga")
        },
        "skill_request": LoadSkillRequest(skill_ids=["skill_a", "skill_b"]),
        "expected": ["skill_a"]
    },
    # happy path -> expected skills present
    {
        "available_skills": {
            "skill_a": Skill(name="skill_a", description="Agagagaga", content="Gagaga")
        },
        "skill_request": LoadSkillRequest(skill_ids=["skill_a"]),
        "expected": ["skill_a"]
    }
]


class MockSkillRegistry:
    def __init__(self, available_skills: Optional[Dict[str, Skill]] = None):
        self._skill_registry: Dict[str, Skill] = available_skills if available_skills else {}
        
    def get_index(self) -> str:
        return "\n".join([
            f"{name}: {skill.description}"
            for name, skill in self._skill_registry.items()
        ])

    def get_available(self) -> List[str]:
        return self._skill_registry.keys()
    
    def get_skill(self, name: str) -> Skill | None:
        return self._skill_registry.get(name, None)


def get_mock_skill_registry(available_skills: Optional[Dict[str, Skill]] = None):
    return MockSkillRegistry(available_skills)


@pytest.mark.parametrize("test_case", _LOAD_SKILL_TEST_PARAMETERS)
def test_load_skill(monkeypatch, test_case):
    # to control MockSkillRegistry initialization monkeypatch the get_skill_registry
    monkeypatch.setattr(
        "ai_ops.core.tools.load_skill.skill.get_skill_registry",
        partial(get_mock_skill_registry, available_skills=test_case["available_skills"])
    )
    
    skill_request = test_case["skill_request"]
    load_skill_tool = LoadSkill()
    result = load_skill_tool(skill_request)

    assert test_case["expected"] == [skill.name for skill in result.skills]