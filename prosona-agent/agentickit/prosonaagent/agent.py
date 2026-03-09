"""Backward-compat re-export. Canonical location: core.factory"""
from agentickit.prosonaagent.core.factory import (  # noqa: F401
    create_handler_registry,
    create_middleware_registry,
    create_prosona_agent,
)

__all__ = [
    "create_handler_registry",
    "create_middleware_registry",
    "create_prosona_agent",
]
