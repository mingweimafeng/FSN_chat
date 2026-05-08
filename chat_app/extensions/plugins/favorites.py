from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chat_app.audio.tts_client import TtsSynthesisThread
from chat_app.extensions.api import BaseExtension


def _get_user_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent.parent


_USER_DATA = _get_user_data_dir()
FAVORITES_FILE = _USER_DATA / "favorites.json"
FAVORITES_AUDIO_DIR = _USER_DATA / "favorites_audio"


class FavoritesStore:
    def __init__(self) -> None:
        FAVORITES_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict]:
        if not FAVORITES_FILE.exists():
            return []
        try:
            data = json.loads(FAVORITES_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save(self, favorites: list[dict]) -> None:
        FAVORITES_FILE.write_text(
            json.dumps(favorites, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, text: str) -> dict:
        fav = {
            "id": f"fav_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": text,
            "audio_path": None,
        }
        favorites = self.load()
        favorites.insert(0, fav)
        self.save(favorites)
        return fav

    def remove(self, fav_id: str) -> None:
        favorites = self.load()
        for fav in favorites:
            if fav["id"] == fav_id:
                audio = fav.get("audio_path")
                if audio:
                    p = Path(audio)
                    if p.exists():
                        try:
                            p.unlink()
                        except Exception:
                            pass
                break
        new_favorites = [f for f in favorites if f["id"] != fav_id]
        self.save(new_favorites)

    def update_audio_path(self, fav_id: str, audio_path: str) -> None:
        favorites = self.load()
        for fav in favorites:
            if fav["id"] == fav_id:
                fav["audio_path"] = audio_path
                break
        self.save(favorites)


class FavoritesExtension(BaseExtension):
    @property
    def name(self) -> str:
        return "Favorites"

    def __init__(self) -> None:
        super().__init__()
        self._store = FavoritesStore()
        self._dialog: FavoritesDialog | None = None
        self._synth_thread: TtsSynthesisThread | None = None
        self._pending_fav_id: str | None = None

    def on_start(self) -> None:
        pass

    def on_stop(self) -> None:
        if self._dialog is not None:
            self._dialog.close()
            self._dialog = None

    def show_favorites(self) -> None:
        parent = self._context.get_main_widget()
        if parent is None:
            return
        if self._dialog is not None and self._dialog.isVisible():
            self._dialog.raise_()
            self._dialog.activateWindow()
            return
        self._dialog = FavoritesDialog(self, parent)
        self._dialog.show()

    def add_favorite(self, text: str) -> None:
        fav = self._store.add(text)
        if self._dialog is not None and self._dialog.isVisible():
            self._dialog.refresh()

    def _play_favorite(self, fav: dict) -> None:
        audio_path = fav.get("audio_path")
        if audio_path:
            p = Path(audio_path)
            if p.exists():
                self._context.play_audio(p)
                return
        self._synthesize_and_play(fav)

    def _synthesize_and_play(self, fav: dict) -> None:
        if self._synth_thread is not None and self._synth_thread.isRunning():
            return
        self._pending_fav_id = fav["id"]
        text = fav.get("text", "")
        self._synth_thread = TtsSynthesisThread(
            self._context._tts_client,
            text,
            "normal",
        )
        self._synth_thread.finished_audio.connect(self._on_synth_ready)
        self._synth_thread.failed.connect(self._on_synth_failed)
        self._synth_thread.start()

    def _on_synth_ready(self, audio_path: str) -> None:
        fav_id = self._pending_fav_id
        self._pending_fav_id = None
        self._synth_thread = None
        if fav_id is None:
            return
        dest = FAVORITES_AUDIO_DIR / f"{fav_id}.wav"
        try:
            src = Path(audio_path)
            if src.exists():
                src.replace(dest)
                self._store.update_audio_path(fav_id, str(dest))
                self._context.play_audio(dest)
        except Exception:
            pass
        if self._dialog is not None and self._dialog.isVisible():
            self._dialog.refresh()

    def _on_synth_failed(self, error_text: str) -> None:
        self._pending_fav_id = None
        self._synth_thread = None


class FavoritesDialog(QDialog):
    def __init__(self, extension: FavoritesExtension, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._extension = extension
        self.setWindowTitle("收藏夹")
        self.resize(480, 380)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("点击收藏语音即可播放", self))

        self.list_widget = QListWidget(self)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        self.play_btn = QPushButton("播放选中", self)
        self.play_btn.clicked.connect(self._play_selected)
        self.delete_btn = QPushButton("删除选中", self)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.refresh_btn = QPushButton("刷新", self)
        self.refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.refresh_btn)
        root.addLayout(btn_row)

        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        favorites = self._extension._store.load()
        for fav in favorites:
            text = fav.get("text", "")
            preview = text.replace("\n", " ").strip()[:80]
            has_audio = fav.get("audio_path") and Path(fav["audio_path"]).exists()
            suffix = " [已合成]" if has_audio else " [待合成]"
            item = QListWidgetItem(f"{preview}{suffix}")
            item.setData(Qt.UserRole, fav)
            item.setToolTip(text)
            self.list_widget.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        fav = item.data(Qt.UserRole)
        if fav is not None:
            self._extension._play_favorite(fav)

    def _play_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        fav = item.data(Qt.UserRole)
        if fav is not None:
            self._extension._play_favorite(fav)

    def _delete_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        fav = item.data(Qt.UserRole)
        if fav is None:
            return
        if QMessageBox.question(self, "确认", "确定删除这条收藏吗？") != QMessageBox.Yes:
            return
        fav_id = fav.get("id", "")
        self._extension._store.remove(fav_id)
        self.refresh()
