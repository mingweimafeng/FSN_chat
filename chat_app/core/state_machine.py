from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, Signal


class UiPhase(str, Enum):
    IDLE = "idle"
    WAITING_REPLY = "waiting_reply"
    OUTPUTTING_REPLY = "outputting_reply"
    OUTPUTTING_NARRATION = "outputting_narration"
    CLOSING = "closing"


class ChatStateMachine(QObject):
    """Centralizes UI dialogue state to avoid conflicting boolean flags in window code."""

    phase_changed = Signal(str, str, str)
    flags_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._phase = UiPhase.IDLE
        self._waiting_audio_before_next_segment = False

    @property
    def phase(self) -> UiPhase:
        return self._phase

    @property
    def waiting_for_reply(self) -> bool:
        return self._phase == UiPhase.WAITING_REPLY

    @property
    def reply_output_active(self) -> bool:
        return self._phase in (UiPhase.OUTPUTTING_REPLY, UiPhase.OUTPUTTING_NARRATION)

    @property
    def is_outputting_narration(self) -> bool:
        return self._phase == UiPhase.OUTPUTTING_NARRATION

    @property
    def waiting_audio_before_next_segment(self) -> bool:
        return self._waiting_audio_before_next_segment

    def transition_to(self, phase: UiPhase, reason: str = "") -> None:
        if phase == self._phase:
            return
        old = self._phase
        self._phase = phase
        self.phase_changed.emit(old.value, self._phase.value, reason)
        self.flags_changed.emit()

    def set_waiting_audio_before_next_segment(self, waiting: bool) -> None:
        waiting = bool(waiting)
        if waiting == self._waiting_audio_before_next_segment:
            return
        self._waiting_audio_before_next_segment = waiting
        self.flags_changed.emit()

    def reset_for_new_input(self) -> None:
        self._waiting_audio_before_next_segment = False
        self.transition_to(UiPhase.WAITING_REPLY, reason="submit_input")

    def begin_reply_output(self) -> None:
        self._waiting_audio_before_next_segment = False
        self.transition_to(UiPhase.OUTPUTTING_REPLY, reason="reply_ready")

    def begin_narration_output(self) -> None:
        self.transition_to(UiPhase.OUTPUTTING_NARRATION, reason="narration_start")

    def end_narration_output(self) -> None:
        if self._phase == UiPhase.OUTPUTTING_NARRATION:
            self.transition_to(UiPhase.OUTPUTTING_REPLY, reason="narration_end")

    def return_to_idle(self, reason: str = "") -> None:
        self._waiting_audio_before_next_segment = False
        self.transition_to(UiPhase.IDLE, reason=reason or "idle")

    def begin_closing(self) -> None:
        self.transition_to(UiPhase.CLOSING, reason="close_event")

