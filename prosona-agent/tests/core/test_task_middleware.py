"""Tests for TaskMiddleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command

from agentickit.prosonaagent.core.middleware.task_middleware import TaskState
from agentickit.prosonaagent.core.handler.handler_registry import HandlerRegistry
from agentickit.prosonaagent.core.middleware.middleware_registry import MiddlewareRegistry
from agentickit.prosonaagent.core.handler.task_handler import TaskHandler
from agentickit.prosonaagent.core.middleware.task_middleware import (
    TaskMiddleware,
    ROOT_HANDLER_NAME,
    GENERAL_HANDLER_NAME,
)


# ==================== Helpers ====================


def _make_handler(name: str = "", **kwargs) -> TaskHandler:
    h = TaskHandler()
    for k, v in kwargs.items():
        setattr(h, k, v)
    return h


def _make_state(**overrides) -> dict:
    base = {
        "messages": [],
        "sub_tasks": [],
        "id": None,
        "name": None,
        "status": None,
        "params": None,
        "result": None,
        "mode": None,
        "context_id": None,
        "user_profile": {"locale": "en"},
        "language": "en",
        "language_name": "English",
    }
    base.update(overrides)
    return base


def _make_runtime() -> MagicMock:
    return MagicMock()


def _make_command(**update) -> Command:
    return Command(update=update if update else {"messages": []})


def _tool_by_name(mw: TaskMiddleware, name: str):
    """Get a tool by name from middleware.tools."""
    return next((t for t in mw.tools if getattr(t, "name", None) == name), None)


# ==================== Init Tests ====================


class TestTaskMiddlewareInit:
    def test_default_root_handler_registered(self):
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        handler = mw.get_handler(ROOT_HANDLER_NAME)
        assert handler is not None
        assert isinstance(handler, TaskHandler)

    def test_default_general_handler_registered(self):
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        handler = mw.get_handler(GENERAL_HANDLER_NAME)
        assert handler is not None
        assert isinstance(handler, TaskHandler)

    def test_custom_root_handler_preserved(self):
        reg = HandlerRegistry()
        root = _make_handler(ROOT_HANDLER_NAME)
        reg.register(ROOT_HANDLER_NAME, root)
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=reg,
        )
        assert mw.get_handler(ROOT_HANDLER_NAME) is root

    def test_get_handler_falls_back_to_general(self):
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        handler = mw.get_handler("nonexistent_task")
        assert handler is not None
        assert handler is mw.get_handler(GENERAL_HANDLER_NAME)

    def test_get_handler_specific_over_general(self):
        reg = HandlerRegistry()
        specific = _make_handler("guide")
        reg.register("guide", specific)
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=reg,
        )
        assert mw.get_handler("guide") is specific

    def test_state_schema_uses_class_attribute(self):
        """Middleware uses its own class-level state_schema directly.
        Handler schemas are merged in _build_subgraph via _create_state_schema."""
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        assert mw.state_schema is TaskState

    def test_task_tools_in_tools(self):
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        names = {t.name for t in mw.tools if getattr(t, "name", None)}
        assert names >= {"_builtin_start_task", "_builtin_end_task", "_builtin_recover_task"}

    def test_tool_by_name_from_tools(self):
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        start = _tool_by_name(mw, "_builtin_start_task")
        assert start is not None
        assert start.name == "_builtin_start_task"

        end = _tool_by_name(mw, "_builtin_end_task")
        assert end is not None
        assert end.name == "_builtin_end_task"

        recover = _tool_by_name(mw, "_builtin_recover_task")
        assert recover is not None
        assert recover.name == "_builtin_recover_task"

        assert _tool_by_name(mw, "nonexistent") is None


# ==================== Task Info Tests ====================


class TestTaskInfo:
    def setup_method(self):
        self.mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )

    def test_get_current_task_info_empty(self):
        state = _make_state()
        assert self.mw._get_current_task_info(state) == (None, None)

    def test_get_current_task_info(self):
        state = _make_state(id="t1", name="guide")
        assert self.mw._get_current_task_info(state) == ("t1", "guide")

    def test_get_current_task_name(self):
        state = _make_state(name="guide")
        assert self.mw._get_current_task_name(state) == "guide"

    def test_get_current_task_name_empty(self):
        state = _make_state()
        assert self.mw._get_current_task_name(state) is None

    def test_make_key(self):
        assert self.mw._make_key("guide", "abc123") == "guide:abc123"


# ==================== Lifecycle Tests ====================


class TestLifecycle:
    def setup_method(self):
        self.reg = HandlerRegistry()
        self.handler = _make_handler("test")
        self.reg.register("test", self.handler)
        self.mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.reg,
        )
        self.runtime = _make_runtime()

    @pytest.mark.asyncio
    async def test_abefore_sets_running(self):
        state = _make_state(id="t1", name="test")
        result = await self.mw.abefore(state, self.runtime)
        assert result["status"] == "running"
        assert result["id"] == "t1"
        assert result["name"] == "test"

    @pytest.mark.asyncio
    async def test_abefore_calls_handler(self):
        self.handler.abefore = AsyncMock(return_value={"custom": "data"})
        state = _make_state(id="t1", name="test")
        result = await self.mw.abefore(state, self.runtime)
        # Handler receives merged state (with status="running")
        call_args = self.handler.abefore.call_args
        merged = call_args[0][0]
        assert merged["status"] == "running"
        assert merged["id"] == "t1"
        assert merged["name"] == "test"
        assert call_args[0][1] is self.runtime
        assert result["custom"] == "data"

    @pytest.mark.asyncio
    async def test_apause_sets_paused(self):
        state = _make_state(id="t1", name="test")
        result = await self.mw.apause(state, self.runtime)
        assert result["status"] == "paused"

    @pytest.mark.asyncio
    async def test_aresume_sets_running(self):
        state = _make_state(id="t1", name="test")
        result = await self.mw.aresume(state, self.runtime)
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_ainterrupt_sets_interrupted(self):
        state = _make_state(id="t1", name="test", result={"reason": "user quit"})
        result = await self.mw.ainterrupt(state, self.runtime)
        assert result["status"] == "interrupted"
        assert result["result"] == {"reason": "user quit"}

    @pytest.mark.asyncio
    async def test_arecover_sets_running(self):
        state = _make_state(id="t1", name="test")
        result = await self.mw.arecover(state, self.runtime)
        assert result["status"] == "running"
        assert result["result"] is None

    @pytest.mark.asyncio
    async def test_aafter_sets_completed(self):
        state = _make_state(id="t1", name="test")
        result = await self.mw.aafter(state, self.runtime)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_aafter_with_handler_result(self):
        self.handler.aafter = AsyncMock(
            return_value={"result": {"summary": "all done", "x": 1}}
        )
        state = _make_state(id="t1", name="test")
        result = await self.mw.aafter(state, self.runtime)
        assert result["result"]["summary"] == "all done"
        assert result["result"]["x"] == 1


# ==================== Sub Task Lifecycle Tests ====================


class TestSubTaskLifecycle:
    def setup_method(self):
        self.reg = HandlerRegistry()
        self.handler = _make_handler("parent")
        self.reg.register("parent", self.handler)
        self.mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.reg,
        )
        self.runtime = _make_runtime()

    @pytest.mark.asyncio
    async def test_abefore_task_appends_sub_task(self):
        state = _make_state(name="parent", sub_tasks=["old_sub"])
        result = await self.mw.abefore_task(
            state, self.runtime, "s1", "child"
        )
        assert result["sub_tasks"] == ["old_sub", "s1"]

    @pytest.mark.asyncio
    async def test_aafter_task_with_handler_result(self):
        self.handler.aafter_task = AsyncMock(
            return_value={"result": {"summary": "done", "count": 3}}
        )
        state = _make_state(name="parent")
        sub_state = {"id": "s1", "name": "child", "status": "completed", "result": None}
        result = await self.mw.aafter_task(
            state, self.runtime, sub_state
        )
        assert result["result"]["summary"] == "done"
        assert result["result"]["count"] == 3


# ==================== Merge Helpers Tests ====================


class TestMergeHelpers:
    def setup_method(self):
        self.mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )

    def test_merge_updates_combines_messages(self):
        base = {"status": "running", "messages": [SystemMessage(content="a")]}
        override = {"status": "paused", "messages": [SystemMessage(content="b")]}
        result = self.mw._merge_updates(base, override)
        assert result["status"] == "paused"
        assert len(result["messages"]) == 2

    def test_merge_updates_override_non_messages(self):
        base = {"x": 1, "y": 2}
        override = {"y": 3, "z": 4}
        result = self.mw._merge_updates(base, override)
        assert result == {"x": 1, "y": 3, "z": 4}



# ==================== Tool Call Dispatch Tests ====================


class TestToolCallDispatch:
    def setup_method(self):
        self.reg = HandlerRegistry()
        self.mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.reg,
        )

    @pytest.mark.asyncio
    async def test_other_tool_delegates_to_handler_wrapper(self):
        custom_handler = _make_handler("guide")
        custom_handler.awrap_tool_call = AsyncMock(return_value=_make_command())
        self.reg.register("guide", custom_handler)

        req = MagicMock()
        req.tool_call = {"name": "some_tool", "args": {}}
        req.state = _make_state(id="1", name="guide", status="running")
        handler = AsyncMock(return_value=_make_command())

        await self.mw.awrap_tool_call(req, handler)
        custom_handler.awrap_tool_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_other_tool_no_handler_falls_through(self):
        req = MagicMock()
        req.tool_call = {"name": "some_tool", "args": {}}
        req.state = _make_state(id="1", name="unknown", status="running")
        handler = AsyncMock(return_value=_make_command())

        result = await self.mw.awrap_tool_call(req, handler)
        handler.assert_awaited_once()


# ==================== abefore_agent Tests ====================


class TestBeforeAgent:
    def setup_method(self):
        self.reg = HandlerRegistry()
        self.root = _make_handler(ROOT_HANDLER_NAME)
        self.reg.register(ROOT_HANDLER_NAME, self.root)
        self.mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=self.reg,
        )
        self.runtime = _make_runtime()

    @pytest.mark.asyncio
    async def test_no_task_initializes_root(self):
        state = _make_state()
        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = "common-session-start"
            proxy.get_params.return_value = None

            result = await self.mw.abefore_agent(state, self.runtime)

        assert result["id"] == "__root__"
        assert result["name"] == ROOT_HANDLER_NAME
        assert result["status"] == "running"  # pending -> abefore -> running

    @pytest.mark.asyncio
    async def test_pending_task_calls_abefore(self):
        state = _make_state(id="t1", name=ROOT_HANDLER_NAME, status="pending")
        self.root.abefore = AsyncMock(return_value={"custom": "init"})

        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = "common-session-start"
            proxy.get_params.return_value = None

            result = await self.mw.abefore_agent(state, self.runtime)

        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_recovering_task_calls_arecover(self):
        state = _make_state(id="t1", name=ROOT_HANDLER_NAME, status="recovering")
        self.root.arecover = AsyncMock(return_value={"custom": "recovered"})

        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = None
            proxy.get_params.return_value = None

            result = await self.mw.abefore_agent(state, self.runtime)

        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_paused_task_no_lifecycle_dispatch(self):
        """Paused tasks are NOT resumed in abefore_agent (that's _on_interrupt_resume's job)."""
        state = _make_state(id="root", name=ROOT_HANDLER_NAME, status="paused")

        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = "common-session-start"
            proxy.get_params.return_value = None

            result = await self.mw.abefore_agent(state, self.runtime)

        # abefore_agent does NOT change status for paused tasks
        assert "status" not in result

    @pytest.mark.asyncio
    async def test_running_task_no_lifecycle_dispatch(self):
        """Running tasks are NOT paused in abefore_agent (that's _on_interrupt_resume's job)."""
        state = _make_state(id="root", name=ROOT_HANDLER_NAME, status="running")

        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = "biz-aitutor-quit-learning"
            proxy.get_params.return_value = None

            result = await self.mw.abefore_agent(state, self.runtime)

        # abefore_agent does NOT change status for running tasks
        assert "status" not in result

    @pytest.mark.asyncio
    async def test_no_jump_to_in_abefore_agent(self):
        """abefore_agent should not set jump_to (that's abefore_model's job)."""
        state = _make_state(id="t1", name=ROOT_HANDLER_NAME, status="pending")

        # Make abefore inject an AIMessage with tool_calls
        self.root.abefore = AsyncMock(return_value={
            "messages": [
                AIMessage(content="", tool_calls=[{
                    "id": "call_test",
                    "name": "_builtin_start_task",
                    "args": {"name": "project"},
                }]),
            ]
        })

        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = None
            proxy.get_params.return_value = None

            result = await self.mw.abefore_agent(state, self.runtime)

        assert "jump_to" not in result

    @pytest.mark.asyncio
    async def test_stores_runtime(self):
        """abefore_agent stores runtime for use by tool closures."""
        state = _make_state(id="root", name=ROOT_HANDLER_NAME, status="running")

        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = None
            proxy.get_params.return_value = None

            await self.mw.abefore_agent(state, self.runtime)

        assert self.mw._runtime is self.runtime

    @pytest.mark.asyncio
    async def test_running_task_stores_runtime(self):
        """abefore_agent stores runtime even for running tasks (no lifecycle dispatch)."""
        state = _make_state(
            messages=[HumanMessage(content="hello")],
            id="root", name=ROOT_HANDLER_NAME, status="running",
        )

        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = None
            proxy.get_params.return_value = None

            await self.mw.abefore_agent(state, self.runtime)

        # Runtime is always stored
        assert self.mw._runtime is self.runtime

    @pytest.mark.asyncio
    async def test_no_task_default_root_works(self):
        """TaskMiddleware always registers a default root."""
        mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        state = _make_state()

        with patch(
            "agentickit.prosonaagent.core.middleware.task_middleware.UserAgentProxy"
        ) as MockProxy:
            proxy = MockProxy.return_value
            proxy.get_action.return_value = "common-session-start"
            proxy.get_params.return_value = None

            result = await mw.abefore_agent(state, self.runtime)

        assert result["id"] == "__root__"


# ==================== Message Metadata Tests ====================


class TestMessageMetadata:
    def setup_method(self):
        self.mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )

    def test_add_message_metadata_preserves_existing(self):
        msg = HumanMessage(content="hi", additional_kwargs={"existing": True})
        state = _make_state(id="task1", name="guide", mode="start")
        result = self.mw._add_message_metadata([msg], state)
        assert len(result) == 1
        assert result[0].additional_kwargs["existing"] is True
        assert result[0].additional_kwargs["__task_id__"] == "task1"
        assert result[0].additional_kwargs["__task_name__"] == "guide"

    def test_add_message_metadata(self):
        msgs = [SystemMessage(content="ctx")]
        state = _make_state(id="t1", name="guide")
        result = self.mw._add_message_metadata(msgs, state)
        assert len(result) == 1
        assert result[0].additional_kwargs["__task_id__"] == "t1"


# ==================== abefore_model Tests ====================


class TestBeforeModel:
    def setup_method(self):
        self.mw = TaskMiddleware(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        self.runtime = _make_runtime()

    @pytest.mark.asyncio
    async def test_jump_to_tools_when_tool_calls_present(self):
        """When messages contain AIMessage with tool_calls, jump_to='tools' is set."""
        state = _make_state(
            id="t1",
            name=ROOT_HANDLER_NAME,
            status="running",
            messages=[
                AIMessage(content="", tool_calls=[{
                    "id": "call_test",
                    "name": "_builtin_start_task",
                    "args": {"name": "project"},
                }]),
            ],
        )
        result = await self.mw.abefore_model(state, self.runtime)
        assert result == {"jump_to": "tools"}

    @pytest.mark.asyncio
    async def test_no_jump_to_without_tool_calls(self):
        """When no AIMessage with tool_calls, returns None."""
        state = _make_state(
            id="t1",
            name=ROOT_HANDLER_NAME,
            status="running",
            messages=[SystemMessage(content="context")],
        )
        result = await self.mw.abefore_model(state, self.runtime)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_messages_raises(self):
        """When messages are empty, tools_condition raises ValueError."""
        state = _make_state(
            id="t1",
            name=ROOT_HANDLER_NAME,
            status="running",
        )
        with pytest.raises(ValueError, match="No messages found"):
            await self.mw.abefore_model(state, self.runtime)

    @pytest.mark.asyncio
    async def test_jump_to_end_when_task_completed(self):
        """When status is completed, jump_to='end' to exit the graph."""
        state = _make_state(
            id="t1",
            name=ROOT_HANDLER_NAME,
            status="completed",
            messages=[SystemMessage(content="context")],
        )
        result = await self.mw.abefore_model(state, self.runtime)
        assert result == {"jump_to": "end"}

    @pytest.mark.asyncio
    async def test_jump_to_end_when_task_interrupted(self):
        """When status is interrupted, jump_to='end' to exit the graph."""
        state = _make_state(
            id="t1",
            name=ROOT_HANDLER_NAME,
            status="interrupted",
            messages=[SystemMessage(content="context")],
        )
        result = await self.mw.abefore_model(state, self.runtime)
        assert result == {"jump_to": "end"}

    def test_has_hook_config(self):
        """abefore_model should have __can_jump_to__ = ['tools', 'end'] from @hook_config."""
        assert hasattr(self.mw.abefore_model, "__can_jump_to__")
        assert self.mw.abefore_model.__can_jump_to__ == ["tools", "end"]
