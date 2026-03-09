"""
Activity Middleware for Level 2 (AOM Adapter).

ActivityMiddleware handles standard/unified work for activity-level tasks:
- Load activity data, sco_list, initialize tracking fields
- Inject activity context
- Send biz-common-activity-lifecycle A2A messages
- Return completion summary via result
"""

from typing import Any, Dict, List

from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime

from agentickit.prosonaagent.core.middleware.enhance_task_middleware import EnhanceTaskMiddleware
from agentickit.prosonaagent.core.tools import _builtin_conversation
from agentickit.prosonaagent.aom.context import (
    get_activity_context,
    get_activity_list_context,
    get_project_context,
)
from agentickit.prosonaagent.aom.api import get_project_info, get_sco_info
from agentickit.prosonaagent.aom.query import get_activity_by_activity_id
from agentickit.prosonaagent.aom.state import ActivityTaskState
from agentickit.prosonaagent.aom.message import send_activity_lifecycle_message
from agentickit.prosonaagent.utils.user import get_user_profile


class ActivityMiddleware(EnhanceTaskMiddleware):
    """
    Level 2: Activity Middleware.

    Extends TaskMiddleware for activity-level task management:
    - Loads activity data and SCO list
    - Injects activity context
    - Sends biz-common-activity-lifecycle A2A messages
    - Creates SCOMiddleware for child tasks
    """

    state_schema = ActivityTaskState
    task_group_name: str = "activity"
    sub_task_group_name: str = "sco"
    tools = [_builtin_conversation]

    # ==================== Current Task Lifecycle ====================

    async def abefore(
        self,
        state: ActivityTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """
        Called when activity task starts.

        1. Load activity data and SCO list
        2. Inject activity context
        3. Call super().abefore() (sets status + calls handler.abefore)
        4. Send biz-common-activity-lifecycle start message
        """
        mw_update: Dict[str, Any] = {}

        # 1. Load activity data
        activity_id = state.get("params", {}).get("id")
        assert activity_id is not None, (
            "ActivityMiddleware.abefore: params must contain 'id'"
        )
        activity = get_activity_by_activity_id(state, activity_id)
        assert activity is not None, "ActivityMiddleware.abefore: activity not found"

        context_id = state.get("context_id")
        user_profile = get_user_profile(context_id)
        sco_list = await get_sco_info(context_id, activity, user_profile)

        mw_update["activity"] = activity
        mw_update["sco_list"] = sco_list

        # 2. Inject context（初始化入口，直接构造完整上下文）
        messages: List[SystemMessage] = []

        project_id = state.get("project_id")
        assert project_id is not None, (
            "ActivityMiddleware.abefore: project_id is missing"
        )
        project_info = await get_project_info(context_id, project_id)
        messages.append(SystemMessage(content=get_project_context(project_info)))

        activity_list = state.get("activity_list")
        assert activity_list, "ActivityMiddleware.abefore: activity_list is empty"
        messages.append(SystemMessage(content=get_activity_list_context(activity_list)))

        activity_context = get_activity_context(activity, sco_list)
        messages.append(SystemMessage(content=activity_context))

        mw_update["messages"] = messages

        # 3. Call super().abefore()
        lifecycle_update = await super().abefore(state, runtime)
        result = self._merge_updates(mw_update, lifecycle_update)

        # 4. Send lifecycle message
        await send_activity_lifecycle_message(
            state,
            lifecycle_type="start",
            activity=activity,
        )

        return result

    async def apause(
        self,
        state: ActivityTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when activity task pauses."""
        result = await super().apause(state, runtime)

        activity = state.get("activity")

        if activity:
            await send_activity_lifecycle_message(
                state,
                lifecycle_type="pause",
                activity=activity,
            )

        return result

    async def aresume(
        self,
        state: ActivityTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when activity task resumes."""
        result = await super().aresume(state, runtime)

        activity = state.get("activity")

        if activity:
            await send_activity_lifecycle_message(
                state,
                lifecycle_type="resume",
                activity=activity,
            )

        return result

    async def ainterrupt(
        self,
        state: ActivityTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when activity task is interrupted."""
        update = await super().ainterrupt(state, runtime)

        activity = state.get("activity")

        if activity:
            await send_activity_lifecycle_message(
                state,
                lifecycle_type="interrupt",
                activity=activity,
            )

        return update

    async def arecover(
        self,
        state: ActivityTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when activity task recovers."""
        result = await super().arecover(state, runtime)

        activity = state.get("activity")

        if activity:
            await send_activity_lifecycle_message(
                state,
                lifecycle_type="recover",
                activity=activity,
            )

        return result

    async def aafter(
        self,
        state: ActivityTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when activity task completes."""
        update = await super().aafter(state, runtime)

        activity = state.get("activity")

        if activity:
            await send_activity_lifecycle_message(
                state,
                lifecycle_type="end",
                activity=activity,
            )

        return update
