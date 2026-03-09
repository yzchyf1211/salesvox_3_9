"""
EnhanceTaskMiddleware — TaskMiddleware extension with _builtin_send_user_content support.

Adds _builtin_send_user_content to the tool list and intercepts the tool call in
awrap_tool_call: calls handler.aget_card(), sends biz-common-layout + biz-common-display
A2A messages, and returns a Command with the ToolMessage result.
"""

import json
from typing import Awaitable, Callable

from langchain_core.messages import ToolMessage
from langchain.agents.middleware.types import ToolCallRequest
from langgraph.types import Command

from agentickit.prosonaagent.core.middleware.task_middleware import TaskMiddleware
from agentickit.prosonaagent.core.tools import _builtin_send_user_content
from agentickit.prosonaagent.utils.context import build_tool_call_success_system_feedback
from agentickit.prosonaagent.utils.message import build_content_kwargs
from agentickit.prosonaagent.aom.message import send_layout_message, send_display_message


class EnhanceTaskMiddleware(TaskMiddleware):
    """
    TaskMiddleware extension that adds _builtin_send_user_content support.

    - Includes _builtin_send_user_content in the tool list automatically.
    - Intercepts the tool call in awrap_tool_call: calls handler.aget_card(),
      builds a ToolMessage with the card, then sends biz-common-layout
      and biz-common-display A2A messages.
    """

    tools = [_builtin_send_user_content]

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        if request.tool_call.get("name") != "_builtin_send_user_content":
            return await super().awrap_tool_call(request, handler)

        state = request.state
        tool_call_id = request.tool_call.get("id")
        args = request.tool_call.get("args", {})
        action = args.get("action", "")
        params = args.get("params") or {}

        task_id, task_name = self._get_current_task_info(state)
        if not task_id or not task_name:
            return Command(update={"messages": [ToolMessage(
                tool_call_id=tool_call_id,
                content=build_tool_call_success_system_feedback(),
            )]})

        card = await self.get_handler(task_name).aget_card(state, action, params)
        if card is None:
            return Command(update={"messages": [ToolMessage(
                tool_call_id=tool_call_id,
                content=build_tool_call_success_system_feedback(),
            )]})

        feedback = (
            card.get("description")
            or json.dumps(card.get("data", {}), ensure_ascii=False)
        )
        tool_msg = ToolMessage(
            content=build_tool_call_success_system_feedback(
                f"user can see the content: {feedback}"
            ),
            tool_call_id=tool_call_id,
            additional_kwargs=build_content_kwargs(
                content_type=card.get("type"),
                card=card,
            ),
        )

        await send_layout_message(state)
        await send_display_message(state, card, ref={
            "id": task_id,
            "name": task_name,
            "group": self.task_group_name,
            "params": state.get("params") or {},
            "mode": state.get("mode") or "",
        })

        messages = self._add_message_metadata([tool_msg], state)
        return Command(update={"messages": messages})
