"""
Graph-based flow test.

Tests the middleware hooks in the correct execution order,
focusing on user-facing behavior: messages produced by the
middleware at each stage of the agent lifecycle.

Key behaviors tested:
- Root initialization: project_id extraction, start_task injection, jump_to
- Lifecycle dispatch: pending->abefore, recovering->arecover, paused->resume
- Blocking subgraph: start_task tool invokes subgraph and returns result
- Tool closures: builtin tools correctly reference their middleware
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command

from agentickit.prosonaagent.core.middleware.task_middleware import (
    TaskMiddleware,
    ROOT_HANDLER_NAME,
)
from agentickit.prosonaagent.core.handler.task_handler import TaskHandler
from agentickit.prosonaagent.core.handler.handler_registry import HandlerRegistry
from agentickit.prosonaagent.core.middleware.middleware_registry import MiddlewareRegistry
from agentickit.prosonaagent.aom.middlewares.root_middleware import RootMiddleware


# ==================== Real Project Data ====================

MOCK_CONTEXT_ID = "ctx-test-001"
MOCK_PROJECT_ID = "1226137525330903040"

MOCK_ACTIVITY = {
    "id": "1226137532134064128",
    "name": "销售博弈策略重构辩论",
    "type": "roleplay",
    "description": "",
    "module_name": "默认模块",
}

MOCK_SCO_GUIDE = {
    "id": "4080f621-c9c9-4b79-be43-1c9b1bd98d71",
    "name": "导练",
    "type": "drill-guide",
    "activity_id": "1226137532134064128",
}


# ==================== Helpers ====================

_TASK_MW = "agentickit.prosonaagent.core.middleware.task_middleware"


def _tool_by_name(middleware, name: str):
    """Get a tool by name from middleware.tools."""
    return next((t for t in middleware.tools if getattr(t, "name", None) == name), None)


def _make_registry():
    """Create handler registry with project, activity, and SCO handlers."""
    registry = HandlerRegistry()

    for name in ("project", "activity", "drill-guide", "drill-deduction", "drill-review", "drill-report"):
        h = TaskHandler()
        h.name = name
        registry.register(name, h)

    return registry


def _make_initial_state() -> Dict[str, Any]:
    """Create initial state as would come from A2A framework."""
    return {
        "context_id": MOCK_CONTEXT_ID,
        "messages": [HumanMessage(content="开始学习")],
        "parts": [
            {
                "root": {
                    "data": {
                        "actionName": "common-session-start",
                        "params": {"projectId": MOCK_PROJECT_ID},
                    }
                }
            }
        ],
        "text_part_size": 0,
        "id": None,
        "name": None,
        "status": None,
        "params": None,
        "sub_tasks": [],
        "result": None,
        "mode": None,
        "user_profile": {"locale": "zh_CN"},
        "language": "zh_CN",
        "language_name": "Chinese",
    }


def _apply_update(state: dict, update: dict) -> dict:
    """Apply a state update dict, merging messages."""
    new_state = {**state}
    for k, v in update.items():
        if k == "messages":
            new_state["messages"] = new_state.get("messages", []) + v
        else:
            new_state[k] = v
    return new_state


def _make_tool_runtime(state: dict, tool_call_id: str = "call_test"):
    """Create a mock ToolRuntime."""
    rt = MagicMock()
    rt.state = state
    rt.tool_call_id = tool_call_id
    return rt


# ==================== Tests ====================


@pytest.mark.asyncio
class TestGraphFlow:
    """
    Graph-based integration test.

    Tests middleware behavior from user perspective:
    - Root startup injects correct messages (AIMessage with tool_calls)
    - jump_to mechanism works
    - Blocking subgraph invocation in start_task tool
    - Builtin tool closures correctly reference middleware
    """

    def setup_method(self):
        self.registry = _make_registry()
        self.runtime = AsyncMock()

    def _create_root_middleware(self) -> RootMiddleware:
        mw = RootMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry,
        )
        mw._get_or_create_subgraph = MagicMock(return_value=MagicMock())
        return mw

    # ---------- Root initialization ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_01_root_startup_produces_correct_messages(self, mock_prompt):
        """
        First invocation: root auto-initializes and produces
        AIMessage with start_task("project").

        This is the key user-facing behavior: the system automatically
        starts the project task without requiring user input.
        jump_to="tools" is handled by abefore_model, not abefore_agent.
        """
        middleware = self._create_root_middleware()
        state = _make_initial_state()

        update = await middleware.abefore_agent(state, self.runtime)

        # Root initialized
        assert update["id"] == "__root__"
        assert update["status"] == "running"
        assert update["project_id"] == MOCK_PROJECT_ID

        # Messages should include AIMessage with start_task("project")
        ai_messages = [
            m for m in update.get("messages", []) if isinstance(m, AIMessage)
        ]
        assert len(ai_messages) >= 1
        tool_call = ai_messages[0].tool_calls[0]
        assert tool_call["name"] == "_builtin_start_task"
        assert tool_call["args"] == {"name": "project", "params": {"id": MOCK_PROJECT_ID}}

        # jump_to is NOT set by abefore_agent (it's abefore_model's job)
        assert "jump_to" not in update

    # ---------- Lifecycle dispatch ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_02_pending_task_triggers_abefore(self, mock_prompt):
        """When status is 'pending', abefore_agent calls abefore (lifecycle start)."""
        middleware = self._create_root_middleware()

        state = _make_initial_state()
        state["id"] = "project-001"
        state["name"] = "project"
        state["status"] = "pending"

        update = await middleware.abefore_agent(state, self.runtime)

        # Status transitions from pending -> running
        assert update["status"] == "running"

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_03_recovering_task_triggers_arecover(self, mock_prompt):
        """When status is 'recovering', abefore_agent calls arecover."""
        middleware = self._create_root_middleware()

        state = _make_initial_state()
        state["id"] = "project-001"
        state["name"] = "project"
        state["status"] = "recovering"

        update = await middleware.abefore_agent(state, self.runtime)

        assert update["status"] == "running"

    # ---------- Builtin tool instances ----------

    def test_04_middleware_creates_three_builtin_tools(self):
        """Each middleware instance exposes 3 builtin task tools in .tools."""
        middleware = self._create_root_middleware()

        names = {t.name for t in middleware.tools if getattr(t, "name", None)}
        assert names >= {
            "_builtin_start_task",
            "_builtin_end_task",
            "_builtin_recover_task",
        }

    def test_05_tool_by_name_from_tools(self):
        """Tools can be looked up by name from middleware.tools."""
        middleware = self._create_root_middleware()

        start = _tool_by_name(middleware, "_builtin_start_task")
        assert start is not None
        assert start.name == "_builtin_start_task"

        assert _tool_by_name(middleware, "nonexistent") is None

    # ---------- Blocking subgraph invocation ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_06_start_task_invokes_subgraph_blocking(self, mock_prompt):
        """
        _builtin_start_task tool invokes subgraph and blocks until completion.
        After the subgraph returns, the tool produces a ToolMessage with result.
        """
        middleware = self._create_root_middleware()
        middleware._runtime = self.runtime

        # Mock subgraph result
        result_state = {
            "status": "completed",
            "result": {"summary": "Project task finished"},
            "messages": [],
        }
        middleware._get_suspended_state = AsyncMock(return_value=None)
        middleware._invoke_subgraph = AsyncMock(return_value=result_state)
        mock_subgraph = MagicMock()
        middleware._get_or_create_subgraph = MagicMock(return_value=mock_subgraph)

        state = _make_initial_state()
        state["id"] = "__root__"
        state["name"] = ROOT_HANDLER_NAME
        state["status"] = "running"

        state["sub_tasks"] = []

        # Get the start_task tool and invoke its coroutine directly
        start_tool = _tool_by_name(middleware, "_builtin_start_task")

        tool_runtime = _make_tool_runtime(state, "call_start_001")
        result = await start_tool.coroutine(
            name="project",
            tool_runtime=tool_runtime,
        )

        # _invoke_subgraph was called
        middleware._invoke_subgraph.assert_awaited_once()

        # Check the invocation args (subgraph, sub_state, thread_id)
        call_args = middleware._invoke_subgraph.call_args
        sub_state = call_args[0][1]  # second positional arg
        assert sub_state["name"] == "project"
        assert sub_state["status"] == "pending"
        assert sub_state["messages"] == []

        # Result should be a Command with ToolMessage
        assert isinstance(result, Command)
        messages = result.update.get("messages", [])
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        assert len(tool_msgs) >= 1
        assert "Project task finished" in tool_msgs[0].content

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_07_start_task_uses_tool_call_id(self, mock_prompt):
        """
        start_task always uses tool_call_id as the task_id.
        Business entity ID is passed via params and stored in params.
        """
        middleware = self._create_root_middleware()
        middleware._runtime = self.runtime

        result_state = {
            "status": "completed",
            "result": None,
            "params": {"id": MOCK_ACTIVITY["id"]},
            "messages": [],
        }
        middleware._get_suspended_state = AsyncMock(return_value=None)
        middleware._invoke_subgraph = AsyncMock(return_value=result_state)
        mock_subgraph = MagicMock()
        middleware._get_or_create_subgraph = MagicMock(return_value=mock_subgraph)

        state = _make_initial_state()
        state["id"] = "__root__"
        state["name"] = ROOT_HANDLER_NAME
        state["status"] = "running"

        state["sub_tasks"] = []

        activity_id = MOCK_ACTIVITY["id"]
        start_tool = _tool_by_name(middleware, "_builtin_start_task")

        tool_runtime = _make_tool_runtime(state, "call_start_002")
        await start_tool.coroutine(
            name="activity",
            params={"id": activity_id},
            tool_runtime=tool_runtime,
        )

        # Subgraph was created with key = "activity:call_start_002"
        expected_key = "activity:call_start_002"
        middleware._get_or_create_subgraph.assert_called_with(expected_key, "activity")

        # Sub state uses tool_call_id, not entity ID
        sub_state = middleware._invoke_subgraph.call_args[0][1]
        assert sub_state["id"] == "call_start_002"
        assert sub_state["params"]["id"] == activity_id

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_08_start_task_always_uses_tool_call_id(self, mock_prompt):
        """start_task always uses tool_call_id as task_id, regardless of params."""
        middleware = self._create_root_middleware()
        middleware._runtime = self.runtime

        result_state = {
            "status": "completed",
            "result": None,
            "messages": [],
        }
        middleware._get_suspended_state = AsyncMock(return_value=None)
        middleware._invoke_subgraph = AsyncMock(return_value=result_state)
        mock_subgraph = MagicMock()
        middleware._get_or_create_subgraph = MagicMock(return_value=mock_subgraph)

        state = _make_initial_state()
        state["id"] = "__root__"
        state["name"] = ROOT_HANDLER_NAME
        state["status"] = "running"

        state["sub_tasks"] = []

        start_tool = _tool_by_name(middleware, "_builtin_start_task")
        tool_runtime = _make_tool_runtime(state, "call_start_003")
        await start_tool.coroutine(
            name="project",
            tool_runtime=tool_runtime,
        )

        # Sub state uses tool_call_id as task_id
        sub_state = middleware._invoke_subgraph.call_args[0][1]
        assert sub_state["id"] == "call_start_003"

    # ---------- End task tool ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_09_end_task_calls_lifecycle(self, mock_prompt):
        """
        _builtin_end_task tool calls aafter lifecycle hook
        and produces a ToolMessage with status=completed.
        """
        middleware = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry,
        )
        middleware._runtime = self.runtime

        state = {
            "id": "guide-001",
            "name": "drill-guide",
            "status": "running",
            "messages": [],
            "sub_tasks": [],
            "result": None,
        }

        end_tool = _tool_by_name(middleware, "_builtin_end_task")
        tool_runtime = _make_tool_runtime(state, "call_end_001")
        result = await end_tool.coroutine(
            is_interrupt=False,
            tool_runtime=tool_runtime,
        )

        assert isinstance(result, Command)
        assert result.update["status"] == "completed"

        # Should have a ToolMessage
        messages = result.update.get("messages", [])
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        assert len(tool_msgs) >= 1

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_10_end_task_interrupt(self, mock_prompt):
        """_builtin_end_task with is_interrupt=True calls ainterrupt."""
        middleware = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.registry,
        )
        middleware._runtime = self.runtime

        state = {
            "id": "guide-001",
            "name": "drill-guide",
            "status": "running",
            "messages": [],
            "sub_tasks": [],
            "result": None,
        }

        end_tool = _tool_by_name(middleware, "_builtin_end_task")
        tool_runtime = _make_tool_runtime(state, "call_end_002")
        result = await end_tool.coroutine(
            is_interrupt=True,
            result={"reason": "用户要求中断"},
            tool_runtime=tool_runtime,
        )

        assert isinstance(result, Command)
        assert result.update["status"] == "interrupted"
        assert result.update["result"]["reason"] == "用户要求中断"

    # ---------- Recover task tool ----------

    @patch(f"{_TASK_MW}.get_task_prompt", return_value=None)
    async def test_11_recover_task_invokes_subgraph(self, mock_prompt):
        """_builtin_recover_task invokes subgraph with status='recovering'."""
        middleware = self._create_root_middleware()
        middleware._runtime = self.runtime

        result_state = {
            "status": "completed",
            "result": {"summary": "Recovery done"},
            "messages": [],
        }
        middleware._get_suspended_state = AsyncMock(return_value=None)
        middleware._invoke_subgraph = AsyncMock(return_value=result_state)
        mock_subgraph = MagicMock()
        middleware._get_or_create_subgraph = MagicMock(return_value=mock_subgraph)

        state = _make_initial_state()
        state["id"] = "__root__"
        state["name"] = ROOT_HANDLER_NAME
        state["status"] = "running"

        state["sub_tasks"] = []

        recover_tool = _tool_by_name(middleware, "_builtin_recover_task")
        tool_runtime = _make_tool_runtime(state, "call_recover_001")
        result = await recover_tool.coroutine(
            task_id="guide-001",
            task_name="drill-guide",
            tool_runtime=tool_runtime,
        )

        # _invoke_subgraph was called with only status update —
        # everything else preserved from checkpoint (same graph).
        middleware._invoke_subgraph.assert_awaited_once()
        sub_state = middleware._invoke_subgraph.call_args[0][1]
        assert sub_state == {"status": "recovering"}

        # Result should contain recovery message
        assert isinstance(result, Command)
        messages = result.update.get("messages", [])
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        assert len(tool_msgs) >= 1
        assert "completed" in tool_msgs[0].content
        assert "Recovery done" in tool_msgs[0].content

    # ---------- hook_config ----------

    def test_12_abefore_model_has_hook_config(self):
        """abefore_model should have __can_jump_to__ = ['tools', 'end'] from @hook_config."""
        middleware = self._create_root_middleware()
        assert hasattr(middleware.abefore_model, "__can_jump_to__")
        assert middleware.abefore_model.__can_jump_to__ == ["tools", "end"]

    def test_13_abefore_agent_has_no_hook_config(self):
        """abefore_agent should NOT have __can_jump_to__."""
        middleware = self._create_root_middleware()
        assert not hasattr(middleware.abefore_agent, "__can_jump_to__")
