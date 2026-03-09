"""
学习回顾通用工具函数和配置
（从 aitutor-magic-agent review_common.py 迁移，适配 prosona-agent LLM 客户端）
"""

import json
import logging
import re
from typing import List, Dict, Any

from agentickit.core.infra.models import get_model_with_fallbacks
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from app.schema.learning_review_schema import ActivityReviewData
from app.utils.user_utils import get_role_label

logger = logging.getLogger(__name__)

llm = get_model_with_fallbacks("main").with_config(
    RunnableConfig(tags=["filtered"])
)


def get_messages_by_activity(all_messages: List, activity_id: str) -> List:
    filtered_messages = []
    for msg in all_messages:
        if hasattr(msg, "additional_kwargs"):
            msg_activity_id = msg.additional_kwargs.get("activity_id")
            if msg_activity_id == activity_id:
                filtered_messages.append(msg)
        elif not filtered_messages:
            filtered_messages.append(msg)

    return filtered_messages if filtered_messages else all_messages


def parse_json_response(response_content: str):
    content = response_content.strip() if response_content else ""

    try:
        if content.startswith("```") and content.endswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        return json.loads(content)

    except json.JSONDecodeError as e:
        logger.warning(f"JSON解析失败，尝试使用正则表达式提取: {e}")

        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, content, re.DOTALL)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        logger.error(f"无法解析JSON响应: {content}")
        return {
            "analysis": [],
            "effective_count": 0,
            "total_count": 0,
            "effectiveness_rate": 0,
        }
    except Exception as e:
        logger.error(
            f"解析JSON时发生未预期的错误: {e}, 原始内容: {content}", exc_info=True
        )
        return {
            "analysis": [],
            "effective_count": 0,
            "total_count": 0,
            "effectiveness_rate": 0,
        }


def parse_highlights_json_response(response_content: str) -> dict:
    try:
        result = parse_json_response(response_content)
        if "highlights" not in result:
            result["highlights"] = ["学习态度积极认真"]
        return result
    except Exception as e:
        logger.error(f"解析精彩时刻响应失败: {e}", exc_info=True)
        return {"highlights": ["学习态度积极认真"]}


def parse_suggestions_json_response(response_content: str) -> dict:
    try:
        result = parse_json_response(response_content)
        if "suggestions" not in result:
            result["suggestions"] = ["建议继续保持学习热情"]
        return result
    except Exception as e:
        logger.error(f"解析学习建议响应失败: {e}", exc_info=True)
        return {"suggestions": ["建议继续保持学习热情"]}


def analyze_activity_messages(
    activity: Dict[str, Any], all_messages: List
) -> Dict[str, Any]:
    activity_messages = []
    first_timestamp = None
    last_timestamp = None

    for msg in get_messages_by_activity(all_messages, activity["activity_id"]):
        if isinstance(msg, (HumanMessage, AIMessage)):
            activity_messages.append(msg)

            if (
                hasattr(msg, "additional_kwargs")
                and "timestamp" in msg.additional_kwargs
            ):
                timestamp = msg.additional_kwargs["timestamp"]
                if first_timestamp is None:
                    first_timestamp = timestamp
                last_timestamp = timestamp

    return {
        "activity_messages": activity_messages,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
    }


def fallback_interaction_analysis(message_analysis: Dict[str, Any]) -> int:
    activity_messages = message_analysis.get("activity_messages", [])
    effective_interactions = 0

    for msg in activity_messages:
        if isinstance(msg, HumanMessage):
            content = msg.content.strip() if msg.content else ""

            if (
                len(content) >= 5
                and not any(
                    keyword in content.lower()
                    for keyword in ["天气", "游戏", "电影", "购物"]
                )
                and content.strip() not in ["好", "嗯", "ok", "好的", "知道了"]
            ):
                effective_interactions += 1

    return effective_interactions


def format_conversation_history(
    messages: List, state: Dict[str, Any] = None
) -> str:
    formatted_messages = []

    teacher_label = get_role_label(state, "teacher") if state else "老师"
    student_label = get_role_label(state, "student") if state else "学员"

    for msg in messages:
        if hasattr(msg, "additional_kwargs"):
            if (
                isinstance(msg, AIMessage)
                and msg.additional_kwargs.get("__role__") == "teacher"
            ):
                formatted_messages.append(
                    f"{teacher_label}: {msg.additional_kwargs.get('__content__', '')}"
                )
            elif (
                isinstance(msg, HumanMessage)
                and msg.additional_kwargs.get("__role__") == "student"
            ):
                formatted_messages.append(
                    f"{student_label}: {msg.additional_kwargs.get('__content__', '')}"
                )

    return "\n".join(formatted_messages) if formatted_messages else "暂无对话记录"


def get_current_activity_info(state: Dict[str, Any]) -> dict[str, Any]:
    current_activity = state.get("current_activity")
    if not current_activity:
        logger.warning("没有找到当前活动")
        return None

    activity_sco_list = state.get("activity_sco_list", {}).get(
        current_activity.get("activity_id", ""), []
    )
    if not activity_sco_list:
        logger.warning("没有找到当前活动对应的教学内容")
        return None
    scos = [item for item in activity_sco_list if item.get("sco_type") == "问答题"]

    if hasattr(current_activity, "dict") and callable(current_activity.dict):
        current_activity_dict = current_activity.dict()
        current_activity_dict["scos"] = scos
    elif isinstance(current_activity, dict):
        current_activity_dict = current_activity
        current_activity_dict["scos"] = scos
    else:
        try:
            current_activity_dict = {
                "activity_id": getattr(
                    current_activity,
                    "actvId",
                    getattr(current_activity, "activity_id", "unknown"),
                ),
                "name": getattr(current_activity, "name", "未知活动"),
                "learning_goals": getattr(current_activity, "learning_goals", ""),
                "core_content": getattr(current_activity, "core_content", []),
                "practical_skills": getattr(current_activity, "practical_skills", []),
                "content": getattr(current_activity, "content", ""),
                "activity_type": getattr(current_activity, "activity_type", ""),
                "narration": getattr(current_activity, "narration", ""),
                "current_sco_index": getattr(
                    current_activity, "current_sco_index", 0
                ),
                "scos": scos,
            }
        except Exception as e:
            logger.error(f"转换当前活动为字典时出错: {e}", exc_info=True)
            current_activity_dict = {
                "activity_id": "unknown",
                "name": "未知活动",
                "learning_goals": "",
                "core_content": [],
                "practical_skills": [],
                "content": "",
                "activity_type": "",
                "narration": "",
                "current_sco_index": 0,
                "scos": [],
            }

    return current_activity_dict


def get_llm_client():
    return llm
