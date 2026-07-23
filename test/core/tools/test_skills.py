from pathlib import Path
from functools import partial
from typing import Optional, List, Dict

import pytest
import ai_ops.core.tools.load_skill.skill
from ai_ops.core.tools.load_skill.skill import (
    Skill, 
    SkillRegistry,
    LoadSkillRequest, 
    LoadSkillResult, 
    LoadSkill, 
    fetch_skill
)
from test.core.mocks.skill_registry import MockSkillRegistry, get_mock_skill_registry


@pytest.fixture
def mock_skill_directories(tmp_path):
    bundled_base = tmp_path / "bundled"
    bundled_skill_dir = bundled_base / "bundled-skill"
    bundled_skill_dir.mkdir(parents=True)

    user_skills_base = tmp_path / "user_skills"
    user_skill_dir = user_skills_base / "user-skill"
    user_skill_dir.mkdir(parents=True)

    bundled_skill_content = """---
name: bundled-skill
description: asd
---
bundled
"""
    user_skill_content = """---
name: user-skill
description: asd
---
user
"""
    (bundled_skill_dir / "SKILL.md").write_text(bundled_skill_content)
    (user_skill_dir / "SKILL.md").write_text(user_skill_content)

    yield bundled_base, user_skills_base


def test_skill_registry(mock_skill_directories, monkeypatch):
    bundled_skills, user_skills = mock_skill_directories
    
    monkeypatch.setattr(
        target=ai_ops.core.tools.load_skill.skill,
        name="BUNDLED_SKILLS",
        value=bundled_skills
    )

    monkeypatch.setattr(
        target=ai_ops.core.tools.load_skill.skill,
        name="USER_SKILLS",
        value=user_skills
    )

    registry = SkillRegistry()
    assert registry.get_skill("bundled-skill") is not None
    assert registry.get_skill("user-skill") is not None


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
        "skill_request": LoadSkillRequest(skill_id="skill_a"),
        "expected": LoadSkillResult(skill=None)
    },
    # happy path -> expected skills present
    {
        "available_skills": {
            "skill_a": Skill(name="skill_a", description="Agagagaga", content="Gagaga")
        },
        "skill_request": LoadSkillRequest(skill_id="skill_a"),
        "expected": LoadSkillResult(
            skill=Skill(name="skill_a", description="Agagagaga", content="Gagaga")
        )
    }
]


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

    assert test_case["expected"] == result