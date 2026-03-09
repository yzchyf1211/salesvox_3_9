"""
SCO Middleware for Level 2 (AOM Adapter).

SCOMiddleware handles standard/unified work for SCO-level tasks:
- Load SCO data, SCO content, SCO history
- Inject SCO context + task prompt
- Call start_sco/end_sco API
- Send biz-common-sco-lifecycle A2A messages
- Provides _builtin_send_user_content as a builtin tool (A2A activity-introduction + sco-display, card from handler.aget_card)

Handlers only retain extra/extension business logic (card rendering,
next_task replacement, etc.).
"""

from typing import Any, Dict, List

from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.runtime import Runtime

from agentickit.prosonaagent.core.middleware.enhance_task_middleware import EnhanceTaskMiddleware
from agentickit.prosonaagent.aom.context import (
    get_project_context,
    get_activity_context,
    get_current_sco_context,
)
from agentickit.prosonaagent.aom.query import (
    get_sco_by_sco_id,
    get_activity_by_activity_id,
)
from agentickit.prosonaagent.aom.api import (
    get_project_info,
    get_sco_content,
    start_sco,
    end_sco,
    get_sco_history,
)
from agentickit.prosonaagent.aom.state import SCOTaskState
from agentickit.prosonaagent.aom.message import send_sco_lifecycle_message


class SCOMiddleware(EnhanceTaskMiddleware):
    """
    Level 3: SCO Middleware.

    Extends TaskMiddleware for SCO-level task management:
    - Loads SCO data, content, and history
    - Injects project/activity/SCO context + task prompt
    - Calls start_sco/end_sco API
    - Sends biz-common-sco-lifecycle A2A messages
    """

    state_schema = SCOTaskState
    task_group_name: str = "sco"
    allow_sub_tasks: bool = False  # SCO level does not create sub-tasks

    # ==================== Current Task Lifecycle ====================

    async def abefore(
        self,
        state: SCOTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """
        Called when SCO task starts.

        1. Load SCO data (sco, activity, sco_list)
        2. Load SCO content
        3. Get SCO history to determine order
        4. Inject project/activity/SCO context + task prompt
        5. Call super().abefore() (sets status + calls handler.abefore)
        6. Call start_sco API
        7. Send biz-common-sco-lifecycle start message
        """
        mw_update: Dict[str, Any] = {}
        merged_messages: List[AnyMessage] = []

        # 1. Load SCO data
        sco_id = state.get("params", {}).get("id")
        assert sco_id is not None, "SCOMiddleware.abefore: params must contain 'id'"
        sco = get_sco_by_sco_id(state, sco_id)
        activity = get_activity_by_activity_id(state, sco.get("activity_id"))
        mw_update["sco"] = sco

        # 2. Load SCO content
        sco_segment_list = await get_sco_content(
            state.get("context_id"),
            activity.get("id"),
            sco.get("id"),
            state.get("user_profile"),
        )
        mw_update["sco_segment_list"] = sco_segment_list

        # 3. Get SCO history to determine order
        history = await get_sco_history(state.get("context_id"), sco.get("id"))
        order = len(history) + 1
        mw_update["order"] = order

        # 4. Inject context（初始化入口，直接构造完整上下文）
        project_id = state.get("project_id")
        assert project_id is not None, "SCOMiddleware.abefore: project_id is missing"
        project_info = await get_project_info(state.get("context_id"), project_id)
        project_context = get_project_context(project_info)
        merged_messages.append(SystemMessage(content=project_context))

        activity_context = get_activity_context(activity, state["sco_list"])
        merged_messages.append(SystemMessage(content=activity_context))

        current_sco_context = get_current_sco_context(sco)
        merged_messages.append(SystemMessage(content=current_sco_context))

        mw_update["messages"] = merged_messages

        # 5. Enrich state so handler.abefore sees SCO data (no in-place mutation)
        enriched_state = {
            **state,
            "sco": sco,
            "activity": activity,
            "sco_segment_list": sco_segment_list,
            "order": order,
        }

        # 6. Call super().abefore() (sets status + loads TASK.md + calls handler.abefore)
        lifecycle_update = await super().abefore(enriched_state, runtime)
        result = self._merge_updates(mw_update, lifecycle_update)

        # 7. Call start_sco API
        await start_sco(state.get("context_id"), sco.get("id"))

        # 8. Send lifecycle message
        await send_sco_lifecycle_message(
            state,
            lifecycle_type="start",
            sco=sco,
            activity=activity,
            order=order,
        )

        return result

    async def apause(
        self,
        state: SCOTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when SCO task pauses."""
        # Call super
        result = await super().apause(state, runtime)

        # Send lifecycle message
        sco = state.get("sco")
        activity = state.get("activity")
        order = state.get("order")

        if sco and activity:
            await send_sco_lifecycle_message(
                state,
                lifecycle_type="pause",
                sco=sco,
                activity=activity,
                order=order,
            )

        return result

    async def aresume(
        self,
        state: SCOTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when SCO task resumes."""
        # Resume context injection is handled by the handler's aresume.
        result = await super().aresume(state, runtime)

        # Send lifecycle message
        sco = state.get("sco")
        activity = state.get("activity")
        order = state.get("order")

        if sco and activity:
            await send_sco_lifecycle_message(
                state,
                lifecycle_type="resume",
                sco=sco,
                activity=activity,
                order=order,
            )

        return result

    async def ainterrupt(
        self,
        state: SCOTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when SCO task is interrupted."""
        update = await super().ainterrupt(state, runtime)

        # Send lifecycle message
        sco = state.get("sco")
        activity = state.get("activity")
        order = state.get("order")

        if sco and activity:
            await send_sco_lifecycle_message(
                state,
                lifecycle_type="interrupt",
                sco=sco,
                activity=activity,
                order=order,
            )

        return update

    async def arecover(
        self,
        state: SCOTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when SCO task recovers."""
        result = await super().arecover(state, runtime)

        # Send lifecycle message
        sco = state.get("sco")
        activity = state.get("activity")
        order = state.get("order")

        if sco and activity:
            await send_sco_lifecycle_message(
                state,
                lifecycle_type="recover",
                sco=sco,
                activity=activity,
                order=order,
            )

        return result

    async def aafter(
        self,
        state: SCOTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any]:
        """Called when SCO task completes."""
        task_name = state["name"]
        # Call super (sets status + calls handler.aafter)
        update = await super().aafter(state, runtime)

        # Get SCO data
        sco = state.get("sco")
        activity = state.get("activity")
        order = state.get("order")

        if sco and activity:
            # Call end_sco API
            # Get current_task_messages from handler if available
            handler = self.get_handler(task_name)
            current_task_messages = (
                getattr(handler, "_current_task_messages", None) or []
            )
            await end_sco(state.get("context_id"), sco.get("id"), current_task_messages)

            # Send lifecycle message
            await send_sco_lifecycle_message(
                state,
                lifecycle_type="end",
                sco=sco,
                activity=activity,
                order=order,
            )

        return update
