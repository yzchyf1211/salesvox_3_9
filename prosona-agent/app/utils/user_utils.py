"""
用户相关工具函数
（从 aitutor-magic-agent common/user.py 直接迁移，适配 prosona-agent）
"""

from typing import Dict, Any, List, Optional
from threading import Lock

from agentickit.core.context.agentic_context_manager import context_saver

DEFAULT_LANGUAGE = "zh_CN"

_LOCALE_CONFIG: dict[str, str] = {}
_locale_lock = Lock()

LANGUAGE_NAMES = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "ha": "繁体中文",
    "zh_CN": "中文",
    "en_US": "英文",
    "ja_JP": "日文",
    "zh_TW": "繁体中文",
    "zh-CN": "中文",
    "en-US": "英文",
    "ja-JP": "日文",
    "zh-TW": "繁体中文",
}

LANGUAGE_TO_LOCALE = {
    "zh": "zh_CN",
    "en": "en",
    "ja": "ja",
    "ha": "zh_TW",
    "zh_CN": "zh_CN",
    "en_US": "en",
    "ja_JP": "ja",
    "zh_TW": "zh_TW",
    "zh-CN": "zh_CN",
    "en-US": "en",
    "ja-JP": "ja",
    "zh-TW": "zh_TW",
}

ROLE_LABELS = {
    "zh": {"teacher": "老师", "student": "学员"},
    "en": {"teacher": "Teacher", "student": "Student"},
    "ja": {"teacher": "講師", "student": "受講者"},
    "ha": {"teacher": "老師", "student": "學生"},
    "zh_TW": {"teacher": "老師", "student": "學生"},
    "en_US": {"teacher": "Teacher", "student": "Student"},
    "ja_JP": {"teacher": "講師", "student": "受講者"},
    "zh_CN": {"teacher": "老师", "student": "学员"},
    "zh-CN": {"teacher": "老师", "student": "学员"},
    "en-US": {"teacher": "Teacher", "student": "Student"},
    "ja-JP": {"teacher": "講師", "student": "受講者"},
    "zh-TW": {"teacher": "老師", "student": "學生"},
}


def get_token(context_id: str) -> Optional[str]:
    if not context_id:
        return None
    agentic_context = context_saver.load(context_id)
    request_header = agentic_context.get("request_header", {})
    return request_header.get("token", "")


def get_language_name(state: Dict[str, Any]) -> str:
    context_id = state.get("context_id", "")
    locale = get_locale(context_id)
    return LANGUAGE_NAMES.get(locale, "中文")


def get_role_label(state: Dict[str, Any], role: str) -> str:
    context_id = state.get("context_id", "")
    locale = get_locale(context_id)
    labels = ROLE_LABELS.get(locale, ROLE_LABELS[DEFAULT_LANGUAGE])
    return labels.get(role, role)


def get_language_locale(state: Dict[str, Any]) -> str:
    context_id = state.get("context_id", "")
    locale = get_locale(context_id)
    return LANGUAGE_TO_LOCALE.get(locale, DEFAULT_LANGUAGE)


def set_locale(context_id: str, locale: str) -> None:
    global _LOCALE_CONFIG
    if not context_id:
        return
    with _locale_lock:
        _LOCALE_CONFIG[context_id] = locale


def get_locale(context_id: str) -> Optional[str]:
    global _LOCALE_CONFIG
    if not context_id:
        return None
    with _locale_lock:
        return _LOCALE_CONFIG.get(context_id)
