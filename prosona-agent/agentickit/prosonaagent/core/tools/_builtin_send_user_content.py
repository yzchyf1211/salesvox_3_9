from typing import Any, Dict, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from agentickit.prosonaagent.utils.context import (
    build_tool_call_success_system_feedback,
)


@tool
async def _builtin_send_user_content(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    tool_runtime: ToolRuntime = None,
) -> Command:
    """
    Send content to user. Different tasks correspond to different content.
    Call the tool _builtin_send_user_content to display the content, after which the user can view it on the interface.
    The detailed content is mapped through defined actions; refer to the action definitions within the task.

    Args:
        action: the action of the content, required
        params: the params of the content, optional
    """
    tool_call_id = tool_runtime.tool_call_id if tool_runtime else None

    messages = []
    if tool_call_id is not None:
        messages.append(
            ToolMessage(
                content=build_tool_call_success_system_feedback(),
                tool_call_id=tool_call_id,
            )
        )

    return Command(update={"messages": messages})
