"""
学习回顾精彩时刻聚合节点
（从 aitutor-magic-agent 迁移，移除 @async_agentic_node 装饰器，
  适配 prosona-agent 的 tracking / redis / user 模块）
"""

import asyncio
import json
import logging
from typing import Any, Dict

from app.graph.review.review_common import get_current_activity_info
from app.graph.review.state import ReviewState
from app.utils.tracking_utils import TrackingReportUtils
from app.infra.redis_client import get_redis_client
from app.enums.report_action_code_enum import ReportActionCodeEnum
from app.utils.user_utils import get_token

logger = logging.getLogger(__name__)


def _get_highlights_from_redis(context_id: str, activity_id: str) -> list:
    if not context_id or not activity_id:
        return []

    try:
        redis_client = get_redis_client()
        results_key = f"highlight:results:{context_id}:{activity_id}"

        results_json = redis_client.get(results_key)
        if not results_json:
            return []

        return json.loads(results_json)
    except Exception as e:
        logger.warning(f"从 Redis 获取高光结果失败: {e}")
        return []


async def _wait_for_highlight_tasks_via_redis(
    context_id: str, activity_id: str, timeout: int = 10
) -> None:
    if not context_id or not activity_id:
        return

    try:
        redis_client = get_redis_client()
        tasks_key = f"highlight:tasks:{context_id}:{activity_id}"

        tasks_json = redis_client.get(tasks_key)
        if not tasks_json:
            logger.info("Redis 中无高光分析任务记录")
            return

        tasks_list = json.loads(tasks_json)
        if not tasks_list:
            logger.info("高光分析任务列表为空")
            return

        logger.info(
            f"等待 {len(tasks_list)} 个高光分析任务完成（最多 {timeout} 秒）..."
        )

        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(
                    f"高光分析任务等待超时（{timeout}秒），将使用当前已有的高光结果"
                )
                break

            all_completed = True
            for sco_id in tasks_list:
                task_key = (
                    f"highlight:task:{context_id}:{activity_id}:{sco_id}"
                )
                status = redis_client.get(task_key)
                if status != "completed":
                    all_completed = False
                    break

            if all_completed:
                logger.info("所有高光分析任务已完成")
                break

            await asyncio.sleep(0.5)

    except Exception as e:
        logger.warning(f"通过 Redis 等待高光任务时出错: {e}")


def _validate_highlight_item(item: dict) -> bool:
    if not isinstance(item, dict):
        return False

    required_fields = ["type", "score", "reference", "comment", "summary"]
    for field in required_fields:
        if field not in item:
            return False

    type_value = item.get("type")
    if isinstance(type_value, str):
        try:
            type_value = int(type_value)
            item["type"] = type_value
        except (TypeError, ValueError):
            logger.warning(f"type is not a valid int: {item.get('type')}")
            return False

    if not isinstance(type_value, (int, float)):
        logger.warning(f"type is not a number: {type_value}")
        return False

    score_value = item.get("score")
    if isinstance(score_value, str):
        try:
            score_value = float(score_value)
            item["score"] = score_value
        except (TypeError, ValueError):
            logger.warning(f"score is not a valid number: {item.get('score')}")
            return False

    if not isinstance(score_value, (int, float)):
        logger.warning(f"score is not a number: {score_value}")
        return False

    reference = item.get("reference")
    if not isinstance(reference, dict):
        logger.warning(f"reference is not a dict: {reference}")
        return False

    if not isinstance(item.get("comment"), str):
        return False
    if not isinstance(item.get("summary"), str):
        return False

    return True


async def review_generate_highlights_v2_node(
    state: ReviewState,
) -> Dict[str, Any]:
    logger.info("开始聚合高光时刻")
    current_activity = None
    try:
        current_activity = get_current_activity_info(state)

        if not current_activity:
            logger.warning("未找到当前活动，跳过高光聚合")
            return {}

        activity_id = current_activity.get("activity_id", "")
        context_id = state.get("context_id", "")

        await _wait_for_highlight_tasks_via_redis(
            context_id, activity_id, timeout=10
        )

        highlights_raw = _get_highlights_from_redis(context_id, activity_id)

        if not highlights_raw:
            logger.info(
                f"活动 {current_activity.get('activity_name', '')} 暂无高光时刻数据"
            )
            return {}

        logger.info(f"从 Redis 获取到 {len(highlights_raw)} 个高光时刻")

        highlights = []
        highlights_track = []
        for item in highlights_raw:
            if isinstance(item, dict) and "comment" in item:
                if _validate_highlight_item(item):
                    title = item.get("summary") or ""
                    description = item.get("comment", "")

                    type_code = (
                        "CognitiveAwareness"
                        if item.get("type") == 2
                        else (
                            "AppliedReflection"
                            if item.get("type") == 3
                            else ""
                        )
                    )

                    dialogue = item.get("reference", {}).get("dialogue", [])

                    if title or description:
                        highlights.append(
                            {
                                "title": title,
                                "description": description,
                                "type_code": type_code,
                                "dialogue": dialogue,
                            }
                        )

                    highlights_track.append(item)
                else:
                    logger.warning(
                        f"高光时刻item结构校验失败，跳过追踪: {item}"
                    )

        highlights_results = {activity_id: highlights}

        review = state.get("current_activity_review")
        if review:
            review.review_highlights_results = highlights_results
        else:
            logger.warning(
                "current_activity_review 不存在，跳过高光结果更新"
            )

        logger.info(
            f"{current_activity.get('activity_name', '')}: 聚合高光时刻{len(highlights)}个"
        )

        if highlights:
            await asyncio.to_thread(
                _tracking_highlights_results, state, highlights_track
            )
            logger.info("上报当前活动的高光时刻成功")

        return {}

    except Exception as e:
        act_name = (
            current_activity.get("activity_name", "未知活动")
            if current_activity
            else "未知活动"
        )
        logger.error(f"聚合活动 {act_name} 高光时刻时出错: {e}", exc_info=True)
        return {}


def _tracking_highlights_results(
    state: Dict[str, Any], highlights_raw: list[dict]
) -> None:
    project_info = state.get("project_info")
    project_id = project_info.get("project_id") if project_info else None
    if not project_id:
        logger.warning("project_id为空，跳过高光时刻上报")
        return
    activity_id = state.get("current_activity", {}).get("activity_id")
    data_items = [
        {"text_val": json.dumps(highlight, ensure_ascii=False)}
        for highlight in highlights_raw
    ]
    TrackingReportUtils(
        state=state, token=get_token(state.get("context_id"))
    ).report_custom_action(
        project_id=project_id,
        action_code=ReportActionCodeEnum.LECTURE_HIGHLIGHT_CARD.action_code,
        actv_id=activity_id,
        data_items=data_items,
    )
