from langchain_core.tools import tool
from langgraph.types import Command, interrupt
from langgraph.prebuilt import ToolRuntime
from langchain_core.messages import ToolMessage

from agentickit.prosonaagent.utils.context import (
    build_tool_call_success_system_feedback,
)

@tool
async def _builtin_conversation(
    text: str,
    ask_question: bool = False,
    tool_runtime: ToolRuntime = None,
) -> Command:
    """
    conversation with user

    Args:
        text: the content of the conversation
        ask_question: set to true if you need the user to reply, false if just delivering information
    """
    tool_call_id = tool_runtime.tool_call_id if tool_runtime else None

    update = {}
    feedback = "user has seen what you said"
    other_messages = []

    if ask_question:
        response = interrupt(text)

        if isinstance(response, dict):
            resp_messages = response.get("messages", [])

            # Extract first human message as user feedback; rest appended after ToolMessage
            human_msg = None
            for msg in resp_messages:
                if human_msg is None and getattr(msg, "type", None) == "human":
                    human_msg = msg
                else:
                    other_messages.append(msg)

            if human_msg:
                content = human_msg.content
                # For interrupted follow-up scenarios, feedback should express:
                # user answered "${content}"
                feedback = f'user answered: "{content}"'

            # Non-message state fields → update directly
            for k, v in response.items():
                if k != "messages":
                    update[k] = v

    messages = []
    if tool_call_id is not None:
        messages.append(
            ToolMessage(
                content=build_tool_call_success_system_feedback(feedback),
                tool_call_id=tool_call_id,
            )
        )
    # Append remaining messages after ToolMessage
    if other_messages:
        messages.extend(other_messages)

    update["messages"] = messages

    return Command(update=update)
