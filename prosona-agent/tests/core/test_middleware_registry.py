"""Tests for MiddlewareRegistry."""

from agentickit.prosonaagent.core.middleware.middleware_registry import MiddlewareRegistry
from agentickit.prosonaagent.core.middleware.task_middleware import TaskMiddleware


class _DummyMiddleware(TaskMiddleware):
    task_group_name = "dummy"


class _OtherMiddleware(TaskMiddleware):
    task_group_name = "other"


class TestMiddlewareRegistry:
    def test_register_and_get(self):
        reg = MiddlewareRegistry()
        reg.register("project", _DummyMiddleware)
        assert reg.get("project") is _DummyMiddleware

    def test_get_not_found_returns_none(self):
        reg = MiddlewareRegistry()
        assert reg.get("nonexistent") is None

    def test_has(self):
        reg = MiddlewareRegistry()
        reg.register("project", _DummyMiddleware)
        assert reg.has("project") is True
        assert reg.has("other") is False

    def test_overwrite_existing(self):
        reg = MiddlewareRegistry()
        reg.register("project", _DummyMiddleware)
        reg.register("project", _OtherMiddleware)
        assert reg.get("project") is _OtherMiddleware

    def test_multiple_registrations(self):
        reg = MiddlewareRegistry()
        reg.register("project", _DummyMiddleware)
        reg.register("activity", _OtherMiddleware)
        assert reg.get("project") is _DummyMiddleware
        assert reg.get("activity") is _OtherMiddleware
