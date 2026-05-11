from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QClipboard, QInputMethodEvent, QKeyEvent

if TYPE_CHECKING:
    from chat_app.core.window_protocol import WindowProtocol


class InputMixin:
    def _is_input_blocked(self: "WindowProtocol") -> bool:
        return (
            self.chat_state.waiting_for_reply
            or self.typewriter_timer.isActive()
            or self.page_turn_timer.isActive()
            or self.animation_timer.isActive()
        )

    def _clamp_caret(self: "WindowProtocol") -> None:
        if self.cursor_caret < 0:
            self.cursor_caret = 0
        if self.cursor_caret > len(self.current_input):
            self.cursor_caret = len(self.current_input)

    def _insert_at_caret(self: "WindowProtocol", text: str) -> None:
        self._clamp_caret()
        self.current_input = (
            self.current_input[: self.cursor_caret]
            + text
            + self.current_input[self.cursor_caret :]
        )
        self.cursor_caret += len(text)
        self.cursor_visible = True

    def _delete_before_caret(self: "WindowProtocol") -> None:
        self._clamp_caret()
        if self.cursor_caret == 0:
            return
        self.current_input = (
            self.current_input[: self.cursor_caret - 1]
            + self.current_input[self.cursor_caret :]
        )
        self.cursor_caret -= 1

    def _move_caret(self: "WindowProtocol", delta: int) -> None:
        self._clamp_caret()
        new_pos = self.cursor_caret + delta
        if 0 <= new_pos <= len(self.current_input):
            self.cursor_caret = new_pos
            self._mark_cursor_dirty()
            self.update()

    def _commit_and_reset_ime(self: "WindowProtocol") -> None:
        input_method = QGuiApplication.inputMethod()
        if input_method is not None:
            if self.preedit_text:
                input_method.commit()
            input_method.reset()

    def keyPressEvent(self: "WindowProtocol", event: QKeyEvent) -> None:
        if self._is_ui_input_locked():
            event.ignore()
            return
        if self._is_input_blocked():
            self._commit_and_reset_ime()
            event.ignore()
            return

        if event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                paste_text = clipboard.text()
                if paste_text:
                    self._insert_at_caret(paste_text)
                    self._mark_layout_dirty()
                    self._mark_cursor_dirty()
                    self.update()
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
            self._delete_before_caret()
            self._mark_layout_dirty()
            self._mark_cursor_dirty()
            self.update()
            return

        if event.key() == Qt.Key_Delete:
            if self.preedit_text:
                super().keyPressEvent(event)
                return
            self._clamp_caret()
            if self.cursor_caret < len(self.current_input):
                self.current_input = (
                    self.current_input[: self.cursor_caret]
                    + self.current_input[self.cursor_caret + 1 :]
                )
                self._mark_layout_dirty()
                self._mark_cursor_dirty()
                self.update()
            return

        if event.key() == Qt.Key_Left:
            self._move_caret(-1)
            return

        if event.key() == Qt.Key_Right:
            self._move_caret(1)
            return

        if event.key() == Qt.Key_Home:
            self.cursor_caret = 0
            self._mark_cursor_dirty()
            self.update()
            return

        if event.key() == Qt.Key_End:
            self.cursor_caret = len(self.current_input)
            self._mark_cursor_dirty()
            self.update()
            return

        if event.key() in (
            Qt.Key_Up,
            Qt.Key_Down,
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

        self._insert_at_caret(text)
        self._mark_layout_dirty()
        self._mark_cursor_dirty()
        self.update()

    def inputMethodEvent(self: "WindowProtocol", event: QInputMethodEvent) -> None:
        if self._is_ui_input_locked():
            event.ignore()
            return
        if self._is_input_blocked():
            self._commit_and_reset_ime()
            event.accept()
            self.update()
            return
        commit_text = event.commitString()
        if commit_text:
            self._insert_at_caret(commit_text)
        self.preedit_text = event.preeditString()
        self.cursor_visible = True
        self._mark_layout_dirty()
        self._mark_cursor_dirty()
        event.accept()
        self.update()

    def inputMethodQuery(self: "WindowProtocol", query):
        if query == Qt.ImEnabled:
            return not self._is_ui_input_locked() and not self._is_input_blocked()
        if query == Qt.ImHints:
            return Qt.ImhNone
        if query == Qt.ImCursorRectangle:
            return self.cursor_rect().toRect()
        if query == Qt.ImSurroundingText:
            self._clamp_caret()
            return (
                self.current_input[: self.cursor_caret]
                + self.preedit_text
                + self.current_input[self.cursor_caret :]
            )
        if query == Qt.ImCurrentSelection:
            return ""
        if query == Qt.ImCursorPosition:
            self._clamp_caret()
            return self.cursor_caret + len(self.preedit_text)
        if query == Qt.ImAnchorPosition:
            self._clamp_caret()
            return self.cursor_caret + len(self.preedit_text)
        return super().inputMethodQuery(query)

    def focusInEvent(self: "WindowProtocol", event) -> None:
        super().focusInEvent(event)
        self._refresh_ime()

    def focusOutEvent(self: "WindowProtocol", event) -> None:
        input_method = QGuiApplication.inputMethod()
        if input_method is not None:
            input_method.commit()
        self.preedit_text = ""
        super().focusOutEvent(event)

    def mousePressEvent(self: "WindowProtocol", event) -> None:
        if self._is_ui_input_locked() and not self.background_drawer.geometry().contains(
            event.pos()
        ):
            event.ignore()
            return
        super().mousePressEvent(event)

    def restore_input_context(self: "WindowProtocol") -> None:
        QTimer.singleShot(0, self._restore_input_context_impl)

    def _refresh_ime(self: "WindowProtocol") -> None:
        self.setInputMethodHints(Qt.ImhNone)
        input_method = QGuiApplication.inputMethod()
        if input_method is not None:
            input_method.show()
            input_method.update(
                Qt.ImEnabled | Qt.ImCursorRectangle | Qt.ImSurroundingText
            )

    def _restore_input_context_impl(self: "WindowProtocol") -> None:
        if not self.isVisible():
            return
        self.activateWindow()
        self.raise_()
        self.setFocus(Qt.ActiveWindowFocusReason)
        self._refresh_ime()
        self.update()
