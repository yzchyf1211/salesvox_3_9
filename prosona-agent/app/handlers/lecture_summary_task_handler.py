"""
Lecture Summary SCO TaskHandler - 授课总结类型SCO的处理器

从 aitutor-magic-agent 的 SCOLectureSummaryPlugin 迁移而来，
通过 prosona-agent 的 TaskHandler 模式实现（仅 study 模式）。

原始方法映射:
- SCOLectureSummaryPlugin.load_content()                 -> abefore(): 计算时长 + 启动异步报告生成
- SCOLectureSummaryPlugin.get_content_context()           -> abefore(): 注入内容上下文
- SCOLectureSummaryPlugin.get_teach_design_context()      -> abefore(): 注入教学设计上下文
- SCOLectureSummaryPlugin.get_action_schema_context()     -> abefore(): 注入动作结构上下文
- SCOLectureSummaryPlugin.get_system_feedback_schema_context -> abefore(): 注入系统反馈结构上下文
- SCOLectureSummaryPlugin.get_reminder_context()          -> abefore(): 注入提醒上下文
- SCOLectureSummaryPlugin.render_action()                 -> aget_card(): 构建AOMCard
- SCOLectureSummaryPlugin.run_lifecycle(RESUME)           -> aresume(): 注入恢复上下文
- SCOLectureSummaryPlugin._fetch_review_from_redis_if_needed -> aget_card 发送前调用，内部轮询等待
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from agentickit.prosonaagent.aom.card import build_content_card
from agentickit.prosonaagent.core.handler.enhance_task_handler import EnhanceTaskHandler
from agentickit.prosonaagent.aom.types import AOMCard
from agentickit.prosonaagent.aom.state import SCOTaskState
from agentickit.prosonaagent.core.tools import _builtin_conversation

from app.api import get_prompt_client
from app.services.lecture_review_client import (
    LectureReviewClient,
    format_learning_duration,
    get_effective_count,
    get_user_study_time_from_api,
)

logger = logging.getLogger(__name__)

# Langfuse prompt keys（对应原始 PromptConstants）
_PROMPT_CONTENT = "v2/plugin/sco/lecture-summary/content"
_PROMPT_LIFECYCLE_STRATEGY = "v2/plugin/sco/lecture-summary/lifecycle_strategy"
_PROMPT_ACTION_SCHEMA = "v2/plugin/sco/lecture-summary/action_schema"
_PROMPT_SYSTEM_FEEDBACK_SCHEMA = (
    "v2/plugin/sco/lecture-summary/system_feedback_schema"
)
_PROMPT_REMINDER = "v2/plugin/sco/lecture-summary/reminder"
_PROMPT_LIFECYCLE_RESUME_CONTEXT = (
    "v2/plugin/sco/lecture-summary/lifecycle_resume_context"
)
_PROMPT_OBSERVE_ACTION_BASIC_DATA = (
    "v2/plugin/sco/lecture-summary/observe_action_basic_data"
)
_PROMPT_OBSERVE_ACTION_HIGHLIGHTS = (
    "v2/plugin/sco/lecture-summary/observe_action_highlights"
)
_PROMPT_OBSERVE_ACTION_LEARNING_SUGGESTIONS = (
    "v2/plugin/sco/lecture-summary/observe_action_learning_suggestions"
)


# ==================== Helper Functions ====================


def _format_highlights(highlights: List[Dict[str, str]]) -> str:
    """格式化精彩时刻列表（从原始插件直接迁移）"""
    return "\n".join(
        [f"{item['title']}: {item['description']}" for item in highlights]
    )


def _format_learning_suggestions(
    learning_suggestions: List[Dict[str, str]],
) -> str:
    """格式化学习建议列表（从原始插件直接迁移）"""
    return "\n".join(
        [
            f"{item['title']}: {item['description']}"
            for item in learning_suggestions
        ]
    )


# ==================== State ====================


class LectureSummaryTaskState(SCOTaskState):
    review_uuid: Optional[str]
    sco_content: Optional[Dict[str, Any]]


# ==================== Handler ====================


class LectureSummaryTaskHandler(EnhanceTaskHandler[LectureSummaryTaskState]):
    """授课总结SCO处理器（study 模式）"""

    name = "sco:lecture_summary"
    state_schema = LectureSummaryTaskState
    tools = [_builtin_conversation]

    # ==================== Lifecycle Hooks ====================

    async def abefore(
        self,
        state: LectureSummaryTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any] | None:
        delta_state: Dict[str, Any] = await super().abefore(state, runtime) or {}

        # ---- load_content 逻辑（从原始插件迁移）----
        review_uuid = state.get("review_uuid")
        if not review_uuid:
            review_uuid, sco_content = await self._load_content(state)
            delta_state["review_uuid"] = review_uuid
            delta_state["sco_content"] = sco_content
        else:
            sco_content = state.get("sco_content") or {}

        messages = delta_state.get("messages", [])

        # 1. 内容上下文（get_content_context）
        content_ctx = self._build_content_context(sco_content)
        if content_ctx:
            messages.append(SystemMessage(content=content_ctx))

        delta_state["messages"] = messages
        return delta_state

    async def aresume(
        self,
        state: LectureSummaryTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any] | None:
        """恢复学习 - 注入恢复上下文（从 run_lifecycle RESUME 迁移）"""
        delta_state: Dict[str, Any] = await super().aresume(state, runtime) or {}

        prompt_client = get_prompt_client(_PROMPT_LIFECYCLE_RESUME_CONTEXT)
        messages = delta_state.get("messages", [])
        messages.append(SystemMessage(content=prompt_client.compile()))
        delta_state["messages"] = messages
        return delta_state

    # ==================== Card Rendering ====================

    async def aget_card(
        self,
        state: LectureSummaryTaskState,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AOMCard:
        """
        构建授课总结的 AOMCard（从 render_action 迁移）

        支持的 action:
        - display_basic_data: 展示基本数据（时长、互动次数）
        - display_highlights: 展示精彩时刻
        - display_learning_suggestions / display_all: 展示学习建议（完整报告）
        """
        params = params or {}
        if isinstance(params, str):
            params = json.loads(params)

        sco_content = dict(state.get("sco_content") or {})
        review_uuid = state.get("review_uuid", "")

        # 根据 action 判断是否需要从 Redis 获取完整数据
        sco_content = await self._fetch_review_from_redis_if_needed(
            action, sco_content, review_uuid
        )

        activity_id = sco_content.get("activity_id", "")
        activity_name = sco_content.get("activity_name", "")
        learning_duration_formatted = sco_content.get(
            "learning_duration_formatted", ""
        )
        learning_duration_minutes = sco_content.get(
            "learning_duration_minutes", 0
        )
        interaction_count = sco_content.get("interaction_count", 0)
        highlights = sco_content.get("highlights", [])
        learning_suggestions = sco_content.get("learning_suggestions", [])
        artifact_id = sco_content.get("artifact_id", "")
        report_name = sco_content.get("report_name", "")
        report_title = sco_content.get("report_title", "")

        if action == "display_basic_data":
            return self._build_basic_data_card(
                activity_id=activity_id,
                activity_name=activity_name,
                interaction_count=interaction_count,
                learning_duration_minutes=learning_duration_minutes,
            )

        elif action == "display_highlights":
            return self._build_highlights_card(
                activity_id=activity_id,
                activity_name=activity_name,
                interaction_count=interaction_count,
                learning_duration_minutes=learning_duration_minutes,
                learning_duration_formatted=learning_duration_formatted,
                highlights=highlights,
            )

        elif action in ("display_learning_suggestions", "display_all"):
            return self._build_learning_suggestions_card(
                activity_id=activity_id,
                activity_name=activity_name,
                interaction_count=interaction_count,
                learning_duration_minutes=learning_duration_minutes,
                learning_duration_formatted=learning_duration_formatted,
                highlights=highlights,
                learning_suggestions=learning_suggestions,
                artifact_id=artifact_id,
                report_name=report_name,
                report_title=report_title,
            )

        return build_content_card(
            id="lecture-summary-fallback",
            name="授课总结",
            content={"action": action},
            description="",
        )

    # ==================== Card Builders ====================

    def _build_basic_data_card(
        self,
        activity_id: str,
        activity_name: str,
        interaction_count: int,
        learning_duration_minutes: float,
    ) -> AOMCard:
        """构建基本数据卡片（display_basic_data）"""
        content = {
            "activity_id": activity_id,
            "activity_name": activity_name,
            "interaction_count": str(interaction_count),
            "learning_duration_minutes": learning_duration_minutes,
        }

        prompt_client = get_prompt_client(_PROMPT_OBSERVE_ACTION_BASIC_DATA)
        description = prompt_client.compile(
            activity_name=activity_name,
            interaction_count=str(interaction_count),
            learning_duration_minutes=str(learning_duration_minutes),
        )

        return build_content_card(
            id="lecture-summary-basic-data",
            name="基本数据",
            content=content,
            description=description,
        )

    def _build_highlights_card(
        self,
        activity_id: str,
        activity_name: str,
        interaction_count: int,
        learning_duration_minutes: float,
        learning_duration_formatted: str,
        highlights: List[Dict],
    ) -> AOMCard:
        """构建精彩时刻卡片（display_highlights）"""
        content = {
            "activity_id": activity_id,
            "activity_name": activity_name,
            "learning_duration_minutes": learning_duration_minutes,
            "interaction_count": str(interaction_count),
            "highlights": highlights,
        }

        highlights_content = _format_highlights(highlights)
        prompt_client = get_prompt_client(_PROMPT_OBSERVE_ACTION_HIGHLIGHTS)
        description = prompt_client.compile(
            activity_name=activity_name,
            interaction_count=str(interaction_count),
            learning_duration_minutes=str(learning_duration_formatted),
            highlights=highlights_content,
        )

        return build_content_card(
            id="lecture-summary-highlights",
            name="精彩时刻",
            content=content,
            description=description,
        )

    def _build_learning_suggestions_card(
        self,
        activity_id: str,
        activity_name: str,
        interaction_count: int,
        learning_duration_minutes: float,
        learning_duration_formatted: str,
        highlights: List[Dict],
        learning_suggestions: List[Dict],
        artifact_id: str,
        report_name: str,
        report_title: str,
    ) -> AOMCard:
        """构建学习建议卡片（display_learning_suggestions / display_all）"""
        if learning_suggestions is None or len(learning_suggestions) == 0:
            learning_suggestions = []

        content = {
            "activity_id": activity_id,
            "activity_name": activity_name,
            "learning_duration_minutes": learning_duration_minutes,
            "interaction_count": str(interaction_count),
            "highlights": highlights,
            "learning_suggestions": learning_suggestions,
            "artifact_id": artifact_id,
            "report_name": report_name,
            "report_title": report_title,
        }

        highlights_content = _format_highlights(highlights)
        learning_suggestions_content = _format_learning_suggestions(
            learning_suggestions
        )
        prompt_client = get_prompt_client(
            _PROMPT_OBSERVE_ACTION_LEARNING_SUGGESTIONS
        )
        description = prompt_client.compile(
            activity_name=activity_name,
            interaction_count=str(interaction_count),
            learning_duration_minutes=str(learning_duration_formatted),
            highlights=highlights_content,
            learning_suggestions=learning_suggestions_content,
        )

        return build_content_card(
            id="lecture-summary-learning-suggestions",
            name="学习建议",
            content=content,
            description=description,
        )

    # ==================== Context Builders ====================

    def _build_content_context(self, sco_content: Dict[str, Any]) -> str:
        """构建内容上下文（从 get_content_context 迁移）"""
        highlights = sco_content.get("highlights", [])
        learning_suggestions = sco_content.get("learning_suggestions", [])
        interaction_count = sco_content.get("interaction_count", 0)
        learning_duration_minutes = sco_content.get(
            "learning_duration_minutes", 0
        )

        prompt_client = get_prompt_client(_PROMPT_CONTENT)
        return prompt_client.compile(
            interaction_count=str(interaction_count),
            learning_duration_minutes=str(learning_duration_minutes),
            highlights=_format_highlights(highlights),
            learning_suggestions=_format_learning_suggestions(
                learning_suggestions
            ),
        )

    # ==================== Data Loading ====================

    async def _load_content(
        self, state: LectureSummaryTaskState
    ) -> tuple:
        """
        加载SCO数据（从原始 load_content 迁移）

        1. 预先计算 duration 和 effective_count
        2. 启动异步授课报告生成任务
        3. 初始化 sco_content

        Returns:
            tuple: (review_uuid, sco_content)
        """
        logger.info(
            "[LectureSummaryTaskHandler] 开始预先计算学习时长和互动次数..."
        )

        activity = state.get("activity", {})
        activity_id = activity.get("id", "")
        activity_name = activity.get("name", "")
        sco_list = state.get("sco_list", [])
        context_id = state.get("context_id", "")
        user_profile = state.get("user_profile") or {}
        user_id = user_profile.get("user_id", "")
        project_id = state.get("project_id", "")

        learning_duration_minutes = 0.0
        learning_duration_formatted = "0分钟"
        effective_count = 0

        try:
            if context_id and project_id and user_id and activity_id:
                learning_duration_minutes = await get_user_study_time_from_api(
                    context_id, project_id, user_id, activity_id
                )

            learning_duration_formatted = format_learning_duration(
                learning_duration_minutes
            )
            effective_count = get_effective_count(sco_list)

            logger.info(
                f"[LectureSummaryTaskHandler] 预先计算完成: "
                f"学习时长={learning_duration_minutes}分钟, "
                f"互动次数={effective_count}"
            )

        except Exception as e:
            logger.error(
                f"[LectureSummaryTaskHandler] 预先计算失败: {e}", exc_info=True
            )

        lecture_review_client = LectureReviewClient()
        review_uuid = await lecture_review_client.start_lecture_review_async(
            dict(state),
            learning_duration_minutes=learning_duration_minutes,
            learning_duration_formatted=learning_duration_formatted,
            effective_count=effective_count,
        )

        sco_content = {
            "highlights": [],
            "learning_suggestions": [],
            "activity_id": activity_id,
            "activity_name": activity_name,
            "learning_duration_minutes": learning_duration_minutes,
            "learning_duration_formatted": learning_duration_formatted,
            "interaction_count": effective_count,
            "artifact_id": "",
            "report_name": "",
            "report_title": "",
            "completion_status": 1,
        }

        logger.info(
            f"[LectureSummaryTaskHandler] SCO 数据加载完成, "
            f"UUID={review_uuid}, duration={learning_duration_formatted}"
        )

        return review_uuid, sco_content

    # ==================== Redis Fetch ====================

    async def _fetch_review_from_redis_if_needed(
        self,
        material_name: str,
        sco_content: Dict[str, Any],
        review_uuid: str,
    ) -> Dict[str, Any]:
        """
        根据 material_name 判断是否需要从 Redis 获取完整报告数据
        （从原始 _fetch_review_from_redis_if_needed 直接迁移）
        """
        if sco_content.get("completion_status") == 2:
            return sco_content

        if material_name not in [
            "display_highlights",
            "display_learning_suggestions",
            "display_all",
        ]:
            return sco_content

        if not review_uuid:
            logger.warning(
                "[LectureSummaryTaskHandler] review_uuid 不存在，使用现有数据"
            )
            return sco_content

        logger.info(
            f"[LectureSummaryTaskHandler] {material_name} 需要完整报告数据，"
            f"开始从 Redis 获取, UUID={review_uuid}"
        )

        try:
            client = LectureReviewClient()
            lecture_review = (
                await client.get_lecture_review_from_redis(
                    review_uuid, timeout_seconds=60, poll_interval=0.5
                )
            )

            if lecture_review:
                sco_content.update({
                    "highlights": lecture_review.highlights,
                    "learning_suggestions": lecture_review.learning_suggestions,
                    "learning_duration_minutes": lecture_review.learning_duration_minutes,
                    "learning_duration_formatted": lecture_review.learning_duration_formatted,
                    "interaction_count": lecture_review.interaction_count,
                    "artifact_id": lecture_review.artifact_id,
                    "report_name": lecture_review.report_name,
                    "report_title": lecture_review.report_title,
                    "completion_status": lecture_review.completion_status,
                })
                logger.info(
                    f"[LectureSummaryTaskHandler] 成功从 Redis 获取完整报告, "
                    f"highlights={len(lecture_review.highlights)}个, "
                    f"suggestions={len(lecture_review.learning_suggestions)}条"
                )
            else:
                logger.warning(
                    f"[LectureSummaryTaskHandler] 从 Redis 获取报告失败或超时, "
                    f"使用现有数据, UUID={review_uuid}"
                )

        except Exception as e:
            logger.error(
                f"[LectureSummaryTaskHandler] 从 Redis 获取报告异常: {e}, "
                f"使用现有数据",
                exc_info=True,
            )

        return sco_content
