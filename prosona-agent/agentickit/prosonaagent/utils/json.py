import json
from typing import Any


def safe_get_value(content: Any, key: str, default: str = "") -> str:
    """
    安全地从content字段中获取值，支持字典和JSON字符串格式

    Args:
        content: content字段，可能是字典或JSON字符串
        key: 要获取的键名
        default: 默认值

    Returns:
        str: 获取到的值或默认值
    """
    try:
        if isinstance(content, dict):
            return content.get(key, default)
        elif isinstance(content, str):
            if content.strip():
                parsed_content = json.loads(content)
                return parsed_content.get(key, default)
            else:
                return default
        else:
            return default
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        return default
