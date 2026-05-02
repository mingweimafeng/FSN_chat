from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QInputMethodEvent, QKeyEvent
from PySide6.QtWidgets import QDialog, QMenu

from chat_app.config import (
    CHARACTER_EMOTIONS,
    IDLE_RETURN_DELAY_MS,
    SEGMENT_GAP_INTERVAL_MS,
    ANIMATION_TICK_MS,
)
from chat_app.services.api_client import ChatRequestThread
from chat_app.ui.dialogs import HistoryDialog, SettingsDialog


class DialogueMixin:
    def quote_text(self, text: str) -> str:
        return f"“{text}”"

    def quoted_input(self) -> str:
        text = self.current_input + self.preedit_text
        return self.quote_text(text) if text else ""

    def normalize_reply_segments(self, payload: dict) -> list[dict[str, str]]:
        segments_raw = payload.get("segments")
        normalized: list[dict[str, str]] = []
        if isinstance(segments_raw, list):
            for item in segments_raw:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("reply", "")).strip()
                if not text:
                    continue
                emotion = (
                    str(item.get("emotion", payload.get("emotion", "normal")))
                    .strip()
                    .lower()
                )
                if emotion not in CHARACTER_EMOTIONS:
                    emotion = "normal"
                jp_text = str(item.get("jp_translation", "")).strip() or text
                normalized.append(
                    {
                        "reply": text,
                        "jp_translation": jp_text,
                        "emotion": emotion,
                    }
                )

        if not normalized:
            text = str(payload.get("reply", "...")).strip() or "..."
            emotion = (
                str(payload.get("emotion", "normal")).strip().lower()
            )
            if emotion not in CHARACTER_EMOTIONS:
                emotion = "normal"
            jp_text = str(payload.get("jp_translation", "")).strip() or text
            normalized = [
                {"reply": text, "jp_translation": jp_text, "emotion": emotion}
            ]

        normalized[0]["reply"] = f"“{normalized[0]['reply']}"
        normalized[-1]["reply"] = f"{normalized[-1]['reply']}”"
        return normalized

    def wrapped_lines_for_entries(self, entries: list[str]) -> list[str]:
        lines: list[str] = []
        for entry in entries:
            lines.extend(self.wrap_text(entry))
        return lines

    def rebuild_cached_chat_lines(self) -> None:
        self.cached_chat_lines = self.wrapped_lines_for_entries(self.chat_entries)

    def append_chat_entry(self, entry: str) -> None:
        self.chat_entries.append(entry)
        self.cached_chat_lines.extend(self.wrap_text(entry))
        self._mark_layout_dirty()

    def clear_chat_entries(self) -> None:
        self.chat_entries.clear()
        self.cached_chat_lines.clear()
        self.current_dialogue_page_text = ""
        self.current_dialogue_base_line_count = 0
        self._mark_layout_dirty()

    def append_or_extend_dialogue_entry(self, segment_text: str) -> None:
        if not self.current_dialogue_page_text:
            self.current_dialogue_page_text = segment_text
            self.append_chat_entry(segment_text)
            self.current_dialogue_base_line_count = len(
                self.wrap_text(self.current_dialogue_page_text)
            )
            return
        self.current_dialogue_page_text += segment_text
        if self.chat_entries:
            self.chat_entries[-1] = self.current_dialogue_page_text
            self.rebuild_cached_chat_lines()
            self.current_dialogue_base_line_count = len(
                self.wrap_text(self.current_dialogue_page_text)
            )
            self._mark_layout_dirty()

    def lines_fit_in_display(self, lines: list[str]) -> bool:
        if not lines:
            return True
        max_lines = max(1, int(self.content_rect().height() // self.line_height()))
        return len(lines) <= max_lines

    def submit_input(self) -> None:
        user_text = (self.current_input + self.preedit_text).strip()
        if not user_text:
            return

        self.audio_manager.stop()
        self.pending_reply_segments.clear()
        if hasattr(self, "tts_pipeline"):
            self.tts_pipeline.reset()
        self.current_dialogue_segment_index = 0
        self.current_dialogue_page_text = ""
        self.current_dialogue_base_line_count = 0

        self.chat_state.end_narration_output()
        self.narration_wait_timer.stop()

        self.append_chat_entry(self.quote_text(user_text))
        self.latest_user_line_count = len(
            self.wrap_text(self.quote_text(user_text))
        )
        self.last_user_message = user_text
        self.chat_state.set_waiting_audio_before_next_segment(False)
        self.pending_page_turn_before_next_segment = False
        self.current_input = ""
        self.preedit_text = ""
        self.chat_state.reset_for_new_input()
        self._apply_state_flags()
        self.cursor_visible = False
        self.idle_timer.stop()
        self._mark_layout_dirty()

        self.reply_output_started = False
        self.user_entry_alpha = 1.0
        self.dialogue_history_stable_len = 0
        self.dialogue_demoting_end = 0
        self.dialogue_demoting_alpha = self.text_demote_target_alpha
        self.user_fade_start_alpha = 1.0
        self.dialogue_fade_start_alpha = self.text_demote_target_alpha
        self.text_fade_progress = 1.0
        self.text_fade_timer.stop()
        self.pending_idle_after_text_demote = False

        extension_reply = self.extension_manager.process_user_input(user_text)
        if extension_reply:
            local_payload = {
                "narration": "",
                "emotion": "normal",
                "reply": extension_reply,
                "jp_translation": extension_reply,
                "segments": [
                    {
                        "emotion": "normal",
                        "reply": extension_reply,
                        "jp_translation": extension_reply,
                    }
                ],
            }
            self.on_reply_ready(local_payload)
            self.on_request_finished()
            return

        background_name = self.current_background_name() if hasattr(self, "current_background_name") else ""
        system_prompt = self.settings.compose_system_prompt(background_name)
        self.request_thread = ChatRequestThread(
            user_text,
            system_prompt=system_prompt,
            api_key=self.settings.api_key,
            memory_messages=self._build_l1_memory_messages(),
        )
        self.request_thread.finished_payload.connect(self.on_reply_ready)
        self.request_thread.failed.connect(self.on_reply_failed)
        self.request_thread.finished.connect(self.on_request_finished)
        self.request_thread.start()

        self.set_character_state("thinking")
        self.update()

    def on_reply_ready(self, payload: dict) -> None:
        self.chat_state.begin_reply_output()
        self._apply_state_flags()
        self.cursor_visible = False
        self.current_dialogue_page_text = ""
        self.current_dialogue_base_line_count = 0
        self.current_dialogue_segment_index = 0
        self.pending_reply_segments = self.normalize_reply_segments(payload)
        self.current_reply_full = ""
        self.current_reply_visible = ""

        self.current_narration = str(payload.get("narration", "")).strip()
        self.top_level_emotion = (
            str(payload.get("emotion", "normal")).strip().lower()
        )
        if self.top_level_emotion not in CHARACTER_EMOTIONS:
            self.top_level_emotion = "normal"

        reply_text = str(payload.get("reply", "...")).strip() or "..."
        if self.last_user_message:
            self.history_store.append_record(
                self.last_user_message, reply_text
            )
            self.history_records = self.history_store.load_records()
            self._maybe_trigger_memory_summary()

        if self.current_narration:
            self.start_narration_output()
        else:
            self.start_next_reply_segment()
            for _seg in self.pending_reply_segments:
                self.begin_tts_for_reply(_seg, start_when_ready=False)

    def start_narration_output(self) -> None:
        self.chat_state.begin_narration_output()
        self._apply_state_flags()
        self.set_character_emotion(self.top_level_emotion)
        self.set_character_state("idle", self._do_start_narration)
        for _seg in self.pending_reply_segments:
            self.begin_tts_for_reply(_seg, start_when_ready=False)

    def _do_start_narration(self) -> None:
        self.current_reply_full = self.current_narration
        self.current_reply_visible = ""
        self.start_text_demote_transition()
        self.typewriter_timer.start()
        self._refresh_render_timer_running()
        self.update()

    def on_narration_wait_elapsed(self) -> None:
        self.current_dialogue_page_text = ""
        self.current_dialogue_base_line_count = 0
        self.start_next_reply_segment()

    def on_reply_failed(self, error_text: str) -> None:
        self.chat_state.begin_reply_output()
        self._apply_state_flags()
        self.cursor_visible = False
        self.current_dialogue_page_text = ""
        self.current_dialogue_base_line_count = 0
        self.current_dialogue_segment_index = 0
        self.pending_reply_segments = [
            {
                "reply": self.quote_text(f"请求失败：{error_text}"),
                "jp_translation": "请求失败",
                "emotion": "normal",
            }
        ]
        self.current_reply_full = ""
        self.current_reply_visible = ""
        if self.last_user_message:
            self.history_store.append_record(
                self.last_user_message, f"请求失败：{error_text}"
            )
            self.history_records = self.history_store.load_records()
            self._maybe_trigger_memory_summary()
        self.start_next_reply_segment()

    def on_request_finished(self) -> None:
        self._apply_state_flags()
        self.last_user_message = ""

    def will_next_segment_overflow(self) -> bool:
        if not self.pending_reply_segments:
            return False
        next_text = self.pending_reply_segments[0].get("reply", "")
        if not next_text:
            return False
        needed_lines = self.wrap_text(next_text)
        return not self.lines_fit_in_display(
            self.cached_chat_lines + needed_lines
        )

    def on_segment_gap_elapsed(self) -> None:
        if self.pending_page_turn_before_next_segment:
            self.pending_page_turn_before_next_segment = False
            self.start_page_turn_transition()
            return
        self.start_next_reply_segment()

    def start_next_reply_segment(self) -> None:
        if not self.pending_reply_segments:
            if not self.audio_manager.is_playing():
                self.idle_timer.start(IDLE_RETURN_DELAY_MS)
            return

        segment = self.pending_reply_segments.pop(0)
        self.current_segment_is_followup = self.current_dialogue_segment_index > 0
        self.current_dialogue_segment_index += 1
        reply_text = segment["reply"]

        needed_lines = self.wrap_text(reply_text)
        if not self.lines_fit_in_display(
            self.cached_chat_lines + needed_lines
        ):
            if self.current_dialogue_segment_index > 1 and self.chat_entries:
                self.pending_reply_segments.insert(0, segment)
                self.current_dialogue_segment_index -= 1
                self.start_page_turn_transition()
                return
            self.clear_chat_entries()

        previous_emotion = self.character_emotion
        self.set_character_emotion(segment["emotion"])
        self.current_segment_requires_transition = (
            self.character_state != "speaking"
            or previous_emotion != self.character_emotion
        )
        self.current_dialogue_base_line_count = (
            len(self.wrap_text(self.current_dialogue_page_text))
            if self.current_dialogue_page_text
            else 0
        )
        self.current_reply_full = reply_text
        self.current_reply_visible = ""
        self.begin_tts_for_reply(segment, start_when_ready=True)

    def start_reply_output(self) -> None:
        self.start_text_demote_transition()
        self.queue_prefetch_next_segment()
        self.typewriter_timer.start()
        self._refresh_render_timer_running()
        self._mark_layout_dirty()
        self.update()

    def advance_typewriter(self) -> None:
        self.current_reply_visible = self.current_reply_full[
            : len(self.current_reply_visible) + 1
        ]
        self._mark_layout_dirty()
        if self.current_reply_visible == self.current_reply_full:
            self.typewriter_timer.stop()
            self._refresh_render_timer_running()
            self.append_or_extend_dialogue_entry(self.current_reply_full)
            self.current_reply_full = ""
            self.current_reply_visible = ""

            if self.is_outputting_narration:
                self.chat_state.end_narration_output()
                self._apply_state_flags()
                self.narration_wait_timer.start(2000)
            else:
                if self.pending_reply_segments:
                    self.queue_prefetch_next_segment()
                    self.pending_page_turn_before_next_segment = (
                        self.will_next_segment_overflow()
                    )
                    if self.audio_manager.is_playing():
                        self.chat_state.set_waiting_audio_before_next_segment(
                            True
                        )
                        self._apply_state_flags()
                    else:
                        self.page_turn_timer.start(SEGMENT_GAP_INTERVAL_MS)
                elif self.audio_manager.is_playing():
                    return
                else:
                    self.idle_timer.start(IDLE_RETURN_DELAY_MS)
        self.update()

    def return_to_idle(self) -> None:
        if (
            self.pending_reply_segments
            or self.typewriter_timer.isActive()
            or self.page_turn_timer.isActive()
        ):
            if getattr(self, "waiting_audio_before_next_segment", False):
                self.idle_timer.start(ANIMATION_TICK_MS)
            return

        if self.pending_idle_after_text_demote:
            if self.text_fade_timer.isActive():
                self.idle_timer.start(ANIMATION_TICK_MS)
                return
            self.pending_idle_after_text_demote = False
        elif self.dialogue_history_stable_len < len(
            self.current_dialogue_page_text
        ):
            self.pending_idle_after_text_demote = True
            self.start_text_demote_transition()
            self.idle_timer.start(int(self.text_demote_duration_ms))
            return
        self.set_character_state("idle", self.finish_return_to_idle)

    def finish_return_to_idle(self) -> None:
        self.chat_state.return_to_idle("finish_return_to_idle")
        self._apply_state_flags()
        self.cursor_visible = True
        self.update()

    def clear_screen_text(self) -> None:
        if (
            self.waiting_for_reply
            or self.typewriter_timer.isActive()
            or self.page_turn_timer.isActive()
            or self.animation_timer.isActive()
        ):
            return

        self.clear_chat_entries()
        self.current_input = ""
        self.preedit_text = ""
        self.current_reply_full = ""
        self.current_reply_visible = ""

        self.latest_user_line_count = 0
        self.reply_output_started = False
        self.user_entry_alpha = 1.0
        self.dialogue_history_stable_len = 0
        self.dialogue_demoting_end = 0
        self.dialogue_demoting_alpha = self.text_demote_target_alpha
        self.user_fade_start_alpha = 1.0
        self.dialogue_fade_start_alpha = self.text_demote_target_alpha
        self.text_fade_progress = 1.0
        self.text_fade_timer.stop()
        self._refresh_render_timer_running()
        self.pending_idle_after_text_demote = False

        self.chat_state.return_to_idle("clear_screen")
        self._apply_state_flags()
        self.cursor_visible = True
        self._mark_layout_dirty()
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
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

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)

        self.fullscreen_action = QAction("全屏模式 (F11)", self)
        self.fullscreen_action.setCheckable(True)
        self.fullscreen_action.setChecked(self.is_fullscreen)
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        menu.addAction(self.fullscreen_action)

        menu.addSeparator()

        overlay_action = QAction("启用蒙版", self)
        overlay_action.setCheckable(True)
        overlay_action.setChecked(self.overlay_enabled)
        overlay_action.triggered.connect(self.set_overlay_enabled)
        menu.addAction(overlay_action)

        history_action = QAction("历史", self)
        history_action.triggered.connect(self.open_history_dialog)
        menu.addAction(history_action)

        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        menu.addAction(settings_action)

        clear_screen_action = QAction("清屏", self)
        clear_screen_action.triggered.connect(self.clear_screen_text)
        menu.addAction(clear_screen_action)

        menu.exec(event.globalPos())

    def open_history_dialog(self) -> None:
        dialog = HistoryDialog(self.history_store, self.settings_store, self)
        dialog.exec()
        self.history_records = self.history_store.load_records()
        self.memory_state = self.settings_store.load_memory_state()
        self.restore_input_context()

    def open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        result = dialog.exec()
        self.restore_input_context()
        if result != QDialog.DialogCode.Accepted:
            return
        updated = dialog.to_settings()
        updated.current_background = self.settings.current_background
        self.settings = updated
        self.settings_store.save(self.settings)
        if self.settings.api_key:
            os.environ["DEEPSEEK_API_KEY"] = self.settings.api_key
        else:
            os.environ.pop("DEEPSEEK_API_KEY", None)

    def restore_input_context(self) -> None:
        QTimer.singleShot(0, self._restore_input_context_impl)

    def _refresh_ime(self) -> None:
        """刷新并激活 IME（输入法）。

        应在获取焦点或对话框关闭后调用，确保输入法保持可用状态。
        """
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
