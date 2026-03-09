from langchain_core.tools import tool

from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from langchain_core.messages import ToolMessage
from agentickit.prosonaagent.utils.context import (
    build_tool_call_success_system_feedback,
)


@tool
async def _builtin_write_scratchpad(
    text: str,
    tool_runtime: ToolRuntime,
) -> Command:
    """
    write scratchpad to help the agent run the task better

    Args:
        text: the text to write to the scratchpad, required
    """
    tool_call_id = tool_runtime.tool_call_id if tool_runtime else ""

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=build_tool_call_success_system_feedback(),
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )
