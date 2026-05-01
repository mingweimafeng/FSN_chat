from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chat_app.audio.audio_manager import AudioManager
    from chat_app.audio.tts_client import GenieTTSClient
    from chat_app.audio.tts_pipeline import TtsPipelineManager
    from chat_app.core.state_machine import ChatStateMachine
    from chat_app.data.history_store import ChatHistoryStore
    from chat_app.data.settings_store import SettingsStore
    from chat_app.extensions import ExtensionManager


@dataclass
class AppContext:
    chat_state: "ChatStateMachine"
    tts_client: "GenieTTSClient"
    tts_pipeline: "TtsPipelineManager"
    audio_manager: "AudioManager"
    settings_store: "SettingsStore"
    history_store: "ChatHistoryStore"
    extension_manager: "ExtensionManager" = field(default=None, repr=False)
