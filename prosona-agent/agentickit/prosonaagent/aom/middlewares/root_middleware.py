"""
Root Middleware for Level 0 (AOM Adapter).

RootMiddleware is the top-level middleware that:
- Never ends (no _builtin_end_task binding)
- Loads project_id from UserAgentProxy on session start
- Injects start_task("project") tool call for LangGraph to process
"""

import uuid
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from agentickit.core.exception import AgenticException
from agentickit.prosonaagent.core.middleware.task_middleware import TaskMiddleware
from agentickit.prosonaagent.aom.state import RootTaskState
from agentickit.prosonaagent.utils.agent_proxy import UserAgentProxy
from agentickit.prosonaagent.core.middleware.middleware_registry import ROOT_MIDDLEWARE_GROUP_NAME


class RootMiddleware(TaskMiddleware):
    """
    Level 0: Root Middleware.

    Session-level middleware that never ends:
    - abefore: loads project_id, programmatically starts project task
    - No aafter (root never ends, calling aafter raises an error)
    - No _builtin_end_task (root level cannot be ended by LLM)
    """

    state_schema = RootTaskState
    task_group_name: str = ROOT_MIDDLEWARE_GROUP_NAME
    sub_task_group_name: str = "project"
    # No _builtin_end_task - root level cannot be ended

    # ==================== Current Task Lifecycle ====================

    async def abefore(
        self,
        state: RootTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """
        Called when root session starts.

        1. Get project_id from UserAgentProxy, store in state
        2. Call super().abefore() (sets root to running)
        3. Inject start_task("project") tool call for LangGraph to process
        """
        mw_update: Dict[str, Any] = {}

        # 1. Get project_id from params
        user_proxy = UserAgentProxy(state)
        params = user_proxy.get_params()
        project_id = params.get("projectId") if params else None
        mw_update["project_id"] = project_id

        # 2. Call super().abefore()
        lifecycle_update = await super().abefore(state, runtime)
        result = self._merge_updates(mw_update, lifecycle_update)

        # 3. Inject start_task("project") tool call
        tool_call_id = f"call_{uuid.uuid4().hex[:22]}"
        result["messages"] = result.get("messages", []) + [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": tool_call_id,
                        "name": "_builtin_start_task",
                        "args": {"name": "project", "params": {"id": project_id}},
                    }
                ],
            ),
        ]

        return result

    async def aafter(
        self,
        state: RootTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Root middleware should never end. Raises RuntimeError if called."""
        raise AgenticException(
            "RootMiddleware.aafter should never be called: root task cannot end."
        )
