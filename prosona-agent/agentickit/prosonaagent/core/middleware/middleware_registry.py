"""
Middleware Registry for the SubAgent architecture.

Maps task_name to TaskMiddleware class so sub-graphs can be created by lookup
instead of each middleware defining its child type.
"""

from typing import Dict, Optional, Type, TYPE_CHECKING

# Default task_group_name for root graph; used in create_prosona_agent and create_middleware_registry.
ROOT_MIDDLEWARE_GROUP_NAME = "__root__"

if TYPE_CHECKING:
    from .task_middleware import TaskMiddleware


class MiddlewareRegistry:
    """
    Registry mapping task name to middleware class.

    Used when creating child middleware for sub-graphs: look up by task_name
    (e.g. "project", "activity", "sco") to get the middleware class to instantiate.
    """

    def __init__(self) -> None:
        self._middlewares: Dict[str, Type["TaskMiddleware"]] = {}

    def register(self, task_name: str, middleware_class: Type["TaskMiddleware"]) -> None:
        """
        Register a middleware class for a task name.

        Args:
            task_name: Task type name (e.g. "project", "activity", "sco").
            middleware_class: TaskMiddleware subclass to use for that task.
        """
        self._middlewares[task_name] = middleware_class

    def get(self, task_name: str) -> Optional[Type["TaskMiddleware"]]:
        """
        Get middleware class by task name.

        Args:
            task_name: Task type name.

        Returns:
            Registered middleware class, or None if not found.
        """
        return self._middlewares.get(task_name)

    def has(self, task_name: str) -> bool:
        """Return True if a middleware is registered for the given task name."""
        return task_name in self._middlewares
