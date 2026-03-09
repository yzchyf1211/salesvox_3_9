"""
Business-specific API functions for AOM.

Quiz content API and related helpers, separated from the framework's
agentickit.prosonaagent.aom.api module.
"""

import json
import logging
from typing import Any, Dict

from agentickit.core.exception import AgenticException
from agentickit.core.infra.clients.http.factory import HttpClientFactory
from agentickit.core.infra.config.loader import get_config
from agentickit.core.infra.langfuse.prompt import get_prompt_langfuse, get_prompt, Langfuse
from agentickit.core.server.types import UserProfile
from agentickit.prosonaagent.utils.user import get_token

logger = logging.getLogger(__name__)


def get_prompt_client(prompt_name: str) -> Langfuse:
    return get_prompt(name=prompt_name, langfuse_client=get_prompt_langfuse("aitutor"))


_BASE_URL = get_config("api.api_base_url")
_API_SOURCE = get_config("api.api_source")


def _get_client(context_id: str):
    return HttpClientFactory.create_async_client(
        base_url=_BASE_URL,
        headers={
            "content-type": "application/json",
            "source": _API_SOURCE,
            "token": get_token(context_id),
        },
    )


def _safe_get_content_value(content: Any, key: str, default: Any = "") -> Any:
    """
    安全地从content字段中获取值，支持字典和JSON字符串格式

    Args:
        content: content字段，可能是字典或JSON字符串
        key: 要获取的键名
        default: 默认值

    Returns:
        获取到的值或默认值
    """
    try:
        if isinstance(content, dict):
            return content.get(key, default)
        elif isinstance(content, str):
            if content.strip():
                parsed_content = json.loads(content)
                return parsed_content.get(key, default)
            else:
                return default
        else:
            return default
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        logger.warning(
            f"[_safe_get_content_value] 解析content字段失败: {e}, content={content}"
        )
        return default


async def get_quiz_content(
    context_id: str, activity_id: str, sco_id: str, user_profile: UserProfile
) -> Dict[str, Any]:
    """
    获取问答题SCO内容

    Args:
        context_id: 上下文ID
        activity_id: 活动ID
        sco_id: SCO ID
        user_profile: 用户信息

    Returns:
        Dict: 问答题内容，包含 exam_id, content, explain_text, answer_content,
              answer_analysis, solution, rules, knowledge_points, ext_info, item_type

    Raises:
        AgenticException: 请求失败时的业务异常
    """
    endpoint = "aitutor/sco/assessment/ques/list"
    payload = {
        "actvId": activity_id,
        "scoId": sco_id,
        "userId": user_profile.get("user_id"),
    }

    try:
        logger.info(
            f"[get_quiz_content] 正在请求问答题内容: activity_id={activity_id}, sco_id={sco_id}"
        )

        client = _get_client(context_id)
        response = await client.request(method="POST", url=endpoint, json=payload)
        response.raise_for_status()
        response = response.json()

        if not response:
            raise AgenticException(
                "apis.prosonaagent.aom.get_quiz_content_empty",
                activity_id,
                sco_id,
            )

        # 返回题目数组，优先按 scoId 匹配，匹配不到时兜底取第一题
        if isinstance(response, list):
            raw_ques = next(
                (item for item in response if item.get("scoId") == sco_id),
                response[0],
            )
        else:
            raw_ques = response

        # 题目类型字段兼容：优先使用旧的 itemType，没有则退回到新字段 type
        item_type = (
            raw_ques.get("itemType")
            if isinstance(raw_ques.get("itemType"), int)
            else raw_ques.get("type", 0)
        ) or 0

        ext_info = raw_ques.get("extInfo", {})

        quiz_content = {
            "exam_id": str(raw_ques.get("id", "")),
            "content": raw_ques.get("content", ""),
            "explain_text": raw_ques.get("explainText", "") or "",
            "answer_content": raw_ques.get("answerContent", "") or "",
            "answer_analysis": _safe_get_content_value(
                ext_info, "answerAnalysis", ""
            ),
            "solution": _safe_get_content_value(ext_info, "solution", ""),
            "rules": _safe_get_content_value(
                ext_info, "passConditions", {}
            ).get("rules", [""]),
            "knowledge_points": [
                {
                    "id": item.get("kpKey", ""),
                    "description": "\uff1a".join(
                        [item.get("title", ""), item.get("description", "")]
                    ),
                }
                for item in _safe_get_content_value(
                    ext_info, "knowledgePoints", []
                )
            ],
            "ext_info": ext_info,
            "item_type": item_type,
        }

        logger.info(
            f"[get_quiz_content] 成功获取问答题内容: activity_id={activity_id}, sco_id={sco_id}"
        )
        return quiz_content

    except Exception as e:
        logger.error(
            f"[get_quiz_content] 获取问答题内容失败: activity_id={activity_id}, sco_id={sco_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_quiz_content_error",
            activity_id,
            sco_id,
            str(e),
        )
