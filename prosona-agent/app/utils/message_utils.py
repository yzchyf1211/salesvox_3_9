"""
消息工具函数
（从 aitutor-magic-agent message_utils.py 迁移，内联 get_message_metadata）
"""

from typing import List, Optional

from langchain_core.messages import BaseMessage


def get_message_metadata(message: BaseMessage, key: str):
    """从消息的 additional_kwargs 中获取元数据字段"""
    if hasattr(message, "additional_kwargs"):
        return message.additional_kwargs.get(key)
    return None


def filter_messages_by_criteria(
    messages: List[BaseMessage],
    activity_id: Optional[str] = None,
    sco_id: Optional[str] = None,
    exclude_sco_ids: Optional[List[str]] = None,
) -> List[BaseMessage]:
    """
    根据指定条件从消息列表中筛选出需要的消息

    所有参数都是可选的，只有当参数不为None且在消息的additional_kwargs中存在时才进行匹配
    """
    filtered_messages = []

    for message in messages:
        matches = True

        if activity_id is not None:
            message_activity_id = get_message_metadata(message, "activity_id")
            if message_activity_id != activity_id:
                matches = False

        if sco_id is not None:
            message_sco_id = get_message_metadata(message, "sco_id")
            if message_sco_id != sco_id:
                matches = False

        if exclude_sco_ids is not None and matches:
            message_sco_id = get_message_metadata(message, "sco_id")
            if message_sco_id in exclude_sco_ids:
                matches = False

        if matches:
            filtered_messages.append(message)

    return filtered_messages
