from langchain_core.tools import tool

from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from agentickit.prosonaagent.utils.context import (
    build_tool_call_success_system_feedback,
)
from agentickit.core.infra.skills.loader import get_resource_text


@tool
async def _builtin_get_skill_resource(
    name: str,
    path: str,
    tool_runtime: ToolRuntime,
) -> Command:
    """
    get skill resource

    Args:
        name: the name of the skill
        path: the path of the resource
    """

    tool_call_id = tool_runtime.tool_call_id

    context = get_resource_text(name, path)
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
