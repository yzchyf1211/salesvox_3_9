"""
TaskHandler - Interface for task-level handlers (business logic).

Current task lifecycle hooks:
- abefore: task starts
- apause: task pauses
- aresume: task resumes
- ainterrupt: task is interrupted
- arecover: task recovers from error
- aafter: task ends normally

Sub task lifecycle hooks (called when sub tasks run within this task):
- abefore_task, arecover_task, ainterrupt_task, aafter_task

Wrappers:
- awrap_model_call: wrap model calls
- awrap_tool_call: wrap tool calls
"""

from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    TYPE_CHECKING,
)

from langchain.agents.middleware.types import (
    ModelRequest,
    ModelResponse,
    ModelCallResult,
    ToolCallRequest,
)
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from agentickit.prosonaagent.core.middleware.task_state import TaskState

if TYPE_CHECKING:
    from langgraph.runtime import Runtime


StateT = TypeVar("StateT", bound=TaskState)


class TaskHandler(Generic[StateT]):
    """
    Interface for task-level handlers (business logic).

    Two levels of lifecycle hooks:

    1. Current task scope (this task's own lifecycle):
       - abefore: this task starts
       - apause: this task pauses
       - aresume: this task resumes
       - ainterrupt: this task is interrupted
       - arecover: this task recovers from error
       - aafter: this task ends

    2. Sub task scope (when sub tasks start/end within this task):
       - abefore_task: a sub task starts
       - arecover_task: a sub task recovers
       - ainterrupt_task: a sub task is interrupted
       - aafter_task: a sub task ends

    Wrappers:
    - awrap_model_call: wrap model calls
    - awrap_tool_call: wrap tool calls
    """

    # Handler name used as registry key. Convention:
    # - Default group handler: name = group_name (e.g. "sco")
    # - Custom task handler:   name = group_name:task_name (e.g. "sco:lecture_summary")
    name: Optional[str] = None

    state_schema: type[StateT] = TaskState  # type: ignore[assignment]
    skills: List[str] = []
    tools: List[Any] = []
    model_group: Optional[str] = None

    # ==================== Current Task Scope (this task's lifecycle) ====================

    async def abefore(
        self,
        state: StateT,
        runtime: "Runtime",
    ) -> Dict[str, Any] | None:
        """Called when this task starts.

        Available from state:
        - state["id"] — task_id
        - state["name"] — task_name
        - state.get("params") — startup parameters
        """
        pass

    async def apause(
        self,
        state: StateT,
        runtime: "Runtime",
    ) -> Dict[str, Any] | None:
        """Called when this task pauses."""
        pass

    async def aresume(
        self,
        state: StateT,
        runtime: "Runtime",
    ) -> Dict[str, Any] | None:
        """Called when this task resumes."""
        pass

    async def ainterrupt(
        self,
        state: StateT,
        runtime: "Runtime",
    ) -> Dict[str, Any] | None:
        """Called when this task is interrupted.

        Available from state:
        - state.get("result") — interrupt result data
        - state.get("status") — "interrupted"
        """
        pass

    async def arecover(
        self,
        state: StateT,
        runtime: "Runtime",
    ) -> Dict[str, Any] | None:
        """Called when this task recovers from error.

        Available from state:
        - state.get("params") — startup parameters
        """
        pass

    async def aafter(
        self,
        state: StateT,
        runtime: "Runtime",
    ) -> Dict[str, Any] | None:
        """Called when this task completes normally.

        Available from state:
        - state.get("result") — completion result data
        - state.get("status") — "completed" or "interrupted"
        """
        pass

    # ==================== Sub Task Scope (sub tasks within this task) ====================

    async def abefore_task(
        self,
        state: StateT,
        runtime: "Runtime",
        sub_task_id: str,
        sub_task_name: str,
    ) -> Dict[str, Any] | None:
        """Called when a sub task starts within this task."""
        pass

    async def arecover_task(
        self,
        state: StateT,
        runtime: "Runtime",
        sub_task_id: str,
        sub_task_name: str,
    ) -> Dict[str, Any] | None:
        """Called when a sub task recovers from error."""
        pass

    async def ainterrupt_task(
        self,
        state: StateT,
        runtime: "Runtime",
        sub_state: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        """Called when a sub task is interrupted within this task.

        Available from sub_state:
        - sub_state["id"] — sub_task_id
        - sub_state["name"] — sub_task_name
        - sub_state.get("result") — sub task result
        - sub_state.get("status") — "interrupted"
        """
        pass

    async def aafter_task(
        self,
        state: StateT,
        runtime: "Runtime",
        sub_state: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        """Called when a sub task ends within this task.

        Available from sub_state:
        - sub_state["id"] — sub_task_id
        - sub_state["name"] — sub_task_name
        - sub_state.get("result") — sub task result
        - sub_state.get("status") — "completed" or "interrupted"
        - sub_state.get("params") — sub task startup parameters
        """
        pass

    # User input
    async def aafter_user_input(
        self,
        state: StateT,
        runtime: "Runtime",
        user_input: str,
        action: Optional[str],
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        """Called after user input at task level."""
        pass

    # Wrappers
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Wrap model calls for custom processing."""
        return await handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Wrap tool calls for custom processing."""
        return await handler(request)
