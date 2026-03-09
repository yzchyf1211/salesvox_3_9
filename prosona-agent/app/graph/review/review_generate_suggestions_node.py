"""
学习回顾学习建议生成节点
（从 aitutor-magic-agent 迁移，移除 @async_agentic_node 装饰器，
  适配 prosona-agent 的 prompt / LLM 模块）
"""

import logging
from typing import Any, Dict

from langchain_core.messages import SystemMessage

from app.api import get_prompt_client
from app.graph.review.review_common import (
    get_llm_client,
    analyze_activity_messages,
    format_conversation_history,
    get_current_activity_info,
    parse_suggestions_json_response,
)
from app.graph.review.state import ReviewState
from app.utils.user_utils import get_language_name

logger = logging.getLogger(__name__)

_PROMPT_LECTURE_STUDY_SUGGESTIONS = "v2/report/lecture/lecture_study_suggestions"


async def review_generate_suggestions_node(
    state: ReviewState,
) -> Dict[str, Any]:
    logger.info("开始生成当前活动的学习建议...")

    try:
        current_activity = get_current_activity_info(state)
        if not current_activity:
            return {}

        all_messages = state.get("messages", [])

        message_analysis = analyze_activity_messages(
            current_activity, all_messages
        )

        logger.info(
            f"生成活动 {current_activity.get('activity_name')} 的学习建议"
        )

        try:
            activity_messages = message_analysis.get("activity_messages", [])

            conversation_history = format_conversation_history(
                activity_messages, state
            )

            prompt_data = get_prompt_client(
                _PROMPT_LECTURE_STUDY_SUGGESTIONS
            )
            prompt = prompt_data.compile(
                activity_name=current_activity.get("activity_name"),
                conversation_history=conversation_history,
                learning_goals=current_activity.get("learning_objectives", "")
                or "提升专业技能",
                language=get_language_name(state),
            )

            llm = get_llm_client()
            messages = [SystemMessage(content=prompt)]
            response = await llm.ainvoke(messages)

            result = parse_suggestions_json_response(response.content)
            suggestions_raw = result.get("suggestions", [])

            suggestions = []
            for item in suggestions_raw:
                if (
                    isinstance(item, dict)
                    and "title" in item
                    and "description" in item
                ):
                    suggestions.append(
                        {
                            "title": item["title"],
                            "reason": item.get("reason", ""),
                            "description": item["description"],
                        }
                    )
                elif isinstance(item, str):
                    suggestions.append(
                        {"title": item, "reason": "", "description": ""}
                    )

            suggestions_results = {
                current_activity.get("activity_id"): suggestions
            }

            logger.info(
                f"{current_activity.get('activity_name')}: 生成学习建议{len(suggestions)}个"
            )

            review = state.get("current_activity_review")
            if review:
                review.review_suggestions_results = suggestions_results
                return {}
            else:
                logger.warning(
                    "current_activity_review 不存在，跳过学习建议结果更新"
                )
                return {}

        except Exception as e:
            logger.error(
                f"生成活动 {current_activity.get('activity_name')} 学习建议时出错: {e}",
                exc_info=True,
            )
            suggestions_results = {current_activity.get("activity_id"): []}

            review = state.get("current_activity_review")
            if review:
                review.review_suggestions_results = suggestions_results
                return {}
            else:
                logger.warning(
                    "current_activity_review 不存在，跳过学习建议结果更新"
                )
                return {}

    except Exception as e:
        logger.error(f"学习建议生成节点执行失败: {e}", exc_info=True)
        return {}
