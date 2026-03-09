from typing import List, Optional, Any
import json
import logging
from langchain_core.messages import AnyMessage
from agentickit.core.exception import AgenticException
from agentickit.core.infra.clients.http.factory import HttpClientFactory
from agentickit.core.infra.config.loader import get_config
from agentickit.core.server.types import UserProfile
from .types import (
    ProjectSchema,
    ProjectModuleSchema,
    ActivitySchema,
    ActivityExtendSchema,
    SCOSchema,
    SCOExtendSchema,
    SCOSegmentSchema,
    SCOChatHistorySchema,
    SCOHistoryExtendSchema,
    SCOChatHistoryStoreSchema,
    ALL_CONTENT_TYPES,
)
from agentickit.prosonaagent.utils.user import get_token
from agentickit.artifact.core import get_artifact_client
from agentickit.artifact.core.models import ArtifactCreate

logger = logging.getLogger(__name__)

BASE_URL = get_config("api.api_base_url")
API_SOURCE = get_config("api.api_source")


def _get_client(context_id: str):
    return HttpClientFactory.create_async_client(
        base_url=BASE_URL,
        headers={
            "content-type": "application/json",
            "source": API_SOURCE,
            "token": get_token(context_id),
        },
    )


async def get_project_info(
    context_id: str, project_id: str, source_type: int = 1
) -> ProjectSchema:
    """
    获取课程基本信息

    Args:
        context_id: 上下文ID
        project_id: 课程ID
        source_type: 查询类型 1:课程 2:活动，默认1

    Returns:
        ProjectSchema: 课程信息

    Raises:
        AgenticException: 请求失败时的业务异常
    """
    endpoint = "aitutor/program/info/query"
    payload = {"actvId": project_id, "sourceType": source_type}

    try:
        logger.info(
            f"[get_project_info] 正在请求课程信息: project_id={project_id}, source_type={source_type}"
        )

        client = _get_client(context_id)
        response = await client.request(method="POST", url=endpoint, json=payload)
        response.raise_for_status()
        response = response.json()

        logger.info(
            f"[get_project_info] 成功获取课程信息: id={project_id}, name={response.get('actvName')}"
        )
        return response

    except Exception as e:
        logger.error(
            f"[get_project_info] 获取课程信息失败: project_id={project_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_project_info_error",
            project_id,
            str(e),
        )


async def get_project_modules(
    context_id: str, project_id: str, include_draft: bool = True
) -> List[ProjectModuleSchema]:
    """
    获取课程模块列表（两层结构：Module -> Activity）

    Args:
        context_id: 上下文ID
        project_id: 课程ID
        include_draft: 是否包含草稿，默认True

    Returns:
        List[ProjectModuleSchema]: 课程模块列表，每个模块包含其活动列表

    Raises:
        AgenticException: 请求失败时的业务异常
    """
    endpoint = "aitutor/program/outline/query"
    payload = {"actvId": project_id, "includeDraft": include_draft}

    try:
        logger.info(
            f"[get_project_modules] 正在请求课程模块列表: project_id={project_id}"
        )

        client = _get_client(context_id)
        response = await client.request(method="POST", url=endpoint, json=payload)
        response.raise_for_status()
        response = response.json()
        response = [ActivitySchema(**item) for item in response.get("items", [])]
        response = _convert_to_modules(response)

        logger.info(
            f"[get_project_modules] 成功获取课程模块列表: project_id={project_id}, 包含{len(response)}个模块"
        )
        return response

    except Exception as e:
        logger.error(
            f"[get_project_modules] 获取课程模块列表失败: project_id={project_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_project_modules_error",
            project_id,
            str(e),
        )


async def get_project_activities(
    context_id: str, project_id: str
) -> List[ActivityExtendSchema]:
    """
    获取课程活动列表

    Args:
        context_id: 上下文ID
        project_id: 课程ID

    Returns:
        List[ActivityExtendSchema]: 课程活动列表
    """
    modules = await get_project_modules(context_id, project_id)
    return get_project_activities_from_modules(modules)


def _convert_to_modules(items: List[ActivitySchema]) -> List[ProjectModuleSchema]:
    """
    将API响应转换为Module结构

    Args:
        items: API返回的items列表

    Returns:
        List[ModuleInfoModel]: 模块列表
    """
    modules: List[ProjectModuleSchema] = []

    for item in items:
        if item.get("itemType", 0) == 1:
            module_name = item.get("name", "")
            module_description = item.get("description", "")
            module = ProjectModuleSchema(
                moduleDescription=module_description,
                moduleName=module_name,
                activities=[],
            )

            # 处理children
            children = item.get("children", [])
            if children:
                module["activities"] = _convert_to_activities(children, module_name)

            modules.append(module)

    return modules


def get_project_activities_from_modules(
    modules: List[ProjectModuleSchema],
) -> List[ActivityExtendSchema]:
    """
    从模块列表中提取活动列表

    Args:
        modules: 模块列表

    Returns:
        List[ActivityExtendSchema]: 课程活动列表
    """
    all_activities = []
    for module in modules:
        module_activities = module.get("activities", [])
        all_activities.extend(module_activities)

    return all_activities


def _convert_to_activities(
    items: List[ActivitySchema], module_name: str
) -> List[ActivityExtendSchema]:
    """
    将API响应转换为Activity结构（用于模块内的活动）

    Args:
        items: API返回的items列表
        module_name: 模块名称

    Returns:
        List[ActivityExtendSchema]: 活动列表
    """
    activities: List[ActivityExtendSchema] = []

    for item in items:
        if item.get("itemType", 0) == 0:
            item_name = item.get("name", "")
            ext = item.get("ext", "")
            # 解析 ext 字段中的 bizActvType
            activity_type = "lecture"
            if ext:
                try:
                    ext_data = json.loads(ext)
                    activity_type = ext_data.get("bizActvType", "")
                except json.JSONDecodeError:
                    logger.warning(f"[ProjectAPIClient] 无法解析ext字段JSON: {ext}")

            activity = ActivityExtendSchema(
                {
                    "id": item.get("refId", ""),
                    "name": item_name,
                    "type": activity_type,
                    "description": item.get("description", ""),
                    "module_name": module_name,
                }
            )
            activities.append(activity)

    return activities


async def get_sco_info(
    context_id: str, activity: ActivityExtendSchema, user_profile: UserProfile
) -> List[SCOExtendSchema]:
    """
    获取授课SCO列表

    Args:
        context_id: 上下文ID
        activity: 活动ID
        user_profile: 用户信息

    Returns:
        List[SCOExtendSchema]: SCO列表
    """
    endpoint = "aitutor/sco/activity/info"
    user_id = user_profile.get("user_id")
    activity_id = activity.get("id")
    activity_type = activity.get("type")
    payload = {"actvId": activity_id, "userId": user_id}

    try:
        logger.info(
            f"[get_sco_info] 正在请求授课SCO列表: activity_id={activity_id}, user_id={user_id}"
        )

        client = _get_client(context_id)
        response = await client.request(method="POST", url=endpoint, json=payload)
        response.raise_for_status()
        response = response.json()
        response = [SCOSchema(**item) for item in response.get("scoList", [])]
        logger.info(
            f"[get_sco_info] 成功获取授课SCO列表: activity_id={activity_id}, 包含{len(response)}个SCO"
        )

        return [
            *[
                SCOExtendSchema(
                    id=item.get("refId"),
                    name=item.get("scoName"),
                    type=(
                        _get_sco_type(item.get("scoType"), item.get("narration"))
                        if activity_type != "report"
                        else "personal_report"
                    ),
                    description=item.get("description"),
                    blueprint=_get_sco_blueprint(item.get("narration")),
                    rule=_get_sco_rule(item.get("narration")),
                    activity_id=activity_id,
                )
                for item in response
            ],
            *(
                [
                    SCOExtendSchema(
                        id=f"{activity_id}-summary",
                        name="lecture summary",
                        type="lecture_summary",
                        description="",
                        content="",
                        blueprint="",
                        rule="",
                        activity_id=activity_id,
                    )
                ]
                if activity_type == "lecture"
                else []
            ),
        ]

    except Exception as e:
        logger.error(
            f"[get_sco_info] 获取授课SCO列表失败: activity_id={activity_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_sco_info",
            activity_id,
            str(e),
        )


async def get_sco_content(
    context_id: str, activity_id: str, sco_id: str, user_profile: UserProfile
) -> List[SCOSegmentSchema]:
    """
    获取SCO内容

    Args:
        activity_id: 活动ID
        sco_id: SCO ID
        user_profile: 用户信息

    Returns:
        List[SCOSegmentSchema]: SCO内容列表

    Raises:
        AgenticException: 请求失败时的业务异常
    """

    endpoint = "aitutor/sco/stu/course/detail"
    payload = {
        "actvId": activity_id,
        "scoId": sco_id,
        "userId": user_profile.get("user_id"),
    }

    try:
        logger.info(
            f"[get_sco_content] 正在请求SCO内容: activity_id={activity_id}, sco_id={sco_id}"
        )

        client = _get_client(context_id)
        response = await client.request(method="POST", url=endpoint, json=payload)
        response.raise_for_status()
        response = response.json()

        response = [
            SCOSegmentSchema(**item) for item in response.get("items", []) or []
        ]

        logger.info(
            f"[get_sco_content] 成功获取SCO内容: activity_id={activity_id}, sco_id={sco_id}"
        )
        return response

    except Exception as e:
        logger.error(
            f"[get_sco_content] 获取SCO内容失败: activity_id={activity_id}, sco_id={sco_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_sco_content_error",
            activity_id,
            sco_id,
            str(e),
        )


async def get_artifact_content(
    user_profile: UserProfile,
    artifact_id: str,
    version: Optional[int] = None,
) -> dict[str, Any] | list[Any]:
    """
    获取Artifact内容
    """
    client = get_artifact_client()

    try:
        logger.info(
            f"[get_artifact_content] 正在请求Artifact内容: artifact_id={artifact_id}, version={version}"
        )

        response = await client.get_artifact_by_id(
            org_id=user_profile.get("org_id"),
            user_id=user_profile.get("user_id"),
            artifact_id=artifact_id,
            version=version,
        )

        # json、md两种格式
        try:
            response = json.loads(response.content)
        except json.JSONDecodeError:
            response = response.content

        logger.info(
            f"[get_artifact_content] 成功获取Artifact内容: artifact_id={artifact_id}, version={version}"
        )
        return response
    except Exception as e:
        logger.error(
            f"[get_artifact_content] 获取Artifact内容失败: artifact_id={artifact_id}, version={version}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_artifact_content_error",
            artifact_id,
            version,
            str(e),
        )


async def create_artifact(
    user_profile: UserProfile, artifact_create: ArtifactCreate
) -> str:
    """
    创建Artifact
    """
    client = get_artifact_client()

    try:
        logger.info(
            f"[create_artifact] 正在创建Artifact: artifact_create={artifact_create}"
        )

        response = await client.create_artifact(
            org_id=user_profile.get("org_id"),
            user_id=user_profile.get("user_id"),
            app_code="prosona",
            artifact=artifact_create,
        )
        artifact_id = response.id

        logger.info(
            f"[create_artifact] 成功创建Artifact: artifact_create={artifact_create}, artifact_id={artifact_id}"
        )
        return artifact_id
    except Exception as e:
        logger.error(
            f"[create_artifact] 创建Artifact失败: artifact_create={artifact_create}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.create_artifact_error",
            json.dumps(artifact_create, ensure_ascii=False),
            str(e),
        )


async def start_sco(context_id: str, sco_id: str) -> None:
    endpoint = "aitutor/sco/stu/course/submit"
    params = {
        "scoId": sco_id,
        "done": False,
    }
    client = _get_client(context_id)

    try:
        logger.info(f"[start_sco] 正在开始SCO: sco_id={sco_id}")

        response = await client.request(method="PUT", url=endpoint, params=params)
        response.raise_for_status()

        logger.info(f"[start_sco] 成功开始SCO: sco_id={sco_id}")
    except Exception as e:
        logger.error(
            f"[start_sco] 开始SCO失败: sco_id={sco_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.start_sco_error",
            sco_id,
            str(e),
        )


async def end_sco(context_id: str, sco_id: str, chat_history: List[AnyMessage]) -> None:
    endpoint = "aitutor/sco/stu/course/submit"
    chat_history = [
        SCOChatHistoryStoreSchema(
            role=msg.additional_kwargs.get("__role__"),
            name=msg.additional_kwargs.get("__name__"),
            avatar=msg.additional_kwargs.get("__avatar__"),
            type=msg.additional_kwargs.get("__content_type__"),
            text=msg.additional_kwargs.get("__text__"),
            card=msg.additional_kwargs.get("__card__"),
        )
        for msg in chat_history
        if msg.additional_kwargs.get("__text__")
        or msg.additional_kwargs.get("__card__")
    ]
    params = {
        "scoId": sco_id,
        "done": True,
    }
    payload = {
        "context_id": context_id,
        "chat_history": chat_history,
    }
    client = _get_client(context_id)

    try:
        logger.info(f"[end_sco] 正在结束SCO: sco_id={sco_id}")

        response = await client.request(
            method="POST", url=endpoint, params=params, json=payload
        )
        response.raise_for_status()

        logger.info(f"[end_sco] 成功结束SCO: sco_id={sco_id}")
    except Exception as e:
        logger.error(
            f"[end_sco] 结束SCO失败: sco_id={sco_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.end_sco_error",
            sco_id,
            str(e),
        )


async def get_sco_history(
    context_id: str,
    sco_id: str,
) -> List[SCOHistoryExtendSchema]:
    """
    获取SCO历史记录，用于获取摘要
    """
    endpoint = "aitutor/sco/stu/course/result/history"
    params = {"scoId": sco_id, "limit": 100, "offset": 0, "includeContent": 0}
    client = _get_client(context_id)

    try:
        logger.info(f"[get_sco_history] 正在请求SCO历史记录: sco_id={sco_id}")

        response = await client.request(method="GET", url=endpoint, params=params)
        response.raise_for_status()
        response = response.json()
        response = response.get("datas", [])

        response = [
            SCOHistoryExtendSchema(
                id=history_item.get("id"),
                order=history_item.get("orderIndex"),
                chat_history=[],
            )
            for history_item in response
        ]

        logger.info(f"[get_sco_history] 成功获取SCO历史记录: sco_id={sco_id}")
        return response
    except Exception as e:
        logger.error(
            f"[get_sco_history] 获取SCO历史记录失败: sco_id={sco_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_sco_history_error",
            sco_id,
            str(e),
        )


async def get_sco_all_messages(
    context_id: str,
    user_profile: UserProfile,
    sco_id: str,
    content_types: List[str] = ALL_CONTENT_TYPES,
) -> List[SCOHistoryExtendSchema]:
    """
    获取SCO所有消息，用于获取SCO历史记录的全量消息
    """
    endpoint = "aitutor/sco/stu/course/result/history"
    # TODO 优化，提供all history
    params = {"scoId": sco_id, "limit": 100, "offset": 0, "includeContent": 1}
    client = _get_client(context_id)

    try:
        logger.info(f"[get_sco_all_messages] 正在请求SCO所有消息: sco_id={sco_id}")

        async def dive_sco_content(
            chat_history_item: SCOChatHistoryStoreSchema,
        ) -> SCOChatHistorySchema["content"]:  # noqa: F821
            item_type = chat_history_item.get("type")
            if item_type == "text":
                return chat_history_item.get("text")

            card = chat_history_item.get("card")
            if not card:
                return None

            data = card.get("data", {})
            if item_type == "record":
                return await get_sco_messages(
                    context_id,
                    user_profile,
                    data.get("sco_id"),
                    data.get("order"),
                    content_types,
                )

            if item_type == "report":
                return await get_artifact_content(
                    user_profile, data.get("artifact_id", "")
                )

            return data

        response = await client.request(method="GET", url=endpoint, params=params)
        response.raise_for_status()
        response = response.json()
        response = response.get("datas", [])
        response = [
            SCOHistoryExtendSchema(
                id=history_item.get("id"),
                order=history_item.get("orderIndex"),
                chat_history=[
                    SCOChatHistorySchema(
                        role=chat_history_item.get("role"),
                        name=chat_history_item.get("name"),
                        avatar=chat_history_item.get("avatar"),
                        type=chat_history_item.get("type"),
                        content=await dive_sco_content(chat_history_item),
                    )
                    for chat_history_item in json.loads(
                        history_item.get("extContent")
                    ).get("chat_history", [])
                    if chat_history_item.get("type") in content_types
                ],
            )
            for history_item in response
        ]

        logger.info(f"[get_sco_all_messages] 成功获取SCO所有消息: sco_id={sco_id}")
        return response
    except Exception as e:
        logger.error(
            f"[get_sco_all_messages] 获取SCO所有消息失败: sco_id={sco_id}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_sco_all_messages_error",
            sco_id,
            str(e),
        )


async def get_sco_messages(
    context_id: str,
    user_profile: UserProfile,
    sco_id: str,
    order: int,
    content_types: List[str] = ALL_CONTENT_TYPES,
) -> List[SCOChatHistorySchema]:
    endpoint = "aitutor/sco/stu/course/result/history/getByOrder"
    params = {
        "scoId": sco_id,
        "orderIndex": order,
    }
    client = _get_client(context_id)

    try:
        logger.info(
            f"[get_sco_messages] 正在请求SCO消息: sco_id={sco_id}, order={order}"
        )

        async def dive_sco_content(
            chat_history_item: SCOChatHistoryStoreSchema,
        ) -> SCOChatHistorySchema["content"]:  # noqa: F821
            item_type = chat_history_item.get("type")
            if item_type == "text":
                return chat_history_item.get("text")

            card = chat_history_item.get("card")
            data = card.get("data", {})
            if item_type == "record":
                return await get_sco_messages(
                    context_id,
                    user_profile,
                    data.get("sco_id"),
                    data.get("order"),
                    content_types,
                )

            if item_type == "report":
                return await get_artifact_content(
                    user_profile, data.get("artifact_id", "")
                )

            return data

        response = await client.request(method="GET", url=endpoint, params=params)
        response.raise_for_status()
        response = response.json()
        response = [
            SCOChatHistorySchema(
                role=item.get("role"),
                name=item.get("name"),
                avatar=item.get("avatar"),
                type=item.get("type"),
                content=await dive_sco_content(item),
            )
            for item in json.loads(response.get("extContent")).get("chat_history", [])
            if item.get("type") in content_types
        ]

        logger.info(
            f"[get_sco_messages] 成功获取SCO消息: sco_id={sco_id}, order={order}"
        )
        return response
    except Exception as e:
        logger.error(
            f"[get_sco_messages] 获取SCO消息失败: sco_id={sco_id}, order={order}, error={e}",
            exc_info=True,
        )
        raise AgenticException(
            "apis.prosonaagent.aom.get_sco_messages_error",
            sco_id,
            order,
            str(e),
        )


def _get_sco_type(sco_type: int, narration: str) -> str:
    """
    获取SCO类型

    Args:
        sco_type: SCO类型
        narration: narration JSON字符串

    Returns:
        str: SCO类型
    """
    if sco_type == 4:
        return "quiz"
    elif sco_type == 3:
        try:
            data = json.loads(narration)
            return data.get("bizType", "content")
        except json.JSONDecodeError:
            return "content"

    return "quiz"


def _get_sco_blueprint(narration: str) -> str:
    """
    从narration中解析教学蓝图

    Args:
        narration: narration JSON字符串

    Returns:
        str: 教学蓝图，指导老师理解素材，教学设计
    """
    try:
        data = json.loads(narration)
        return data.get("blueprint", "")
    except Exception as e:
        return ""


def _get_sco_rule(narration: str) -> str:
    """
    从narration中解析完成标准

    Args:
        narration: narration JSON字符串

    Returns:
        str: 完成标准，指导整个SCO的教学
    """
    try:
        data = json.loads(narration)
        return data.get("rule", "")
    except Exception as e:
        return ""
