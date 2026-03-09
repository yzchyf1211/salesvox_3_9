"""
Task Middleware for the SubAgent architecture.

TaskMiddleware manages task lifecycle with:
- Flat state fields (id, name, status, params): current task identity
- SubGraph Cache: stores LangGraph SubGraphs keyed by task_name:task_id
- Handler Registry: manages TaskHandler instances; default handlers keyed by group_name, custom handlers by group_name:task_name
- Builtin task tools (closures): _builtin_start_task, _builtin_end_task, _builtin_recover_task

Key responsibilities:
- Create builtin task tools as closures with access to middleware methods
- Manage task lifecycle: abefore, apause, aresume, ainterrupt, arecover, aafter
- Build and cache SubGraphs for task execution
- Use @hook_config(can_jump_to=["tools"]) on abefore_model for jump_to mechanism
- Blocking subgraph execution in start_task/recover_task tools
"""

from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TYPE_CHECKING,
)
from langchain_core.messages import (
    AnyMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
    HumanMessage,
)
from langchain_core.runnables.config import ensure_config
from langchain_core.tools import tool
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ModelCallResult,
    ToolCallRequest,
    hook_config,
)
from langgraph.prebuilt import ToolRuntime, tools_condition
from langgraph.types import Command, interrupt

from .task_state import TaskState, ACTION_SESSION_START, ACTION_QUIT_LEARNING
from ..handler.task_handler import TaskHandler
from ..handler.handler_registry import (
    HandlerRegistry,
    ROOT_HANDLER_NAME,
    GENERAL_HANDLER_NAME,
)
from .middleware_registry import MiddlewareRegistry
from ..factory import create_prosona_agent
from ..tools import (
    _builtin_get_skill_information,
    _builtin_get_skill_resource,
)
from agentickit.prosonaagent.utils.agent_proxy import UserAgentProxy
from agentickit.prosonaagent.utils.message import build_compressible_kwargs
from agentickit.prosonaagent.utils.time import get_timestamp
from agentickit.core.infra.skills.manager import get_skills_by_names
from agentickit.prosonaagent.utils.context import (
    build_language_context,
    build_skill_information_context_list,
    build_tool_call_success_system_feedback,
)
from agentickit.prosonaagent.utils.prompt import get_task_prompt

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.runtime import Runtime


class TaskMiddleware(AgentMiddleware):
    """
    Task Middleware - manages task execution with flat state fields.

    State fields:
    - id, name: current task identification
    - status: current task status (pending/running/paused/completed/interrupted/recovering)
    - params: parameters passed when task was started

    Builtin Tools (closures):
    - _builtin_start_task: creates subgraph, invokes it blocking, returns result
    - _builtin_end_task: calls lifecycle hooks, sets status to completed/interrupted
    - _builtin_recover_task: recovers interrupted task via blocking subgraph invocation

    SubGraph Cache:
    - Stores compiled LangGraph SubGraphs for each task
    - Key format: "{task_name}:{task_id}"
    - SubGraphs are created lazily when tasks start

    Task group vs task name:
    - task_group_name: identifies this middleware's group (one middleware per group); used for middleware_registry lookup.
    - task name (e.g. state["name"]): within a group, can be more specific; used for handler lookup. Defaults to task_group_name.

    Handler Registry:
    - Default handler keyed by group_name (e.g. "sco")
    - Custom handler keyed by group_name:task_name (e.g. "sco:lecture_summary")
    - Lookup order: {group_name}:{task_name} → {group_name} → "general"

    Lifecycle hooks:
    - Current task: abefore, apause, aresume, ainterrupt, arecover, aafter
    - Sub tasks: abefore_task, arecover_task, ainterrupt_task, aafter_task
    """

    # Task group name: identifies this middleware's group (one middleware per group).
    # Used to register in middleware_registry and as fallback for handler/task prompt lookup.
    # Subclasses override: e.g. "project", "activity", "sco".
    task_group_name: str = GENERAL_HANDLER_NAME

    # Default sub task group for start_task: when name is empty, use this to look up
    # child middleware in registry (must match child's task_group_name). E.g. Root -> "project".
    sub_task_group_name: Optional[str] = None

    # Default state schema for this middleware level.
    # Subclasses override: e.g. RootTaskState, ProjectTaskState, etc.
    state_schema: type = TaskState

    # Whether this middleware level can create sub-tasks (exposes start_task, recover_task).
    # Subclasses override: e.g. RootMiddleware may set False.
    allow_sub_tasks: bool = True

    # Default skill names for context injection (e.g. get_skills_by_names in abefore).
    # Merged with handler.skills in __init__. Override in subclass if needed.
    skills: List[str] = ["manage_task"]

    # Default tools for this middleware level.
    # Merged with handler.tools in _create_tools. Override in subclass if needed.
    tools: List[Any] = []

    def __init__(
        self,
        task_name: str,
        system_prompt: str,
        middleware_registry: MiddlewareRegistry,
        handler_registry: HandlerRegistry,
        **agent_kwargs,
    ) -> None:
        """
        Initialize TaskMiddleware.

        Args:
            task_name: Used for handler lookup via get_handler(). Root: use ROOT_HANDLER_NAME;
                       child: use group_name (e.g. "sco") or group_name:task_name (e.g. "sco:lecture_summary").
            system_prompt: System prompt shared across all task levels (required).
            middleware_registry: Registry mapping task_name -> middleware class for creating child sub-graphs. Required.
            handler_registry: Shared handler registry for global handler lookup (required).
            **agent_kwargs: Extra keyword arguments forwarded to create_prosona_agent when creating sub-agents
                            (e.g. tts_configs). Automatically passed through to child agents.
        """
        self._name = task_name
        self._system_prompt: str = system_prompt
        self._registry = handler_registry
        self._agent_kwargs = agent_kwargs
        self._middleware_registry = middleware_registry
        self._handler: TaskHandler = self.get_handler(task_name)
        self._subgraph_cache: Dict[str, "CompiledStateGraph"] = {}
        self._sub_middleware_cache: Dict[str, "TaskMiddleware"] = {}

        self.skills = self._create_skills(self._handler)
        self.tools = self._create_tools(self._handler)
        self.state_schema = self._create_state_schema(
            self._handler, task_name, base=type(self).state_schema
        )

        self._runtime: Optional["Runtime"] = None

    # ==================== Schema & Tools Building ====================

    def _create_state_schema(
        self, handler: TaskHandler, task_name: str, base: type = TaskState
    ) -> type:
        """Create a merged state schema from handler's state_schema + base.

        If handler defines a custom state_schema beyond the base,
        creates a dynamic merged type. Otherwise returns base as-is.
        """
        bases = [base]

        if (
            hasattr(handler, "state_schema")
            and handler.state_schema
            and handler.state_schema not in bases
        ):
            bases.append(handler.state_schema)

        if len(bases) > 1:
            schema_name = f"{task_name.title().replace('-', '_')}State"
            return type(schema_name, tuple(bases), {})

        return base

    def _create_skills(self, handler: TaskHandler) -> List[str]:
        """Build the full skill list: class-level skills + handler.skills (deduplicated, order-preserving)."""
        base = list(type(self).skills)
        seen = set(base)
        for s in handler.skills or []:
            if s not in seen:
                base.append(s)
                seen.add(s)
        return base

    def _create_tools(self, handler: TaskHandler) -> List[Any]:
        """Build the full tool list: default_builtin_tools + middleware.tools + handler.tools + task lifecycle tools (always)."""
        default_builtin_tools = [
            _builtin_get_skill_information,
            _builtin_get_skill_resource,
        ]
        base = list(default_builtin_tools)
        seen = {t.name for t in base}
        for t in type(self).tools:
            if t.name not in seen:
                base.append(t)
                seen.add(t.name)
        for t in handler.tools:
            if t.name not in seen:
                base.append(t)
                seen.add(t.name)
        start = self._create_start_task_tool()
        end = self._create_end_task_tool()
        recover = self._create_recover_task_tool()
        allow_sub_tasks = getattr(type(self), "allow_sub_tasks", True)
        if allow_sub_tasks:
            base.extend([start, end, recover])
        else:
            base.append(end)
        return base

    # ==================== Builtin Task Tools (Closures) ====================

    def _create_start_task_tool(self) -> Any:
        """Create the _builtin_start_task tool (closure over this middleware)."""
        middleware = self

        @tool
        async def _builtin_start_task(
            name: str,  # noqa
            params: Optional[Dict[str, Any]] = None,
            tool_runtime: ToolRuntime = None,
        ) -> Command:
            """Start a new task.

            Args:
                name: Task type name (e.g. guide, activity).
                params: Optional parameters dict for the task.
            """
            state = tool_runtime.state
            sub_task_id = tool_runtime.tool_call_id
            # Resolve sub task name: use argument or current middleware's sub_task_group_name.
            sub_task_name = (name and name.strip()) or getattr(
                type(middleware), "sub_task_group_name", None
            )
            if not sub_task_name:
                raise ValueError(
                    "start_task requires a task name or middleware.sub_task_group_name"
                )

            def build_first_exec_state():
                sub_state = dict(state)
                sub_state.update(
                    {
                        "id": sub_task_id,
                        "name": sub_task_name,
                        "status": "pending",
                        "params": params or {},
                        "messages": [],
                        "sub_tasks": [],
                        "result": None,
                    }
                )
                return sub_state

            return await middleware._execute_subtask(
                state=state,
                tool_call_id=sub_task_id,
                sub_task_id=sub_task_id,
                sub_task_name=sub_task_name,
                first_exec_state=build_first_exec_state,
                first_exec_lifecycle=middleware.abefore_task,
            )

        return _builtin_start_task

    def _create_end_task_tool(self) -> Any:
        """Create the _builtin_end_task tool (closure over this middleware)."""
        middleware = self

        @tool
        async def _builtin_end_task(
            is_interrupt: bool,
            result: Optional[Dict[str, Any]] = None,
            tool_runtime: ToolRuntime = None,
        ) -> Command:
            """End current task.

            Args:
                is_interrupt: True to interrupt, False to complete normally.
                result: Optional task result data, all fields are optional.
                    Supported fields include summary (what was accomplished),
                    reason (why ending or interrupted), next_intent (user's next step).
                    Can be omitted entirely if there is nothing to report.
            """
            tool_call_id = tool_runtime.tool_call_id
            runtime = middleware._runtime
            state = tool_runtime.state

            task_id, task_name = middleware._get_current_task_info(state)
            if not task_id:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                content=build_tool_call_success_system_feedback(),
                                tool_call_id=tool_call_id,
                            )
                        ]
                    }
                )

            # Merge result into state before calling lifecycle
            merged_state = dict(state)
            merged_state["result"] = result or {}
            if is_interrupt:
                task_update = await middleware.ainterrupt(merged_state, runtime)
            else:
                task_update = await middleware.aafter(merged_state, runtime)

            update: Dict[str, Any] = middleware._merge_updates(
                task_update,
                {
                    "messages": [
                        ToolMessage(
                            content=build_tool_call_success_system_feedback(),
                            tool_call_id=tool_call_id,
                        )
                    ],
                },
            )
            return Command(update=update)

        return _builtin_end_task

    def _create_recover_task_tool(self) -> Any:
        """Create the _builtin_recover_task tool (closure over this middleware)."""
        middleware = self

        @tool
        async def _builtin_recover_task(
            task_id: str,
            task_name: str,
            tool_runtime: ToolRuntime = None,
        ) -> Command:
            """Recover an interrupted task. Original params are preserved via checkpoint.

            Args:
                task_id: ID of the task to recover.
                task_name: Task type name (e.g. guide, activity).
            """
            state = tool_runtime.state
            sub_task_id, sub_task_name = task_id, task_name

            # Continue the same graph — only update status.
            # All other fields (messages, params, sub_tasks, result)
            # are preserved from the checkpoint.
            return await middleware._execute_subtask(
                state=state,
                tool_call_id=tool_runtime.tool_call_id,
                sub_task_id=sub_task_id,
                sub_task_name=sub_task_name,
                first_exec_state=lambda: {"status": "recovering"},
                first_exec_lifecycle=middleware.arecover_task,
            )

        return _builtin_recover_task

    async def _execute_subtask(
        self,
        state: Dict[str, Any],
        tool_call_id: str,
        sub_task_id: str,
        sub_task_name: str,
        first_exec_state: "Callable[[], Dict[str, Any]]",
        first_exec_lifecycle: Any,
    ) -> Command:
        """Common execution logic for start_task and recover_task.

        Args:
            state: Parent task state.
            tool_call_id: Tool call ID for the ToolMessage response.
            sub_task_id: Sub task ID.
            sub_task_name: Sub task type name.
            first_exec_state: Callable that builds the initial state for first
                execution. Only called when the subgraph is NOT suspended
                (i.e., not during interrupt resume).
            first_exec_lifecycle: Lifecycle method to call on first execution
                (abefore_task or arecover_task).
        """
        runtime = self._runtime
        current_task_id, current_task_name = self._get_current_task_info(state)

        key = self._make_key(sub_task_name, sub_task_id)
        subgraph = self._get_or_create_subgraph(key, sub_task_name)
        thread_id = self._make_thread_id(state, sub_task_name, sub_task_id)

        # Returns the real checkpoint state if suspended, None otherwise.
        suspended_state = await self._get_suspended_state(subgraph, thread_id)

        current_update: Dict[str, Any] = {}

        if suspended_state is not None:
            # Resume path: use the real subgraph state from checkpoint.
            response = interrupt(None)
            command = await self._on_interrupt_resume(
                response, suspended_state, cache_key=key
            )
            result_state = await self._invoke_subgraph(subgraph, command, thread_id)
        else:
            current_update = await first_exec_lifecycle(
                state,
                runtime,
                sub_task_id,
                sub_task_name,
            )

            result_state = await self._invoke_subgraph(
                subgraph, first_exec_state(), thread_id
            )

        # Post-execution: lifecycle dispatch + build response
        result = result_state.get("result") or {}
        is_interrupt = result_state.get("status") == "interrupted"

        if current_task_id:
            if is_interrupt:
                lifecycle_update = await self.ainterrupt_task(
                    state,
                    runtime,
                    result_state,
                )
            else:
                lifecycle_update = await self.aafter_task(
                    state,
                    runtime,
                    result_state,
                )
            current_update = self._merge_updates(current_update, lifecycle_update)

        summary_text = self._build_task_summary(
            sub_task_name, sub_task_id, is_interrupt, result
        )
        update: Dict[str, Any] = {
            "messages": [
                ToolMessage(
                    content=build_tool_call_success_system_feedback(summary_text),
                    tool_call_id=tool_call_id,
                )
            ],
        }
        update = self._merge_updates(update, current_update)
        return Command(update=update)

    # ==================== Registry Access ====================

    def get_handler(self, name: str) -> TaskHandler:
        """Get a handler by task name (within this group). Never returns None; raises if not found.

        Lookup order:
          1. "{group_name}:{task_name}"  — custom handler for this specific task
          2. "{group_name}"              — default handler for this group
          3. "general"                   — global fallback
        """
        qualified = f"{self.task_group_name}:{name}" if name != self.task_group_name else None
        for candidate in filter(None, (qualified, self.task_group_name, GENERAL_HANDLER_NAME)):
            handler = self._registry.get(candidate)
            if handler:
                return handler
        raise ValueError(f"No handler found for task name: {name!r}")

    # ==================== State-based Task Info ====================

    def _get_current_task_name(self, state: TaskState) -> Optional[str]:
        """Get current task name from state."""
        return state.get("name")

    def _get_current_task_info(
        self, state: TaskState
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get (task_id, task_name) from state."""
        return state.get("id"), state.get("name")

    # ==================== SubGraph Methods ====================

    def _make_key(self, *parts: str) -> str:
        """Generate cache key by joining parts with ':'."""
        return ":".join(parts)

    @staticmethod
    def _make_thread_id(state: TaskState, task_name: str, task_id: str) -> str:
        """Generate a deterministic thread_id for a child subgraph."""
        context_id = state.get("context_id")
        return f"{context_id}:{task_name}:{task_id}"

    def _get_or_create_subgraph(
        self,
        key: str,
        task_name: str,
    ) -> "CompiledStateGraph":
        """Get or create a SubGraph for the given task.

        Key format: task_name:task_id — start_task and recover_task share
        the same graph instance so recovery can continue the conversation.
        """
        if key not in self._subgraph_cache:
            handler = self.get_handler(task_name)
            subgraph, sub_middleware = create_prosona_agent(
                system_prompt=self._system_prompt,
                middleware_registry=self._middleware_registry,
                handler_registry=self._registry,
                model_group=handler.model_group or "main",
                task_name=task_name,
                task_group_name=self.sub_task_group_name,
                **self._agent_kwargs,
            )
            self._sub_middleware_cache[key] = sub_middleware
            self._subgraph_cache[key] = subgraph
        return self._subgraph_cache[key]

    async def _get_suspended_state(
        self,
        subgraph: "CompiledStateGraph",
        thread_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the subgraph state if it is suspended at an interrupt.

        Returns the checkpoint state values if the graph is suspended
        (state.next non-empty), or None otherwise.

        This correctly distinguishes:
        - Suspended (paused at interrupt) → returns state values
        - Completed/interrupted (reached END) → None
        - No checkpoint → None
        """
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = await subgraph.aget_state(config)
            if state is not None and state.values and state.next:
                return dict(state.values)
            return None
        except Exception:
            return None

    async def _invoke_subgraph(
        self,
        subgraph: "CompiledStateGraph",
        input_data: Any,
        thread_id: str,
    ) -> Dict[str, Any]:
        """Invoke subgraph and return final state.

        Subgraph is a standalone compiled graph with its own checkpointer,
        only thread_id is needed. Parent callbacks are forwarded for event
        propagation (streaming).
        """
        parent_config = ensure_config()
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": parent_config.get("callbacks"),
        }
        return await subgraph.ainvoke(input_data, config)

    async def _on_interrupt_resume(
        self,
        response: Any,
        sub_state: Dict[str, Any],
        cache_key: str,
    ) -> Command:
        """Handle all logic when resuming from an interrupt.

        Two mutually exclusive branches:
        1. Has human message → user text input → aafter_user_input, merge state
        2. No message → action-based (pause/resume etc.), merge state

        Returns Command(update=..., resume=response) so state updates are applied
        when the subgraph resumes. Caller should pass this Command to _invoke_subgraph.
        """
        if not isinstance(response, dict):
            return Command(resume=response)

        sub_middleware = self._sub_middleware_cache[cache_key]

        sub_middleware._runtime = self._runtime
        user = UserAgentProxy(response)
        action = user.get_action()
        params = user.get_params()
        current_status = sub_state.get("status")

        update: Dict[str, Any] = {}

        # Convention: if messages are present, the first one is always a HumanMessage.
        resp_messages = response.get("messages", [])
        message = None
        if resp_messages:
            first = resp_messages[0]
            if isinstance(first, dict):
                message = HumanMessage(
                    content=first.get("content", ""),
                    id=first.get("id"),
                    additional_kwargs=first.get("additional_kwargs") or {},
                )
                resp_messages[0] = message
                response["messages"] = resp_messages
            else:
                message = first

        has_human_message = message is not None

        if has_human_message:
            # Branch 1: user sent text input → aafter_user_input
            user_input = (
                message.content
                if isinstance(message.content, str)
                else str(message.content)
            )
            after_input_update = await sub_middleware.aafter_user_input(
                sub_state,
                self._runtime,
                user_input,
                action,
                params,
            )
            if after_input_update:
                update = self._merge_updates(update, after_input_update)
        else:
            # Branch 2: no message → action-based lifecycle transitions
            if action == ACTION_SESSION_START and current_status == "paused":
                resume_update = await sub_middleware.aresume(sub_state, self._runtime)
                if resume_update:
                    update = self._merge_updates(update, resume_update)
            elif action == ACTION_QUIT_LEARNING and current_status == "running":
                pause_update = await sub_middleware.apause(sub_state, self._runtime)
                if pause_update:
                    update = self._merge_updates(update, pause_update)

        if update:
            if update.get("messages"):
                update["messages"] = self._add_message_metadata(
                    update["messages"], sub_state
                )
            return Command(update=update, resume=response)
        return Command(resume=response)

    # ==================== State Helpers ====================

    @staticmethod
    def _build_task_summary(
        task_name: str,
        task_id: str,
        is_interrupt: bool,
        result: Dict[str, Any],
    ) -> str:
        """Build a human-readable summary line for a completed/interrupted sub task."""
        status = "interrupted" if is_interrupt else "completed"
        header = f"Task '{task_name}' (id: {task_id}) {status}."
        parts = []
        for key in ("summary", "reason", "next_intent"):
            value = result.get(key)
            if value:
                parts.append(f"{key}: {value}")
        if parts:
            return header + " " + " | ".join(parts)
        return header

    def _get_sub_tasks(self, state: TaskState) -> List[str]:
        return state.get("sub_tasks", [])

    @staticmethod
    def _compressible_message(content: str) -> SystemMessage:
        """Create a SystemMessage marked as compressible."""
        return SystemMessage(
            content=content,
            additional_kwargs=build_compressible_kwargs(),
        )

    def _load_task_prompt(self, task_name: str) -> Optional[str]:
        """Load TASK.md prompt. Tries handler.name, then task_group_name, then 'general'."""
        handler = self.get_handler(task_name)
        handler_name = getattr(handler, "name", None)
        candidates = dict.fromkeys(
            c for c in [handler_name, self.task_group_name, GENERAL_HANDLER_NAME] if c
        )
        for candidate in candidates:
            try:
                prompt = get_task_prompt(name=candidate)
                if prompt:
                    return prompt
            except Exception:
                continue
        return None

    # ==================== Current Task Lifecycle ====================

    async def abefore(
        self,
        state: TaskState,
        runtime: "Runtime",
    ) -> Dict[str, Any]:
        """Called when this task starts. Sets status to running, loads TASK.md prompt."""
        task_id = state["id"]
        task_name = state["name"]
        updated: Dict[str, Any] = {
            "id": task_id,
            "name": task_name,
            "status": "running",
        }

        handler = self.get_handler(task_name)
        prompt = self._load_task_prompt(task_name)
        if prompt:
            updated["messages"] = [SystemMessage(content=prompt)]

        msgs = updated.get("messages", [])

        # Inject language context
        locale_name = state.get("locale_name")
        if locale_name:
            msgs.append(SystemMessage(content=build_language_context(locale_name)))

        # Inject skill context (self.skills already includes handler skills)
        skill_content = build_skill_information_context_list(
            get_skills_by_names(list(self.skills))
        )
        msgs.append(self._compressible_message(skill_content))
        updated["messages"] = msgs

        merged = {**state, **updated}
        handler_update = await handler.abefore(merged, runtime)
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    async def apause(
        self,
        state: TaskState,
        runtime: "Runtime",
    ) -> Dict[str, Any]:
        """Called when this task pauses. Sets status to paused."""
        task_name = state["name"]
        updated: Dict[str, Any] = {
            "status": "paused",
        }

        handler = self.get_handler(task_name)
        merged = {**state, **updated}
        handler_update = await handler.apause(merged, runtime)
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    async def aresume(
        self,
        state: TaskState,
        runtime: "Runtime",
    ) -> Dict[str, Any]:
        """Called when this task resumes. Sets status to running."""
        task_name = state["name"]
        updated: Dict[str, Any] = {
            "status": "running",
        }

        handler = self.get_handler(task_name)
        merged = {**state, **updated}
        handler_update = await handler.aresume(merged, runtime)
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    async def ainterrupt(
        self,
        state: TaskState,
        runtime: "Runtime",
    ) -> Dict[str, Any]:
        """Called when this task is interrupted. Sets status to interrupted."""
        task_name = state["name"]
        result = state.get("result") or {}
        updated: Dict[str, Any] = {
            "status": "interrupted",
            "result": result,
        }

        handler = self.get_handler(task_name)
        merged = {**state, **updated}
        handler_update = await handler.ainterrupt(merged, runtime)
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    async def arecover(
        self,
        state: TaskState,
        runtime: "Runtime",
    ) -> Dict[str, Any]:
        """Called when this task recovers from interruption. Sets status to running."""
        task_name = state["name"]
        updated: Dict[str, Any] = {
            "status": "running",
            "result": None,
        }

        handler = self.get_handler(task_name)
        merged = {**state, **updated}
        handler_update = await handler.arecover(merged, runtime)
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    async def aafter(
        self,
        state: TaskState,
        runtime: "Runtime",
    ) -> Dict[str, Any]:
        """Called when this task completes normally. Sets status to completed."""
        task_name = state["name"]
        result = dict(state.get("result")) if state.get("result") else {}
        updated: Dict[str, Any] = {
            "status": "completed",
            "result": result,
        }

        handler = self.get_handler(task_name)
        merged = {**state, **updated}
        handler_update = await handler.aafter(merged, runtime)
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    # ==================== Sub Task Lifecycle ====================

    async def abefore_task(
        self,
        state: TaskState,
        runtime: "Runtime",
        sub_task_id: str,
        sub_task_name: str,
    ) -> Dict[str, Any]:
        """Called when a sub task starts within this task."""
        task_name = state["name"]
        sub_tasks = self._get_sub_tasks(state).copy()
        sub_tasks.append(sub_task_id)

        updated: Dict[str, Any] = {
            "sub_tasks": sub_tasks,
        }

        handler = self.get_handler(task_name)
        handler_update = await handler.abefore_task(
            state, runtime, sub_task_id, sub_task_name
        )
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    async def arecover_task(
        self,
        state: TaskState,
        runtime: "Runtime",
        sub_task_id: str,
        sub_task_name: str,
    ) -> Dict[str, Any]:
        """Called when a sub task recovers from error."""
        task_name = state["name"]
        updated: Dict[str, Any] = {}

        handler = self.get_handler(task_name)
        handler_update = await handler.arecover_task(
            state, runtime, sub_task_id, sub_task_name
        )
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    async def ainterrupt_task(
        self,
        state: TaskState,
        runtime: "Runtime",
        sub_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Called when a sub task is interrupted within this task."""
        task_name = state["name"]
        updated: Dict[str, Any] = {}

        handler = self.get_handler(task_name)
        handler_update = await handler.ainterrupt_task(state, runtime, sub_state)
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    async def aafter_task(
        self,
        state: TaskState,
        runtime: "Runtime",
        sub_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Called when a sub task ends within this task."""
        task_name = state["name"]
        updated: Dict[str, Any] = {}

        handler = self.get_handler(task_name)
        handler_update = await handler.aafter_task(
            state,
            runtime,
            sub_state,
        )
        if handler_update:
            updated = self._merge_updates(updated, handler_update)
        return updated

    # ==================== User Input Handling ====================

    async def aafter_user_input(
        self,
        state: TaskState,
        runtime: "Runtime",
        user_input: str,
        action: Optional[str],
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        """Called after user input at task level."""
        task_name = state["name"]
        handler = self.get_handler(task_name)
        return await handler.aafter_user_input(
            state, runtime, user_input, action, params
        )

    # ==================== Tool Call Handling ====================

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """
        Wrap tool calls.

        Delegates to the current task's handler wrapper if exists.
        After execution, adds message metadata to any messages in the result.
        """
        task_name = self._get_current_task_name(request.state)
        if task_name:
            result = await self.get_handler(task_name).awrap_tool_call(request, handler)
        else:
            result = await handler(request)

        if isinstance(result, Command):
            update = result.update
            if isinstance(update, dict) and update.get("messages"):
                update["messages"] = self._add_message_metadata(
                    update["messages"], request.state
                )

        return result

    # ==================== Model Call Handling ====================

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Wrap model calls. Delegates to handler. Adds message metadata to result."""
        state = request.state
        task_name = self._get_current_task_name(state)

        if task_name:
            result = await self.get_handler(task_name).awrap_model_call(
                request, handler
            )
        else:
            result = await handler(request)

        if isinstance(result, ModelResponse) and result.result:
            result.result = self._add_message_metadata(result.result, state)
        elif isinstance(result, BaseMessage):
            result = self._add_message_metadata([result], state)[0]

        return result

    # ==================== Agent Lifecycle ====================

    async def abefore_agent(
        self, state: TaskState, runtime: "Runtime"
    ) -> Dict[str, Any] | None:
        """
        Called before agent execution (first call only; NOT re-executed on interrupt resume).

        1. If no task -> initialize root entry
        2. Initialize user_profile / locale if missing
        3. Lifecycle dispatch (pending->before, recovering->recover)

        Note: action-based lifecycle (session-start->resume, quit->pause),
        human message handling and per-request logic are all handled
        in _on_interrupt_resume instead, since user actions arrive via
        the interrupt resume path.
        """
        # Store runtime for use by tool closures
        self._runtime = runtime

        updated: Dict[str, Any] = {}

        current_task_id = state.get("id")
        current_status = state.get("status")

        # Step 1: No task -> initialize root entry
        if not current_task_id:
            root_id = "__root__"
            updated["id"] = root_id
            updated["name"] = ROOT_HANDLER_NAME
            updated["status"] = "pending"
            updated["params"] = None

            current_task_id = root_id
            current_status = "pending"

        # Build merged state so lifecycle hooks see updated fields
        merged_state = {**state, **updated}

        # Step 3: Lifecycle dispatch based on status
        lifecycle_state = None

        if current_status == "pending":
            updated["mode"] = "start"
            lifecycle_state = await self.abefore(
                merged_state,
                runtime,
            )
            updated["status"] = "running"
        elif current_status == "recovering":
            updated["mode"] = "recover"
            lifecycle_state = await self.arecover(
                merged_state,
                runtime,
            )
            updated["status"] = "running"

        if lifecycle_state:
            msgs = self._add_message_metadata(
                lifecycle_state.get("messages", []),
                {**state, **updated},
            )
            updated.update(
                {k: v for k, v in lifecycle_state.items() if k != "messages"}
            )
            if msgs:
                updated["messages"] = updated.get("messages", []) + msgs

        return updated

    async def aafter_agent(
        self, state: TaskState, runtime: "Runtime"
    ) -> Dict[str, Any] | None:
        """Called after agent execution."""
        return None

    # ==================== Model Lifecycle ====================

    @hook_config(can_jump_to=["tools", "end"])
    async def abefore_model(
        self, state: TaskState, runtime: "Runtime"
    ) -> Dict[str, Any] | None:
        """
        Called before model is called.

        Uses @hook_config(can_jump_to=["tools", "end"]) to enable jump_to mechanism.
        - If task status is completed/interrupted (set by end_task), jump to end.
        - If latest message contains tool calls, jump to tools.
        """
        status = state.get("status")
        if status in ("completed", "interrupted"):
            return {"jump_to": "end"}
        if tools_condition(state) == "tools":
            return {"jump_to": "tools"}
        return None

    # ==================== Message Metadata Helpers ====================

    def _add_message_metadata(
        self,
        messages: List[AnyMessage],
        state: Dict[str, Any],
    ) -> List[AnyMessage]:
        """Add task metadata to messages incrementally.

        All messages get: __task_id__, __task_name__, __task_group_name__,
        __task_mode__, __timestamp__.
        """
        task_id = state.get("id") or ""
        task_name = self._get_current_task_name(state) or ""
        task_mode = state.get("mode") or ""

        result = []
        for message in messages:
            kwargs = {
                **message.additional_kwargs,
                "__task_id__": task_id,
                "__task_name__": task_name,
                "__task_group_name__": self.task_group_name or "",
                "__task_mode__": task_mode,
                "__timestamp__": get_timestamp(),
            }
            result.append(message.model_copy(update={"additional_kwargs": kwargs}))
        return result

    # ==================== Helpers ====================

    def _merge_updates(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two state updates, combining messages."""
        result = {**base}
        for key, value in override.items():
            if key == "messages":
                result["messages"] = result.get("messages", []) + value
            else:
                result[key] = value
        return result
