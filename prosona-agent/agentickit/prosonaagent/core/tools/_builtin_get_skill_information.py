from langchain_core.tools import tool

from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from agentickit.prosonaagent.utils.context import (
    build_tool_call_success_system_feedback,
    build_tool_call_error_system_feedback,
    build_skill_information_context,
)
from agentickit.core.infra.skills.manager import get_skills_by_names


@tool
async def _builtin_get_skill_information(
    name: str,
    tool_runtime: ToolRuntime,
) -> Command:
    """
    get skill information

    Args:
        name: the name of the skill
    """
    tool_call_id = tool_runtime.tool_call_id

    skills = get_skills_by_names([name])
    if not skills:
        # skill not found, return error feedback instead of raising IndexError
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        tool_call_id=tool_call_id,
                        content=build_tool_call_error_system_feedback(
                            f"skill name is not found: {name}"
                        ),
                    ),
                ]
            }
        )

    context = build_skill_information_context(skills[0])
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=build_tool_call_success_system_feedback(context),
                    tool_call_id=tool_call_id,
                ),
            ]
        }
    )
