from __future__ import annotations

from pathlib import Path

from ._helpers import _BASE, _load_text_file
from .character_settings import _CHARACTER_NAME


_PROMPT_DIR = _BASE / "characters" / _CHARACTER_NAME / "prompts"
_CONFIG_DIR = Path(__file__).parent

DEFAULT_ROLE_PROMPT = _load_text_file(
    _PROMPT_DIR / "role_prompt.txt",
    fallback="",
)

DEFAULT_USER_PROFILE_PROMPT = _load_text_file(
    _PROMPT_DIR / "user_profile_prompt.txt",
    fallback="",
)

DEFAULT_FIXED_REQUIREMENTS_PROMPT = _load_text_file(
    _CONFIG_DIR / "fixed_requirements_prompt.txt",
    fallback="",
)

SYSTEM_PROMPT = (
    DEFAULT_ROLE_PROMPT + "\n" + DEFAULT_USER_PROFILE_PROMPT + "\n" + DEFAULT_FIXED_REQUIREMENTS_PROMPT
)

# 记忆参数
MEMORY_L1_TURNS = 4
MEMORY_L2_TRIGGER_EVERY = 4
MEMORY_L2_RECENT_TURNS = 10
MEMORY_L2_MAX_SUMMARY_CHARS = 200
MEMORY_L2_MIN_SUMMARY_CHARS = 20

MEMORY_STRICT_JSON_GUARD_PROMPT = _load_text_file(
    _CONFIG_DIR / "json_guard_prompt.txt",
    fallback="",
)

MEMORY_SUMMARY_PROMPT = _load_text_file(
    _CONFIG_DIR / "summary_prompt.txt",
    fallback="",
)
