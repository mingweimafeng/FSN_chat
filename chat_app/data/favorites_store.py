from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path


def _get_user_data_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


_USER_DATA = _get_user_data_dir()
FAVORITES_FILE = _USER_DATA / "favorites.json"
FAVORITES_AUDIO_DIR = _USER_DATA / "favorites_audio"


class FavoritesStore:
    def __init__(self) -> None:
        FAVORITES_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict]:
        if not FAVORITES_FILE.exists():
            return []
        try:
            data = json.loads(FAVORITES_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save(self, favorites: list[dict]) -> None:
        FAVORITES_FILE.write_text(
            json.dumps(favorites, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, text: str) -> dict:
        fav = {
            "id": f"fav_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": text,
            "audio_path": None,
        }
        favorites = self.load()
        favorites.insert(0, fav)
        self.save(favorites)
        return fav

    def remove(self, fav_id: str) -> None:
        favorites = self.load()
        for fav in favorites:
            if fav["id"] == fav_id:
                audio = fav.get("audio_path")
                if audio:
                    p = Path(audio)
                    if p.exists():
                        try:
                            p.unlink()
                        except Exception:
                            pass
                break
        new_favorites = [f for f in favorites if f["id"] != fav_id]
        self.save(new_favorites)

    def update_audio_path(self, fav_id: str, audio_path: str) -> None:
        favorites = self.load()
        for fav in favorites:
            if fav["id"] == fav_id:
                fav["audio_path"] = audio_path
                break
        self.save(favorites)