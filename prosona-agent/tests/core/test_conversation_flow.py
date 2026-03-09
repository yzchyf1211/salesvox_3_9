"""
Conversation flow integration test.

Simulates the full lifecycle: Root -> Project -> Activity -> SCO -> end
by calling middleware lifecycle methods directly at each level,
verifying state transitions, API calls, and context injection.

Uses real project data:
- Project: 博弈与破局：复杂销售操盘手的全局掌控之道
- Activity: 销售博弈策略重构辩论 (roleplay)
- SCOs: drill-guide -> drill-deduction -> drill-review -> drill-report
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command

from agentickit.prosonaagent.core.middleware.task_middleware import (
    TaskMiddleware,
    ROOT_HANDLER_NAME,
    GENERAL_HANDLER_NAME,
)
from agentickit.prosonaagent.core.handler.task_handler import TaskHandler
from agentickit.prosonaagent.core.handler.handler_registry import HandlerRegistry
from agentickit.prosonaagent.core.middleware.middleware_registry import MiddlewareRegistry
from agentickit.prosonaagent.aom.middlewares.root_middleware import RootMiddleware
from agentickit.prosonaagent.aom.middlewares.project_middleware import ProjectMiddleware
from agentickit.prosonaagent.aom.middlewares.activity_middleware import ActivityMiddleware
from agentickit.prosonaagent.aom.middlewares.sco_middleware import SCOMiddleware


# ==================== Real Project Data ====================

MOCK_CONTEXT_ID = "ctx-test-001"
MOCK_PROJECT_ID = "1226137525330903040"

MOCK_PROJECT_INFO = {
    "id": MOCK_PROJECT_ID,
    "name": "博弈与破局：复杂销售操盘手的全局掌控之道",
    "description": "",
}

MOCK_MODULES = [
    {
        "name": "默认模块",
        "description": "",
        "activities": [],
    },
]

MOCK_ACTIVITY = {
    "id": "1226137532134064128",
    "name": "销售博弈策略重构辩论",
    "type": "roleplay",
    "description": "",
    "module_name": "默认模块",
}

MOCK_ACTIVITY_LIST = [MOCK_ACTIVITY]

MOCK_SCO_GUIDE = {
    "id": "4080f621-c9c9-4b79-be43-1c9b1bd98d71",
    "name": "导练",
    "type": "drill-guide",
    "activity_id": "1226137532134064128",
    "description": "",
}

MOCK_SCO_DEDUCTION = {
    "id": "041939a8-a2fa-4d38-9bde-8a98d253cfbe",
    "name": "演练",
    "type": "drill-deduction",
    "activity_id": "1226137532134064128",
    "description": "",
}

MOCK_SCO_REVIEW = {
    "id": "20aa8f13-83b7-4e99-8391-524314330ff7",
    "name": "复盘",
    "type": "drill-review",
    "activity_id": "1226137532134064128",
    "description": "",
}

MOCK_SCO_REPORT = {
    "id": "1aaf0ec8-e4d2-4475-a405-206c57d1aded",
    "name": "报告",
    "type": "drill-report",
    "activity_id": "1226137532134064128",
    "description": "",
}

MOCK_SCO_LIST = [MOCK_SCO_GUIDE, MOCK_SCO_DEDUCTION, MOCK_SCO_REVIEW, MOCK_SCO_REPORT]

MOCK_SCO_SEGMENTS = [
    {"id": "seg-001", "content": "销售博弈策略引导内容", "type": "text"},
]

MOCK_SCO_HISTORY = []  # First attempt


# ==================== Helpers ====================


def _make_initial_state():
    """Create initial state as would come from the A2A framework."""
    return {
        "context_id": MOCK_CONTEXT_ID,
        "messages": [HumanMessage(content="开始学习")],
        "parts": [
            {
                "root": {
                    "data": {
                        "actionName": "common-session-start",
                        "params": {
                            "projectId": MOCK_PROJECT_ID,
                        },
                    }
                }
            }
        ],
        "text_part_size": 0,
        # Framework fields (empty at start)
        "id": None,
        "name": None,
        "status": None,
        "params": None,
        "sub_tasks": [],
        "result": None,
        "mode": None,
        "user_profile": {"locale": "zh_CN", "id": "user-001"},
        "language": "zh_CN",
        "language_name": "Chinese",
    }


def _apply_update(state: dict, update: dict) -> dict:
    """Apply a state update dict to state, merging messages."""
    new_state = {**state}
    for k, v in update.items():
        if k == "messages":
            new_state["messages"] = new_state.get("messages", []) + v
        else:
            new_state[k] = v
    return new_state


def _make_registry():
    """Create a handler registry with project, activity, and 4 SCO handlers."""
    registry = HandlerRegistry()

    project_handler = TaskHandler()
    project_handler.name = "project"
    registry.register("project", project_handler)

    activity_handler = TaskHandler()
    activity_handler.name = "activity"
    registry.register("activity", activity_handler)

    for sco_type in ("drill-guide", "drill-deduction", "drill-review", "drill-report"):
        h = TaskHandler()
        h.name = sco_type
        registry.register(sco_type, h)

    return registry


# ==================== Patch Targets ====================

_ROOT_MW = "agentickit.prosonaagent.aom.middlewares.root_middleware"
_PROJECT_MW = "agentickit.prosonaagent.aom.middlewares.project_middleware"
_ACTIVITY_MW = "agentickit.prosonaagent.aom.middlewares.activity_middleware"
_SCO_MW = "agentickit.prosonaagent.aom.middlewares.sco_middleware"
_TASK_MW = "agentickit.prosonaagent.core.middleware.task_middleware"
_BIZ_MSG = "agentickit.prosonaagent.aom.message"


# ==================== Tests ====================


@pytest.mark.asyncio
class TestConversationFlow:
    """
    Integration test: middleware lifecycle methods at each level.

    Tests that each middleware correctly:
    - Loads data and injects context messages
    - Calls APIs and sends lifecycle messages
    - Sets status correctly
    - Produces appropriate messages for the LLM
    """

    def setup_method(self):
        self.registry = _make_registry()
        self.runtime = AsyncMock()

    # ---------- Level 0: Root ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_01_root_startup(self, mock_prompt):
        """Root abefore_agent: extracts project_id, injects start_task("project")."""
        root_mw = RootMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry,
        )

        state = _make_initial_state()
        result = await root_mw.abefore_agent(state, self.runtime)

        assert result["id"] == "__root__"
        assert result["name"] == ROOT_HANDLER_NAME
        assert result["status"] == "running"
        assert result["project_id"] == MOCK_PROJECT_ID

        # AIMessage with start_task("project") tool call
        ai_messages = [
            m for m in result.get("messages", []) if isinstance(m, AIMessage)
        ]
        assert len(ai_messages) >= 1
        assert ai_messages[0].tool_calls[0]["name"] == "_builtin_start_task"
        assert ai_messages[0].tool_calls[0]["args"] == {"name": "project", "params": {"id": MOCK_PROJECT_ID}}

        # jump_to is NOT set by abefore_agent (it's abefore_model's job)
        assert "jump_to" not in result

    # ---------- Level 1: Project ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    @patch(f"{_TASK_MW}.build_skill_information_context_list", return_value="<skills/>")
    @patch(f"{_TASK_MW}.get_skills_by_names", return_value=[])
    @patch(f"{_PROJECT_MW}.get_project_activities", new_callable=AsyncMock)
    @patch(f"{_PROJECT_MW}.get_project_modules", new_callable=AsyncMock)
    @patch(f"{_PROJECT_MW}.get_project_info", new_callable=AsyncMock)
    async def test_02_project_startup(
        self,
        mock_project_info,
        mock_modules,
        mock_activities,
        mock_skills,
        mock_skill_ctx,
        mock_prompt,
    ):
        """Project abefore: loads project data, injects context."""
        mock_project_info.return_value = MOCK_PROJECT_INFO
        mock_modules.return_value = MOCK_MODULES
        mock_activities.return_value = MOCK_ACTIVITY_LIST

        project_mw = ProjectMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry
        )

        state = _make_initial_state()
        state["project_id"] = MOCK_PROJECT_ID
        state["id"] = "project-task-001"
        state["name"] = "project"
        state["status"] = "pending"

        result = await project_mw.abefore_agent(state, self.runtime)

        mock_project_info.assert_called_once_with(MOCK_CONTEXT_ID, MOCK_PROJECT_ID)
        mock_modules.assert_called_once_with(MOCK_CONTEXT_ID, MOCK_PROJECT_ID)
        mock_activities.assert_called_once_with(MOCK_CONTEXT_ID, MOCK_PROJECT_ID)

        assert result["module_list"] == MOCK_MODULES
        assert result["activity_list"] == MOCK_ACTIVITY_LIST
        assert result["status"] == "running"

        # Context: project + activity list + skills + lifecycle event
        sys_messages = [
            m for m in result.get("messages", []) if isinstance(m, SystemMessage)
        ]
        assert len(sys_messages) >= 2

    # ---------- Level 2: Activity ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    @patch(f"{_TASK_MW}.build_skill_information_context_list", return_value="<skills/>")
    @patch(f"{_TASK_MW}.get_skills_by_names", return_value=[])
    @patch(f"{_BIZ_MSG}.send_to", new_callable=AsyncMock)
    @patch(f"{_ACTIVITY_MW}.get_user_profile", return_value={"id": "user-001"})
    @patch(f"{_ACTIVITY_MW}.get_project_info", new_callable=AsyncMock)
    @patch(f"{_ACTIVITY_MW}.get_sco_info", new_callable=AsyncMock)
    async def test_03_activity_startup(
        self,
        mock_sco_info,
        mock_project_info,
        mock_user_profile,
        mock_send_to,
        mock_skills,
        mock_skill_ctx,
        mock_prompt,
    ):
        """Activity abefore: loads activity & SCO list, sends lifecycle message."""
        mock_sco_info.return_value = MOCK_SCO_LIST
        mock_project_info.return_value = MOCK_PROJECT_INFO

        activity_mw = ActivityMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry
        )

        state = _make_initial_state()
        state["project_id"] = MOCK_PROJECT_ID
        state["activity_list"] = MOCK_ACTIVITY_LIST
        state["id"] = "call_activity_001"
        state["name"] = "activity"
        state["status"] = "pending"
        state["params"] = {"id": MOCK_ACTIVITY["id"]}

        result = await activity_mw.abefore_agent(state, self.runtime)

        assert result["activity"] == MOCK_ACTIVITY
        assert result["sco_list"] == MOCK_SCO_LIST
        assert len(result["sco_list"]) == 4
        assert result["status"] == "running"

        # Lifecycle start message sent
        mock_send_to.assert_called_once()

    # ---------- Level 3: SCO (all 4 types) ----------

    @pytest.mark.parametrize(
        "sco_data,sco_type",
        [
            (MOCK_SCO_GUIDE, "drill-guide"),
            (MOCK_SCO_DEDUCTION, "drill-deduction"),
            (MOCK_SCO_REVIEW, "drill-review"),
            (MOCK_SCO_REPORT, "drill-report"),
        ],
        ids=["导练", "演练", "复盘", "报告"],
    )
    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    @patch(f"{_BIZ_MSG}.send_to", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.start_sco", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.get_sco_history", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.get_sco_content", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.get_project_info", new_callable=AsyncMock)
    async def test_04_sco_startup(
        self,
        mock_project_info,
        mock_sco_content,
        mock_sco_history,
        mock_start_sco,
        mock_send_to,
        mock_prompt,
        sco_data,
        sco_type,
    ):
        """SCO abefore: loads SCO data/content, calls start_sco, sends lifecycle."""
        mock_project_info.return_value = MOCK_PROJECT_INFO
        mock_sco_content.return_value = MOCK_SCO_SEGMENTS
        mock_sco_history.return_value = MOCK_SCO_HISTORY

        sco_mw = SCOMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry
        )

        state = _make_initial_state()
        state["project_id"] = MOCK_PROJECT_ID
        state["activity_list"] = MOCK_ACTIVITY_LIST
        state["activity"] = MOCK_ACTIVITY
        state["sco_list"] = MOCK_SCO_LIST
        state["user_profile"] = {"id": "user-001"}
        state["id"] = f"call_sco_{sco_type}"
        state["name"] = sco_type
        state["status"] = "pending"
        state["params"] = {"id": sco_data["id"]}

        result = await sco_mw.abefore_agent(state, self.runtime)

        assert result["sco"] == sco_data
        assert result["sco_segment_list"] == MOCK_SCO_SEGMENTS
        assert result["order"] == 1
        assert result["status"] == "running"

        mock_start_sco.assert_called_once_with(MOCK_CONTEXT_ID, sco_data["id"])
        mock_send_to.assert_called_once()

        sys_messages = [
            m for m in result.get("messages", []) if isinstance(m, SystemMessage)
        ]
        assert len(sys_messages) >= 3

    # ---------- SCO Completion (all 4 types) ----------

    @pytest.mark.parametrize(
        "sco_data,sco_type",
        [
            (MOCK_SCO_GUIDE, "drill-guide"),
            (MOCK_SCO_DEDUCTION, "drill-deduction"),
            (MOCK_SCO_REVIEW, "drill-review"),
            (MOCK_SCO_REPORT, "drill-report"),
        ],
        ids=["导练", "演练", "复盘", "报告"],
    )
    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    @patch(f"{_BIZ_MSG}.send_to", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.end_sco", new_callable=AsyncMock)
    async def test_05_sco_end(
        self, mock_end_sco, mock_send_to, mock_prompt, sco_data, sco_type
    ):
        """SCO aafter: calls end_sco API, sends lifecycle end message."""
        sco_mw = SCOMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry
        )

        state = _make_initial_state()
        state["sco"] = sco_data
        state["activity"] = MOCK_ACTIVITY
        state["order"] = 1
        state["id"] = sco_data["id"]
        state["name"] = sco_type
        state["status"] = "running"

        result = await sco_mw.aafter(state, self.runtime)

        assert result["status"] == "completed"
        mock_end_sco.assert_called_once()
        mock_send_to.assert_called_once()

    # ---------- Activity completion ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    @patch(f"{_BIZ_MSG}.send_to", new_callable=AsyncMock)
    async def test_06_activity_end(self, mock_send_to, mock_prompt):
        """Activity aafter: sends lifecycle end message."""
        activity_mw = ActivityMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry
        )

        state = _make_initial_state()
        state["activity"] = MOCK_ACTIVITY
        state["id"] = MOCK_ACTIVITY["id"]
        state["name"] = "activity"
        state["status"] = "running"

        result = await activity_mw.aafter(state, self.runtime)

        assert result["status"] == "completed"
        mock_send_to.assert_called_once()

    # ---------- Project detects activity completion ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_07_project_aafter_task_detects_end(self, mock_prompt):
        """Project aafter_task: detects no more activities -> ended=True."""
        project_mw = ProjectMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry
        )

        state = _make_initial_state()
        state["name"] = "project"
        state["activity_list"] = MOCK_ACTIVITY_LIST  # Only 1 activity

        sub_state = {
            "id": "call_activity_001",
            "name": "activity",
            "status": "completed",
            "result": {"summary": "销售博弈策略重构辩论完成"},
            "params": {"id": MOCK_ACTIVITY["id"]},
        }

        result = await project_mw.aafter_task(
            state, self.runtime, sub_state,
        )

        assert result.get("ended") is True

    # ---------- Full 4-SCO sequence simulation ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    @patch(f"{_BIZ_MSG}.send_to", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.start_sco", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.end_sco", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.get_sco_history", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.get_sco_content", new_callable=AsyncMock)
    @patch(f"{_SCO_MW}.get_project_info", new_callable=AsyncMock)
    @patch(f"{_BIZ_MSG}.send_to", new_callable=AsyncMock)
    async def test_08_full_sco_sequence(
        self,
        mock_act_send_to,
        mock_project_info,
        mock_sco_content,
        mock_sco_history,
        mock_end_sco,
        mock_start_sco,
        mock_sco_send_to,
        mock_prompt,
    ):
        """Simulate all 4 SCOs: guide -> deduction -> review -> report."""
        mock_project_info.return_value = MOCK_PROJECT_INFO
        mock_sco_content.return_value = MOCK_SCO_SEGMENTS
        mock_sco_history.return_value = MOCK_SCO_HISTORY

        sco_mw = SCOMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry
        )

        sco_sequence = [
            (MOCK_SCO_GUIDE, "drill-guide"),
            (MOCK_SCO_DEDUCTION, "drill-deduction"),
            (MOCK_SCO_REVIEW, "drill-review"),
            (MOCK_SCO_REPORT, "drill-report"),
        ]

        for i, (sco_data, sco_type) in enumerate(sco_sequence):
            # --- SCO startup ---
            sco_task_id = f"call_sco_{i}"
            sco_state = _make_initial_state()
            sco_state["project_id"] = MOCK_PROJECT_ID
            sco_state["activity_list"] = MOCK_ACTIVITY_LIST
            sco_state["activity"] = MOCK_ACTIVITY
            sco_state["sco_list"] = MOCK_SCO_LIST
            sco_state["user_profile"] = {"id": "user-001"}
            sco_state["id"] = sco_task_id
            sco_state["name"] = sco_type
            sco_state["status"] = "pending"
            sco_state["params"] = {"id": sco_data["id"]}

            result = await sco_mw.abefore_agent(sco_state, self.runtime)

            assert result["sco"] == sco_data
            assert result["status"] == "running"

            # --- SCO end ---
            sco_state = _apply_update(sco_state, result)
            after_update = await sco_mw.aafter(sco_state, self.runtime)
            assert after_update["status"] == "completed"

        # After all 4 SCOs: start_sco called 4 times, end_sco called 4 times
        assert mock_start_sco.call_count == 4
        assert mock_end_sco.call_count == 4
