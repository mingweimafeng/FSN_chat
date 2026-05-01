from __future__ import annotations

from pathlib import Path

from chat_app.audio.tts_client import TtsWarmupThread
from chat_app.config import SEGMENT_GAP_INTERVAL_MS, IDLE_RETURN_DELAY_MS, TEMP_AUDIO_DIR


class AudioMixin:
    def _setup_audio_connections(self) -> None:
        self.tts_pipeline.audio_ready.connect(self._on_tts_audio_ready)
        self.tts_pipeline.synthesis_failed.connect(self._on_tts_synthesis_failed)

    def start_tts_warmup(self) -> None:
        self.tts_warmup_thread = TtsWarmupThread(self.tts_client)
        self.tts_warmup_thread.failed.connect(self.on_tts_warmup_failed)

    def on_tts_warmup_failed(self, error_text: str) -> None:
        print(f"[TTS warmup failed] {error_text}")

    def begin_tts_for_reply(
        self, segment: dict[str, str], start_when_ready: bool
    ) -> None:
        self.tts_pipeline.begin_tts_for_reply(segment, start_when_ready)

    def pump_synthesis_queue(self) -> None:
        self.tts_pipeline.pump_synthesis_queue()

    def queue_prefetch_next_segment(self) -> None:
        self.tts_pipeline.queue_prefetch_next_segment(self.pending_reply_segments)

    def start_segment_after_audio_ready(self, segment: dict[str, str]) -> None:
        audio_path = segment.get("audio_path")
        if audio_path:
            self.audio_manager.play(Path(audio_path))
        if self.current_segment_requires_transition:
            quick = self.current_segment_is_followup
            self.set_character_state("speaking", self.start_reply_output, quick=quick)
        else:
            self.character_state = "speaking"
            self.start_reply_output()

    def _on_tts_audio_ready(self, segment: dict[str, str], start_when_ready: bool) -> None:
        if start_when_ready:
            self.start_segment_after_audio_ready(segment)

    def _on_tts_synthesis_failed(self, segment: dict[str, str], start_when_ready: bool, error_text: str) -> None:
        print(f"[TTS synth failed] {error_text}")
        if start_when_ready:
            self.start_segment_after_audio_ready(segment)

    def _on_audio_manager_finished(self) -> None:
        if self.waiting_audio_before_next_segment:
            self.chat_state.set_waiting_audio_before_next_segment(False)
            self._apply_state_flags()
            self.page_turn_timer.start(SEGMENT_GAP_INTERVAL_MS)
            return

        if (
            not self.pending_reply_segments
            and not self.typewriter_timer.isActive()
            and not self.page_turn_timer.isActive()
        ):
            self.idle_timer.start(IDLE_RETURN_DELAY_MS)

    def _on_audio_manager_failed(self, error_msg: str) -> None:
        print(f"[Audio Error] {error_msg}")
        self._on_audio_manager_finished()

    def cleanup_all_temp_audio(self) -> None:
        if not TEMP_AUDIO_DIR.exists():
            return
        for file_path in TEMP_AUDIO_DIR.iterdir():
            if file_path.is_file() and file_path.suffix.lower() == ".wav":
                try:
                    file_path.unlink()
                except Exception:
                    pass
