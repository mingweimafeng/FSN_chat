from __future__ import annotations

import sys
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _get_user_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _load_text_file(path: Path, fallback: str = "") -> str:
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return fallback


def _load_character_manifest(base: Path) -> dict:
    import json
    manifest_path = base / "characters" / "character_manifest.json"
    if not manifest_path.exists():
        return {"default": "Saber", "Saber": {"name": "Saber", "default_dress": "Casual", "tts_character_name": "Saber", "tts_language": "jp", "tts_reference_language": "jp"}}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {"default": "Saber"}


_BASE = _get_base_dir()
_USER_DATA = _get_user_data_dir()
