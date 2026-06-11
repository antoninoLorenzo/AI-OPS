from typing import Optional, Dict, List

from ai_ops.core.tools.load_skill.skill import Skill

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