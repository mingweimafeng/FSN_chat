from __future__ import annotations

from ._helpers import _USER_DATA


# Genie TTS 服务与音频参数。
GENIE_SERVER_HOST = "127.0.0.1"
GENIE_SERVER_PORT = 8000
GENIE_AUDIO_SAMPLE_RATE = 32000
GENIE_AUDIO_CHANNELS = 1
GENIE_AUDIO_BYTES_PER_SAMPLE = 2
TEMP_AUDIO_DIR = _USER_DATA / "tmp_audio"

# 历史记录持久化路径。
HISTORY_FILE_PATH = _USER_DATA / "chat_history.json"

# 应用设置持久化路径。
SETTINGS_FILE_PATH = _USER_DATA / "app_settings.json"

# 记忆状态持久化路径（独立于应用设置）。
MEMORY_STATE_FILE_PATH = _USER_DATA / "memory_state.json"
