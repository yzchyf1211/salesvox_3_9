"""
Core SubAgent Architecture Module.

This module provides the core framework components:

TaskMiddleware - Middleware for task lifecycle management
  - Task Stack: tracks current execution hierarchy
  - SubGraph Cache: stores LangGraph SubGraphs
  - Lifecycle hooks: abefore, apause, aresume, ainterrupt, arecover, aafter
  - Builtin task tools (closures): _builtin_start_task, _builtin_end_task, _builtin_recover_task
  - Optional root handler: acts as session-level root task

TaskHandler - Interface for task-level handlers
HandlerRegistry - Registry for TaskHandler lookup
"""

from .state import ProsonaAgentState
from .middleware.task_state import TaskState
from .handler.task_handler import TaskHandler
from .handler.handler_registry import HandlerRegistry
from .middleware.middleware_registry import MiddlewareRegistry
from .middleware.task_middleware import TaskMiddleware
from .factory import (
    create_handler_registry,
    create_middleware_registry,
    create_prosona_agent,
)

__all__ = [
    # Base classes
    "ProsonaAgentState",
    "TaskState",
    "TaskHandler",
    # Registries
    "HandlerRegistry",
    "MiddlewareRegistry",
    # Middleware
    "TaskMiddleware",
    # Factory
    "create_handler_registry",
    "create_middleware_registry",
    "create_prosona_agent",
]
