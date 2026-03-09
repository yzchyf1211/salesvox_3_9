import json
from typing import Optional, Any

from langchain_core.messages import BaseMessage


# Messages marked with this key can be safely removed or
# summarized by context compression strategies.
COMPRESSIBLE_KEY = "__compressible__"


def build_compressible_kwargs() -> dict[str, Any]:
    """Build kwargs that mark a message as compressible.

    Usage:
        SystemMessage(content=..., additional_kwargs=build_compressible_kwargs())
    """
    return {COMPRESSIBLE_KEY: True}


def build_user_kwargs(
    name: Optional[str] = None,
    avatar: Optional[str] = None,
) -> dict[str, Any]:
    """Build user identity metadata (__name__, __avatar__)."""
    return {
        "__name__": name,
        "__avatar__": avatar,
    }


def build_content_kwargs(
    content_type: str = "text",
    text: Optional[str] = None,
    card: Optional[dict] = None,
) -> dict[str, Any]:
    """Build content metadata (__content_type__, __text__, __card__)."""
    return {
        "__content_type__": content_type,
        "__text__": text,
        "__card__": card,
    }



# 将messages转换为chat_history
def format_chat_history(messages: list[BaseMessage]) -> str:
    """
    获取历史对话
    """
    chat_history = []
    for message in messages:
        timestamp = message.additional_kwargs.get("__timestamp__", "")
        if message.additional_kwargs.get("__role__") == "assistant":
            if message.additional_kwargs.get("__text__"):
                chat_history.append(
                    f'[{timestamp}] {message.additional_kwargs.get("__name__", "you")} say: "{message.additional_kwargs.get("__text__", "")}"'
                )
            if message.additional_kwargs.get("__card__"):
                content = message.additional_kwargs.get("__card__", {}).get(
                    "description", ""
                ) or json.dumps(
                    message.additional_kwargs.get("__card__", {}).get("data", {}),
                    ensure_ascii=False,
                )
                chat_history.append(
                    f"[{timestamp}] {message.additional_kwargs.get('__name__', 'you')} send content to user: {content}"
                )

        if message.additional_kwargs.get(
            "__role__"
        ) == "user" and message.additional_kwargs.get("__text__"):
            chat_history.append(
                f'[{timestamp}] user say: "{message.additional_kwargs.get("__text__", "")}"'
            )

    return "\n\n".join(chat_history)
