"""Speaker Middleware — attaches conversation tag and speaker metadata to model."""

from typing import Awaitable, Callable, Dict, Literal, Optional, TypedDict

from langchain_core.runnables.config import (
    ensure_config,
    var_child_runnable_config,
)
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ModelCallResult,
)


class Sender(TypedDict):
    name: str
    avatar: str


class TTSConfig(TypedDict):
    vendor: Literal["ali", "bytedance", "google"]

    voice: str

    # 音频格式
    # 阿里：   'pcm' | 'wav' | 'mp3'
    # 字节：   'pcm' | 'mp3' | 'ogg_opus'
    # google: 'pcm' | 'mp3' | 'ogg_opus'
    format: str

    # 采样率
    # 阿里：8000 | 16000(default) | 24000
    # 字节：8000 | 16000 | 22050 | 24000（default） | 32000 | 44100 | 48000
    # google: 24000(default)
    sampleRate: int

    # 语速
    # 阿里： -500 ~ 500
    # 字节： 0.2  ~ 3
    # google： 0.25 - 4.0
    speechRate: int

    # 语调
    # 阿里： -500 ~ 500   default 0
    # 字节：  没有支持
    # google: 语调 (-20.0 - 20.0)
    pitchRate: int

    # 音量
    # 阿里： 0-100   default 50
    # 字节： 0.1 ~ 3   default 1
    # google: -96 ~ 16  default 0
    volume: int


class Speaker(TypedDict):
    sender: Sender
    ttsConfig: TTSConfig
    isCustomTTS: bool


class SpeakerMiddleware(AgentMiddleware):
    """Injects conversation tag and speaker metadata into ContextVar config.

    Args:
        tts_configs: Mapping from locale code to TTSConfig.
    """

    def __init__(self, tts_configs: Optional[Dict[str, TTSConfig]] = None):
        self.tts_configs = tts_configs or {}

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        state = request.state
        user_profile = state.get("user_profile") or {}
        locale = state.get("locale", "zh_CN")

        sender: Sender = {
            "name": user_profile.get("fullname", ""),
            "avatar": user_profile.get("img_url", ""),
        }

        tts_config = self.tts_configs.get(locale)
        if not tts_config:
            return await handler(request)

        speaker: Speaker = {
            "sender": sender,
            "ttsConfig": tts_config,
            "isCustomTTS": False,
        }

        # 直接修改 ContextVar 注入 tags/metadata，
        # 框架的 model_.ainvoke(messages) 不传 config，
        # 模型内部通过 ensure_config() 从 ContextVar 读取，
        # 这样 astream_events 的事件自然携带正确的 tags 和 metadata。
        current_config = ensure_config()
        patched_config = {
            **current_config,
            "metadata": {
                **(current_config.get("metadata") or {}),
                "speaker": speaker,
            },
        }
        token = var_child_runnable_config.set(patched_config)
        try:
            return await handler(request)
        finally:
            var_child_runnable_config.reset(token)
