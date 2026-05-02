from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from chat_app.config import (
    DEFAULT_FIXED_REQUIREMENTS_PROMPT,
    DEFAULT_ROLE_PROMPT,
    DEFAULT_USER_PROFILE_PROMPT,
    MEMORY_STATE_FILE_PATH,
    SETTINGS_FILE_PATH,
)


@dataclass
class AppSettings:
    fixed_requirements_prompt: str = DEFAULT_FIXED_REQUIREMENTS_PROMPT
    role_prompt: str = DEFAULT_ROLE_PROMPT
    user_profile_prompt: str = DEFAULT_USER_PROFILE_PROMPT
    api_key: str = ""
    current_background: str = ""

    def compose_system_prompt(self) -> str:
        return "\n".join(
            [
                self.role_prompt.strip(),
                self.user_profile_prompt.strip(),
                self.fixed_requirements_prompt.strip(),
            ]
        ).strip()


@dataclass
class MemoryState:
    last_summary: str = ""
    turns_since_summary: int = 0


class _BaseStore:
    def _atomic_write(self, file_path: Path, payload: dict) -> None:
        tmp_path = file_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            tmp_path.replace(file_path)
        except OSError:
            shutil.move(str(tmp_path), str(file_path))

    def _read_payload(self, file_path: Path) -> dict:
        if not file_path.exists():
            return {}
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}


class AppSettingsStore(_BaseStore):
    def __init__(self, file_path: Path = SETTINGS_FILE_PATH) -> None:
        super().__init__()
        self.file_path = file_path

    def load(self) -> AppSettings:
        if not self.file_path.exists():
            return AppSettings()
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return AppSettings()
        if not isinstance(payload, dict):
            return AppSettings()

        settings = AppSettings()
        fixed_prompt = str(payload.get("fixed_requirements_prompt", settings.fixed_requirements_prompt)).strip() or settings.fixed_requirements_prompt
        legacy_markers = (
            '"emotion": "normal|happy|angry|shy"',
            "emotion 只能是 normal、happy、angry、shy 之一",
        )
        if '"narration"' not in fixed_prompt or any(marker in fixed_prompt for marker in legacy_markers):
            fixed_prompt = DEFAULT_FIXED_REQUIREMENTS_PROMPT
        settings.fixed_requirements_prompt = fixed_prompt
        settings.role_prompt = str(payload.get("role_prompt", settings.role_prompt)).strip() or settings.role_prompt
        settings.user_profile_prompt = str(payload.get("user_profile_prompt", settings.user_profile_prompt)).strip() or settings.user_profile_prompt
        settings.api_key = str(payload.get("api_key", "")).strip()
        settings.current_background = str(payload.get("current_background", "")).strip()
        return settings

    def save(self, settings: AppSettings) -> None:
        payload = {
            "fixed_requirements_prompt": settings.fixed_requirements_prompt,
            "role_prompt": settings.role_prompt,
            "user_profile_prompt": settings.user_profile_prompt,
            "api_key": settings.api_key,
            "current_background": settings.current_background,
        }
        self._atomic_write(self.file_path, payload)


class MemoryStateStore(_BaseStore):
    def __init__(self, file_path: Path = MEMORY_STATE_FILE_PATH) -> None:
        super().__init__()
        self.file_path = file_path

    def load(self) -> MemoryState:
        payload = self._read_payload(self.file_path)
        try:
            turns_since_summary = max(0, int(payload.get("memory_turns_since_summary", 0) or 0))
        except (TypeError, ValueError):
            turns_since_summary = 0
        return MemoryState(
            last_summary=str(payload.get("memory_last_summary", "")).strip(),
            turns_since_summary=turns_since_summary,
        )

    def save(self, state: MemoryState) -> None:
        payload = {
            "memory_last_summary": state.last_summary.strip(),
            "memory_turns_since_summary": max(0, int(state.turns_since_summary)),
        }
        self._atomic_write(self.file_path, payload)


class SettingsStore:
    def __init__(
        self,
        settings_file_path: Path = SETTINGS_FILE_PATH,
        memory_file_path: Path = MEMORY_STATE_FILE_PATH,
    ) -> None:
        self._app_settings_store = AppSettingsStore(settings_file_path)
        self._memory_state_store = MemoryStateStore(memory_file_path)

    def load(self) -> AppSettings:
        return self._app_settings_store.load()

    def save(self, settings: AppSettings) -> None:
        self._app_settings_store.save(settings)

    def load_memory_state(self) -> MemoryState:
        return self._memory_state_store.load()

    def save_memory_state(self, memory_state: MemoryState) -> None:
        self._memory_state_store.save(memory_state)
