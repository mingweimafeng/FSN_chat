from __future__ import annotations

from collections import deque
from typing import Optional

from PySide6.QtCore import QObject, Signal

from chat_app.audio.tts_client import TtsSynthesisThread


class TtsPipelineManager(QObject):
    audio_ready = Signal(dict, bool)
    synthesis_failed = Signal(dict, bool, str)

    def __init__(self, tts_client) -> None:
        super().__init__()
        self._tts_client = tts_client
        self._synth_task_queue: deque[tuple[dict, bool]] = deque()
        self._active_synth_segment: Optional[dict] = None
        self._active_synth_start_when_ready: bool = False
        self._tts_thread: Optional[TtsSynthesisThread] = None

    def begin_tts_for_reply(self, segment: dict[str, str], start_when_ready: bool) -> None:
        if segment.get("audio_path") or segment.get("audio_failed"):
            if start_when_ready:
                self.audio_ready.emit(segment, True)
            return

        if self._active_synth_segment is segment:
            if start_when_ready and not self._active_synth_start_when_ready:
                self._active_synth_start_when_ready = True
            return

        for queued_segment, queued_start_when_ready in self._synth_task_queue:
            if queued_segment is segment:
                if start_when_ready and not queued_start_when_ready:
                    index = list(self._synth_task_queue).index((queued_segment, queued_start_when_ready))
                    temp_list = list(self._synth_task_queue)
                    temp_list[index] = (queued_segment, True)
                    self._synth_task_queue = deque(temp_list)
                return

        self._synth_task_queue.append((segment, start_when_ready))
        self.pump_synthesis_queue()

    def pump_synthesis_queue(self) -> None:
        if self._tts_thread is not None and self._tts_thread.isRunning():
            return
        if not self._synth_task_queue:
            return

        segment, start_when_ready = self._synth_task_queue.popleft()
        self._active_synth_segment = segment
        self._active_synth_start_when_ready = start_when_ready
        self._tts_thread = TtsSynthesisThread(
            self._tts_client,
            segment.get("jp_translation", "...").strip() or "...",
            segment.get("emotion", "normal"),
        )
        self._tts_thread.finished_audio.connect(self._on_tts_audio_ready)
        self._tts_thread.failed.connect(self._on_tts_audio_failed)
        self._tts_thread.start()

    def queue_prefetch_next_segment(self, pending_reply_segments: list) -> None:
        if not pending_reply_segments:
            return
        next_segment = pending_reply_segments[0]
        if next_segment.get("audio_path") or next_segment.get("audio_failed"):
            return
        if self._active_synth_segment is next_segment:
            return

        for queued_segment, _ in self._synth_task_queue:
            if queued_segment is next_segment:
                return

        self.begin_tts_for_reply(next_segment, start_when_ready=False)

    def _on_tts_audio_ready(self, audio_path: str) -> None:
        segment = self._active_synth_segment
        start_when_ready = self._active_synth_start_when_ready
        if segment is not None:
            segment["audio_path"] = audio_path

        self._active_synth_segment = None
        self._active_synth_start_when_ready = False
        self._tts_thread = None

        if segment is not None:
            self.audio_ready.emit(segment, start_when_ready)
        self.pump_synthesis_queue()

    def _on_tts_audio_failed(self, error_text: str) -> None:
        print(f"[TTS synth failed] {error_text}")
        segment = self._active_synth_segment
        if segment is None:
            self._tts_thread = None
            self.pump_synthesis_queue()
            return
        start_when_ready = self._active_synth_start_when_ready
        segment["audio_failed"] = "1"

        self._active_synth_segment = None
        self._active_synth_start_when_ready = False
        self._tts_thread = None

        self.synthesis_failed.emit(segment, start_when_ready, error_text)
        self.pump_synthesis_queue()

    def reset(self) -> None:
        self._synth_task_queue.clear()
        self._active_synth_segment = None
        self._active_synth_start_when_ready = False
        if self._tts_thread is not None and self._tts_thread.isRunning():
            self._tts_thread.stop()
