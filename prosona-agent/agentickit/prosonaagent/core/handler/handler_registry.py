"""
Handler Registry for the SubAgent architecture.

This module provides the HandlerRegistry class that manages TaskHandler
registration and lookup. Registry is initialized with default root and
general (fallback) handlers.
"""

from typing import Dict, Optional

from .task_handler import TaskHandler

# Default handler names (used by TaskMiddleware and create_handler_registry)
ROOT_HANDLER_NAME = "__root__"
GENERAL_HANDLER_NAME = "general"


class HandlerRegistry:
    """
    Registry for TaskHandlers.

    Provides:
    - Registration of named handlers
    - Lookup by name
    - Default __root__ and general handlers on init
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, TaskHandler] = {}
        self.register(ROOT_HANDLER_NAME, TaskHandler())
        self.register(GENERAL_HANDLER_NAME, TaskHandler())

    def register(self, name: str, handler: TaskHandler) -> None:
        """
        Register a handler for a specific task name.

        Args:
            name: Handler registry key. Use group_name for the default group handler
                  (e.g. "sco"), or group_name:task_name for a custom handler (e.g. "sco:lecture_summary").
            handler: TaskHandler implementation
        """
        self._handlers[name] = handler

    def unregister(self, name: str) -> Optional[TaskHandler]:
        """
        Unregister a handler by name.

        Args:
            name: Task type name to unregister

        Returns:
            The removed handler, or None if not found
        """
        return self._handlers.pop(name, None)

    def get(self, name: str) -> Optional[TaskHandler]:
        """
        Get a handler by task name.

        Args:
            name: Task type name

        Returns:
            TaskHandler for the given name, or None if not found
        """
        return self._handlers.get(name)

    def has(self, name: str) -> bool:
        """
        Check if a handler is registered for the given name.

        Args:
            name: Task type name

        Returns:
            True if a handler exists
        """
        return name in self._handlers

    def get_all_names(self) -> list[str]:
        """
        Get all registered handler names.

        Returns:
            List of registered task type names
        """
        return list(self._handlers.keys())

    def get_all_handlers(self) -> Dict[str, TaskHandler]:
        """
        Get all registered handlers.

        Returns:
            Dictionary mapping task names to handlers
        """
        return dict(self._handlers)

    def clear(self) -> None:
        """Clear all registered handlers."""
        self._handlers.clear()

    def __len__(self) -> int:
        return len(self._handlers)

    def __contains__(self, name: str) -> bool:
        return self.has(name)
