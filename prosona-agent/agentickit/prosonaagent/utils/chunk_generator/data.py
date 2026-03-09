import uuid
from typing import AsyncIterable, Any

from agentickit.prosonaagent.utils.chunk_generator.base import A2AMessageChunkGenerator

DATA_STREAM_TAG = "data"


class DataChunkGenerator(A2AMessageChunkGenerator):
    """数据流 chunk 生成器。"""

    def __init__(self):
        self.buffer: str = ""

    @staticmethod
    def _build_first_data_content(tool_name: str, args: str) -> dict:
        """构建数据流首个 chunk 的 content（包含完整工具元信息）。"""
        return {
            "type": "tool",
            "identifier": "tool-call-data",
            "name": tool_name,
            "id": f"call_{uuid.uuid4().hex[:22]}",
            "index": 0,
            "args": args,
        }

    def _build_data_end_chunk_part(self, data: dict) -> None:
        """填充数据流结束 chunk（end 标记 + DATA 类型）。"""
        self._build_end_chunk_part(data, {})
        self._build_data_type_chunk_part(data)

    def _build_data_stream_chunk_part(
        self, data: dict, tool_name: str, args: str, is_first: bool
    ) -> None:
        """填充数据流 chunk 的 content、part_metadata、append、last_chunk。"""
        if is_first:
            content = self._build_first_data_content(tool_name, args)
            self._build_start_chunk_part(data, content)
        else:
            self._build_stream_chunk_part(data, {"args": args})
        self._build_part_metadata_chunk_part(data, {"execEnv": "frontend"})

    async def handle(self, event: dict, data: dict) -> AsyncIterable[dict[str, Any]]:
        event_type = event.get("event")

        if event_type == "on_chat_model_start":
            self.buffer = ""
            return

        if event_type == "on_chat_model_end":
            self.buffer = ""
            if DATA_STREAM_TAG in event.get("tags", []):
                self._build_data_end_chunk_part(data)
                # see agentickit EnhancedAgenticExecutor._process
                self._build_speaker_for_conversation_chunk_part(data, event)
                self._build_yield_chunk_part(data)
                yield data
            return

        # on_chat_model_stream
        if DATA_STREAM_TAG not in event.get("tags", []):
            return
        chunk = event.get("data", {}).get("chunk")
        if not (chunk and hasattr(chunk, "content") and chunk.content):
            return
        self._build_data_type_chunk_part(data)
        self._build_data_stream_chunk_part(
            data,
            event.get("metadata", {}).get("tool_name"),
            chunk.content,
            is_first=not self.buffer,
        )
        self._build_speaker_for_data_chunk_part(data, event)
        self._build_yield_chunk_part(data)
        self.buffer += chunk.content
        yield data
