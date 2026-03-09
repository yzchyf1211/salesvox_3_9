"""
学习回顾工具函数
（从 aitutor-magic-agent review_utils.py 直接迁移）
"""

import logging
from typing import Optional, Dict, Any

from app.schema.learning_review_schema import ActivityReviewData

logger = logging.getLogger(__name__)


def get_or_create_activity_review(
    state: Dict[str, Any],
    activity_id: str,
    activity_name: str,
) -> ActivityReviewData:
    current_review = state.get("current_activity_review")

    if current_review is None or current_review.activity_id != activity_id:
        logger.info(f"创建新的活动回顾数据: {activity_name} ({activity_id})")
        current_review = ActivityReviewData(
            activity_id=activity_id, activity_name=activity_name
        )
        state["current_activity_review"] = current_review

    return current_review


def start_review_generation(
    state: Dict[str, Any],
) -> Optional[ActivityReviewData]:
    try:
        current_activity = state.get("current_activity")
        if not current_activity:
            logger.warning("没有找到当前活动")
            return None

        if hasattr(current_activity, "activity_id"):
            activity_id = current_activity.activity_id
            activity_name = current_activity.activity_name
        elif isinstance(current_activity, dict):
            activity_id = current_activity.get("activity_id", "")
            activity_name = current_activity.get("activity_name", "")
        else:
            activity_id = ""
            activity_name = ""

        review = get_or_create_activity_review(state, activity_id, activity_name)
        review.start_generation()

        logger.info(f"开始生成活动回顾: {activity_name} ({activity_id})")
        return review

    except Exception as e:
        logger.error(f"开始回顾生成失败: {e}", exc_info=True)
        return None


def finish_review_generation(
    state: Dict[str, Any],
) -> Optional[ActivityReviewData]:
    try:
        current_review = state.get("current_activity_review")
        if current_review:
            current_review.finish_generation()
            logger.info(f"完成活动回顾生成: {current_review.activity_name}")
            return current_review
        else:
            logger.warning("没有找到当前活动回顾数据")
            return None
    except Exception as e:
        logger.error(f"完成回顾生成失败: {e}", exc_info=True)
        return None
