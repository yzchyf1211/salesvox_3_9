from abc import ABC, abstractmethod
from typing import AsyncIterable, Any

from agentickit.core.server.types import A2APartType


class A2AMessageChunkGenerator(ABC):
    """A2A 消息块生成器基类。"""

    @abstractmethod
    async def handle(self, event: dict, data: dict) -> AsyncIterable[dict[str, Any]]:
        """处理 on_chat_model_* 事件，yield 0-N 个 chunk。"""
        ...

    # ── data type ──

    @staticmethod
    def _build_data_type_chunk_part(data: dict) -> None:
        """设置 DATA 类型三元组。"""
        data["part_type"] = A2APartType.DATA
        data["partType"] = A2APartType.DATA
        data["content_type"] = A2APartType.DATA.value

    # ── streaming lifecycle（content / append / last_chunk） ──

    @staticmethod
    def _build_start_chunk_part(data: dict, content) -> None:
        """填充首个 chunk：content + append=False + last_chunk=False。"""
        data["content"] = content
        data["append"] = False
        data["last_chunk"] = False

    @staticmethod
    def _build_stream_chunk_part(data: dict, content) -> None:
        """填充后续流式 chunk：content + append=True + last_chunk=False。"""
        data["content"] = content
        data["append"] = True
        data["last_chunk"] = False

    @staticmethod
    def _build_end_chunk_part(data: dict, content) -> None:
        """标记为 part 结束块。"""
        data["content"] = content
        data["append"] = True
        data["last_chunk"] = True

    @staticmethod
    def _build_yield_chunk_part(data: dict) -> None:
        """标记为可 yield 的 chunk。"""
        data["is_yield_data"] = True

    # ── metadata ──

    @staticmethod
    def _build_metadata_chunk_part(data: dict, metadata: dict) -> None:
        """设置 metadata（替换）。"""
        data["metadata"] = {
            **data.get("metadata", {}),
            **metadata,
        }

    @staticmethod
    def _build_speaker_for_conversation_chunk_part(data: dict, event: dict) -> None:
        """从 event metadata 中提取 speaker 信息并合并到 metadata。"""
        speaker = event.get("metadata", {}).get("speaker")
        if not speaker:
            return
        return A2AMessageChunkGenerator._build_metadata_chunk_part(data, speaker)

    @staticmethod
    def _build_speaker_for_data_chunk_part(data: dict, event: dict) -> None:
        """从 event metadata 中提取 speaker 信息并以 data stream 格式合并到 metadata。"""
        speaker = event.get("metadata", {}).get("speaker")
        if not speaker:
            return
        return A2AMessageChunkGenerator._build_metadata_chunk_part(
            data, {"sender": speaker.get("sender")}
        )

    # ── part_metadata ──

    @staticmethod
    def _build_part_metadata_chunk_part(data: dict, part_metadata: dict) -> None:
        """合并 part_metadata。"""
        data["part_metadata"] = {
            **data.get("part_metadata", {}),
            **part_metadata,
        }
