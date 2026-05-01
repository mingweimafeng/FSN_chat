from __future__ import annotations

from pathlib import Path

from chat_app.config import CHARACTER_EMOTIONS, STATE_TO_ASSET, SUPPORTED_EXTENSIONS


def find_backgrounds(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS],
        key=lambda x: x.name.lower(),
    )


def load_character_images(root: Path) -> dict[str, dict[str, list[Path]]]:
    images = {emotion: {state: [] for state in STATE_TO_ASSET.values()} for emotion in CHARACTER_EMOTIONS}
    for emotion in CHARACTER_EMOTIONS:
        for state in STATE_TO_ASSET.values():
            folder = root / emotion / state
            if folder.exists() and folder.is_dir():
                images[emotion][state] = sorted(
                    [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS],
                    key=lambda item: item.name.lower(),
                )
    return images
