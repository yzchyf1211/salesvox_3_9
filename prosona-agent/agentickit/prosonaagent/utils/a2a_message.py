from agentickit.core.server.message_sender import send_data_message, send_text_message
from typing import Dict, Any
import uuid


class A2AMessage:
    def __init__(self) -> None:
        pass

    def typeof() -> str:
        return ""

    async def send_to(context_id: str) -> None:
        pass

    def get_content(self):
        return self.content


class A2ADataMessage(A2AMessage):
    def __init__(self, content: Dict[str, Any]) -> None:
        self.content = content

    def typeof() -> str:
        return "data"

    async def send_to(
        self,
        context_id: str,
        metadata: Dict[str, Any] = {},
        part_metadata: Dict[str, Any] = {},
        message_id: str | None = None,
    ) -> None:
        return await send_data_message(
            context_id=context_id,
            data=self.content,
            metadata=metadata,
            part_metadata=part_metadata,
            message_id=message_id,
        )


class A2ATextMessage(A2AMessage):
    def __init__(self, content: str) -> None:
        self.content = content

    def typeof() -> str:
        return "text"

    async def send_to(
        self,
        context_id: str,
        metadata: Dict[str, Any] = {},
        part_metadata: Dict[str, Any] = {},
        message_id: str | None = None,
    ) -> None:
        return await send_text_message(
            context_id=context_id,
            text=self.content,
            metadata=metadata,
            part_metadata=part_metadata,
            message_id=message_id,
        )


class A2ABizDataMessage(A2ADataMessage):
    def __init__(
        self,
        name: str = "",
        identifier: str = "",
        params: Dict[str, Any] = {},
    ) -> None:
        content = {
            "type": "biz",
            "id": str(uuid.uuid4()),
            "name": name,
            "identifier": identifier,
            "params": params,
        }
        self.content = content
