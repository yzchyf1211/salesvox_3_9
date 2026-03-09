from langchain_core.tools import tool

from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from langchain_core.messages import ToolMessage
from agentickit.prosonaagent.utils.context import (
    build_tool_call_success_system_feedback,
    build_tool_call_error_system_feedback,
)
from agentickit.prosonaagent.aom.api import get_sco_info
from agentickit.prosonaagent.utils.user import get_user_profile
from agentickit.prosonaagent.aom.context import get_activity_context
from agentickit.prosonaagent.aom.query import get_activity_by_activity_id


@tool
async def get_activity_information(
    activity_id: str,
    tool_runtime: ToolRuntime,
) -> Command:
    """
    get activity information by activity_id

    Args:
        activity_id: the ID of the activity to get, required
    """
    context_id = tool_runtime.state.get("context_id")
    user_profile = get_user_profile(context_id)

    target_activity = get_activity_by_activity_id(tool_runtime.state, activity_id)
    if not target_activity:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        tool_call_id=tool_runtime.tool_call_id,
                        content=build_tool_call_error_system_feedback(
                            f"activity id is not found: {activity_id}"
                        ),
                    )
                ]
            }
        )

    sco_list = await get_sco_info(context_id, target_activity, user_profile)
    context = get_activity_context(target_activity, sco_list)

    return Command(
        update={
            "messages": [
                ToolMessage(
                    tool_call_id=tool_runtime.tool_call_id,
                    content=build_tool_call_success_system_feedback(context),
                )
            ]
        }
    )
