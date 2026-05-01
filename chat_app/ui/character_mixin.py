from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPixmap

from chat_app.config import (
    CHARACTER_BASELINE_Y_RATIO,
    CHARACTER_CENTER_X_RATIO,
    CHARACTER_EMOTIONS,
    CHARACTER_MAX_HEIGHT_RATIO,
    CHARACTER_MAX_WIDTH_RATIO,
    EMOTION_RESET_INTERVAL_MS,
    STATE_TO_ASSET,
)


class CharacterMixin:
    def character_asset_state(self) -> str:
        return STATE_TO_ASSET[self.character_state]

    def character_candidates(self, emotion: str, asset_state: str) -> list[Path]:
        return self.character_images.get(emotion, {}).get(asset_state, [])

    def next_character_image_path(self) -> Path | None:
        asset_state = self.character_asset_state()
        for emotion, state in (
            (self.character_emotion, asset_state),
            ("normal", asset_state),
            ("normal", "idle"),
        ):
            candidates = self.character_candidates(emotion, state)
            if candidates:
                n = len(candidates)
                if n == 1:
                    return candidates[0]
                last_index = self.character_indices[emotion][state]
                available_indices = [i for i in range(n) if i != last_index]
                new_index = random.choice(available_indices)
                self.character_indices[emotion][state] = new_index
                return candidates[new_index]
        return None

    def refresh_character_portrait(self) -> None:
        image_path = self.next_character_image_path()
        self.character_pixmap = QPixmap(str(image_path)) if image_path else QPixmap()
        self.previous_character_pixmap = QPixmap()
        self.next_character_pixmap = QPixmap()
        self.portrait_blend_progress = 1.0
        self.animation_phase = "idle"
        self.pending_resume_action = None
        self.cursor_visible = True
        self.update()

    def set_character_state(
        self, state: str, resume_action=None, quick: bool = False
    ) -> None:
        if state not in STATE_TO_ASSET:
            return
        self.character_state = state
        image_path = self.next_character_image_path()
        new_pixmap = QPixmap(str(image_path)) if image_path else QPixmap()
        self.begin_portrait_transition(new_pixmap, resume_action, quick=quick)

    def set_character_emotion(self, emotion: str) -> None:
        self.character_emotion = emotion if emotion in CHARACTER_EMOTIONS else "normal"
        if self.character_emotion == "normal":
            self.emotion_reset_timer.stop()
        else:
            self.emotion_reset_timer.start(EMOTION_RESET_INTERVAL_MS)

    def reset_emotion_to_normal(self) -> None:
        if self.character_emotion != "normal":
            self.character_emotion = "normal"
            self.set_character_state(self.character_state)

    def character_draw_rect(self, pixmap: QPixmap) -> QRectF:
        cache_key = pixmap.cacheKey()
        cached_rect = self.character_draw_cache.get(cache_key)
        if cached_rect is not None:
            return cached_rect

        max_width = self.width() * CHARACTER_MAX_WIDTH_RATIO
        max_height = self.height() * CHARACTER_MAX_HEIGHT_RATIO
        center_x = self.width() * CHARACTER_CENTER_X_RATIO
        baseline_y = self.height() * CHARACTER_BASELINE_Y_RATIO

        scaled = pixmap.scaled(
            int(max_width), int(max_height), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        left = center_x - scaled.width() / 2
        top = baseline_y - scaled.height()
        rect = QRectF(left, top, scaled.width(), scaled.height())
        self.character_draw_cache[cache_key] = rect
        return rect

    def draw_character_layer(self, painter) -> None:
        painter.save()
        if (
            self.animation_phase in ("portrait", "portrait_only")
            and not self.previous_character_pixmap.isNull()
            and not self.next_character_pixmap.isNull()
        ):
            old_rect = self.character_draw_rect(self.previous_character_pixmap)
            painter.setOpacity(1.0 - self.portrait_blend_progress)
            painter.drawPixmap(old_rect.toRect(), self.previous_character_pixmap)
            new_rect = self.character_draw_rect(self.next_character_pixmap)
            painter.setOpacity(self.portrait_blend_progress)
            painter.drawPixmap(new_rect.toRect(), self.next_character_pixmap)
            painter.restore()
            return
        if not self.character_pixmap.isNull():
            draw_rect = self.character_draw_rect(self.character_pixmap)
            painter.drawPixmap(draw_rect.toRect(), self.character_pixmap)
        painter.restore()
