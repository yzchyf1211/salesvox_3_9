"""User Context Middleware — initializes user_profile, locale, locale_name."""

from typing import Any, Dict, Optional

from langchain.agents.middleware.types import AgentMiddleware

from agentickit.prosonaagent.utils.i18n import get_locale_name
from agentickit.prosonaagent.utils.user import get_user_profile
from agentickit.prosonaagent.core.state import ProsonaAgentState


class UserContextMiddleware(AgentMiddleware):
    """Initializes user context fields before the agent loop starts.

    Must be placed before other middlewares that depend on these fields
    (task_middleware, SpeakerMiddleware, ChatMetadataMiddleware).

    Sets:
    - user_profile: from context_id via get_user_profile
    - locale: from user_profile.locale (default "zh_CN")
    - locale_name: human-readable locale name
    """

    async def abefore_agent(
        self, state: ProsonaAgentState, runtime: Any
    ) -> Optional[Dict[str, Any]]:
        updated: Dict[str, Any] = {}

        if not state.get("user_profile"):
            context_id = state.get("context_id")
            user_profile = get_user_profile(context_id)
            updated["user_profile"] = user_profile

        if not state.get("locale"):
            user_profile = (
                updated.get("user_profile") or state.get("user_profile") or {}
            )
            locale = user_profile.get("locale", "zh_CN")
            updated["locale"] = locale
            updated["locale_name"] = get_locale_name(locale)

        return updated or None
