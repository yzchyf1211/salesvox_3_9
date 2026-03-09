from typing import AsyncIterable, Any

from agentickit.prosonaagent.utils.chunk_generator.base import A2AMessageChunkGenerator

CONVERSATION_STREAM_TAG = "conversation"


class ConversationChunkGenerator(A2AMessageChunkGenerator):
    """对话流 chunk 生成器。"""

    def __init__(self):
        self.buffer: str = ""

    async def handle(self, event: dict, data: dict) -> AsyncIterable[dict[str, Any]]:
        event_type = event.get("event")

        if event_type == "on_chat_model_start":
            self.buffer = ""
            return

        if event_type == "on_chat_model_end":
            self.buffer = ""
            if CONVERSATION_STREAM_TAG in event.get("tags", []):
                self._build_end_chunk_part(data, "")
                self._build_speaker_for_conversation_chunk_part(data, event)
                self._build_yield_chunk_part(data)
                yield data
            return

        # on_chat_model_stream
        if CONVERSATION_STREAM_TAG not in event.get("tags", []):
            return
        chunk = event.get("data", {}).get("chunk")
        if not (chunk and hasattr(chunk, "content") and chunk.content):
            return
        if self.buffer:
            self._build_stream_chunk_part(data, chunk.content)
        else:
            self._build_start_chunk_part(data, chunk.content)
        self._build_speaker_for_conversation_chunk_part(data, event)
        self._build_yield_chunk_part(data)
        self.buffer += chunk.content
        yield data
