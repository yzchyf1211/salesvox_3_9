"""
授课报告客户端

提供获取授课报告的接口，内部调用review graph生成报告。
（从 aitutor-magic-agent 的 LectureReviewClient 迁移，适配 prosona-agent 状态结构）
"""

import asyncio
import copy
import json
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from agentickit.core.exception import AgenticException

from app.schema.lecture_review_types import LectureReviewModel
from app.infra.redis_client import get_redis_client

logger = logging.getLogger(__name__)


def format_learning_duration(minutes: float) -> str:
    """格式化学习时长（从原始 load_content 中提取）"""
    if minutes < 1:
        return "不足1分钟"
    elif minutes < 60:
        return f"{int(minutes)}分钟"
    else:
        hours = int(minutes / 60)
        remaining = int(minutes % 60)
        if remaining > 0:
            return f"{hours}小时{remaining}分钟"
        return f"{hours}小时"


def get_effective_count(sco_list: list) -> int:
    """
    获取有效互动次数：直接计算问答题SCO数量
    （从 aitutor-magic-agent review_calculate_duration_node.get_effective_count 迁移）
    """
    count = 0
    for sco in sco_list:
        if sco.get("type") == "quiz":
            count += 1
    return count


async def get_user_study_time_from_api(
    context_id: str,
    project_id: str,
    user_id: str,
    activity_id: str,
) -> int:
    """
    调用API获取用户学习时长
    （从 aitutor-magic-agent review_calculate_duration_node.get_user_study_time_from_api 迁移，
     适配 prosona-agent 的 HTTP client）

    Returns:
        int: 学习时长（分钟），如果API调用失败返回0
    """
    from app.api import _get_client

    endpoint = "aitutor/sco/stu/learn/userStudyTimes"
    params = {
        "projectId": project_id,
        "userId": user_id,
        "activityId": activity_id,
        "contextId": context_id,
    }

    try:
        logger.info(
            f"[get_user_study_time_from_api] 调用学习时长API: "
            f"projectId={project_id}, userId={user_id}, activityId={activity_id}"
        )

        client = _get_client(context_id)
        response = await client.request(method="GET", url=endpoint, params=params)
        response.raise_for_status()
        response_data = response.json()

        if isinstance(response_data, dict):
            study_time_ms = (
                response_data.get("data", {}).get("studyTimeMs")
                or response_data.get("studyTimeMs")
                or response_data.get("studyTime")
                or response_data.get("data")
                or 0
            )
        else:
            study_time_ms = (
                response_data if isinstance(response_data, (int, float)) else 0
            )

        study_time_minutes = max(1, int(study_time_ms / 60))
        logger.info(
            f"[get_user_study_time_from_api] API返回学习时长: "
            f"{study_time_ms}秒 = {study_time_minutes}分钟"
        )
        return study_time_minutes

    except Exception as e:
        logger.error(
            f"[get_user_study_time_from_api] 调用学习时长API异常: {e}", exc_info=True
        )
        return 0


class LectureReviewClient:
    """授课报告客户端（从 aitutor-magic-agent 迁移）"""

    def __init__(self):
        self.redis_client = get_redis_client()

    async def start_lecture_review_async(
        self,
        state: Dict[str, Any],
        learning_duration_minutes: float = 0.0,
        learning_duration_formatted: str = "",
        effective_count: int = 0,
    ) -> str:
        """
        启动异步授课报告生成任务

        Returns:
            str: UUID，用作 Redis 的 key
        """
        try:
            task_uuid = str(uuid.uuid4())
            redis_key = f"aitutor:lecture_review:{task_uuid}"

            logger.info(
                f"[LectureReviewClient] 启动异步授课报告生成任务, UUID={task_uuid}, "
                f"学习时长={learning_duration_minutes}分钟, 互动次数={effective_count}"
            )

            initial_status = {
                "status": "in_progress",
                "completion_status": 1,
                "created_at": datetime.now().isoformat(),
                "learning_duration_minutes": learning_duration_minutes,
                "learning_duration_formatted": learning_duration_formatted,
                "effective_count": effective_count,
            }
            await self.redis_client.aset(
                redis_key,
                json.dumps(initial_status, ensure_ascii=False),
                ex=3600,
            )

            state_copy = copy.deepcopy(state)

            asyncio.create_task(
                self._generate_review_async(
                    task_uuid,
                    redis_key,
                    state_copy,
                    learning_duration_minutes,
                    learning_duration_formatted,
                    effective_count,
                )
            )

            logger.info(f"[LectureReviewClient] 异步任务已启动, UUID={task_uuid}")
            return task_uuid

        except Exception as e:
            logger.error(
                f"[LectureReviewClient] 启动异步任务失败, error={e}", exc_info=True
            )
            raise AgenticException(
                "error.agentic_server.lecture_review.start_async_error", str(e)
            )

    async def _generate_review_async(
        self,
        task_uuid: str,
        redis_key: str,
        state: Dict[str, Any],
        learning_duration_minutes: float = 0.0,
        learning_duration_formatted: str = "",
        effective_count: int = 0,
    ) -> None:
        """
        后台异步生成授课报告并存储到 Redis
        （依赖 run_learning_review_workflow，需要在实际部署时对接报告生成服务）
        """
        try:
            logger.info(
                f"[LectureReviewClient] 开始生成授课报告, UUID={task_uuid}"
            )

            from app.graph.review.learning_journey_review_graph import (
                run_learning_review_workflow,
            )

            activity = state.get("activity", {})
            activity_id = activity.get("id", "")
            duration_results = None

            if learning_duration_minutes > 0 and activity_id:
                duration_results = {
                    activity_id: {
                        "learning_duration_minutes": learning_duration_minutes,
                        "data_source": "pre_calculated",
                        "activity_id": activity_id,
                    }
                }

            review_data = await run_learning_review_workflow(
                user_input="",
                initial_state=state,
                duration_results=duration_results,
                effective_count=effective_count,
            )

            if not review_data:
                raise AgenticException(
                    "error.agentic_server.lecture_review.no_review_data",
                    "报告生成失败：未找到报告数据",
                )

            lecture_review_model = self._convert_to_model(review_data)

            result_data = {
                "status": "completed",
                "completion_status": 2,
                "completed_at": datetime.now().isoformat(),
                "data": lecture_review_model.model_dump(),
            }
            await self.redis_client.aset(
                redis_key,
                json.dumps(result_data, ensure_ascii=False),
                ex=3600,
            )

            logger.info(
                f"[LectureReviewClient] 授课报告生成成功, UUID={task_uuid}"
            )

        except Exception as e:
            logger.error(
                f"[LectureReviewClient] 授课报告生成失败, UUID={task_uuid}, error={e}",
                exc_info=True,
            )
            error_data = {
                "status": "failed",
                "completion_status": 0,
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
            }
            try:
                await self.redis_client.aset(
                    redis_key,
                    json.dumps(error_data, ensure_ascii=False),
                    ex=3600,
                )
            except Exception as redis_error:
                logger.error(
                    f"[LectureReviewClient] 存储错误状态到 Redis 失败: {redis_error}"
                )

    async def get_lecture_review_from_redis(
        self,
        task_uuid: str,
        timeout_seconds: int = 60,
        poll_interval: float = 0.5,
    ) -> Optional[LectureReviewModel]:
        """
        从 Redis 获取授课报告（带轮询和超时机制）

        Returns:
            LectureReviewModel: 授课报告数据，如果未完成或超时则返回 None
        """
        import time

        redis_key = f"aitutor:lecture_review:{task_uuid}"
        start_time = time.time()

        logger.info(
            f"[LectureReviewClient] 开始轮询获取报告, UUID={task_uuid}, "
            f"超时={timeout_seconds}秒"
        )

        while True:
            try:
                elapsed_time = time.time() - start_time
                if elapsed_time >= timeout_seconds:
                    logger.warning(
                        f"[LectureReviewClient] 获取报告超时, UUID={task_uuid}, "
                        f"已等待={elapsed_time:.1f}秒"
                    )
                    error_data = {
                        "status": "failed",
                        "completion_status": 0,
                        "error": f"获取报告超时，已等待{elapsed_time:.1f}秒",
                        "timeout_at": datetime.now().isoformat(),
                    }
                    try:
                        await self.redis_client.aset(
                            redis_key,
                            json.dumps(error_data, ensure_ascii=False),
                            ex=3600,
                        )
                    except Exception as redis_error:
                        logger.error(
                            f"[LectureReviewClient] 更新超时状态失败: {redis_error}"
                        )
                    return None

                result_str = await self.redis_client.aget(redis_key)

                if not result_str:
                    await asyncio.sleep(poll_interval)
                    continue

                result_data = json.loads(result_str)
                status = result_data.get("status")

                if status == "completed":
                    data = result_data.get("data")
                    if data:
                        logger.info(
                            f"[LectureReviewClient] 报告生成完成, UUID={task_uuid}, "
                            f"耗时={elapsed_time:.1f}秒"
                        )
                        return LectureReviewModel(**data)
                    else:
                        logger.error(
                            f"[LectureReviewClient] 报告数据为空, UUID={task_uuid}"
                        )
                        return None

                elif status == "in_progress":
                    logger.debug(
                        f"[LectureReviewClient] 报告生成中, UUID={task_uuid}, "
                        f"已等待={elapsed_time:.1f}秒"
                    )
                    await asyncio.sleep(poll_interval)
                    continue

                elif status == "failed":
                    logger.error(
                        f"[LectureReviewClient] 报告生成失败, UUID={task_uuid}, "
                        f"error={result_data.get('error')}"
                    )
                    return None

                logger.warning(
                    f"[LectureReviewClient] 未知状态: {status}, UUID={task_uuid}"
                )
                await asyncio.sleep(poll_interval)
                continue

            except json.JSONDecodeError as e:
                logger.error(
                    f"[LectureReviewClient] JSON 解析失败, UUID={task_uuid}, error={e}",
                    exc_info=True,
                )
                await asyncio.sleep(poll_interval)
                continue

            except Exception as e:
                logger.error(
                    f"[LectureReviewClient] 轮询过程中出现异常, UUID={task_uuid}, error={e}",
                    exc_info=True,
                )
                await asyncio.sleep(poll_interval)
                continue

    def _convert_to_model(self, review_data) -> LectureReviewModel:
        """将 ActivityReviewData 转换为 LectureReviewModel"""
        start_time = None
        end_time = None
        if review_data.start_time:
            if isinstance(review_data.start_time, datetime):
                start_time = review_data.start_time.isoformat()
            else:
                start_time = str(review_data.start_time)

        if review_data.end_time:
            if isinstance(review_data.end_time, datetime):
                end_time = review_data.end_time.isoformat()
            else:
                end_time = str(review_data.end_time)

        return LectureReviewModel(
            activity_id=review_data.activity_id,
            activity_name=review_data.activity_name,
            completion_status=review_data.completion_status,
            learning_duration_minutes=review_data.learning_duration_minutes,
            learning_duration_formatted=review_data.get_formatted_duration(),
            start_time=start_time,
            end_time=end_time,
            interaction_count=review_data.interaction_count,
            highlights=review_data.highlights,
            learning_suggestions=review_data.learning_suggestions,
            summary=review_data.summary,
            artifact_id=review_data.artifact_id,
            report_name=review_data.report_name,
            report_title=review_data.report_title,
        )
