from __future__ import annotations

import io
import multiprocessing
import os
import socket
import sys
import time
import uuid
import wave
from pathlib import Path
from typing import Optional

import requests
from PySide6.QtCore import QThread, Signal

from chat_app.config import (
    GENIE_AUDIO_BYTES_PER_SAMPLE,
    GENIE_AUDIO_CHANNELS,
    GENIE_AUDIO_SAMPLE_RATE,
    GENIE_CHARACTER_NAME,
    GENIE_MODEL_LANGUAGE,
    GENIE_ONNX_MODEL_DIR,
    GENIE_REFERENCE_AUDIO_DIR,
    GENIE_REFERENCE_LANGUAGE,
    GENIE_SERVER_HOST,
    GENIE_SERVER_PORT,
    TEMP_AUDIO_DIR,
)


def _run_genie_server(host: str, port: int) -> None:
    import builtins
    import os
    import sys

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if getattr(sys, "frozen", False):
        genie_data = os.path.join(sys._MEIPASS, "GenieData")
        os.environ["GENIE_DATA_DIR"] = genie_data

    _real_input = builtins.input

    def _noninteractive_input(*args, **kwargs):
        return "n"

    builtins.input = _noninteractive_input

    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    try:
        import genie_tts as genie
    finally:
        builtins.input = _real_input

    genie.start_server(host=host, port=port, workers=1)


class GenieTTSClient:
    def __init__(self) -> None:
        self.base_url = f"http://{GENIE_SERVER_HOST}:{GENIE_SERVER_PORT}"
        self.server_process: Optional[multiprocessing.Process] = None
        self.character_loaded = False
        self.current_reference_emotion = ""

    def ensure_server_running(self, timeout_s: float = 10.0) -> None:
        if self._is_server_ready():
            return

        if self.server_process is None or not self.server_process.is_alive():
            os.environ.setdefault("PYTHONIOENCODING", "utf-8")
            if getattr(sys, "frozen", False):
                os.environ["GENIE_DATA_DIR"] = os.path.join(sys._MEIPASS, "GenieData")
            self.server_process = multiprocessing.Process(
                target=_run_genie_server,
                args=(GENIE_SERVER_HOST, GENIE_SERVER_PORT),
                daemon=True,
            )
            self.server_process.start()

        start = time.time()
        while time.time() - start < timeout_s:
            if self._is_server_ready():
                return
            time.sleep(0.2)
        raise RuntimeError("Genie TTS server 启动超时。")

    def initialize(self) -> None:
        TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        self.ensure_server_running()
        if self.character_loaded:
            return

        payload = {
            "character_name": GENIE_CHARACTER_NAME,
            "onnx_model_dir": str(GENIE_ONNX_MODEL_DIR),
            "language": GENIE_MODEL_LANGUAGE,
        }
        self._post_json("/load_character", payload)
        self.character_loaded = True

    def synthesize_to_temp_file(self, text: str, emotion: str) -> Path:
        content = text.strip()
        if not content:
            raise RuntimeError("空文本无法生成语音。")

        self.initialize()
        self._set_reference_audio(emotion)

        payload = {
            "character_name": GENIE_CHARACTER_NAME,
            "text": content,
            "split_sentence": False,
        }

        audio_bytes = self._request_tts_audio_bytes(payload)

        output_path = TEMP_AUDIO_DIR / f"tts_{uuid.uuid4().hex}.wav"
        self._write_audio_file(output_path, audio_bytes)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Genie TTS 音频文件写入失败。")
        return output_path

    def shutdown(self) -> None:
        if self.character_loaded:
            try:
                self._post_json("/unload_character", {"character_name": GENIE_CHARACTER_NAME}, timeout=10)
            except Exception:
                pass
            self.character_loaded = False

        try:
            self._post_json("/clear_reference_audio_cache", None, timeout=10)
        except Exception:
            pass

        if self.server_process is not None and self.server_process.is_alive():
            self.server_process.terminate()
            self.server_process.join(timeout=2)
        self.server_process = None

    def _set_reference_audio(self, emotion: str) -> None:
        normalized = emotion if emotion else "normal"
        folder = GENIE_REFERENCE_AUDIO_DIR / normalized
        if not folder.exists() or not folder.is_dir():
            normalized = "normal"
            folder = GENIE_REFERENCE_AUDIO_DIR / "normal"

        if normalized == self.current_reference_emotion:
            return

        audio_path = folder / "audio.wav"
        text_path = folder / "reference.txt"
        if not audio_path.exists() or not text_path.exists():
            raise RuntimeError(f"参考音频缺失: {folder}")

        payload = {
            "character_name": GENIE_CHARACTER_NAME,
            "audio_path": str(audio_path),
            "audio_text": text_path.read_text(encoding="utf-8").strip(),
            "language": GENIE_REFERENCE_LANGUAGE,
        }
        self._post_json("/set_reference_audio", payload)
        self.current_reference_emotion = normalized

    def _is_server_ready(self) -> bool:
        try:
            with socket.create_connection((GENIE_SERVER_HOST, GENIE_SERVER_PORT), timeout=2) as sock:
                return True
        except (OSError, socket.error, socket.timeout):
            return False

    def _post_json(self, endpoint: str, payload: Optional[dict], timeout: int = 30) -> dict:
        response = requests.post(f"{self.base_url}{endpoint}", json=payload, timeout=timeout)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {}

    def _request_tts_audio_bytes(self, payload: dict) -> bytes:
        response = requests.post(f"{self.base_url}/tts", json=payload, timeout=30, stream=True)
        response.raise_for_status()

        audio_bytes = b""
        for chunk in response.iter_content(chunk_size=8192):
            audio_bytes += chunk

        if not audio_bytes:
            raise RuntimeError("Genie TTS 返回了空音频。")
        return audio_bytes

    def _write_audio_file(self, output_path: Path, audio_bytes: bytes) -> None:
        if audio_bytes[:4] == b"RIFF":
            output_path.write_bytes(audio_bytes)
            return

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(GENIE_AUDIO_CHANNELS)
            wav_file.setsampwidth(GENIE_AUDIO_BYTES_PER_SAMPLE)
            wav_file.setframerate(GENIE_AUDIO_SAMPLE_RATE)
            wav_file.writeframes(audio_bytes)


class TtsSynthesisThread(QThread):
    finished_audio = Signal(str)
    failed = Signal(str)

    def __init__(self, client: GenieTTSClient, text: str, emotion: str) -> None:
        super().__init__()
        self.client = client
        self.text = text
        self.emotion = emotion
        self._interrupted = False

    def run(self) -> None:
        try:
            audio_path = self.client.synthesize_to_temp_file(self.text, self.emotion)
            if not self._interrupted:
                self.finished_audio.emit(str(audio_path))
        except Exception as error:
            if not self._interrupted:
                self.failed.emit(str(error))

    def stop(self) -> None:
        self._interrupted = True


class TtsWarmupThread(QThread):
    warmed_up = Signal()
    failed = Signal(str)

    def __init__(self, client: GenieTTSClient) -> None:
        super().__init__()
        self.client = client
        self._interrupted = False

    def run(self) -> None:
        try:
            self.client.initialize()
            if not self._interrupted:
                self.warmed_up.emit()
        except Exception as error:
            if not self._interrupted:
                self.failed.emit(str(error))

    def stop(self) -> None:
        self._interrupted = True
