"""Chat Metadata Middleware — adds role, user identity, and text metadata to messages.

Handles metadata for _builtin_conversation tool:
- __role__: "user" for HumanMessage and _builtin_conversation ToolMessage, "assistant" otherwise
- __name__, __avatar__: from user_profile in state
- __content_type__, __text__: text content for conversation messages
"""

import re
from typing import Awaitable, Callable, List, Optional

from langchain_core.messages import AnyMessage, BaseMessage, AIMessage, ToolMessage
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ModelCallResult,
    ToolCallRequest,
)
from langgraph.types import Command
from agentickit.prosonaagent.core.state import ProsonaAgentState

_CONVERSATION_TOOL_NAME = "_builtin_conversation"

# Pattern to extract user answer from system_feedback content:
#   user answered: "..."
_USER_ANSWERED_RE = re.compile(r'user answered:\s*"(.*)"', re.DOTALL)


class ChatMetadataMiddleware(AgentMiddleware):
    """Adds chat metadata to messages produced by model calls and tool calls.

    awrap_model_call:
    - All messages get __role__, __name__, __avatar__
    - AIMessage with _builtin_conversation tool call gets __content_type__: "text",
      __text__: <text arg from tool call>

    awrap_tool_call:
    - All messages get __role__, __name__, __avatar__
    - _builtin_conversation ToolMessage: __role__ is "user",
      __content_type__: "text", __text__: parsed user answer (if present)
    """

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        result = await handler(request)
        state = request.state
        if isinstance(result, ModelResponse) and result.result:
            result.result = self._process_model_messages(result.result, state)
        elif isinstance(result, BaseMessage):
            result = self._process_model_messages([result], state)[0]
        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        result = await handler(request)
        is_conversation = request.tool_call.get("name") == _CONVERSATION_TOOL_NAME

        if isinstance(result, Command):
            update = result.update
            if isinstance(update, dict) and update.get("messages"):
                update["messages"] = self._process_tool_messages(
                    update["messages"], request.state, is_conversation
                )
        elif isinstance(result, ToolMessage):
            result = self._process_tool_messages(
                [result], request.state, is_conversation
            )[0]

        return result

    # ---- message processing ----

    def _process_model_messages(
        self, messages: List[AnyMessage], state: ProsonaAgentState
    ) -> List[AnyMessage]:
        user_profile = state.get("user_profile") or {}

        result = []
        for msg in messages:
            role = "user" if msg.type == "human" else "assistant"
            kwargs = {
                **msg.additional_kwargs,
                "__role__": role,
            }

            # Only user role gets __name__ / __avatar__
            if role == "user":
                kwargs["__name__"] = user_profile.get("fullname")
                kwargs["__avatar__"] = user_profile.get("img_url")

            # AIMessage with _builtin_conversation tool call → add text metadata
            if isinstance(msg, AIMessage) and not msg.additional_kwargs.get(
                "__content_type__"
            ):
                text = self._extract_conversation_text(msg)
                if text is not None:
                    kwargs["__content_type__"] = "text"
                    kwargs["__text__"] = text

            result.append(msg.model_copy(update={"additional_kwargs": kwargs}))
        return result

    def _process_tool_messages(
        self,
        messages: List[AnyMessage],
        state: ProsonaAgentState,
        is_conversation: bool,
    ) -> List[AnyMessage]:
        user_profile = state.get("user_profile") or {}

        result = []
        for msg in messages:
            role = self._get_role(msg, is_conversation)
            kwargs = {
                **msg.additional_kwargs,
                "__role__": role,
            }

            # Only user role gets __name__ / __avatar__
            if role == "user":
                kwargs["__name__"] = user_profile.get("fullname")
                kwargs["__avatar__"] = user_profile.get("img_url")

            # _builtin_conversation ToolMessage → parse user answer as text metadata
            if (
                is_conversation
                and isinstance(msg, ToolMessage)
                and not msg.additional_kwargs.get("__content_type__")
            ):
                user_text = self._parse_user_answer(msg.content)
                if user_text is not None:
                    kwargs["__content_type__"] = "text"
                    kwargs["__text__"] = user_text

            result.append(msg.model_copy(update={"additional_kwargs": kwargs}))
        return result

    # ---- helpers ----

    @staticmethod
    def _get_role(message: AnyMessage, is_conversation: bool = False) -> str:
        if message.type == "human":
            return "user"
        if is_conversation and isinstance(message, ToolMessage):
            return "user"
        return "assistant"

    @staticmethod
    def _extract_conversation_text(ai_message: AIMessage) -> Optional[str]:
        """Extract the ``text`` argument from a _builtin_conversation tool call."""
        for tc in getattr(ai_message, "tool_calls", None) or []:
            if tc.get("name") == _CONVERSATION_TOOL_NAME:
                return (tc.get("args") or {}).get("text")
        return None

    @staticmethod
    def _parse_user_answer(content: str) -> Optional[str]:
        """Parse user answer from system_feedback content.

        Expected format (after prettify_xml):
          <system_feedback>
          user answered: "the user's actual text"
          </system_feedback>
        """
        if not content or "user answered:" not in content:
            return None
        match = _USER_ANSWERED_RE.search(content)
        return match.group(1) if match else None
