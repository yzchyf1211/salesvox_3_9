"""
学习回顾开始节点
（从 aitutor-magic-agent 迁移，移除 @async_agentic_node 装饰器）
"""

import logging
from typing import Dict, Any

from app.utils.review_utils import start_review_generation
from app.graph.review.state import ReviewState

logger = logging.getLogger(__name__)


async def review_start_node(state: ReviewState) -> Dict[str, Any]:
    logger.info("开始学习回顾分析...")

    current_activity = state.get("current_activity")
    if not current_activity:
        logger.warning("没有找到当前活动")
        return {}

    if hasattr(current_activity, "dict") and callable(current_activity.dict):
        current_activity_dict = current_activity.dict()
    elif isinstance(current_activity, dict):
        current_activity_dict = current_activity
    else:
        current_activity_dict = {
            "activity_id": getattr(current_activity, "activity_id"),
            "activity_name": getattr(current_activity, "activity_name"),
        }

    logger.info(f"准备分析当前活动: {current_activity_dict.get('activity_name', '')}")

    start_review_generation(state)

    return {}
