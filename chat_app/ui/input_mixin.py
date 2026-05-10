from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QInputMethodEvent, QKeyEvent

if TYPE_CHECKING:
    from chat_app.core.window_protocol import WindowProtocol


class InputMixin:
    def keyPressEvent(self: "WindowProtocol", event: QKeyEvent) -> None:
        if self._is_ui_input_locked():
            event.ignore()
            return
        if (
            self.waiting_for_reply
            or self.typewriter_timer.isActive()
            or self.page_turn_timer.isActive()
            or self.animation_timer.isActive()
        ):
            event.ignore()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.preedit_text:
                super().keyPressEvent(event)
                return
            self.submit_input()
            return
        if event.key() == Qt.Key_Backspace:
            if self.preedit_text:
                super().keyPressEvent(event)
                return
            self.current_input = self.current_input[:-1]
            self._mark_layout_dirty()
            self.update()
            return

        if event.key() in (
            Qt.Key_Left,
            Qt.Key_Right,
            Qt.Key_Up,
            Qt.Key_Down,
            Qt.Key_Home,
            Qt.Key_End,
            Qt.Key_PageUp,
            Qt.Key_PageDown,
        ):
            super().keyPressEvent(event)
            return
        if event.key() in (
            Qt.Key_Shift,
            Qt.Key_Control,
            Qt.Key_Alt,
            Qt.Key_Meta,
            Qt.Key_CapsLock,
        ):
            super().keyPressEvent(event)
            return

        text = event.text()
        if not text:
            super().keyPressEvent(event)
            return
        if text == "\r":
            super().keyPressEvent(event)
            return
        if text.isspace() and text != " ":
            super().keyPressEvent(event)
            return

        self.current_input += text
        self._mark_layout_dirty()
        self.update()

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        if self._is_ui_input_locked():
            event.ignore()
            return
        if (
            self.waiting_for_reply
            or self.typewriter_timer.isActive()
            or self.page_turn_timer.isActive()
            or self.animation_timer.isActive()
        ):
            event.ignore()
            return
        commit_text = event.commitString()
        if commit_text:
            self.current_input += commit_text
        self.preedit_text = event.preeditString()
        self.cursor_visible = True
        self._mark_layout_dirty()
        self._mark_cursor_dirty()
        event.accept()
        self.update()

    def inputMethodQuery(self, query):
        if query == Qt.ImEnabled:
            return True
        if query == Qt.ImHints:
            return Qt.ImhNone
        if query == Qt.ImCursorRectangle:
            return self.cursor_rect().toRect()
        if query == Qt.ImSurroundingText:
            return self.current_input + self.preedit_text
        if query == Qt.ImCurrentSelection:
            return ""
        if query == Qt.ImCursorPosition:
            return len(self.current_input + self.preedit_text)
        if query == Qt.ImAnchorPosition:
            return len(self.current_input + self.preedit_text)
        return super().inputMethodQuery(query)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._refresh_ime()

    def focusOutEvent(self, event) -> None:
        input_method = QGuiApplication.inputMethod()
        if input_method is not None:
            input_method.commit()
        self.preedit_text = ""
        super().focusOutEvent(event)

    def mousePressEvent(self, event) -> None:
        if self._is_ui_input_locked() and not self.background_drawer.geometry().contains(
            event.pos()
        ):
            event.ignore()
            return
        super().mousePressEvent(event)

    def restore_input_context(self) -> None:
        QTimer.singleShot(0, self._restore_input_context_impl)

    def _refresh_ime(self) -> None:
        input_method = QGuiApplication.inputMethod()
        if input_method is not None:
            input_method.show()
            input_method.update(
                Qt.ImEnabled | Qt.ImCursorRectangle | Qt.ImSurroundingText
            )

    def _restore_input_context_impl(self) -> None:
        if not self.isVisible():
            return
        self.activateWindow()
        self.raise_()
        self.setFocus(Qt.ActiveWindowFocusReason)
        self._refresh_ime()
        self.update()