"""
Multimodal Content SCO TaskHandler - 多模态内容类型SCO的处理器

从 aitutor-magic-agent 的 SCOMultimodalContentPlugin 迁移而来，
通过 prosona-agent 的 TaskHandler 模式实现（仅 study 模式）。

原始方法映射:
- SCOMultimodalContentPlugin.load_content()           -> SCOMiddleware 已加载 sco_segment_list
- SCOMultimodalContentPlugin.get_content_context()     -> abefore(): 注入内容上下文
- SCOMultimodalContentPlugin.get_teach_design_context  -> abefore(): 注入教学设计上下文
- SCOMultimodalContentPlugin.get_action_schema_context -> abefore(): 注入动作结构上下文
- SCOMultimodalContentPlugin.get_system_feedback_schema_context -> abefore(): 注入系统反馈结构上下文
- SCOMultimodalContentPlugin.get_reminder_context()    -> abefore(): 注入提醒上下文
- SCOMultimodalContentPlugin.render_action()           -> aget_card(): 构建AOMCard (play_video/display_ppt)
- SCOMultimodalContentPlugin._render_next_item_action  -> move_to_next_item tool
- SCOMultimodalContentPlugin.run_lifecycle(RESUME)     -> aresume(): 注入恢复上下文
- SCOMultimodalContentPlugin.trigger_action()          -> aafter_user_input(): 视频播放结束事件
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from agentickit.prosonaagent.aom.card import build_content_card
from agentickit.prosonaagent.core.handler.enhance_task_handler import EnhanceTaskHandler
from agentickit.prosonaagent.aom.types import AOMCard
from agentickit.prosonaagent.aom.state import SCOTaskState
from agentickit.prosonaagent.utils.context import (
    build_tool_call_success_system_feedback,
)

from app.api import get_prompt_client
from app.utils.time_utils import calculate_duration
from agentickit.prosonaagent.core.tools import _builtin_conversation


logger = logging.getLogger(__name__)

# Langfuse prompt keys (对应原始 PromptConstants)
_PROMPT_CONTENT = "v2/plugin/sco/multimodal/content"
_PROMPT_TEACH_DESIGN = "v2/plugin/sco/multimodal/teach_design"
_PROMPT_ACTION_SCHEMA = "v2/plugin/sco/multimodal/action_schema"
_PROMPT_SYSTEM_FEEDBACK_SCHEMA = "v2/plugin/sco/multimodal/system_feedback_schema"
_PROMPT_REMINDER = "v2/plugin/sco/multimodal/reminder"
_PROMPT_REMINDER_COMPLETE = "v2/plugin/sco/multimodal/reminder_complete"
_PROMPT_VIDEO_REMINDER = "v2/plugin/sco/multimodal/video_reminder"
_PROMPT_VIDEO_USER_INPUT_REMINDER = "v2/plugin/sco/multimodal/video_user_input_reminder"
_PROMPT_PPT_REMINDER = "v2/plugin/sco/multimodal/ppt_reminder"
_PROMPT_OBSERVE_ACTION_PLAY_VIDEO = "v2/plugin/sco/content/observe_action_play_video"
_PROMPT_OBSERVE_ACTION_REPLAY_VIDEO = "v2/plugin/sco/content/observe_action_replay_video"
_PROMPT_OBSERVE_ACTION_DISPLAY_PPT = "v2/plugin/sco/multimodal/observe_action_display_ppt"
_PROMPT_OBSERVE_ACTION_NEXT_ITEM = "v2/plugin/sco/multimodal/observe_action_next_item"
_PROMPT_OBSERVE_ACTION_ALL_COMPLETE = "v2/plugin/sco/multimodal/observe_action_all_complete"
_PROMPT_OBSERVE_ACTION_COMPLETE = "v2/plugin/sco/multimodal/observe_action_complete"
_PROMPT_LIFECYCLE_RESUME_REMINDER = "v2/plugin/sco/multimodal/lifecycle_resume_reminder"
_PROMPT_WAIT_SYSTEM_FEEDBACK_PLAY_VIDEO_ENDED = (
    "v2/plugin/sco/content/wait_system_feedback_play_video_ended"
)
_PROMPT_OBSERVE_SYSTEM_FEEDBACK_VIDEO_PLAY_ENDED = (
    "v2/plugin/sco/content/observe_system_feedback_video_play_ended"
)


# ==================== Helper Functions ====================


def _get_item_type_name(item_type: int) -> str:
    if item_type == 1 or item_type == 6:
        return "视频"
    elif item_type == 5:
        return "PPT"
    return "未知"


def _get_item_by_id(
    items: List[Dict[str, Any]], target_id: str
) -> Optional[Dict[str, Any]]:
    for item in items:
        if str(item.get("id", "")) == str(target_id or ""):
            return item
    return None


def _build_items_context(items: List[Dict[str, Any]]) -> str:
    """构建素材列表的上下文描述（从原始 _build_items_context 迁移，字段名适配 SCOSegmentSchema camelCase）"""
    items_desc = []
    for i, item in enumerate(items):
        item_type = item.get("itemType", 0)
        item_type_name = _get_item_type_name(item_type)

        item_desc = f"【素材{i + 1}】\n"
        item_desc += f"- 素材ID: {item.get('id', '')}\n"
        item_desc += f"- 名称: {item.get('name', '')}\n"
        item_desc += f"- 类型: {item_type_name}\n"

        if item_type == 1:
            start_time = item.get("startTime", "")
            end_time = item.get("endTime", "")
            if start_time and end_time:
                try:
                    duration = calculate_duration(start_time, end_time)
                    item_desc += f"- 时长: {duration}\n"
                except ValueError:
                    pass
        elif item_type == 5:
            item_desc += f"- 链接: {item.get('contentUrl', '')}\n"

        if item.get("description"):
            item_desc += f"- 描述: {item.get('description', '')}\n"
        if item.get("script"):
            item_desc += f"- 脚本: {item.get('script', '')}\n"

        items_desc.append(item_desc)

    return "\n".join(items_desc)


# ==================== Custom Tool: move_to_next_item ====================


@tool
async def wait_system_feedback(
    name: str,
    tool_runtime: ToolRuntime = None,
) -> Command:
    """Wait for system feedback before proceeding.
    The agent will be paused until the specified system feedback is received.

    Args:
        name: the name of the system feedback to wait for (e.g. "video_play_ended")
    """
    prompt_client = get_prompt_client(_PROMPT_WAIT_SYSTEM_FEEDBACK_PLAY_VIDEO_ENDED)
    wait_context = prompt_client.compile()

    response = interrupt({
        "type": "wait_system_feedback",
        "name": name,
        "context": wait_context,
    })

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    finished_prompt = get_prompt_client(
        _PROMPT_OBSERVE_SYSTEM_FEEDBACK_VIDEO_PLAY_ENDED
    )
    finished_context = finished_prompt.compile(timestamp=timestamp)

    tool_call_id = tool_runtime.tool_call_id if tool_runtime else None
    messages = []
    if tool_call_id is not None:
        messages.append(
            ToolMessage(
                content=build_tool_call_success_system_feedback(
                    finished_context
                ),
                tool_call_id=tool_call_id,
            )
        )

    return Command(update={"messages": messages})


@tool
async def move_to_next_item(
    tool_runtime: ToolRuntime = None,
) -> Command:
    """Move to the next item in the multimodal content sequence.
    Advances the current item index and provides context about the next item or completion.
    """
    state = tool_runtime.state
    items = state.get("sco_segment_list", [])
    current_index = state.get("current_item_index", 0) or 0
    sco = state.get("sco", {})
    rule = sco.get("rule", "")

    new_index = current_index + 1

    if new_index >= len(items):
        prompt_client = get_prompt_client(_PROMPT_OBSERVE_ACTION_ALL_COMPLETE)
        context = prompt_client.compile(rule=rule)
    else:
        next_item = items[new_index]
        item_type = next_item.get("itemType", 0)
        item_type_name = _get_item_type_name(item_type)
        prompt_client = get_prompt_client(_PROMPT_OBSERVE_ACTION_NEXT_ITEM)
        context = prompt_client.compile(
            current_index=new_index + 1,
            total_items=len(items),
            item_name=next_item.get("name", ""),
            item_type=item_type_name,
        )

    tool_msg = ToolMessage(
        content=build_tool_call_success_system_feedback(context),
        tool_call_id=tool_runtime.tool_call_id,
    )

    return Command(
        update={
            "current_item_index": new_index,
            "messages": [tool_msg],
        }
    )


# ==================== State ====================


class MultimodalTaskState(SCOTaskState):
    current_item_index: Optional[int]


# ==================== Handler ====================


class MultimodalTaskHandler(EnhanceTaskHandler[MultimodalTaskState]):
    """多模态内容SCO处理器（study 模式）"""

    name = "sco:content"
    state_schema = MultimodalTaskState
    tools = [
        move_to_next_item,
        wait_system_feedback,
        _builtin_conversation,
    ]



    # ==================== Lifecycle Hooks ====================

    async def abefore(
        self,
        state: MultimodalTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any] | None:
        delta_state: Dict[str, Any] = await super().abefore(state, runtime) or {}

        items = state.get("sco_segment_list", [])

        delta_state["current_item_index"] = 0

        messages = delta_state.get("messages", [])

        # 1. 内容上下文（get_content_context）
        content_ctx = self._build_content_context(items)
        if content_ctx:
            messages.append(SystemMessage(content=content_ctx))

        delta_state["messages"] = messages
        return delta_state

    async def aresume(
        self,
        state: MultimodalTaskState,
        runtime: Runtime,
    ) -> Dict[str, Any] | None:
        """恢复学习 - 注入当前素材上下文（从 run_lifecycle RESUME 迁移）"""
        delta_state: Dict[str, Any] = await super().aresume(state, runtime) or {}

        items = state.get("sco_segment_list", [])
        current_index = state.get("current_item_index", 0) or 0

        current_item = items[current_index] if current_index < len(items) else None
        if not current_item:
            prompt_client = get_prompt_client(_PROMPT_REMINDER_COMPLETE)
            messages = delta_state.get("messages", [])
            messages.append(SystemMessage(content=prompt_client.compile()))
            delta_state["messages"] = messages
            return delta_state

        item_type = current_item.get("itemType", 0)
        item_type_name = _get_item_type_name(item_type)

        prompt_client = get_prompt_client(_PROMPT_LIFECYCLE_RESUME_REMINDER)
        context = prompt_client.compile(
            current_index=current_index + 1,
            total_items=len(items),
            item_name=current_item.get("name", ""),
            item_type=item_type_name,
        )

        messages = delta_state.get("messages", [])
        messages.append(SystemMessage(content=context))
        delta_state["messages"] = messages
        return delta_state

    async def aafter_user_input(
        self,
        state: MultimodalTaskState,
        runtime: Runtime,
        user_input: str,
        action: Optional[str],
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        """处理用户输入/系统事件（从 trigger_action 迁移）"""
        if action == "biz-aitutor-finished-video":
            return self._handle_video_finished()
        return None

    # ==================== Card Rendering ====================

    async def aget_card(
        self,
        state: MultimodalTaskState,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AOMCard:
        """
        构建多模态内容的 AOMCard（从 render_action 迁移）

        支持的 action:
        - play_video / replay_video: 播放/重播视频
        - display_ppt: 展示PPT
        """
        params = params or {}
        if isinstance(params, str):
            params = json.loads(params)

        items = state.get("sco_segment_list", [])
        current_index = state.get("current_item_index", 0) or 0

        # 通过 params.id 定位素材，或 fallback 到 current_item_index
        target_id = params.get("id", "")
        if target_id:
            current_item = _get_item_by_id(items, target_id)
        else:
            current_item = items[current_index] if current_index < len(items) else None

        if not current_item:
            prompt_client = get_prompt_client(_PROMPT_OBSERVE_ACTION_COMPLETE)
            return build_content_card(
                id="multimodal-complete",
                name="完成",
                content={"action": "complete"},
                description=prompt_client.compile(),
            )

        item_type = current_item.get("itemType", 0)

        # 播放视频 / 重播视频
        if (item_type == 1 or item_type == 6) and action in (
            "play_video",
            "replay_video",
        ):
            return self._build_video_card(current_item, action, params)

        # 展示PPT
        if item_type == 5 and action == "display_ppt":
            return self._build_ppt_card(current_item, action, params)

        prompt_client = get_prompt_client(_PROMPT_OBSERVE_ACTION_COMPLETE)
        return build_content_card(
            id="multimodal-fallback",
            name="内容",
            content={"action": action},
            description=prompt_client.compile(),
        )

    # ==================== Card Builders ====================

    def _build_video_card(
        self,
        item: Dict[str, Any],
        action: str,
        params: Dict[str, Any],
    ) -> AOMCard:
        """构建视频卡片（从 _render_video_action study 模式迁移）"""
        item_type = item.get("itemType", 0)
        action_label = "播放视频" if action == "play_video" else "重新播放视频"

        if item_type == 1:
            content = {
                "id": item.get("id", ""),
                "title": item.get("name", ""),
                "fileId": item.get("fileId", ""),
                "startTime": item.get("startTime", ""),
                "endTime": item.get("endTime", ""),
                "playback_rate": params.get("playback_rate", 1),
                "action": action_label,
            }
        else:
            content = {
                "id": item.get("id", ""),
                "title": item.get("name", ""),
                "richText": item.get("richText", ""),
                "playback_rate": params.get("playback_rate", 1),
                "action": action_label,
            }

        prompt_key = (
            _PROMPT_OBSERVE_ACTION_PLAY_VIDEO
            if action == "play_video"
            else _PROMPT_OBSERVE_ACTION_REPLAY_VIDEO
        )
        prompt_client = get_prompt_client(prompt_key)
        description = prompt_client.compile(
            name=item.get("name", ""),
            playback_rate=params.get("playback_rate", 1),
        )

        return build_content_card(
            id="multimodal-video",
            name=action_label,
            content=content,
            description=description,
        )

    def _build_ppt_card(
        self,
        item: Dict[str, Any],
        action: str,
        params: Dict[str, Any],
    ) -> AOMCard:
        """构建PPT卡片（从 _render_ppt_action study 模式迁移）"""
        action_label = "展示PPT" if action == "display_ppt" else "讲解PPT"

        content = {
            "id": item.get("id", ""),
            "title": item.get("name", ""),
            "contentUrl": item.get("contentUrl", ""),
            "script": item.get("script", ""),
            "description": item.get("description", ""),
            "action": action_label,
        }

        prompt_client = get_prompt_client(_PROMPT_OBSERVE_ACTION_DISPLAY_PPT)
        description = prompt_client.compile(
            name=item.get("name", ""),
            content_url=item.get("contentUrl", ""),
            script=item.get("script", ""),
            description=item.get("description", ""),
        )

        return build_content_card(
            id="multimodal-ppt",
            name=action_label,
            content=content,
            description=description,
        )

    # ==================== Context Builders ====================

    def _build_content_context(self, items: List[Dict[str, Any]]) -> str:
        """构建素材列表上下文（从 get_content_context 迁移）"""
        items_context = _build_items_context(items)
        prompt_client = get_prompt_client(_PROMPT_CONTENT)
        return prompt_client.compile(
            items_context=items_context,
            total_items=len(items),
        )

    def _build_teach_design_context(self, sco: Dict[str, Any]) -> str:
        """构建教学设计上下文（study 模式，从 get_teach_design_context 迁移）"""
        blueprint = sco.get("blueprint", "")
        rule = sco.get("rule", "")
        narration = sco.get("blueprint", "")

        prompt_client = get_prompt_client(_PROMPT_TEACH_DESIGN)
        return prompt_client.compile(
            blueprint=blueprint,
            rule=rule,
            narration=narration,
        )

    def _build_action_schema_context(self) -> str:
        """构建动作结构上下文（study 模式，从 get_action_schema_context 迁移）"""
        prompt_client = get_prompt_client(_PROMPT_ACTION_SCHEMA)
        return prompt_client.compile()

    def _build_system_feedback_schema_context(self) -> str:
        """构建系统反馈结构上下文（从 get_system_feedback_schema_context 迁移）"""
        prompt_client = get_prompt_client(_PROMPT_SYSTEM_FEEDBACK_SCHEMA)
        return prompt_client.compile()

    def _build_reminder_context(
        self,
        items: List[Dict[str, Any]],
        current_index: int,
    ) -> str:
        """构建提醒上下文（study 模式，从 get_reminder_context 迁移）"""
        current_item = items[current_index] if current_index < len(items) else None
        if not current_item:
            prompt_client = get_prompt_client(_PROMPT_REMINDER_COMPLETE)
            return prompt_client.compile()

        item_type = current_item.get("itemType", 0)
        item_type_name = _get_item_type_name(item_type)

        reminder_prompt = get_prompt_client(_PROMPT_REMINDER)
        unified_reminder = reminder_prompt.compile(
            current_index=current_index + 1,
            total_items=len(items),
            item_name=current_item.get("name", ""),
            item_type=item_type_name,
            item_script=current_item.get("script", ""),
            item_description=current_item.get("description", ""),
        )

        # 非用户输入时（初始进入），附加所有类型的提醒
        type_prompt = get_prompt_client(_PROMPT_VIDEO_REMINDER)
        type_reminder = type_prompt.compile()

        ppt_prompt = get_prompt_client(_PROMPT_PPT_REMINDER)
        type_reminder += ppt_prompt.compile()

        return f"{unified_reminder}\n\n{type_reminder}"

    # ==================== Event Handlers ====================

    def _handle_video_finished(self) -> Dict[str, Any]:
        """处理视频播放结束事件（从 trigger_action / _handle_video_finished 迁移）"""
        prompt_client = get_prompt_client(
            _PROMPT_OBSERVE_SYSTEM_FEEDBACK_VIDEO_PLAY_ENDED
        )
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context = prompt_client.compile(timestamp=timestamp)
        return {"messages": [SystemMessage(content=context)]}
