import logging
from typing import AsyncIterable, Any

from agentickit.core.server import StandardStreamAgenticHandler
from agentickit.core.server.context import (
    ExecutionContext,
    ExecutionStatus,
)
from agentickit.langgraph import get_default_runnable_config
from agentickit.langgraph.checkpoint import async_checkpoint_saver
from agentickit.langgraph.stream import build_from_astream_event
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from agentickit.prosonaagent.utils.chunk_generator import (
    ConversationChunkGenerator,
    DataChunkGenerator,
    ToolCallChunkGenerator,
)


logger = logging.getLogger(__name__)


class ProsonaA2AStreamAgenticExecutor(StandardStreamAgenticHandler):
    """
    A2A流式Agent执行器抽象基类

    定义了A2A流式Agent执行器的标准接口，所有具体的A2A流式Agent执行器实现都应该继承此类。
    提供了流式处理用户请求的抽象方法，支持异步迭代器模式。
    """

    def __init__(self, graph: CompiledStateGraph):
        self.graph = graph
        self._chunk_generators = [
            ConversationChunkGenerator(),
            DataChunkGenerator(),
            ToolCallChunkGenerator(),
        ]

    async def stream(
        self, state: Any, context: ExecutionContext
    ) -> AsyncIterable[dict[str, Any]]:
        """
        流式处理方法

        这是智能体的核心执行方法，处理用户输入并返回流式响应。

        参数：
            state: 当前状态，包含用户消息和上下文信息
            context: 执行上下文，包含配置和元数据

        返回：
            AsyncIterable[A2AMessageChunk]: 流式输出的消息块

        处理流程：
        1. 获取运行配置
        2. 检查是否有中断需要恢复
        3. 流式执行智能体图
        4. 处理各种事件（模型输出、工具调用等）
        5. 返回流式结果
        """
        logger.info(f"开始处理请求，context_id: {state.get('context_id')}")

        # 获取默认运行配置
        config: RunnableConfig = get_default_runnable_config(context)
        # 增加递归限制，防止复杂流程超过默认的100次限制
        config["recursion_limit"] = 100

        # 检查是否有需要恢复的中断
        # 第一次进入为正常启动，后续进入均视为中断恢复（因为上次一定是 interrupt 暂停的）
        inputs = None
        if state["opt_type"] != "resume":
            inputs = (
                Command(resume=state)
                if context and context["status"] == ExecutionStatus.INTERRUPT
                else state
            )
        # 第一次初始化checkpointer无法设置上，start_default_agentic_application之后才会初始化async_checkpoint_saver。
        # 这里算是补丁
        if not self.graph.checkpointer:
            self.graph.checkpointer = async_checkpoint_saver()
        # 流式执行智能体图
        # astream_events 提供实时的事件流
        async for event in self.graph.astream_events(
            inputs, config, subgraphs=True, debug=True
        ):
            # 使用 agentickit 提供的辅助函数构建输出数据
            data = build_from_astream_event(event)

            # 处理聊天模型事件（start / stream / end）
            if event.get("event", "").startswith("on_chat_model"):
                for gen in self._chunk_generators:
                    async for chunk_data in gen.handle(event, data):
                        yield chunk_data

            elif (
                event["event"] in ["on_chain_end"]
                and event["name"] == "LangGraph"
                and len(event["parent_ids"]) == 0
            ):
                yield data
            elif event["event"] == "on_tool_error":
                yield data
        logger.info(f"请求处理完成，context_id: {state.get('context_id')}")
