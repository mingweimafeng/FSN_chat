from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioManager(QObject):
    playback_finished = Signal()
    playback_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_ready = True
        self.current_audio_path: Path | None = None

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        self._player.errorOccurred.connect(self._on_error)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlayingState

    def play(self, audio_path: Path) -> None:
        if not audio_path.exists():
            self.playback_failed.emit("音频文件不存在")
            return

        self.stop()
        try:
            self.current_audio_path = audio_path
            self._player.setSource(QUrl.fromLocalFile(str(audio_path)))
            self._player.play()
        except Exception as error:
            self.playback_failed.emit(str(error))
            self._cleanup_current_file()

    def stop(self) -> None:
        self._player.stop()
        self._cleanup_current_file()

    def set_volume(self, volume: float) -> None:
        """设置音量 (0.0 ~ 1.0)"""
        self._audio_output.setVolume(max(0.0, min(1.0, volume)))

    def volume(self) -> float:
        """获取当前音量"""
        return self._audio_output.volume()

    def _on_media_status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.stop()
            self.playback_finished.emit()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.stop()
            self.playback_failed.emit("无效的媒体文件")

    def _on_error(self, error, error_string) -> None:
        if error != QMediaPlayer.Error.NoError:
            print(f"[AudioManager] 播放错误: {error_string}")
            self.stop()
            self.playback_failed.emit(error_string)

    def _cleanup_current_file(self) -> None:
        if self.current_audio_path and self.current_audio_path.exists():
            try:
                self.current_audio_path.unlink()
            except Exception:
                pass
        self.current_audio_path = None
