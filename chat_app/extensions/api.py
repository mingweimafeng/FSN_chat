from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from chat_app.audio.audio_manager import AudioManager
    from chat_app.audio.tts_pipeline import TtsPipelineManager
    from chat_app.core.state_machine import ChatStateMachine


class ExtensionContext:
    """沙盒上下文，向插件暴露宿主安全的底层核心服务。

    通过依赖注入接收服务实例，绝不直接操作主窗口业务逻辑，
    仅通过本上下文定义的有限 API 与宿主交互。
    """

    def __init__(
        self,
        tts_pipeline: TtsPipelineManager | None = None,
        audio_manager: AudioManager | None = None,
        chat_state: ChatStateMachine | None = None,
        main_widget: QWidget | None = None,
        emotion_changer: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._tts_pipeline = tts_pipeline
        self._audio_manager = audio_manager
        self._chat_state = chat_state
        self._main_widget = main_widget
        self._emotion_changer = emotion_changer

    def get_main_widget(self) -> QWidget | None:
        """返回主窗口实例，供需要挂载 UI 控件的插件作为父控件。

        注意：插件不应直接操作主窗口的内部逻辑，仅用此引用作为 parent 参数。
        """
        return self._main_widget

    def speak(self, text: str) -> None:
        """让角色说出指定文本（走 TTS 合成 + 播放管线）。"""
        if self._tts_pipeline is not None:
            self._tts_pipeline.begin_tts_for_reply(
                {"reply": text, "emotion": "normal", "jp_translation": text},
                start_when_ready=True,
            )

    def change_emotion(self, emotion: str) -> None:
        """切换角色情绪（如 'happy'、'angry'），仅在聊天空闲时生效。"""
        if self._emotion_changer is not None:
            self._emotion_changer(emotion)

    def play_audio(self, path: Path) -> None:
        """播放本地音频文件。"""
        if self._audio_manager is not None:
            self._audio_manager.play(path)

    def stop_audio(self) -> None:
        """立即停止当前播放的音频。"""
        if self._audio_manager is not None:
            self._audio_manager.stop()

    @property
    def is_replying(self) -> bool:
        """插件是否处于回复输出态（可用于判断是否允许干预）。"""
        if self._chat_state is not None:
            return self._chat_state.reply_output_active
        return False


class BaseExtension(ABC):
    """插件抽象基类。

    所有插件必须继承此类并实现 on_start / on_stop 方法。
    on_user_input_intercept 是可选的输入拦截至多返回一条字符串。
    """

    def __init__(self) -> None:
        self._context: ExtensionContext | None = None
        self._enabled: bool = True

    @property
    @abstractmethod
    def name(self) -> str:
        """插件显示名称，用于日志与调试。"""
        ...

    @abstractmethod
    def on_start(self) -> None:
        """插件被管理器加载并注入上下文后调用，用于初始化资源与注册回调。"""

    @abstractmethod
    def on_stop(self) -> None:
        """插件被卸载前调用，用于释放资源与注销回调。"""

    def on_user_input_intercept(self, text: str) -> str | None:
        """输入拦截钩子。

        返回非空字符串时会短路正常聊天流程（插件充当回复方）。
        返回 None 则继续走正常 API 请求。
        """
        return None

    def set_context(self, context: ExtensionContext) -> None:
        """由 ExtensionManager 在加载时调用，注入沙盒上下文。"""
        self._context = context
