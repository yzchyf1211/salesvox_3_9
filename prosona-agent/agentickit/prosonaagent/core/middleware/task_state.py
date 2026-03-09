"""
TaskState — shared state definition for task-level middleware and handlers.

Lives in a separate module to avoid circular imports between
task_middleware (imports TaskHandler) and task_handler (imports TaskState).
"""

from typing import Any, Dict, List, Literal, Optional

from ..state import ProsonaAgentState


class TaskState(ProsonaAgentState, total=False):
    """Task state with lifecycle fields."""

    # Current task identification
    id: Optional[str]
    name: Optional[str]

    # Current task status: pending | running | paused | completed | interrupted | recovering
    status: Optional[str]

    # Current task params (from start_task args)
    params: Optional[dict]

    # Task relationships
    sub_tasks: List[str]  # Sub task ID list

    # Task result: carries summary, reason, next_intent, etc.
    result: Optional[Dict[str, Any]]

    # Task mode: "start" or "recover"
    mode: Optional[str]


# Task status literals
TaskStatus = Literal[
    "pending", "running", "paused", "completed", "interrupted", "recovering"
]

# A2A actionName values used in abefore_agent to handle pause/resume edge cases.
ACTION_SESSION_START = "common-session-start"   # re-connect on a paused session → resume
ACTION_QUIT_LEARNING = "biz-aitutor-quit-learning"  # user quits while running → interrupt
