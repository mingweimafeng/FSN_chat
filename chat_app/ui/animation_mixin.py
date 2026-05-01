from __future__ import annotations

from PySide6.QtGui import QPixmap

from chat_app.config import (
    AFTER_FADE_OUT_DELAY_MS,
    ANIMATION_TICK_MS,
    BEFORE_FADE_IN_DELAY_MS,
    CURSOR_BLINK_INTERVAL_MS,
    FOREGROUND_FADE_IN_DURATION_MS,
    FOREGROUND_FADE_OUT_DURATION_MS,
    PAGE_TURN_FADE_IN_DURATION_MS,
    PAGE_TURN_FADE_OUT_DURATION_MS,
    PORTRAIT_FADE_DURATION_MS,
    TYPEWRITER_INTERVAL_MS,
)
from chat_app.core.window_runtime import VirtualTimer


class AnimationMixin:
    def _refresh_render_timer_running(self) -> None:
        active = (
            self.cursor_timer.isActive()
            or self.typewriter_timer.isActive()
            or self.animation_timer.isActive()
            or self.text_fade_timer.isActive()
        )
        if active and not self.render_timer.isActive():
            self.render_timer.start()
        elif not active and self.render_timer.isActive():
            self.render_timer.stop()

    def _on_render_tick(self) -> None:
        if self.cursor_timer.tick(ANIMATION_TICK_MS):
            self.toggle_cursor()
        if self.typewriter_timer.tick(ANIMATION_TICK_MS):
            self.advance_typewriter()
        if self.animation_timer.tick(ANIMATION_TICK_MS):
            self.advance_animation()
        if self.text_fade_timer.tick(ANIMATION_TICK_MS):
            self.advance_text_fade()
        self._refresh_render_timer_running()

    def toggle_cursor(self) -> None:
        self.cursor_visible = not self.cursor_visible
        self._mark_cursor_dirty()
        self.update()

    def begin_portrait_transition(
        self, new_pixmap, resume_action=None, quick: bool = False
    ) -> None:
        if self.character_pixmap.cacheKey() == new_pixmap.cacheKey():
            self.character_pixmap = new_pixmap
            self.previous_character_pixmap = QPixmap()
            self.next_character_pixmap = QPixmap()
            self.portrait_blend_progress = 1.0
            if resume_action is not None:
                resume_action()
            else:
                self.update()
            return

        self.previous_character_pixmap = self.character_pixmap
        self.next_character_pixmap = new_pixmap
        self.portrait_blend_progress = 0.0
        self.pending_resume_action = resume_action
        if quick:
            self.animation_phase = "portrait_only"
            self.animation_timer.start(ANIMATION_TICK_MS)
            self._refresh_render_timer_running()
            self.update()
            return

        self.text_layer_alpha = 1.0
        self.overlay_alpha = 1.0
        self.animation_phase = "fade_out"
        self.animation_timer.start()
        self._refresh_render_timer_running()
        self.update()

    def start_page_turn_transition(self) -> None:
        self.text_layer_alpha = 1.0
        self.overlay_alpha = 1.0
        self.pending_resume_action = self.start_next_reply_segment
        self.animation_phase = "page_fade_out"
        self.animation_timer.start(ANIMATION_TICK_MS)
        self._refresh_render_timer_running()
        self.update()

    def start_text_demote_transition(self) -> None:
        self.reply_output_started = True
        demoting_start = self.dialogue_history_stable_len
        demoting_end = len(self.current_dialogue_page_text)
        self.dialogue_demoting_end = demoting_end

        need_user_fade = (
            self.user_entry_alpha > self.text_demote_target_alpha + 0.0001
        )
        need_dialogue_fade = demoting_end > demoting_start

        self.text_fade_progress = 0.0
        self.user_fade_start_alpha = max(
            self.text_demote_target_alpha, min(1.0, self.user_entry_alpha)
        )
        if need_dialogue_fade:
            start_alpha = (
                self.dialogue_demoting_alpha
                if self.text_fade_timer.isActive()
                else 1.0
            )
            self.dialogue_fade_start_alpha = max(
                self.text_demote_target_alpha, min(1.0, start_alpha)
            )
            self.dialogue_demoting_alpha = self.dialogue_fade_start_alpha
        else:
            self.dialogue_fade_start_alpha = self.text_demote_target_alpha
            self.dialogue_demoting_alpha = self.text_demote_target_alpha

        if need_user_fade or need_dialogue_fade:
            self.text_fade_timer.start()
            self._refresh_render_timer_running()
        else:
            self.user_entry_alpha = self.text_demote_target_alpha
            self.dialogue_history_stable_len = demoting_end
            self.dialogue_demoting_alpha = self.text_demote_target_alpha
        self._mark_layout_dirty()

    def advance_animation(self) -> None:
        phase_handlers = {
            "portrait_only": self._advance_portrait_only,
            "page_fade_out": self._advance_page_fade_out,
            "page_fade_in": self._advance_page_fade_in,
        }
        handler = phase_handlers.get(self.animation_phase)
        if handler:
            handler()
            return

        if self.animation_phase in (
            "fade_out", "after_fade_out_delay", "portrait",
            "before_fade_in_delay", "fade_in",
        ):
            self._advance_character_transition()

    def _advance_portrait_only(self) -> None:
        step = ANIMATION_TICK_MS / PORTRAIT_FADE_DURATION_MS
        self.portrait_blend_progress = min(1.0, self.portrait_blend_progress + step)
        if self.portrait_blend_progress >= 1.0:
            self.character_pixmap = self.next_character_pixmap
            self.previous_character_pixmap = QPixmap()
            self.next_character_pixmap = QPixmap()
            self.portrait_blend_progress = 1.0
            self.animation_phase = "idle"
            self.animation_timer.stop()
            resume_action = self.pending_resume_action
            self.pending_resume_action = None
            if resume_action is not None:
                resume_action()
        self._mark_layout_dirty()
        self.update()

    def _advance_page_fade_out(self) -> None:
        step = ANIMATION_TICK_MS / PAGE_TURN_FADE_OUT_DURATION_MS
        self.text_layer_alpha = max(0.0, self.text_layer_alpha - step)
        self.overlay_alpha = max(0.0, self.overlay_alpha - step)
        if self.text_layer_alpha <= 0.0 and self.overlay_alpha <= 0.0:
            self.text_layer_alpha = 0.0
            self.overlay_alpha = 0.0
            self.clear_chat_entries()
            self.animation_phase = "page_fade_in"
            self.animation_timer.start(ANIMATION_TICK_MS)
        self._mark_layout_dirty()
        self.update()

    def _advance_page_fade_in(self) -> None:
        step = ANIMATION_TICK_MS / PAGE_TURN_FADE_IN_DURATION_MS
        self.text_layer_alpha = min(1.0, self.text_layer_alpha + step)
        self.overlay_alpha = min(1.0, self.overlay_alpha + step)
        if self.text_layer_alpha >= 1.0 and self.overlay_alpha >= 1.0:
            self.text_layer_alpha = 1.0
            self.overlay_alpha = 1.0
            self.animation_phase = "idle"
            self.animation_timer.stop()
            resume_action = self.pending_resume_action
            self.pending_resume_action = None
            if resume_action is not None:
                resume_action()
        self._mark_layout_dirty()
        self.update()

    def _advance_character_transition(self) -> None:
        if self.animation_phase == "fade_out":
            step = ANIMATION_TICK_MS / FOREGROUND_FADE_OUT_DURATION_MS
            self.text_layer_alpha = max(0.0, self.text_layer_alpha - step)
            self.overlay_alpha = max(0.0, self.overlay_alpha - step)
            if self.text_layer_alpha <= 0.0 and self.overlay_alpha <= 0.0:
                self.text_layer_alpha = 0.0
                self.overlay_alpha = 0.0
                self.animation_phase = "after_fade_out_delay"
                self.animation_timer.start(AFTER_FADE_OUT_DELAY_MS)
        elif self.animation_phase == "after_fade_out_delay":
            self.animation_phase = "portrait"
            self.animation_timer.start(ANIMATION_TICK_MS)
        elif self.animation_phase == "portrait":
            step = ANIMATION_TICK_MS / PORTRAIT_FADE_DURATION_MS
            self.portrait_blend_progress = min(1.0, self.portrait_blend_progress + step)
            if self.portrait_blend_progress >= 1.0:
                self.character_pixmap = self.next_character_pixmap
                self.previous_character_pixmap = QPixmap()
                self.next_character_pixmap = QPixmap()
                self.portrait_blend_progress = 1.0
                self.animation_phase = "before_fade_in_delay"
                self.animation_timer.start(BEFORE_FADE_IN_DELAY_MS)
        elif self.animation_phase == "before_fade_in_delay":
            self.animation_phase = "fade_in"
            self.animation_timer.start(ANIMATION_TICK_MS)
        elif self.animation_phase == "fade_in":
            step = ANIMATION_TICK_MS / FOREGROUND_FADE_IN_DURATION_MS
            self.text_layer_alpha = min(1.0, self.text_layer_alpha + step)
            self.overlay_alpha = min(1.0, self.overlay_alpha + step)
            if self.text_layer_alpha >= 1.0 and self.overlay_alpha >= 1.0:
                self.text_layer_alpha = 1.0
                self.overlay_alpha = 1.0
                self.animation_phase = "idle"
                self.animation_timer.stop()
                resume_action = self.pending_resume_action
                self.pending_resume_action = None
                if resume_action is not None:
                    resume_action()
        self._mark_layout_dirty()
        self.update()

    def advance_text_fade(self) -> None:
        if self.text_demote_duration_ms <= 0:
            self.text_fade_timer.stop()
            return
        step = ANIMATION_TICK_MS / self.text_demote_duration_ms
        self.text_fade_progress = min(1.0, self.text_fade_progress + step)

        user_drop = self.user_fade_start_alpha - self.text_demote_target_alpha
        self.user_entry_alpha = max(
            self.text_demote_target_alpha,
            self.user_fade_start_alpha - user_drop * self.text_fade_progress,
        )

        if self.dialogue_demoting_end > self.dialogue_history_stable_len:
            dialogue_drop = (
                self.dialogue_fade_start_alpha - self.text_demote_target_alpha
            )
            self.dialogue_demoting_alpha = max(
                self.text_demote_target_alpha,
                self.dialogue_fade_start_alpha - dialogue_drop * self.text_fade_progress,
            )

        if self.text_fade_progress >= 1.0:
            self.text_fade_timer.stop()
            self.user_entry_alpha = self.text_demote_target_alpha
            self.dialogue_demoting_alpha = self.text_demote_target_alpha
            self.dialogue_history_stable_len = self.dialogue_demoting_end
        self._mark_layout_dirty()
        self.update()
