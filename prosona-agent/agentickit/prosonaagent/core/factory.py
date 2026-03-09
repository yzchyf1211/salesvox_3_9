"""
Agent Factory for Prosona Agent.

Provides create_handler_registry and create_prosona_agent.
Root/sub-agent creation both use the same handler_registry.
"""

from typing import Optional, Sequence, Tuple, Type, TYPE_CHECKING

from langgraph.graph.state import CompiledStateGraph

if TYPE_CHECKING:
    from .middleware.task_middleware import TaskMiddleware
from agentickit.langgraph.checkpoint import async_checkpoint_saver
from langchain.agents import create_agent
from langchain.agents.middleware.model_fallback import ModelFallbackMiddleware

from .middleware.model_enhance_middleware import ModelEnhanceMiddleware
from .middleware.speaker_middleware import SpeakerMiddleware
from .middleware.chat_metadata_middleware import ChatMetadataMiddleware
from .middleware.user_context_middleware import UserContextMiddleware

from agentickit.core.infra.config.loader import get_config
from agentickit.core.infra.models import get_model

from .handler.handler_registry import HandlerRegistry, ROOT_HANDLER_NAME
from .middleware.middleware_registry import (
    MiddlewareRegistry,
    ROOT_MIDDLEWARE_GROUP_NAME,
)
from .handler.task_handler import TaskHandler


def create_handler_registry(
    root_handler: TaskHandler | None = None,
    task_handlers: Optional[Sequence[TaskHandler]] = None,
) -> HandlerRegistry:
    """
    Create and populate a handler registry for use by create_prosona_agent
    and by task middleware when building sub-agents.

    Args:
        root_handler: TaskHandler for root-level (session) logic.
                      Registered as "__root__". If not provided, a default TaskHandler is used.
        task_handlers: List of TaskHandlers. Each must have a non-empty .name;
                      registered under handler.name. Naming convention:
                      - Default group handler: name = "{group_name}" (e.g. "sco")
                      - Custom task handler:   name = "{group_name}:{task_name}" (e.g. "sco:lecture_summary")

    Returns:
        HandlerRegistry with root and task handlers registered.
    """
    registry = HandlerRegistry()  # already has default root + general
    if root_handler is not None:
        registry.register(ROOT_HANDLER_NAME, root_handler)
    if task_handlers:
        for handler in task_handlers:
            name = getattr(handler, "name", None)
            if not name:
                raise ValueError(
                    f"task_handlers entry must have a non-empty 'name'; got {type(handler).__name__!r} without name"
                )
            registry.register(name, handler)
    return registry


def create_middleware_registry(
    root_middleware: Type["TaskMiddleware"],
    task_middlewares: Optional[Sequence[Type["TaskMiddleware"]]] = None,
) -> MiddlewareRegistry:
    """
    Create and populate a middleware registry for use by create_prosona_agent
    and by task middleware when building sub-graphs.

    Args:
        root_middleware: Middleware class for root (session) level. Registered under ROOT_MIDDLEWARE_GROUP_NAME.
        task_middlewares: Optional list of TaskMiddleware subclasses. Each is registered under
                         its class attribute task_group_name (e.g. "project", "activity", "sco").
                         Each must have a non-empty task_group_name.

    Returns:
        MiddlewareRegistry with root and task middlewares registered.
    """
    registry = MiddlewareRegistry()
    registry.register(ROOT_MIDDLEWARE_GROUP_NAME, root_middleware)
    if task_middlewares:
        for middleware_class in task_middlewares:
            name = getattr(middleware_class, "task_group_name", None)
            if not name:
                raise ValueError(
                    f"task_middlewares entry must have a non-empty 'task_group_name'; "
                    f"got {middleware_class.__name__!r} without task_group_name"
                )
            registry.register(name, middleware_class)
    return registry


def create_prosona_agent(
    system_prompt: str,
    middleware_registry: MiddlewareRegistry,
    handler_registry: HandlerRegistry,
    model_group: str = "main",
    task_name: Optional[str] = ROOT_HANDLER_NAME,
    task_group_name: Optional[str] = ROOT_MIDDLEWARE_GROUP_NAME,
    **agent_kwargs,
) -> Tuple[CompiledStateGraph, "TaskMiddleware"]:
    """
    Create a Prosona Agent (root or sub-graph). Middleware class is taken from middleware_registry (ROOT_MIDDLEWARE_GROUP_NAME for root, or task_group_name for sub-graph).
    Tool list (default builtins + handler tools + lifecycle) is built inside TaskMiddleware.

    Args:
        system_prompt: System prompt for the agent (str). Required.
        middleware_registry: Registry mapping task_group_name to middleware class. Required.
        handler_registry: Registry from create_handler_registry(root_handler, task_handlers). Required.
        model_group: Config key under model_groups (default "main"). Used for primary/fallback models.
        task_name: Default ROOT_HANDLER_NAME. When ROOT_HANDLER_NAME or None, create root graph; else create sub-graph (used as middleware's name for handler lookup).
        task_group_name: Default ROOT_MIDDLEWARE_GROUP_NAME. Used to look up middleware class from registry. For sub-graph, pass the group name (e.g. "project"); if None when task_name is not root, falls back to task_name.
        **agent_kwargs: Extra keyword arguments forwarded to TaskMiddleware and relevant middlewares
                        (e.g. tts_configs). Automatically passed through to sub-agents.

    Returns:
        (CompiledStateGraph, TaskMiddleware instance used).
    """
    middleware_class = middleware_registry.get(task_group_name)
    if middleware_class is None:
        raise ValueError(
            f"middleware_registry must register middleware[task_group_name: {task_group_name}]"
        )

    task_middleware = middleware_class(
        task_name=task_name,
        system_prompt=system_prompt,
        middleware_registry=middleware_registry,
        handler_registry=handler_registry,
        **agent_kwargs,
    )
    primary_model = get_model(get_config(f"model_groups.{model_group}.primary_model"))
    fallback_model = get_model(get_config(f"model_groups.{model_group}.fallback_model"))

    tts_configs = agent_kwargs.get("tts_configs")
    agent_middlewares = [
        UserContextMiddleware(),
        task_middleware,
        ModelEnhanceMiddleware(skill_names=list(task_middleware.skills)),
        ModelFallbackMiddleware(fallback_model),
        SpeakerMiddleware(tts_configs=tts_configs),
        ChatMetadataMiddleware(),
    ]

    graph = create_agent(
        model=primary_model,
        system_prompt=system_prompt,
        middleware=agent_middlewares,
        checkpointer=async_checkpoint_saver(),
    )
    return (graph, task_middleware)
