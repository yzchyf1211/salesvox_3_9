"""
学习回顾并行工作流主图构建文件
（从 aitutor-magic-agent 迁移，适配 prosona-agent）

将学习回顾功能拆分为多个并行节点：
1. 开始节点 - 验证数据并初始化回顾状态
2. 精彩时刻聚合节点 - 从 Redis 聚合高光结果
3. 学习建议生成节点 - LLM 生成学习建议
4. 分数生成节点 - 计算QA得分
5. 结果聚合节点 - 聚合所有结果并完成生成
"""

import logging

from langgraph.graph import StateGraph, END

from app.graph.review.review_generate_score_node import (
    review_generate_score_node,
)
from app.graph.review.review_aggregate_results_node import (
    review_aggregate_results_node,
)
from app.graph.review.review_calculate_duration_node import (
    calculate_duration_and_count,
)
from app.graph.review.review_generate_highlights_node import (
    review_generate_highlights_v2_node,
)
from app.graph.review.review_generate_suggestions_node import (
    review_generate_suggestions_node,
)
from app.graph.review.review_start_node import review_start_node
from app.schema.learning_review_schema import ActivityReviewData
from app.graph.review.state import ReviewState

logger = logging.getLogger(__name__)


async def create_learning_review_graph():
    workflow = StateGraph(ReviewState)

    workflow.add_node("review_start", review_start_node)
    workflow.add_node(
        "review_generate_highlights", review_generate_highlights_v2_node
    )
    workflow.add_node(
        "review_generate_suggestions", review_generate_suggestions_node
    )
    workflow.add_node("review_generate_score", review_generate_score_node)
    workflow.add_node(
        "review_aggregate_results", review_aggregate_results_node
    )

    workflow.set_entry_point("review_start")

    workflow.add_edge("review_start", "review_generate_highlights")
    workflow.add_edge("review_start", "review_generate_suggestions")
    workflow.add_edge("review_start", "review_generate_score")

    workflow.add_edge(
        "review_generate_suggestions", "review_aggregate_results"
    )
    workflow.add_edge(
        "review_generate_highlights", "review_aggregate_results"
    )
    workflow.add_edge("review_generate_score", "review_aggregate_results")

    workflow.add_edge("review_aggregate_results", END)

    return workflow.compile()


async def run_learning_review_workflow(
    user_input: str,
    initial_state: ReviewState = None,
    duration_results: dict = None,
    effective_count: int = None,
) -> ActivityReviewData:
    logger.info("=== 启动学习回顾并行工作流 ===")

    if initial_state is None:
        logger.warning("初始状态为空")
        return None

    app = await create_learning_review_graph()

    try:
        current_activity = initial_state.get("current_activity")
        current_activity_review = ActivityReviewData(
            activity_id=current_activity.get("activity_id"),
            activity_name=current_activity.get("activity_name"),
        )

        if duration_results is not None and effective_count is not None:
            logger.info("使用预先计算的学习时长和互动次数...")
        else:
            logger.info("开始计算学习时长和互动次数...")
            duration_results, effective_count = (
                await calculate_duration_and_count(initial_state)
            )
            logger.info(
                f"预先计算完成: 时长={duration_results}, 互动次数={effective_count}"
            )

        current_activity_review.review_duration_results = duration_results
        current_activity_review.review_interaction_results = {
            current_activity.get("activity_id", ""): {
                "effective_count": effective_count,
                "total_count": effective_count,
            }
        }

        initial_state["current_activity_review"] = current_activity_review
        final_state = await app.ainvoke(initial_state)

        logger.info("学习回顾并行工作流执行完成")

        review_data = final_state.get("current_activity_review")
        if review_data is None:
            logger.warning("工作流执行完成但未生成回顾数据，返回初始状态")
            return initial_state.get("current_activity_review")

        return review_data
    except Exception as e:
        logger.error(f"学习回顾并行工作流执行失败: {e}", exc_info=True)
        error_state = initial_state.copy()
        review = error_state.get("current_activity_review")
        if review:
            review.review_generation_in_progress = False
        return error_state
