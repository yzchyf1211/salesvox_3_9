import re
import logging
from typing import AsyncIterable, Any

from agentickit.prosonaagent.utils.chunk_generator.base import A2AMessageChunkGenerator

logger = logging.getLogger(__name__)


def _is_stream_text_tool_call(name: str) -> bool:
    return name == "_builtin_conversation"


def _extract_args_from_incomplete_json(json_string: str, key: str) -> str:
    """从可能不完整的JSON字符串中提取关键参数"""
    # 目前Agent会返回非标的文本内容
    # text: "你能抓住'飞行中换翅膀'这个比喻，说明你已经理解了转型的艰难和必须边做边学的现实。"}"
    # 流式输出会出现"}分开输出的情况，需要处理当只输出"，让外部不做流式输出
    if json_string.endswith("\u201d"):
        raise ValueError(f"JSON字符串最后包含多余的右引号: {json_string}")

    # 提取type字段
    match = re.search(rf'"{key}"\s*:\s*"([^"]*)', json_string)
    if not match:
        return None

    value = match.group(1)
    # 如果字符串最后包含多余的右大括号，去掉它
    if value.endswith("\u201d}"):
        value = value[:-2]
    return value


class ToolCallChunkGenerator(A2AMessageChunkGenerator):
    """工具调用流 chunk 生成器。"""

    def __init__(self):
        self.name: str = ""
        self.text: str = ""
        self.buffer: str = ""

    def _build_tool_call_start_chunk_part(
        self, data: dict, content: str, event: dict
    ) -> None:
        """填充工具调用首个 chunk。"""
        self._build_start_chunk_part(data, content)
        user_data = event.get("metadata", {}).get("user_data", {})
        self._build_metadata_chunk_part(data, user_data)

    def _build_tool_call_stream_chunk_part(
        self, data: dict, content: str, event: dict
    ) -> None:
        """填充工具调用后续 chunk。"""
        self._build_stream_chunk_part(data, content)
        user_data = event.get("metadata", {}).get("user_data", {})
        self._build_metadata_chunk_part(data, user_data)

    async def handle(self, event: dict, data: dict) -> AsyncIterable[dict[str, Any]]:
        if event.get("event") != "on_chat_model_stream":
            return

        chunk = event.get("data", {}).get("chunk")

        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
            tool_call_chunk = chunk.tool_call_chunks[0]
            name = tool_call_chunk.get("name")

            # 开始发送PART_START和设置工具调用名称、文本、缓冲区
            is_stream_start = bool(name)
            # 一次LLM请求多个工具调用，is_stream_end条件无法触发，需要根据开始新工具来触发PART_END
            if is_stream_start and _is_stream_text_tool_call(self.name):
                self._build_end_chunk_part(data, "")
                self._build_speaker_for_conversation_chunk_part(data, event)
                self._build_yield_chunk_part(data)
                yield data

            if is_stream_start:
                self.name = name
                self.text = ""
                self.buffer = ""

            if _is_stream_text_tool_call(self.name):
                args = tool_call_chunk.get("args")
                if args:
                    self.buffer += args
                try:
                    text = _extract_args_from_incomplete_json(self.buffer, "text") or ""
                    is_first = len(self.text) == 0
                    delta_text = text[len(self.text) :]
                    self.text = text
                    if delta_text:
                        if is_first:
                            self._build_tool_call_start_chunk_part(
                                data, delta_text, event
                            )
                        else:
                            self._build_tool_call_stream_chunk_part(
                                data, delta_text, event
                            )
                        self._build_speaker_for_conversation_chunk_part(data, event)
                        self._build_yield_chunk_part(data)
                        yield data
                except Exception as e:
                    logger.warning(
                        f"[ToolCallChunkGenerator] 处理_extract_args_from_incomplete_json时出错: event={event.get('event')}, error={e}",
                        exc_info=True,
                    )

        # 结束发送PART_END和清空工具调用名称、文本、缓冲区
        # 一次LLM请求结束，最后一个工具是对话工具
        is_stream_end = len(chunk.tool_call_chunks) == 0
        if is_stream_end and _is_stream_text_tool_call(self.name):
            self._build_end_chunk_part(data, "")
            self._build_speaker_for_conversation_chunk_part(data, event)
            self._build_yield_chunk_part(data)
            yield data

        if is_stream_end:
            self.name = ""
            self.text = ""
            self.buffer = ""
