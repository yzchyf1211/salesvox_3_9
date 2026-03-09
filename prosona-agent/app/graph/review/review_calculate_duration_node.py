"""
学习回顾时长计算
（从 aitutor-magic-agent review_calculate_duration_node.py 迁移，
  仅保留 calculate_duration_and_count 供 run_learning_review_workflow 降级使用）
"""

import logging
from typing import Dict, Any, Tuple

from agentickit.core.context.agentic_context_manager import context_saver

from app.graph.review.review_common import get_current_activity_info
from app.graph.review.state import ReviewState
from app.services.lecture_review_client import get_user_study_time_from_api

logger = logging.getLogger(__name__)


def _get_effective_count(current_activity: dict) -> int:
    """获取有效互动次数：直接计算问答题SCO数量"""
    scos = current_activity.get("scos", [])
    effective_count = 0
    for sco in scos:
        if sco.get("sco_type") == "问答题":
            effective_count += 1
    return effective_count


async def calculate_duration_and_count(
    state: ReviewState,
) -> Tuple[Dict[str, Any], int]:
    logger.info("开始计算学习时长和互动次数...")

    try:
        current_activity = get_current_activity_info(state)
        if not current_activity:
            return {}, 0

        project_info = state.get("project_info")
        if not project_info:
            logger.warning("未找到项目信息")
            return {}, 0

        if hasattr(project_info, "project_id"):
            project_id = project_info.project_id
        elif isinstance(project_info, dict):
            project_id = project_info.get("project_id")
        else:
            project_id = getattr(project_info, "project_id")

        activity_id = current_activity.get("activity_id")

        context_id = state.get("context_id")
        context = context_saver.load(context_id)
        user_id = context.get("user_profile", {}).get("user_id")

        if not user_id:
            logger.warning("未找到用户ID")
            return {}, 0

        learning_duration_minutes = await get_user_study_time_from_api(
            context_id, project_id, user_id, activity_id
        )

        logger.info(
            f"{current_activity.get('name', '未知活动')}: 最终学习时长 {learning_duration_minutes} 分钟"
        )

        duration_results = {
            current_activity.get("activity_id"): {
                "learning_duration_minutes": learning_duration_minutes,
                "data_source": "api"
                if user_id and learning_duration_minutes > 0
                else "fallback",
                "project_id": project_id,
                "user_id": user_id,
                "activity_id": activity_id,
            }
        }

        effective_count = _get_effective_count(current_activity)

        logger.info(
            f"时长计算完成: {learning_duration_minutes}分钟, 互动次数: {effective_count}"
        )

        return duration_results, effective_count

    except Exception as e:
        logger.error(f"时长和互动次数计算失败: {e}", exc_info=True)
        return {}, 0
