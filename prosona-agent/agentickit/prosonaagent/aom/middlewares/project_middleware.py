"""
Project Middleware for Level 1 (AOM Adapter).

ProjectMiddleware handles standard/unified work for project-level tasks:
- Load project_info, modules, activities
- Inject project/skill context
- Detect project end after activity completion
- Handle user input commands (e.g., restart)
"""

from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime

from agentickit.prosonaagent.core.middleware.task_middleware import TaskMiddleware
from agentickit.prosonaagent.core.tools import _builtin_conversation
from agentickit.prosonaagent.aom.api import (
    get_project_info,
    get_project_modules,
    get_project_activities,
)
from agentickit.prosonaagent.aom.context import (
    get_project_context,
    get_activity_list_context,
    get_prompt_client,
)
from agentickit.prosonaagent.aom.query import get_next_activity_by_activity_id
from agentickit.prosonaagent.aom.state import ProjectTaskState
from agentickit.prosonaagent.utils.time import get_timestamp


class ProjectMiddleware(TaskMiddleware):
    """
    Level 1: Project Middleware.

    Extends TaskMiddleware for project/session-level task management:
    - Loads project info, modules, activities at session start
    - Injects project/skill context
    - Detects project end after activity completion
    - Creates ActivityMiddleware for child tasks
    """

    state_schema = ProjectTaskState
    task_group_name: str = "project"
    sub_task_group_name: str = "activity"
    tools = [_builtin_conversation]

    # ==================== Current Task Lifecycle ====================

    async def abefore(
        self,
        state: ProjectTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """
        Called when session starts (first time).

        1. Load project info, modules, activities
        2. Inject project/skill context
        3. Call super().abefore() (sets status + calls handler.abefore)
        """
        mw_update: Dict[str, Any] = {}

        context_id = state.get("context_id")

        # Get project_id from state (set by RootMiddleware)
        project_id = state.get("project_id")

        # Load project info (used locally for context, not stored in state)
        project_info = await get_project_info(context_id, project_id)

        # Load modules
        module_list = await get_project_modules(context_id, project_id)
        mw_update["module_list"] = module_list

        # Load activities
        activity_list = await get_project_activities(context_id, project_id)
        mw_update["activity_list"] = activity_list
        assert activity_list, "ProjectMiddleware.abefore: activity_list is empty"

        # Inject project/activity/skill context
        project_context = get_project_context(project_info)

        messages = [
            SystemMessage(content=project_context),
        ]

        activity_list_context = get_activity_list_context(activity_list)
        messages.append(SystemMessage(content=activity_list_context))

        mw_update["messages"] = messages

        # Call super().abefore() (sets status + calls handler.abefore)
        lifecycle_update = await super().abefore(state, runtime)
        return self._merge_updates(mw_update, lifecycle_update)

    # ==================== User Input Handling ====================

    async def aafter_user_input(
        self,
        state: ProjectTaskState,
        runtime: Runtime,
        user_input: str,
        action: Optional[str],
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        """Handle user input at project level (e.g., restart command)."""
        result = await super().aafter_user_input(
            state, runtime, user_input, action, params
        )

        if action == "biz-common-sco-restart":
            client = get_prompt_client(prompt_name="commands/restart")
            messages = [
                SystemMessage(
                    content=client.compile(
                        timestamp=get_timestamp(),
                        activity_id=params.get("activity_id") if params else None,
                    )
                ),
            ]
            restart_update = {"messages": messages}
            return self._merge_updates(result or {}, restart_update)

        return result

    # ==================== Sub Task Lifecycle ====================

    async def aafter_task(
        self,
        state: ProjectTaskState,
        runtime: Runtime,
        sub_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Called after an activity task ends within this session.

        Checks if there are more activities; if not, marks project as ended.
        """
        # Call super().aafter_task() first (tracks sub_tasks, calls handler.aafter_task)
        result = await super().aafter_task(
            state,
            runtime,
            sub_state,
        )

        # Check if there are more activities
        activity_id = sub_state.get("params", {}).get("id")
        next_activity = get_next_activity_by_activity_id(state, activity_id) if activity_id else None
        if not next_activity:
            # No more activities - project ended
            return self._merge_updates(result, {"ended": True})

        return result
