from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QMessageBox

from chat_app.config import (
    MASK_CENTER_OPACITY,
    MASK_SIDE_FADE_END_RATIO,
    MASK_SIDE_FADE_START_RATIO,
)


class BackgroundMixin:
    def resolve_saved_background(self, saved_path_text: str) -> Path | None:
        saved = (saved_path_text or "").strip()
        if not saved:
            return None
        for bg in self.backgrounds:
            if str(bg) == saved:
                return bg
        return None

    def refresh_scaled_background(self) -> None:
        if self.current_pixmap.isNull():
            self.scaled_background_pixmap = QPixmap()
            return
        self.scaled_background_pixmap = self.current_pixmap.scaled(
            self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )

    def set_background(self, image_path: Path, persist: bool = True) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            QMessageBox.warning(self, "加载失败", f"无法加载图片:\n{image_path}")
            return
        self.current_background = image_path
        self.current_pixmap = pixmap
        if persist:
            self.settings.current_background = str(image_path)
            self.settings_store.save(self.settings)
        self.refresh_scaled_background()
        self.update()

    def set_overlay_enabled(self, enabled: bool) -> None:
        self.overlay_enabled = enabled
        self.update()

    def draw_mask_layer(self, painter: QPainter) -> None:
        gradient = QLinearGradient(0, self.height() / 2, self.width(), self.height() / 2)
        center_alpha = max(
            0.0, min(1.0, MASK_CENTER_OPACITY * self.overlay_alpha * self.ui_visibility_factor)
        )
        transparent = QColor(0, 0, 0, 0)
        center = QColor(0, 0, 0)
        center.setAlphaF(center_alpha)
        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(MASK_SIDE_FADE_START_RATIO, center)
        gradient.setColorAt(MASK_SIDE_FADE_END_RATIO, center)
        gradient.setColorAt(1.0, transparent)
        painter.fillRect(self.rect(), gradient)

    def _drawer_hidden_x(self) -> int:
        return self.width()

    def _drawer_open_x(self) -> int:
        return self.width() - self.background_drawer.drawer_width

    def _sync_ui_visibility_with_drawer(self) -> None:
        hidden_x = self._drawer_hidden_x()
        open_x = self._drawer_open_x()
        denom = hidden_x - open_x
        if denom <= 0:
            factor = 1.0
        else:
            factor = (self.background_drawer.x() - open_x) / denom
        self.ui_visibility_factor = max(0.0, min(1.0, factor))
        self._background_drawer_active = self.ui_visibility_factor < 0.999
        self._mark_layout_dirty()
        self._mark_cursor_dirty()
        self.update()

    def _in_drawer_trigger_zone(self, pos) -> bool:
        return pos.x() >= self.width() - self.drawer_trigger_margin_px

    def _open_background_drawer_from_trigger(self) -> None:
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(cursor_pos):
            return
        if self._in_drawer_trigger_zone(cursor_pos):
            self._set_active_overlay("background")
            self.background_drawer.open_drawer()
            self.background_drawer.raise_()

    def _should_close_drawer_for_pos(self, pos) -> bool:
        if not self.background_drawer.is_open and not self.background_drawer.isVisible():
            return False
        return not self.background_drawer.geometry().contains(pos)

    def _update_background_drawer_trigger(self, pos) -> None:
        if self.background_drawer.geometry().contains(pos):
            self.drawer_trigger_timer.stop()
            return
        if self.background_drawer.is_open:
            if self._should_close_drawer_for_pos(pos):
                self.drawer_trigger_timer.stop()
                self.background_drawer.close_drawer()
            return
        if self._in_drawer_trigger_zone(pos):
            if not self.drawer_trigger_timer.isActive():
                self.drawer_trigger_timer.start(self.drawer_open_delay_ms)
        else:
            self.drawer_trigger_timer.stop()

    def toggle_background_drawer(self) -> None:
        if self.background_drawer.is_open:
            self.background_drawer.close_drawer()
        else:
            self._set_active_overlay("background")
            self.background_drawer.open_drawer()
        self.background_drawer.raise_()

    def _on_drawer_background_selected(self, image_path: Path) -> None:
        self.set_background(image_path)
        self.background_drawer.set_current_background(image_path)

    def _is_ui_input_locked(self) -> bool:
        return self.ui_visibility_factor < 0.999

    def _on_drawer_pos_changed(self, _value) -> None:
        self._sync_ui_visibility_with_drawer()

    def _on_drawer_anim_finished(self) -> None:
        self._sync_ui_visibility_with_drawer()
        if not self.background_drawer.is_open:
            self._set_active_overlay(None)

    def mouseMoveEvent(self, event) -> None:
        self._update_background_drawer_trigger(event.pos())
        if hasattr(self, "extension_manager"):
            self.extension_manager.notify_mouse_moved()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self.drawer_trigger_timer.stop()
        if self.background_drawer.is_open:
            self.background_drawer.close_drawer()
        super().leaveEvent(event)
