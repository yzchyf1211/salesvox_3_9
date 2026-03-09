"""
Quiz SCO TaskHandler - 问答题类型SCO的处理器

从 aitutor-magic-agent 的 SCOQuizPlugin 迁移而来，
通过 prosona-agent 的 TaskHandler 模式实现。

原始方法映射:
- SCOQuizPlugin.load_content()           -> abefore(): 从API获取问答题内容
- SCOQuizPlugin.get_content_context()    -> abefore(): 注入内容上下文
- SCOQuizPlugin.get_teach_design_context -> abefore(): 注入教学设计上下文
- SCOQuizPlugin.get_action_schema_context-> abefore(): 注入动作结构上下文
- SCOQuizPlugin.get_reminder_context()   -> abefore(): 注入提醒上下文
- SCOQuizPlugin.render_action()          -> aget_card(): 构建AOMCard
- SCOQuizPlugin.run_lifecycle()          -> SCOMiddleware已处理
- SCORuntime._analyze_single_quiz_highlight -> aafter(): 异步高光分析
- sco_client.evaluation_score              -> aafter(): 评分 + 上报
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from agentickit.core.infra.config.loader import get_config
from agentickit.core.infra.models import get_model_with_fallbacks
from agentickit.prosonaagent.aom.api import get_sco_all_messages
from agentickit.prosonaagent.aom.card import build_content_card
from app.api import get_prompt_client
from agentickit.prosonaagent.aom.state import SCOTaskState
from agentickit.prosonaagent.core.handler.enhance_task_handler import EnhanceTaskHandler
from agentickit.prosonaagent.aom.types import AOMCard
from langchain_core.runnables import RunnableConfig
from app.api import get_quiz_content
from app.enums.report_action_code_enum import ReportActionCodeEnum
from app.utils.tracking_utils import TrackingReportUtils
from agentickit.prosonaagent.core.tools import _builtin_conversation

logger = logging.getLogger(__name__)

# Langfuse prompt keys
_PROMPT_HIGHLIGHT_TEMPLATE = "v2/report/personal/analysis/analysis_highlight_template"
_PROMPT_HIGHLIGHT_TASK = "v2/report/personal/analysis/task/analysis_lecture_highlight_task"
_PROMPT_HIGHLIGHT_CONSTRAINTS = "v2/report/personal/analysis/constraints/analysis_lecture_highlight_constraints"
_PROMPT_EXERCISES_SCORE = "v2/task/lecture_exercises_score"

HIGHLIGHTS_TTL = 30 * 24 * 60 * 60  # 30 days
HIGHLIGHT_TASK_TTL = 600  # 10 minutes


class QuizTaskState(SCOTaskState):
    quiz_content: Optional[Dict[str, Any]]
    history_qa_sessions: Optional[Dict[str, Any]]


class QuizTaskHandler(EnhanceTaskHandler[QuizTaskState]):
    """问答题SCO处理器"""

    name = "sco:quiz"
    state_schema = QuizTaskState
    tools = [_builtin_conversation]

    # ==================== Lifecycle Hooks ====================

    async def abefore(
        self,
        state: QuizTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any] | None:
        delta_state: Dict[str, Any] = (
            await super().abefore(state, runtime) or {}
        )

        context_id = state.get("context_id")
        sco = state.get("sco", {})
        activity_id = sco.get("activity_id", "")
        sco_id = sco.get("id", "")
        user_profile = state.get("user_profile", {})

        quiz_content = await get_quiz_content(
            context_id,
            activity_id,
            sco_id,
            user_profile,
        )
        delta_state["quiz_content"] = quiz_content

        messages = delta_state.get("messages", [])

        content_context = self._build_content_context(quiz_content)
        if content_context:
            messages.append(SystemMessage(content=content_context))

        reminder_context = self._build_reminder_context()
        if reminder_context:
            messages.append(SystemMessage(content=reminder_context))

        delta_state["messages"] = messages
        return delta_state

    async def aafter(
        self,
        state: QuizTaskState,
        runtime: Runtime,
        is_interrupt: bool = False,
    ) -> Dict[str, Any] | None:
        delta_state: Dict[str, Any] = (
            await super().aafter(state, runtime, is_interrupt) or {}
        )

        if is_interrupt:
            return delta_state

        quiz_content = state.get("quiz_content", {})
        sco = state.get("sco", {})
        context_id = state.get("context_id", "")
        messages = get_sco_all_messages(context_id, sco.get("id", ""))

        # 1. 评分（从 sco_runtime.py evaluation_score 迁移）
        qa_session = None
        try:
            score_result = await self._evaluate_score(state, quiz_content, messages)
            if score_result:
                qa_session = self._build_qa_session(state, quiz_content, messages, score_result)
                history_qa_sessions = dict(state.get("history_qa_sessions") or {})
                history_qa_sessions[qa_session["id"]] = qa_session
                delta_state["history_qa_sessions"] = history_qa_sessions

                try:
                    await self._tracking_score(
                        state, score_result, quiz_content, is_passed=True
                    )
                    logger.info("上报分数结果成功")
                except Exception as e:
                    logger.error(f"上报分数结果失败: {e}, result: {score_result}", exc_info=True)
        except Exception as e:
            logger.error(f"评分失败: {e}", exc_info=True)

        # 2. 异步执行高光分析（不阻塞主流程）
        try:
            snapshot = {
                "context_id": context_id,
                "sco": dict(sco),
                "activity": dict(state.get("activity", {})),
                "quiz_content": dict(quiz_content),
                "messages": messages,
                "user_profile": dict(state.get("user_profile", {})),
                "language_name": state.get("language_name", ""),
                "qa_session": qa_session,
            }
            asyncio.create_task(self._analyze_quiz_highlight(snapshot))
            logger.info(f"已启动问答题的高光分析任务")
        except Exception as e:
            logger.warning(f"启动高光分析任务失败: {e}")

        return delta_state

    # ==================== Card Rendering ====================

    async def aget_card(
        self,
        state: QuizTaskState,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AOMCard:
        quiz_content = state.get("quiz_content", {})
        sco = state.get("sco", {})

        content = quiz_content.get("content", "")
        answer_content = quiz_content.get("answer_content", "")
        sco_name = sco.get("name", "")

        is_display_answer = self._get_is_display_answer(quiz_content)
        is_display_analysis = action == "display_answer" or (
            action == "display_all" and is_display_answer
        )

        if is_display_analysis:
            prompt = get_prompt_client(
                "v2/plugin/sco/quiz/observe_action_display_answer"
            )
            description = prompt.compile(
                content=content, answer_content=answer_content
            )
        else:
            prompt = get_prompt_client(
                "v2/plugin/sco/quiz/observe_action_display_question"
            )
            description = prompt.compile(content=content)

        return build_content_card(
            id="quiz-display",
            name="展示解析" if is_display_analysis else "开始",
            content={
                "title": sco_name,
                "question": content,
                "explanation": answer_content if is_display_analysis else "",
                "action": "展示解析" if is_display_analysis else "开始",
            },
            description=description,
        )

    # ==================== Score Evaluation ====================

    async def _evaluate_score(
        self,
        state: QuizTaskState,
        quiz_content: Dict[str, Any],
        messages: List[AnyMessage],
    ) -> Optional[Dict[str, Any]]:
        """
        评估问答题分数（从 aitutor-magic-agent evaluation_score 迁移）

        通过 LLM 分析对话历史，给出分数和评分理由。
        """
        if not quiz_content:
            logger.warning("quiz_content 为空，跳过评分")
            return None

        original_query = quiz_content.get("content", "")
        pass_condition = (quiz_content.get("rules", []) or [""])[0]
        practice_context = self._get_prev_sco_description(state)
        history_messages = _compress_task_messages(messages)
        language = state.get("language_name", "")

        try:
            prompt_obj = get_prompt_client(_PROMPT_EXERCISES_SCORE)
            prompt_text = prompt_obj.compile(
                descption=practice_context,
                original_query=original_query,
                pass_condition=pass_condition,
                is_passed=True,
                history_messages=history_messages,
                language=language,
            )

            model_name = get_config("model_groups.main.primary_model")
            llm = get_model_with_fallbacks(
                model_name,
            ).with_config(RunnableConfig(tags=['filtered']))
            response = await llm.ainvoke([SystemMessage(content=prompt_text)])
            result = _parse_json_response(response.content)
            logger.info(f"生成当前分数结果: {result}")
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.error(f"评分 LLM 调用失败: {e}", exc_info=True)
            return None

    def _build_qa_session(
        self,
        state: QuizTaskState,
        quiz_content: Dict[str, Any],
        messages: List[AnyMessage],
        score_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        构建 QA Session 数据结构（从 aitutor-magic-agent create_qa_session 迁移）
        """
        content = quiz_content or {}
        rules = content.get("rules", [])
        knowledge_points = content.get("knowledge_points", [])

        ext_info = content.get("ext_info") or "{}"
        try:
            ext_info_dict = json.loads(ext_info) if isinstance(ext_info, str) else ext_info
            show_answer = ext_info_dict.get("showAnswer", True)
        except (json.JSONDecodeError, TypeError):
            show_answer = True

        prev_sco_desc = self._get_prev_sco_description(state)
        prev_sco = self._get_prev_sco(state)
        prev_item_type = 0
        if prev_sco and prev_sco.get("content"):
            prev_item_type = prev_sco["content"].get("item_type", 0)

        return {
            "id": content.get("exam_id", ""),
            "is_active": True,
            "original_query": content.get("content", ""),
            "explanation": content.get("explain_text", ""),
            "reference_answer": content.get("answer_content", ""),
            "show_answer": show_answer,
            "solution": content.get("solution", ""),
            "pass_condition": rules[0] if rules else "",
            "knowledge_points": knowledge_points,
            "score": score_result.get("score", 0),
            "scoring_reasoning": score_result.get("scoring_reasoning", ""),
            "last_sco_video_desc": prev_sco_desc,
            "last_sco_course_info": {
                "last_sco_course_desc": prev_sco_desc,
                "last_sco_item_type": prev_item_type,
            },
            "task_messages": _compress_task_messages(messages),
        }

    async def _tracking_score(
        self,
        state: QuizTaskState,
        result: Dict[str, Any],
        quiz_content: Dict[str, Any],
        is_passed: bool = False,
    ) -> None:
        """
        上报分数到 tracking API（从 aitutor-magic-agent tracking_score 迁移）

        使用 TrackingReportUtils.report_custom_action 通过 asyncio.to_thread 同步上报。
        """
        from agentickit.prosonaagent.utils.user import get_token

        project_id = state.get("project_id")
        if not project_id:
            logger.warning("project_id为空，跳过分数上报")
            return

        context_id = state.get("context_id", "")
        sco = state.get("sco", {})
        activity_id = sco.get("activity_id", "")
        sco_id = sco.get("id", "")

        pass_condition = (quiz_content.get("rules", []) or [""])[0]
        score = result.get("score", 0) or 0
        scoring_reasoning = result.get("scoring_reasoning", "")

        await asyncio.to_thread(
            TrackingReportUtils(state=state, token=get_token(context_id)).report_custom_action,
            project_id=project_id,
            action_code=ReportActionCodeEnum.TUTOR_SCO_SCORE.action_code,
            actv_id=activity_id,
            item_id=sco_id,
            data_items=[{
                "enum_val": str(is_passed),
                "decimal_val": str(score),
                "text_val1": pass_condition,
                "text_val2": scoring_reasoning,
            }],
        )

    def _get_prev_sco(self, state: QuizTaskState) -> Optional[Dict[str, Any]]:
        """从 sco_list 中获取当前 SCO 的前一个 SCO"""
        sco_list = state.get("sco_list", [])
        current_sco_id = state.get("sco", {}).get("id", "")
        for idx, sco_item in enumerate(sco_list):
            if sco_item.get("id") == current_sco_id and idx > 0:
                return sco_list[idx - 1]
        return None

    def _get_prev_sco_description(self, state: QuizTaskState) -> str:
        """获取前一个 SCO 的描述信息（用作 practice_context）"""
        prev_sco = self._get_prev_sco(state)
        if prev_sco:
            return prev_sco.get("description", "")
        return ""

    # ==================== Highlight Analysis ====================

    async def _analyze_quiz_highlight(self, snapshot: Dict[str, Any]) -> None:
        """
        异步分析问答题高光时刻（从 sco_runtime._analyze_single_quiz_highlight 迁移）

        流程:
        1. 从 quiz_content 构建 QA 上下文
        2. 格式化对话历史
        3. 调用 LLM 分析高光
        4. 存储到 Redis
        """
        from app.infra.redis_client import redis_set, redis_append_json_list

        context_id = snapshot["context_id"]
        sco = snapshot["sco"]
        activity = snapshot["activity"]
        quiz_content = snapshot["quiz_content"]
        messages = snapshot["messages"]
        qa_session = snapshot.get("qa_session") or {}

        sco_id = sco.get("id", "")
        activity_id = sco.get("activity_id", "")
        activity_name = activity.get("name", "")
        language = snapshot.get("language_name", "")
        user_profile = snapshot.get("user_profile", {})
        fullname = user_profile.get("fullname", "")

        task_key = f"highlight:task:{context_id}:{activity_id}:{sco_id}"

        try:
            # 1. 在 Redis 中记录任务状态
            redis_set(task_key, "pending", ex=HIGHLIGHT_TASK_TTL)
            self._register_highlight_task(context_id, activity_id, sco_id)

            # 2. 从 qa_session 中获取分析上下文（与原始 sco_runtime 一致）
            query = qa_session.get("original_query", "") or quiz_content.get("content", "")
            pass_condition = qa_session.get("pass_condition", "") or (quiz_content.get("rules", []) or [""])[0]
            practice_context = qa_session.get("last_sco_video_desc", "")
            score = qa_session.get("score", 0)
            scoring_reasoning = qa_session.get("scoring_reasoning", "")
            knowledge_points = self._format_knowledge_points(
                qa_session.get("knowledge_points", []) or quiz_content.get("knowledge_points", [])
            )
            conversation_text = _format_conversation_history(messages)

            quiz_text = (
                f"- 问题背景：{practice_context}\n"
                f"- 问题：{query}\n"
                f"- 问题知识点：{knowledge_points}\n"
                f"- 通关条件：{pass_condition}\n"
                f"- 得分：{score}\n"
                f"- 综合评价：{scoring_reasoning}\n"
                f"- 答题历史对话记录: {conversation_text}"
            )

            # 3. 获取 Langfuse prompt
            template_prompt = get_prompt_client(_PROMPT_HIGHLIGHT_TEMPLATE)
            task_prompt_text = get_prompt_client(_PROMPT_HIGHLIGHT_TASK).prompt
            constraints_text = get_prompt_client(_PROMPT_HIGHLIGHT_CONSTRAINTS).compile(
                language=language, activity_name=activity_name
            )

            system_content = template_prompt.compile(
                context=quiz_text,
                task=task_prompt_text,
                constraints=constraints_text,
            )

            # 4. 调用 LLM
            model_name = get_config("model_groups.main.primary_model")
            llm = get_model_with_fallbacks(
                model_name,
            ).with_config(RunnableConfig(tags=['filtered']))

            result = await asyncio.wait_for(
                llm.ainvoke([SystemMessage(content=system_content)]),
                timeout=30,
            )

            parsed = _parse_json_response(result.content)
            if not parsed:
                logger.warning(f"问答题 {sco_id} 高光分析结果为空")
                redis_set(task_key, "completed", ex=HIGHLIGHT_TASK_TTL)
                return

            # 5. 后处理：替换 fullname
            highlights_raw = parsed if isinstance(parsed, list) else parsed.get("highlights", [])
            if not highlights_raw:
                logger.info(f"问答题 {sco_id} 未生成高光时刻")
                redis_set(task_key, "completed", ex=HIGHLIGHT_TASK_TTL)
                return

            for item in highlights_raw:
                if isinstance(item, dict):
                    item["sco_id"] = sco_id
                    if fullname:
                        self._replace_fullname_in_highlight(item, fullname)

            # 6. 存储到 Redis
            results_key = f"highlight:results:{context_id}:{activity_id}"
            redis_append_json_list(results_key, highlights_raw, ex=HIGHLIGHTS_TTL)

            redis_set(task_key, "completed", ex=HIGHLIGHT_TASK_TTL)
            logger.info(
                f"问答题 {sco_id} 高光分析完成，生成 {len(highlights_raw)} 个高光时刻"
            )

        except asyncio.TimeoutError:
            logger.warning(f"问答题 {sco_id} 高光分析超时")
            redis_set(task_key, "completed", ex=HIGHLIGHT_TASK_TTL)
        except Exception as e:
            logger.error(f"问答题 {sco_id} 高光分析失败: {e}", exc_info=True)
            redis_set(task_key, "completed", ex=HIGHLIGHT_TASK_TTL)

    def _register_highlight_task(
        self, context_id: str, activity_id: str, sco_id: str
    ) -> None:
        """将 sco_id 添加到 Redis 任务列表"""
        from app.infra.redis_client import redis_get, redis_set

        tasks_key = f"highlight:tasks:{context_id}:{activity_id}"
        tasks_json = redis_get(tasks_key) or "[]"
        try:
            tasks_list = json.loads(tasks_json)
        except (json.JSONDecodeError, TypeError):
            tasks_list = []
        if sco_id not in tasks_list:
            tasks_list.append(sco_id)
            redis_set(tasks_key, json.dumps(tasks_list), ex=HIGHLIGHT_TASK_TTL)

    @staticmethod
    def _format_knowledge_points(knowledge_points: list) -> str:
        if not isinstance(knowledge_points, list):
            return str(knowledge_points)
        normalized = []
        for kp in knowledge_points:
            if isinstance(kp, dict):
                val = kp.get("description") or kp.get("title") or ""
                if val:
                    normalized.append(str(val))
            elif isinstance(kp, str) and kp:
                normalized.append(kp)
            else:
                normalized.append(str(kp))
        return "\n".join(normalized)

    @staticmethod
    def _replace_fullname_in_highlight(item: dict, fullname: str) -> None:
        ref = item.get("reference")
        if not ref or not isinstance(ref, dict):
            return
        dialogues = ref.get("dialogue")
        if not dialogues or not isinstance(dialogues, list):
            return
        for dialogue in dialogues:
            if isinstance(dialogue, dict):
                role = dialogue.get("role", "")
                if role.startswith(fullname):
                    dialogue["role"] = role.replace(fullname, "我")

    # ==================== Private Helpers ====================

    def _build_content_context(self, quiz_content: Dict[str, Any]) -> str:
        content = quiz_content.get("content", "")
        explain_text = quiz_content.get("explain_text", "")
        answer_content = quiz_content.get("answer_content", "")
        answer_analysis = quiz_content.get("answer_analysis", "")
        solution = quiz_content.get("solution", "")
        is_display_answer = self._get_is_display_answer(quiz_content)

        prompt = get_prompt_client("v2/plugin/sco/quiz/content")
        return prompt.compile(
            content=content,
            explain_text=explain_text,
            answer_content=answer_content,
            answer_analysis=answer_analysis,
            solution=solution,
            is_display_answer=is_display_answer,
        )

    def _build_teach_design_context(
        self, sco: Dict[str, Any], quiz_content: Dict[str, Any]
    ) -> str:
        narration = sco.get("blueprint", "")
        rule = (
            "\n".join(quiz_content.get("rules", []))
            if isinstance(quiz_content, dict)
            else ""
        )

        # TODO: 支持 review 模式 (v2/plugin/sco/quiz/review/teach_design)
        prompt = get_prompt_client("v2/plugin/sco/quiz/teach_design")
        return prompt.compile(narration=narration, rule=rule)

    def _build_action_schema_context(self) -> str:
        # TODO: 支持 review 模式 (v2/plugin/sco/quiz/review/action_schema)
        prompt = get_prompt_client("v2/plugin/sco/quiz/action_schema")
        return prompt.compile()

    def _build_reminder_context(self) -> str:
        # TODO: 支持 review 模式 (v2/plugin/sco/quiz/review/reminder)
        prompt = get_prompt_client("v2/plugin/sco/quiz/reminder")
        return prompt.compile()

    def _get_is_display_answer(self, quiz_content: Dict[str, Any]) -> bool:
        ext_info = quiz_content.get("ext_info", {})
        if isinstance(ext_info, dict):
            return ext_info.get("showAnswer", True)
        try:
            return json.loads(ext_info).get("showAnswer", True)
        except (json.JSONDecodeError, TypeError):
            logger.warning("ext_info 解析失败，内容：%s", ext_info)
            return False


# ==================== Module-level Helpers ====================


def _compress_task_messages(messages: List[AnyMessage]) -> str:
    """
    压缩消息为格式化文本（从 aitutor-magic-agent compress_messages + format 迁移）

    保留教师/学员消息，格式化为可读文本供 LLM prompt 使用。
    """
    parts: List[str] = []
    for msg in messages:
        kwargs = getattr(msg, "additional_kwargs", {}) or {}
        text = kwargs.get("__text__", "")
        if not text:
            continue
        if isinstance(msg, AIMessage) and kwargs.get("__role__") in ("assistant", "teacher"):
            parts.append(f"老师: {text}")
        elif isinstance(msg, HumanMessage) and kwargs.get("__role__") in ("user", "student"):
            parts.append(f"学员: {text}")
    return "\n".join(parts) if parts else ""


def _format_conversation_history(messages: List[AnyMessage]) -> str:
    """
    格式化对话历史为文本（从 aitutor-magic-agent review_common.format_conversation_history 迁移）
    """
    formatted = []
    for msg in messages:
        kwargs = getattr(msg, "additional_kwargs", {}) or {}
        if isinstance(msg, AIMessage) and kwargs.get("__role__") == "assistant":
            text = kwargs.get("__text__", "")
            if text:
                formatted.append(f"老师: {text}")
        elif isinstance(msg, HumanMessage) and kwargs.get("__role__") == "user":
            text = kwargs.get("__text__", "")
            if text:
                formatted.append(f"学员: {text}")
    return "\n".join(formatted) if formatted else "暂无对话记录"


def _parse_json_response(content: str) -> Any:
    """Parse LLM response that may be wrapped in markdown code blocks."""
    text = (content or "").strip()
    if not text:
        return None
    if text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"高光分析 JSON 解析失败: {text[:200]}")
        return None
