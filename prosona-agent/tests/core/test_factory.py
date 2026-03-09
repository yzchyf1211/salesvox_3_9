"""Tests for factory functions (create_handler_registry, create_middleware_registry)."""

import pytest

from agentickit.prosonaagent.core.factory import (
    create_handler_registry,
    create_middleware_registry,
)
from agentickit.prosonaagent.core.handler.handler_registry import (
    HandlerRegistry,
    ROOT_HANDLER_NAME,
    GENERAL_HANDLER_NAME,
)
from agentickit.prosonaagent.core.middleware.middleware_registry import (
    MiddlewareRegistry,
    ROOT_MIDDLEWARE_GROUP_NAME,
)
from agentickit.prosonaagent.core.handler.task_handler import TaskHandler
from agentickit.prosonaagent.core.middleware.task_middleware import TaskMiddleware


class _DummyMiddleware(TaskMiddleware):
    task_group_name = "project"


class _ActivityMiddleware(TaskMiddleware):
    task_group_name = "activity"


class TestCreateHandlerRegistry:
    def test_default_registry_has_root_and_general(self):
        reg = create_handler_registry()
        assert isinstance(reg, HandlerRegistry)
        assert reg.has(ROOT_HANDLER_NAME)
        assert reg.has(GENERAL_HANDLER_NAME)

    def test_custom_root_handler(self):
        root = TaskHandler()
        root.name = ROOT_HANDLER_NAME
        reg = create_handler_registry(root_handler=root)
        assert reg.get(ROOT_HANDLER_NAME) is root

    def test_task_handlers_registered_by_name(self):
        h = TaskHandler()
        h.name = "drill-guide"
        reg = create_handler_registry(task_handlers=[h])
        assert reg.get("drill-guide") is h

    def test_task_handler_without_name_raises(self):
        h = TaskHandler()  # name is None by default
        with pytest.raises(ValueError, match="non-empty 'name'"):
            create_handler_registry(task_handlers=[h])


class TestCreateMiddlewareRegistry:
    def test_root_middleware_registered(self):
        reg = create_middleware_registry(root_middleware=_DummyMiddleware)
        assert isinstance(reg, MiddlewareRegistry)
        assert reg.get(ROOT_MIDDLEWARE_GROUP_NAME) is _DummyMiddleware

    def test_task_middlewares_registered_by_group_name(self):
        reg = create_middleware_registry(
            root_middleware=_DummyMiddleware,
            task_middlewares=[_ActivityMiddleware],
        )
        assert reg.get("activity") is _ActivityMiddleware

    def test_task_middleware_without_group_name_raises(self):
        class BadMiddleware(TaskMiddleware):
            task_group_name = ""

        with pytest.raises(ValueError, match="non-empty 'task_group_name'"):
            create_middleware_registry(
                root_middleware=_DummyMiddleware,
                task_middlewares=[BadMiddleware],
            )
