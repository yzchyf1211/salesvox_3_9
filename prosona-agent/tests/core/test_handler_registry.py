"""Tests for HandlerRegistry."""

import pytest

from agentickit.prosonaagent.core.handler.handler_registry import HandlerRegistry
from agentickit.prosonaagent.core.handler.task_handler import TaskHandler


def _make_handler(name: str) -> TaskHandler:
    h = TaskHandler()
    h.name = name
    return h


class TestHandlerRegistry:
    def test_register_and_get(self):
        reg = HandlerRegistry()
        handler = _make_handler("guide")
        reg.register("guide", handler)
        assert reg.get("guide") is handler

    def test_get_not_found(self):
        reg = HandlerRegistry()
        assert reg.get("nonexistent") is None

    def test_has(self):
        reg = HandlerRegistry()
        reg.register("guide", _make_handler("guide"))
        assert reg.has("guide") is True
        assert reg.has("other") is False

    def test_contains(self):
        reg = HandlerRegistry()
        reg.register("guide", _make_handler("guide"))
        assert "guide" in reg
        assert "other" not in reg

    def test_unregister(self):
        reg = HandlerRegistry()
        handler = _make_handler("guide")
        reg.register("guide", handler)
        removed = reg.unregister("guide")
        assert removed is handler
        assert reg.get("guide") is None

    def test_unregister_not_found(self):
        reg = HandlerRegistry()
        assert reg.unregister("nope") is None

    def test_get_all_names(self):
        reg = HandlerRegistry()
        reg.register("a", _make_handler("a"))
        reg.register("b", _make_handler("b"))
        names = sorted(reg.get_all_names())
        # Default __root__ and general + a, b
        assert names == ["__root__", "a", "b", "general"]

    def test_get_all_handlers(self):
        reg = HandlerRegistry()
        h1 = _make_handler("a")
        h2 = _make_handler("b")
        reg.register("a", h1)
        reg.register("b", h2)
        all_handlers = reg.get_all_handlers()
        assert all_handlers["a"] is h1
        assert all_handlers["b"] is h2
        assert "__root__" in all_handlers
        assert "general" in all_handlers
        # Should be a copy
        all_handlers["c"] = _make_handler("c")
        assert "c" not in reg

    def test_len(self):
        reg = HandlerRegistry()
        # Default __root__ and general handlers
        assert len(reg) == 2
        reg.register("a", _make_handler("a"))
        assert len(reg) == 3

    def test_clear(self):
        reg = HandlerRegistry()
        reg.register("a", _make_handler("a"))
        reg.register("b", _make_handler("b"))
        reg.clear()
        assert len(reg) == 0
        assert reg.get("a") is None

    def test_register_overwrites(self):
        reg = HandlerRegistry()
        h1 = _make_handler("guide")
        h2 = _make_handler("guide")
        reg.register("guide", h1)
        reg.register("guide", h2)
        assert reg.get("guide") is h2
        # __root__ + general + guide = 3
        assert len(reg) == 3
