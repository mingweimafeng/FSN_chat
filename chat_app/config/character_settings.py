from __future__ import annotations

from pathlib import Path

from ._helpers import _BASE, _load_character_manifest, _load_text_file


# 角色情绪列表。
CHARACTER_EMOTIONS = ("normal", "happy", "angry", "shy", "flustered", "embarrassed", "speechless", "serious", "shocked", "worried", "disgusted")
STATE_TO_ASSET = {"idle": "idle", "listen": "listen", "speaking": "talk", "react": "react"}

# 角色绘制位置与尺寸比例（全局默认值）。
CHARACTER_CENTER_X_RATIO = 0.45
CHARACTER_BASELINE_Y_RATIO = 1.10
CHARACTER_MAX_WIDTH_RATIO = 0.90
CHARACTER_MAX_HEIGHT_RATIO = 0.90


# 从 character_manifest.json 加载当前角色配置。
_manifest = _load_character_manifest(_BASE)
_CHARACTER_NAME = _manifest.get("default", "Saber")
_char_cfg = _manifest.get(_CHARACTER_NAME, {})

CHARACTER_DRESS_DIR = _BASE / "characters" / _CHARACTER_NAME / "dress"
CHARACTER_DIR = CHARACTER_DRESS_DIR / _char_cfg.get("default_dress", "Casual")
GENIE_CHARACTER_NAME = _char_cfg.get("tts_character_name", _CHARACTER_NAME)
GENIE_MODEL_LANGUAGE = _char_cfg.get("tts_language", "jp")
GENIE_REFERENCE_LANGUAGE = _char_cfg.get("tts_reference_language", "jp")
GENIE_ONNX_MODEL_DIR = _BASE / "characters" / _CHARACTER_NAME / "audio_package" / "onnx_model"
GENIE_REFERENCE_AUDIO_DIR = _BASE / "characters" / _CHARACTER_NAME / "audio_package" / "reference_audio"

# 提示词目录（供外部模块访问提示词存储位置）。
PROMPT_DIR = _BASE / "characters" / _CHARACTER_NAME / "prompts"


def get_character_dir() -> Path:
    return CHARACTER_DIR


def get_character_name() -> str:
    return _CHARACTER_NAME


def load_dress_config(dress_name: str) -> dict[str, float]:
    import json
    cfg_path = CHARACTER_DRESS_DIR / "dress_config.json"
    if not cfg_path.exists():
        return _default_dress_config()
    try:
        all_configs = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return _default_dress_config()
    dress_cfg = all_configs.get(dress_name, {})
    if not isinstance(dress_cfg, dict):
        return _default_dress_config()
    return {
        "center_x_ratio": float(dress_cfg.get("center_x_ratio", CHARACTER_CENTER_X_RATIO)),
        "baseline_y_ratio": float(dress_cfg.get("baseline_y_ratio", CHARACTER_BASELINE_Y_RATIO)),
        "max_width_ratio": float(dress_cfg.get("max_width_ratio", CHARACTER_MAX_WIDTH_RATIO)),
        "max_height_ratio": float(dress_cfg.get("max_height_ratio", CHARACTER_MAX_HEIGHT_RATIO)),
    }


def _default_dress_config() -> dict[str, float]:
    return {
        "center_x_ratio": CHARACTER_CENTER_X_RATIO,
        "baseline_y_ratio": CHARACTER_BASELINE_Y_RATIO,
        "max_width_ratio": CHARACTER_MAX_WIDTH_RATIO,
        "max_height_ratio": CHARACTER_MAX_HEIGHT_RATIO,
    }
