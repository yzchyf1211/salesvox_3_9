from typing import Optional

from a2a.types import Part
from agentickit.core.server.types import UserProfile
from langchain.agents.middleware.types import AgentState


class ProsonaAgentState(AgentState):
    context_id: str

    # A2A请求体part信息
    parts: list[Part]

    # 文本类型消息数量
    text_part_size: int

    # 用户信息
    user_profile: Optional[UserProfile]

    # 多语言locale, zh_CN、zh_TW、ja、en...（符合平台2.0规范）
    locale: Optional[str]

    # 多语言描述
    locale_name: Optional[str]
