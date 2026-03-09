"""ModelEnhance Middleware — sets tool_choice and appends skill system prompt."""

from typing import Awaitable, Callable, List

from langchain_core.messages import SystemMessage
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ModelCallResult,
)

from agentickit.core.infra.skills.manager import get_skills_by_names
from agentickit.prosonaagent.utils.context import build_skill_system_prompt


class ModelEnhanceMiddleware(AgentMiddleware):
    """Sets tool_choice='required' and appends skill system prompt to system message."""

    def __init__(self, skill_names: List[str]) -> None:
        super().__init__()
        self._skill_names = skill_names
        skills = get_skills_by_names(skill_names) if skill_names else []
        metadata_list = [s.metadata for s in skills]
        self._skill_system_prompt = (
            build_skill_system_prompt(metadata_list) if metadata_list else ""
        )

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        # 1. Set tool_choice
        request = request.override(tool_choice="required")

        # 2. Append skill system prompt to system_message
        if self._skill_system_prompt:
            current = request.system_message
            if current:
                new_content = current.content + "\n\n" + self._skill_system_prompt
            else:
                new_content = self._skill_system_prompt
            request = request.override(
                system_message=SystemMessage(content=new_content)
            )

        return await handler(request)
