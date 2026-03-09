"""
学习回顾分数生成节点
（从 aitutor-magic-agent 迁移，移除 @async_agentic_node 装饰器）
"""

import logging
from typing import Any, Dict

from app.graph.review.review_common import get_current_activity_info
from app.graph.review.state import ReviewState

logger = logging.getLogger(__name__)


async def review_generate_score_node(state: ReviewState) -> Dict[str, Any]:
    logger.info("开始生成当前活动的分数...")
    current_activity = get_current_activity_info(state)
    if not current_activity:
        return {}

    scos = current_activity.get("scos") or []
    question_id_list = list(
        map(
            lambda x: x.get("sco_id"),
            filter(lambda x: x.get("sco_type") == "问答题", scos),
        )
    )
    history_qa_sessions = state.get("history_qa_sessions") or {}
    qa_session_list = [
        history_qa_sessions[qid]
        for qid in question_id_list
        if qid in history_qa_sessions
    ]
    if not qa_session_list:
        logger.warning("QA会话未激活，无法生成分数")
        return {}

    total_score = 0
    for qa_session in qa_session_list:
        score = qa_session.get("score", 0) or 0
        total_score += score
    if total_score == 0:
        logger.warning("没有有效的分数，无法生成分数")
        return {}

    avg_score = round(total_score / len(qa_session_list), 2)
    score_wight = round(100 / len(qa_session_list), 2)

    review = state.get("current_activity_review")
    if review:
        review.review_score_results = {
            current_activity.get("activity_id"): avg_score
        }
        review.review_score_wight_results = {
            current_activity.get("activity_id"): score_wight
        }
        return {}
    else:
        logger.warning("current_activity_review 不存在，跳过分数结果更新")
        return {}
