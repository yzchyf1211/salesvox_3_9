"""Tests for TaskMiddleware._create_state_schema and _create_tools."""

from unittest.mock import MagicMock

from agentickit.prosonaagent.core.middleware.task_middleware import TaskState
from agentickit.prosonaagent.core.handler.task_handler import TaskHandler
from agentickit.prosonaagent.core.middleware.task_middleware import TaskMiddleware
from agentickit.prosonaagent.core.handler.handler_registry import HandlerRegistry, ROOT_HANDLER_NAME
from agentickit.prosonaagent.core.middleware.middleware_registry import MiddlewareRegistry


def _make_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _mw() -> TaskMiddleware:
    return TaskMiddleware(
        task_name=ROOT_HANDLER_NAME,
        system_prompt="",
        middleware_registry=MiddlewareRegistry(),
        handler_registry=HandlerRegistry(),
    )


class TestCreateStateSchema:
    def test_no_custom_schema_returns_base(self):
        handler = TaskHandler()
        result = _mw()._create_state_schema(handler, "test")
        assert result is TaskState

    def test_custom_schema_merged(self):
        class CustomState(TaskState, total=False):
            custom_field: str

        handler = TaskHandler()
        handler.state_schema = CustomState

        result = _mw()._create_state_schema(handler, "guide")
        assert result is not TaskState
        assert result.__name__ == "GuideState"
        assert issubclass(result, dict)

    def test_custom_base(self):
        class ParentState(TaskState, total=False):
            parent_field: str

        class ChildState(TaskState, total=False):
            child_field: str

        handler = TaskHandler()
        handler.state_schema = ChildState

        result = _mw()._create_state_schema(handler, "child", base=ParentState)
        assert result is not ParentState
        assert issubclass(result, dict)

    def test_same_schema_as_base_returns_base(self):
        handler = TaskHandler()
        handler.state_schema = TaskState

        result = _mw()._create_state_schema(handler, "test")
        assert result is TaskState

    def test_name_with_hyphen(self):
        class MyState(TaskState, total=False):
            x: int

        handler = TaskHandler()
        handler.state_schema = MyState

        result = _mw()._create_state_schema(handler, "my-task")
        assert result.__name__ == "My_TaskState"


class TestCreateTools:
    def test_default_builtin_tools_included(self):
        """_create_tools always includes 2 default builtins + 3 task tools."""
        handler = TaskHandler()
        handler.tools = []

        result = _mw()._create_tools(handler)
        # 2 default builtin (get_skill_information, get_skill_resource) + 3 task tools
        assert len(result) == 5
        names = [getattr(t, "name", None) for t in result]
        assert "_builtin_get_skill_information" in names
        assert "_builtin_get_skill_resource" in names

    def test_handler_tools_appended(self):
        handler = TaskHandler()
        handler.tools = [_make_tool("biz_tool")]

        result = _mw()._create_tools(handler)
        # 2 default builtin + 1 handler tool + 3 task tools = 6
        assert len(result) == 6
        names = [getattr(t, "name", None) for t in result]
        assert "biz_tool" in names

    def test_deduplication(self):
        """Handler tool with same name as default builtin is skipped."""
        handler = TaskHandler()
        handler.tools = [_make_tool("_builtin_get_skill_information")]

        result = _mw()._create_tools(handler)
        # 2 default builtin + 0 deduped handler + 3 task tools = 5
        assert len(result) == 5

    def test_start_task_filtered_when_no_sub_tasks(self):
        """Middleware with allow_sub_tasks=False adds only _builtin_end_task."""
        class NoSubTaskMW(TaskMiddleware):
            allow_sub_tasks = False

        handler = TaskHandler()
        handler.tools = []

        mw = NoSubTaskMW(
            task_name=ROOT_HANDLER_NAME,
            system_prompt="",
            middleware_registry=MiddlewareRegistry(),
            handler_registry=HandlerRegistry(),
        )
        result = mw._create_tools(handler)
        # 2 default builtin + 1 task tool (end only) = 3
        assert len(result) == 3
        assert any(getattr(t, "name", None) == "_builtin_end_task" for t in result)

    def test_start_task_kept_when_sub_tasks_allowed(self):
        """Default middleware (allow_sub_tasks=True) adds all 3 task tools."""
        handler = TaskHandler()
        handler.tools = []

        result = _mw()._create_tools(handler)
        # 2 default builtin + 3 task tools = 5
        assert len(result) == 5
        names = [getattr(t, "name", None) for t in result]
        assert "_builtin_start_task" in names
        assert "_builtin_end_task" in names
        assert "_builtin_recover_task" in names
