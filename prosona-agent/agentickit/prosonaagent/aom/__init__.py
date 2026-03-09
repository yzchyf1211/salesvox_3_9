"""
AOM (Activity Object Model) Module.

This module provides AOM-specific components:
- Middleware: RootMiddleware, ProjectMiddleware, ActivityMiddleware, SCOMiddleware
- State: AOM state definitions
"""

# State definitions
from .state import (
    RootTaskState,
    RootTaskStateT,
    ProjectTaskState,
    ProjectTaskStateT,
    ActivityTaskState,
    ActivityTaskStateT,
    SCOTaskState,
    SCOTaskStateT,
)

# Middleware
from .middlewares import RootMiddleware, ProjectMiddleware, ActivityMiddleware, SCOMiddleware

__all__ = [
    # Middleware
    "RootMiddleware",
    "ProjectMiddleware",
    "ActivityMiddleware",
    "SCOMiddleware",
    # State classes
    "RootTaskState",
    "RootTaskStateT",
    "ProjectTaskState",
    "ProjectTaskStateT",
    "ActivityTaskState",
    "ActivityTaskStateT",
    "SCOTaskState",
    "SCOTaskStateT",
]
