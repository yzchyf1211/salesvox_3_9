"""
学习回顾结果聚合节点
（从 aitutor-magic-agent 迁移，移除 @async_agentic_node 装饰器，
  适配 prosona-agent 的 tracking / artifact / prompt / user 模块）
"""

import asyncio
import json
import logging
from typing import Dict, Any

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from app.api import get_prompt_client
from app.enums.report_action_code_enum import ReportActionCodeEnum
from app.graph.review.review_common import (
    format_conversation_history,
    get_current_activity_info,
    get_llm_client,
    parse_json_response,
)
from app.schema.learning_review_schema import ActivityReviewData
from app.utils.tracking_utils import TrackingReportUtils
from app.utils.message_utils import filter_messages_by_criteria
from app.graph.review.state import ReviewState
from agentickit.core.context.agentic_context_manager import context_saver
from app.utils.artifact_utils import ArtifactService
from app.utils.user_utils import get_language_name, get_language_locale, get_token
from agentunit.llm.trait_analysis import trait_analysis 

logger = logging.getLogger(__name__)

_PROMPT_LECTURE_MESSAGES_ANALYZE = "v2/report/lecture/lecture_messages_analyze"


async def _report_custom_action_async(
    state: Dict[str, Any], token: str = None, **kwargs
) -> None:
    def _send():
        TrackingReportUtils(state=state, token=token).report_custom_action(
            **kwargs
        )

    await asyncio.to_thread(_send)


async def review_aggregate_results_node(
    state: ReviewState,
) -> ActivityReviewData:
    logger.info("开始聚合当前活动分析结果...")

    review = state.get("current_activity_review")
    try:
        current_activity = get_current_activity_info(state)
        if not current_activity:
            return state

        if not review:
            logger.warning("current_activity_review 不存在，跳过结果聚合")
            return state

        interaction_results = review.review_interaction_results or {}
        highlights_results = review.review_highlights_results or {}
        suggestions_results = review.review_suggestions_results or {}
        duration_results = review.review_duration_results or {}
        summary_results = review.review_summary_results or {}

        activity_id = current_activity.get("activity_id", "")

        interaction_count = 0
        if activity_id in interaction_results:
            interaction_count = interaction_results[activity_id].get(
                "effective_count", 0
            )

        highlights = highlights_results.get(activity_id, [])
        suggestions = suggestions_results.get(activity_id, [])
        summary = summary_results.get(activity_id, [])

        learning_duration_minutes = 5
        start_time = None
        end_time = None
        if activity_id in duration_results:
            duration_data = duration_results[activity_id]
            learning_duration_minutes = duration_data.get(
                "learning_duration_minutes", 5
            )
            start_time = duration_data.get("start_time")
            end_time = duration_data.get("end_time")

        review.learning_duration_minutes = learning_duration_minutes
        review.interaction_count = interaction_count
        review.highlights = highlights
        review.learning_suggestions = suggestions
        review.summary = summary
        review.start_time = start_time
        review.end_time = end_time
        review.activity_id = activity_id
        review.activity_name = current_activity.get("activity_name")
        review.completion_status = 2
        review.finish_generation()

        logger.info(
            f"当前活动 {current_activity.get('activity_name')} 聚合完成: "
            f"学习时长={learning_duration_minutes}分钟, "
            f"互动次数={interaction_count}次, "
            f"精彩时刻={len(highlights)}个, "
            f"学习建议={len(suggestions)}条, "
            f"学习总结={len(summary)}条"
        )

        # 异步分数上报
        try:
            asyncio.create_task(tracking_score_results(review, dict(state)))
            logger.info("已启动异步分数上报任务")
        except RuntimeError:
            logger.warning("当前环境没有运行中的事件循环，尝试后台线程")
            try:
                import threading

                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        new_loop.run_until_complete(
                            tracking_score_results(review, dict(state))
                        )
                    finally:
                        new_loop.close()

                thread = threading.Thread(target=run_in_thread, daemon=True)
                thread.start()
            except Exception as e:
                logger.error(f"启动异步分数上报任务失败: {e}", exc_info=True)

        # 创建产物
        context_id = state.get("context_id")
        context = context_saver.load(context_id)
        token = context.get("request_header", {}).get("token", "")
        with ArtifactService(token) as arti_srv:
            locale = get_language_locale(state)
            try:
                from agentickit.core.infra.i18n.message_helper import (
                    get_message,
                )

                review.report_title = get_message(
                    locale,
                    "agentic.aitutor.review.report.section.title",
                    review.activity_name,
                )
            except ImportError:
                review.report_title = review.activity_name
            review.report_name = review.activity_name
            artifact_id = await asyncio.to_thread(
                arti_srv.create_report, review, review.report_title
            )
            logger.info(
                f"review_aggregate_results_node artifact_id:{artifact_id}"
            )
            review.artifact_id = artifact_id

        # 个人档案特质分析
        await _personal_profile_saver(state)
        logger.info("个人档案结果保存成功")
        return review

    except Exception as e:
        logger.error(f"结果聚合节点执行失败: {e}", exc_info=True)
        return review


async def _personal_profile_saver(state: Dict[str, Any]) -> None:
    personal_profile = state.get("personal_profile_context")
    if personal_profile is None:
        logger.warning("个人档案上下文不存在，跳过特质分析")
    else:
        try:
            personal_profile.trait = await trait_analysis(state)
            state["personal_profile_context"] = personal_profile
        except ImportError:
            logger.warning(
                "agentunit.llm.trait_analysis 不可用，跳过特质分析"
            )


async def tracking_score_results(
    review: ActivityReviewData, state: Dict[str, Any]
) -> None:
    try:
        current_activity = get_current_activity_info(state)
        if not current_activity:
            logger.warning("没有找到当前活动，跳过分数上报")
            return

        activity_id = current_activity.get("activity_id", None)
        if not activity_id:
            logger.warning("activity_id 为空，跳过分数上报")
            return

        reported_map = state.get("_score_reported_map")
        if not isinstance(reported_map, dict):
            reported_map = {}
        if reported_map.get(activity_id):
            logger.info(
                f"检测到重复触发，跳过分数上报，activity_id={activity_id}"
            )
            return

        logger.info("开始生成当前活动的经验分析...")

        history_qa_sessions = state.get("history_qa_sessions") or {}

        activity_sco_list = state.get("activity_sco_list", {}) or {}
        sco_list = activity_sco_list.get(activity_id, []) or []
        scos = list(
            filter(
                lambda x: isinstance(x, dict) and x.get("sco_type") == "问答题",
                sco_list,
            )
        )
        question_info = []
        for sco in scos:
            content = sco.get("sco_content", {}) or {}
            qid = content.get("exam_id", "")
            qa_session = history_qa_sessions.get(qid, {}) or {}
            query = qa_session.get("original_query") or ""
            pass_condition = qa_session.get("pass_condition", "")
            practice_context = qa_session.get("last_sco_video_desc", "")
            scoring_reasoning = qa_session.get("scoring_reasoning", "")
            knowledge_points_list = qa_session.get("knowledge_points", []) or []
            if isinstance(knowledge_points_list, list):
                normalized_kps = []
                for kp in knowledge_points_list:
                    if isinstance(kp, dict):
                        val = kp.get("description") or kp.get("title") or ""
                        if val:
                            normalized_kps.append(str(val))
                    elif isinstance(kp, str):
                        if kp:
                            normalized_kps.append(kp)
                    else:
                        normalized_kps.append(str(kp))
                knowledge_points = "\n".join(normalized_kps)
            else:
                knowledge_points = str(knowledge_points_list)
            task_messages = qa_session.get("task_messages", [])
            conversation_task_messages = format_conversation_history(
                task_messages, state
            )
            quiz_text = (
                f"\n - 问题背景：{practice_context}"
                f"\n - 问题：{query}"
                f"\n - 问题知识点：{knowledge_points}"
                f"\n - 通关条件：{pass_condition}"
                f"\n - 综合评价：{scoring_reasoning}"
                f"\n - 答题历史对话记录: {conversation_task_messages}"
            )
            question_info.append(quiz_text)

        messages = state.get("messages", [])
        activity_messages = filter_messages_by_criteria(
            messages, activity_id=activity_id
        )
        activity_messages_text = format_conversation_history(
            activity_messages, state
        )
        context_text = (
            "\n\n".join(question_info)
            + "\n\n"
            + f"- 完整历史对话记录: {activity_messages_text}"
        )

        language = get_language_name(state)

        llm = get_llm_client()
        prompt = get_prompt_client(_PROMPT_LECTURE_MESSAGES_ANALYZE)
        llm.with_config(
            RunnableConfig(metadata={"langfuse_prompt": prompt})
        )
        llm_messages = [
            SystemMessage(
                content=prompt.compile(
                    question_info=context_text, language=language
                )
            )
        ]

        response = await llm.ainvoke(llm_messages)
        result = parse_json_response(response.content)
        logger.info(f"生成当前活动的经验结果: {result}")
        await _tracking_data(state, result)

        if review:
            review.review_overall_summary_results = {
                activity_id: result.get("overall_summary", "")
            }
            review.review_overall_feedback_results = {
                activity_id: result.get("overall_feedback", "")
            }

        score_results = review.review_score_results or {}
        score_wight_results = review.review_score_wight_results or {}
        overall_summary_results = review.review_overall_summary_results or {}
        overall_feedback_results = review.review_overall_feedback_results or {}

        if activity_id not in score_results:
            logger.info("分数结果未就绪，跳过本次上报")
            return
        if (
            activity_id not in overall_summary_results
            or activity_id not in overall_feedback_results
        ):
            logger.info("总体总结或总体反馈未就绪，跳过本次上报")
            return

        score_value = score_results.get(activity_id, 0) or 0
        if isinstance(score_value, dict):
            score = score_value.get("avg_score", 0) or 0
        else:
            score = score_value

        score_wight = score_wight_results.get(activity_id, 0) or 0
        overall_summary = overall_summary_results.get(activity_id, "") or ""

        project_info = state.get("project_info")
        project_id = project_info.get("project_id") if project_info else None
        await _report_custom_action_async(
            state,
            token=get_token(state.get("context_id")),
            project_id=project_id,
            action_code=ReportActionCodeEnum.LECTURE_SCORE.action_code,
            actv_id=activity_id,
            data_items=[
                {
                    "decimal_val": float(score) if score is not None else None,
                    "text_val": str(score_wight)
                    if score_wight is not None
                    else "",
                    "text_val2": str(overall_summary)
                    if overall_summary is not None
                    else "",
                }
            ],
        )
        logger.info("活动分数上报完成")

        reported_map[activity_id] = True
        state["_score_reported_map"] = reported_map

    except Exception as e:
        logger.error(f"分数上报失败: {e}", exc_info=True)


async def _tracking_data(state: Dict[str, Any], result: dict) -> None:
    project_info = state.get("project_info")
    project_id = project_info.get("project_id") if project_info else None
    current_activity = state.get("current_activity")
    activity_id = (
        current_activity.get("activity_id", None) if current_activity else None
    )
    valid_interactions = result.get("valid_interactions", []) or []
    applied_interactions = result.get("applied_interactions", []) or []
    error_behaviors = result.get("error_behaviors", []) or []
    total_interactions = result.get("total_interactions", []) or []

    data_items_1 = [
        {
            "text_val": vi.get("reason", ""),
            "text_val1": vi.get("text_excerpt", ""),
        }
        for vi in valid_interactions
    ]
    data_items_2 = [
        {
            "text_val": ai.get("reason", ""),
            "text_val1": ai.get("text_excerpt", ""),
        }
        for ai in applied_interactions
    ]

    data_items_3 = []
    for eb in error_behaviors:
        dialogue_excerpt = eb.get("dialogue_excerpt", [])
        dialogue_json = json.dumps(dialogue_excerpt, ensure_ascii=False)
        data_items_3.append(
            {
                "enum_val": eb.get("error_type", ""),
                "text_val": eb.get("detailed_description", ""),
                "text_val1": dialogue_json,
            }
        )

    data_items_4 = []
    for interaction in total_interactions:
        dialogue_excerpt = interaction.get("dialogue_excerpt", [])
        dialogue_json = json.dumps(dialogue_excerpt, ensure_ascii=False)
        data_items_4.append(
            {
                "text_val": interaction.get("detailed_description", ""),
                "text_val1": dialogue_json,
            }
        )

    token = get_token(state.get("context_id"))

    if data_items_1:
        await _report_custom_action_async(
            state,
            token=token,
            project_id=project_id,
            action_code=ReportActionCodeEnum.TUTOR_LECTURE_QUIZ.action_code,
            actv_id=activity_id,
            data_items=data_items_1,
        )

    if data_items_2:
        await _report_custom_action_async(
            state,
            token=token,
            project_id=project_id,
            action_code=ReportActionCodeEnum.TUTOR_LECTURE_SHARE.action_code,
            actv_id=activity_id,
            data_items=data_items_2,
        )

    if data_items_3:
        await _report_custom_action_async(
            state,
            token=token,
            project_id=project_id,
            action_code=ReportActionCodeEnum.LECTURE_ERROR.action_code,
            actv_id=activity_id,
            data_items=data_items_3,
        )

    if data_items_4:
        await _report_custom_action_async(
            state,
            token=token,
            project_id=project_id,
            action_code=ReportActionCodeEnum.TUTOR_LECTURE_ALL_QUIZ.action_code,
            actv_id=activity_id,
            data_items=data_items_4,
        )
