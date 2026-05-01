from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPixmap

from chat_app.config import (
    CURSOR_CHAR,
    DISPLAY_BOTTOM_RATIO,
    DISPLAY_LEFT_RATIO,
    DISPLAY_RIGHT_RATIO,
    DISPLAY_TOP_RATIO,
    FONT_SIZE,
    FULLSCREEN_MIN_FONT_SIZE,
    LINE_SPACING,
    TEXT_COLOR,
    TEXT_OUTLINE_COLOR,
    TEXT_OUTLINE_WIDTH,
    TEXT_PADDING,
)


class TextRenderMixin:
    @property
    def effective_font_size(self) -> int:
        base_size = FONT_SIZE
        scaled = int(base_size * self.scale_factor)
        return max(FULLSCREEN_MIN_FONT_SIZE, scaled)

    def display_rect(self) -> QRect:
        left = int(self.width() * DISPLAY_LEFT_RATIO)
        right = int(self.width() * DISPLAY_RIGHT_RATIO)
        top = int(self.height() * DISPLAY_TOP_RATIO)
        bottom = int(self.height() * DISPLAY_BOTTOM_RATIO)
        return QRect(left, top, right - left, bottom - top)

    def text_metrics(self) -> QFontMetricsF:
        return QFontMetricsF(self.text_font)

    def line_height(self) -> float:
        return self.text_metrics().height() + LINE_SPACING * self.scale_factor

    def content_rect(self) -> QRectF:
        r = self.display_rect()
        padding = TEXT_PADDING * self.scale_factor
        return QRectF(
            r.left() + padding,
            r.top() + padding,
            r.width() - padding * 2,
            r.height() - padding * 2,
        )

    def _mark_layout_dirty(self) -> None:
        self._line_runs_dirty = True
        self._cursor_rect_dirty = True

    def _mark_cursor_dirty(self) -> None:
        self._cursor_rect_dirty = True

    def _ensure_render_cache(self) -> None:
        if self._line_runs_dirty:
            self._render_line_runs_cache = self.build_render_line_runs()
            self._all_draw_lines_cache = [
                "".join(text for text, _ in line_runs)
                for line_runs in self._render_line_runs_cache
            ]
            self._line_runs_dirty = False
            self._cursor_rect_dirty = True

    def all_draw_lines(self) -> list[str]:
        self._ensure_render_cache()
        return list(self._all_draw_lines_cache)

    def cursor_rect(self) -> QRectF:
        if self._cursor_rect_dirty:
            content = self.content_rect()
            lines = self.all_draw_lines()
            line = lines[-1] if lines else ""
            metrics = self.text_metrics()
            x = content.left() + metrics.horizontalAdvance(line)
            y = content.top() + max(0, len(lines) - 1) * self.line_height()
            self._cursor_rect_cache = QRectF(
                x, y, max(2.0, metrics.horizontalAdvance(CURSOR_CHAR)), metrics.height()
            )
            self._cursor_rect_dirty = False
        return QRectF(self._cursor_rect_cache)

    def wrap_text(self, text: str) -> list[str]:
        if not text:
            return [""]
        width = int(self.content_rect().width())
        cache_key = (text, width)
        cached_lines = self.wrap_cache.get(cache_key)
        if cached_lines is not None:
            return list(cached_lines)

        metrics = self.text_metrics()
        lines, current = [], ""
        current_width = 0.0

        for ch in text:
            ch_width = metrics.horizontalAdvance(ch)
            if current and current_width + ch_width >= width:
                lines.append(current)
                current = ch
                current_width = ch_width
            else:
                current += ch
                current_width += ch_width

        lines.append(current)
        self.wrap_cache[cache_key] = list(lines)
        return lines

    def wrap_alpha_spans(
        self, spans: list[tuple[str, float]]
    ) -> list[list[tuple[str, float]]]:
        if not spans:
            return [[("", 1.0)]]
        width = int(self.content_rect().width())
        metrics = self.text_metrics()
        lines: list[list[tuple[str, float]]] = []
        current_line: list[list[object]] = []
        current_width = 0.0

        for text, alpha in spans:
            for ch in text:
                ch_width = metrics.horizontalAdvance(ch)
                if current_line and current_width + ch_width >= width:
                    lines.append(
                        [(str(seg), float(a)) for seg, a in current_line]
                    )
                    current_line = []
                    current_width = 0.0
                if current_line and abs(float(current_line[-1][1]) - alpha) < 1e-6:
                    current_line[-1][0] = str(current_line[-1][0]) + ch
                else:
                    current_line.append([ch, alpha])
                current_width += ch_width

        if current_line:
            lines.append([(str(seg), float(a)) for seg, a in current_line])
        return lines or [[("", 1.0)]]

    def build_render_line_runs(self) -> list[list[tuple[str, float]]]:
        runs: list[list[tuple[str, float]]] = []
        input_text = self.quoted_input()

        base_lines = list(self.cached_chat_lines)
        if (
            self.current_dialogue_page_text
            and self.chat_entries
            and self.current_dialogue_base_line_count > 0
            and len(base_lines) >= self.current_dialogue_base_line_count
        ):
            base_lines = base_lines[: -self.current_dialogue_base_line_count]
        elif self.current_dialogue_base_line_count > len(base_lines):
            base_lines = []

        user_count = min(self.latest_user_line_count, len(base_lines))
        history_count = len(base_lines) - user_count
        for idx, line in enumerate(base_lines):
            if idx < history_count:
                runs.append([(line, self.text_demote_target_alpha)])
            else:
                user_alpha = self.user_entry_alpha if self.reply_output_started else 1.0
                runs.append([(line, user_alpha)])

        if self.current_dialogue_page_text or self.current_reply_visible:
            stable_len = min(
                self.dialogue_history_stable_len, len(self.current_dialogue_page_text)
            )
            demoting_end = min(
                max(self.dialogue_demoting_end, stable_len),
                len(self.current_dialogue_page_text),
            )
            spans: list[tuple[str, float]] = []
            if stable_len > 0:
                spans.append(
                    (
                        self.current_dialogue_page_text[:stable_len],
                        self.text_demote_target_alpha,
                    )
                )
            if demoting_end > stable_len:
                spans.append(
                    (
                        self.current_dialogue_page_text[stable_len:demoting_end],
                        self.dialogue_demoting_alpha,
                    )
                )
            if demoting_end < len(self.current_dialogue_page_text):
                spans.append(
                    (self.current_dialogue_page_text[demoting_end:], 1.0)
                )
            if self.current_reply_visible:
                spans.append((self.current_reply_visible, 1.0))
            runs.extend(self.wrap_alpha_spans(spans))

        if input_text:
            for line in self.wrap_text(input_text):
                runs.append([(line, 1.0)])
        elif (
            not self.waiting_for_reply
            and not self.typewriter_timer.isActive()
            and not self.page_turn_timer.isActive()
        ):
            runs.append([("", 1.0)])

        return runs or [[("", 1.0)]]

    def get_text_pixmap(self, text: str) -> QPixmap:
        if text in self.text_pixmap_cache:
            return self.text_pixmap_cache[text]

        if len(self.text_pixmap_cache) > 500:
            self.text_pixmap_cache.clear()

        metrics = self.text_metrics()
        w = float(TEXT_OUTLINE_WIDTH * self.scale_factor)
        width = int(metrics.horizontalAdvance(text) + w * 2 + 4)
        height = int(metrics.height() + w * 2 + 4)

        if width <= 0 or height <= 0:
            return QPixmap()

        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(int(width * ratio), int(height * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setFont(self.text_font)

        painter.setPen(QColor(TEXT_OUTLINE_COLOR))
        x = w + 2
        y = metrics.ascent() + w + 2

        painter.drawText(QPointF(x - w, y), text)
        painter.drawText(QPointF(x + w, y), text)
        painter.drawText(QPointF(x, y - w), text)
        painter.drawText(QPointF(x, y + w), text)
        painter.drawText(QPointF(x - w, y - w), text)
        painter.drawText(QPointF(x + w, y - w), text)
        painter.drawText(QPointF(x - w, y + w), text)
        painter.drawText(QPointF(x + w, y + w), text)

        painter.setPen(QColor(TEXT_COLOR))
        painter.drawText(QPointF(x, y), text)
        painter.end()

        self.text_pixmap_cache[text] = pixmap
        return pixmap

    def draw_outlined_text(
        self,
        painter: QPainter,
        x: float,
        baseline_y: float,
        text: str,
        alpha_factor: float = 1.0,
    ) -> None:
        if not text:
            return

        pixmap = self.get_text_pixmap(text)
        painter.save()
        painter.setOpacity(
            self.text_layer_alpha * alpha_factor * self.ui_visibility_factor
        )

        w = float(TEXT_OUTLINE_WIDTH * self.scale_factor)
        metrics = self.text_metrics()
        draw_x = x - (w + 2)
        draw_y = baseline_y - metrics.ascent() - (w + 2)

        painter.drawPixmap(QPointF(draw_x, draw_y), pixmap)
        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.fillRect(self.rect(), Qt.black)

        if not self.scaled_background_pixmap.isNull():
            sx = max(0, (self.scaled_background_pixmap.width() - self.width()) // 2)
            sy = max(0, (self.scaled_background_pixmap.height() - self.height()) // 2)
            painter.drawPixmap(
                self.rect(),
                self.scaled_background_pixmap,
                QRect(sx, sy, self.width(), self.height()),
            )

        self.draw_character_layer(painter)

        if self.overlay_enabled:
            self.draw_mask_layer(painter)

        self.text_font.setPointSize(self.effective_font_size)
        painter.setFont(self.text_font)
        content = self.content_rect()
        metrics = self.text_metrics()
        y = content.top() + metrics.ascent()
        self._ensure_render_cache()
        line_runs = self._render_line_runs_cache

        for i, runs in enumerate(line_runs):
            x = content.left()
            for seg_text, seg_alpha in runs:
                if seg_text:
                    self.draw_outlined_text(painter, x, y, seg_text, alpha_factor=seg_alpha)
                    x += metrics.horizontalAdvance(seg_text)
            if (
                i == len(line_runs) - 1
                and self.cursor_visible
                and not self.reply_output_active
                and not self.waiting_for_reply
                and not self.typewriter_timer.isActive()
                and not self.page_turn_timer.isActive()
                and not self.animation_timer.isActive()
            ):
                self.draw_outlined_text(painter, x, y, CURSOR_CHAR)
            y += self.line_height()

        if (
            self.current_pixmap.isNull()
            and not self.chat_entries
            and not self.current_input
            and not self.preedit_text
        ):
            placeholder_color = QColor(Qt.white)
            placeholder_color.setAlphaF(self.text_layer_alpha * self.ui_visibility_factor)
            painter.setPen(placeholder_color)
            painter.drawText(self.rect(), Qt.AlignCenter, "请右键选择背景")
