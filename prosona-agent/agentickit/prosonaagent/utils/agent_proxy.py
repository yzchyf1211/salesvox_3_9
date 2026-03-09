from typing import Dict, Any, Optional
from .a2a_message import A2AMessage
from agentickit.prosonaagent.core.middleware.speaker_middleware import Sender, TTSConfig, Speaker  # noqa: F401
from agentickit.prosonaagent.core.state import ProsonaAgentState


class AgentProxy:
    def __init__(self) -> None:
        pass

    @staticmethod
    async def sendTo(
        agentProxy,
        message: A2AMessage,
        metadata: Dict[str, Any] = {},
        part_metadata: Dict[str, Any] = {},
        message_id: str | None = None,
    ) -> None:
        return await agentProxy.onMessage(
            message,
            metadata=metadata,
            part_metadata=part_metadata,
            message_id=message_id,
        )

    async def onMessage(
        self,
        message: A2AMessage,
        metadata: Dict[str, Any] = {},
        part_metadata: Dict[str, Any] = {},
        message_id: str | None = None,
    ) -> None:
        pass


class UserAgentProxy(AgentProxy):
    """
    定义用户输入解析类
    """

    def __init__(self, state: ProsonaAgentState) -> None:
        self.state = state
        self.context_id = state.get("context_id")

        text_part_size = state.get("text_part_size", 0)
        if text_part_size == 0 and state.get("parts"):
            # 支持Mock的Dict数据
            part = state.get("parts", [])[-1]
            action_data = (
                part.root.data
                if hasattr(part, "root")
                else part.get("root", {}).get("data", {})
            )
            self.action = action_data.get("actionName")
            self.params = action_data.get("params", {})

    def get_action(self):
        return self.action if hasattr(self, "action") else None

    def get_params(self):
        return self.params if hasattr(self, "params") else None

    def get_context_id(self):
        return self.context_id

    def when_do(self, action: str) -> bool:
        return self.action == action if hasattr(self, "action") else False

    async def on_message(
        self,
        message: A2AMessage,
        metadata: Dict[str, Any] = {},
        part_metadata: Dict[str, Any] = {},
        message_id: str | None = None,
    ) -> None:
        return await message.send_to(
            self.context_id,
            metadata=metadata,
            part_metadata=part_metadata,
            message_id=message_id,
        )


async def send_to(
    agentProxy: AgentProxy,
    message: A2AMessage,
    metadata: Optional[Dict[str, Any]] = None,
    part_metadata: Optional[Dict[str, Any]] = None,
    message_id: str | None = None,
):
    return await agentProxy.on_message(
        message,
        metadata=metadata or {},
        part_metadata=part_metadata or {},
        message_id=message_id,
    )
