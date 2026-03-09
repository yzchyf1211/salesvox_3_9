"""
EnhanceTaskHandler — TaskHandler extension with aget_card support.

Handlers that use _builtin_send_user_content should inherit this class
and override aget_card() to return a content card.
"""

from typing import Any, Dict, Optional, TypeVar, TYPE_CHECKING

from agentickit.prosonaagent.core.handler.task_handler import TaskHandler
from agentickit.prosonaagent.core.middleware.task_state import TaskState

if TYPE_CHECKING:
    from agentickit.prosonaagent.aom.types import AOMCard

StateT = TypeVar("StateT", bound=TaskState)


class EnhanceTaskHandler(TaskHandler[StateT]):
    """
    TaskHandler extension that supports _builtin_send_user_content.

    Override aget_card() to return an AOMCard when the agent calls
    _builtin_send_user_content. Return None to fall back to empty feedback.
    """

    async def aget_card(
        self,
        state: StateT,
        action: str,
        params: Dict[str, Any],
    ) -> "Optional[AOMCard]":
        """Return a content card for _builtin_send_user_content.

        Override to provide rich content (type, data, description, etc.).
        Return None to fall back to the default empty feedback.
        """
        return None
