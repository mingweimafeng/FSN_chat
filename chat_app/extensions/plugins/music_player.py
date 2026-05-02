from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QCursor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from chat_app.extensions.api import BaseExtension
from chat_app.config import MUSIC_DIR

# ================= 配置参数区 =================
_DRAWER_WIDTH = 550               # 播放器宽度（加宽以容纳音量和标题）
_DRAWER_HEIGHT = 100               # 播放器高度
_TRIGGER_ZONE_HEIGHT = 70         # 顶部触发区高度
_TRIGGER_DELAY_MS = 0             # 【优化】悬停触发延迟：0秒立刻滑出
_HIDE_DELAY_MS = 100              # 移开隐藏延迟
_PLAYLIST_MAX_VISIBLE_ITEMS = 8   # 歌单最大可见行数
_SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".flac")
# ==============================================


def _connect(signal: Any, slot) -> None:
    signal.connect(slot)


def _disconnect(signal: Any, slot) -> None:
    try:
        signal.disconnect(slot)
    except (TypeError, RuntimeError):
        pass


class _EventFilter(QObject):
    """内部事件过滤器，转发事件到 MusicPlayerExtension 的回调。"""

    def __init__(self, extension: MusicPlayerExtension) -> None:
        super().__init__()
        self._ext = extension

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        ext = self._ext

        # 【修复冲突】：在音乐播放器范围内有任何鼠标动作，强行唤醒被隐藏的光标
        if event.type() in (
            QEvent.Type.MouseMove,
            QEvent.Type.HoverMove,
            QEvent.Type.Enter,
            QEvent.Type.MouseButtonPress,
        ):
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        if obj is ext._parent_widget:
            if event.type() == QEvent.Type.Resize:
                ext._recenter()
            return False

        if obj is ext._trigger_zone:
            if event.type() == QEvent.Type.Enter:
                ext._trigger_timer.stop()
                ext._trigger_timer.start(_TRIGGER_DELAY_MS)
            return False

        if obj is ext._drawer:
            if event.type() == QEvent.Type.Enter:
                ext._hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                # 【修复痛点 1】：如果歌单菜单是打开的，不允许抽屉收回
                if ext._playlist_menu and ext._playlist_menu.isVisible():
                    pass
                else:
                    ext._hide_timer.start(_HIDE_DELAY_MS)
            return False

        if obj is ext._playlist_menu:
            if event.type() == QEvent.Type.Leave:
                ext._playlist_menu.setVisible(False)
                # 歌单关闭后，检查鼠标是否还在抽屉里，不在则开始收回倒计时
                drawer_rect = ext._drawer.rect()
                drawer_rect.moveTo(ext._drawer.mapToGlobal(QPoint(0, 0)))
                if not drawer_rect.contains(QCursor.pos()):
                    ext._hide_timer.start(_HIDE_DELAY_MS)
            elif event.type() == QEvent.Type.Enter:
                ext._hide_timer.stop()
            return False

        return super().eventFilter(obj, event)


class MusicPlayerExtension(BaseExtension):
    """音乐播放器插件。居中悬浮岛风格。"""

    @property
    def name(self) -> str:
        return "MusicPlayer"

    def __init__(self) -> None:
        super().__init__()
        self._parent_widget: Optional[QWidget] = None
        self._player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None
        self._playlist: list[Path] = []
        self._current_index: int = -1
        self._slider_dragging: bool = False

        self._drawer: Optional[QWidget] = None
        self._trigger_zone: Optional[QWidget] = None
        self._playlist_menu: Optional[QListWidget] = None
        self._slide_anim: Optional[QPropertyAnimation] = None
        self._hide_timer: Optional[QTimer] = None
        self._trigger_timer: Optional[QTimer] = None

        self._play_btn: Optional[QPushButton] = None
        self._prev_btn: Optional[QPushButton] = None
        self._next_btn: Optional[QPushButton] = None
        self._menu_btn: Optional[QPushButton] = None
        self._title_label: Optional[QLabel] = None

        self._progress_slider: Optional[QSlider] = None
        self._time_cur_label: Optional[QLabel] = None
        self._time_tot_label: Optional[QLabel] = None

        self._vol_slider: Optional[QSlider] = None
        self._drawer_content: Optional[QWidget] = None
        self._is_showing: bool = False
        self._event_filter: Optional[_EventFilter] = None

    def on_start(self) -> None:
        self._parent_widget = self._context.get_main_widget() if self._context else None
        if self._parent_widget is None:
            return

        self._scan_music()
        self._event_filter = _EventFilter(self)
        self._parent_widget.installEventFilter(self._event_filter)

        self._player = QMediaPlayer(self._parent_widget)
        self._audio_output = QAudioOutput(self._parent_widget)
        self._player.setAudioOutput(self._audio_output)
        
        # 默认音量 50%
        self._audio_output.setVolume(0.5)

        _connect(self._player.mediaStatusChanged, self._on_media_status_changed)
        _connect(self._player.positionChanged, self._on_position_changed)
        _connect(self._player.durationChanged, self._on_duration_changed)

        self._build_drawer(self._parent_widget)
        self._build_trigger_zone(self._parent_widget)
        self._build_playlist_menu(self._parent_widget)

        self._hide_timer = QTimer(self._drawer)
        self._hide_timer.setSingleShot(True)
        _connect(self._hide_timer.timeout, self._slide_up)

        self._trigger_timer = QTimer(self._drawer)
        self._trigger_timer.setSingleShot(True)
        _connect(self._trigger_timer.timeout, self._slide_down)

    def on_stop(self) -> None:
        if self._player:
            self._player.stop()
        self._hide_timer.stop() if self._hide_timer else None
        self._trigger_timer.stop() if self._trigger_timer else None
        self._slide_anim.stop() if self._slide_anim else None
        if self._playlist_menu:
            self._playlist_menu.deleteLater()
        if self._trigger_zone:
            self._trigger_zone.deleteLater()
        if self._drawer:
            self._drawer.deleteLater()

    def _scan_music(self) -> None:
        music_dir = MUSIC_DIR
        if not music_dir.exists():
            music_dir.mkdir(parents=True, exist_ok=True)
        entries: list[Path] = []
        for f in sorted(music_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS:
                entries.append(f)
        self._playlist = entries

    def _get_target_x(self) -> int:
        if not self._parent_widget:
            return 0
        return (self._parent_widget.width() - _DRAWER_WIDTH) // 2

    def _recenter(self) -> None:
        if not self._parent_widget or not self._drawer or not self._trigger_zone:
            return
        x = self._get_target_x()
        self._trigger_zone.setGeometry(x, 0, _DRAWER_WIDTH, _TRIGGER_ZONE_HEIGHT)
        current_y = self._drawer.y()
        self._drawer.setGeometry(x, current_y, _DRAWER_WIDTH, _DRAWER_HEIGHT)
        self._drawer_content.setGeometry(0, 0, _DRAWER_WIDTH, _DRAWER_HEIGHT)
        
        if self._slide_anim:
            if self._is_showing:
                self._slide_anim.setStartValue(QPoint(x, -_DRAWER_HEIGHT))
                self._slide_anim.setEndValue(QPoint(x, 0))
            else:
                self._slide_anim.setStartValue(QPoint(x, 0))
                self._slide_anim.setEndValue(QPoint(x, -_DRAWER_HEIGHT))

    def _build_drawer(self, parent: QWidget) -> None:
        x = self._get_target_x()
        
        self._drawer = QWidget(parent)
        self._drawer.setObjectName("MusicPlayerDrawer")
        self._drawer.setGeometry(x, 0, _DRAWER_WIDTH, _DRAWER_HEIGHT)
        self._drawer.setVisible(True)
        self._drawer.installEventFilter(self._event_filter)

        self._drawer_content = QWidget(self._drawer)
        self._drawer_content.setGeometry(0, 0, _DRAWER_WIDTH, _DRAWER_HEIGHT)

        # 整体水平布局
        main_layout = QHBoxLayout(self._drawer_content)
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(12)

        # --- 1. 左侧播放控制 ---
        self._prev_btn = QPushButton("⏮")
        self._play_btn = QPushButton("▶")
        self._next_btn = QPushButton("⏭")
        for btn in (self._prev_btn, self._play_btn, self._next_btn):
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        _connect(self._prev_btn.clicked, self._play_previous)
        _connect(self._play_btn.clicked, self._toggle_play)
        _connect(self._next_btn.clicked, self._play_next)

        main_layout.addWidget(self._prev_btn)
        main_layout.addWidget(self._play_btn)
        main_layout.addWidget(self._next_btn)

        # --- 2. 中间信息区 (歌名 + 进度条) ---
        center_layout = QVBoxLayout()
        center_layout.setSpacing(2)
        
        self._title_label = QLabel("暂无播放")
        self._title_label.setObjectName("MusicTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(6)
        self._time_cur_label = QLabel("00:00")
        self._time_tot_label = QLabel("00:00")
        self._time_cur_label.setObjectName("TimeLabel")
        self._time_tot_label.setObjectName("TimeLabel")
        
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setRange(0, 0)
        self._progress_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        _connect(self._progress_slider.sliderPressed, self._on_slider_pressed)
        _connect(self._progress_slider.sliderReleased, self._on_slider_released)
        _connect(self._progress_slider.sliderMoved, self._on_slider_moved)

        progress_layout.addWidget(self._time_cur_label)
        progress_layout.addWidget(self._progress_slider, 1)
        progress_layout.addWidget(self._time_tot_label)
        
        center_layout.addWidget(self._title_label)
        center_layout.addLayout(progress_layout)
        main_layout.addLayout(center_layout, 1)

        # --- 3. 右侧音量与菜单 ---
        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("color: white; font-size: 16px;")
        
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setObjectName("VolumeSlider")
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(50)
        self._vol_slider.setFixedWidth(60)
        self._vol_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        _connect(self._vol_slider.valueChanged, self._on_volume_changed)

        self._menu_btn = QPushButton("☰")
        self._menu_btn.setFixedSize(36, 36)
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        _connect(self._menu_btn.clicked, self._toggle_playlist)

        main_layout.addWidget(vol_icon)
        main_layout.addWidget(self._vol_slider)
        main_layout.addSpacing(4)
        main_layout.addWidget(self._menu_btn)

        # ================= UI 颜值美化 (QSS) =================
        self._drawer.setStyleSheet("""
            #MusicPlayerDrawer {
                background-color: rgba(25, 25, 35, 210);
                border: 1px solid rgba(255, 255, 255, 20);
                border-top: none;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 15);
                color: white;
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 18px; /* 正圆形 */
                font-family: "Segoe UI Symbol", "Apple Color Emoji";
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 40);
                border: 1px solid rgba(255, 255, 255, 60);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 10);
            }
            #MusicTitle {
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            #TimeLabel {
                color: rgba(255, 255, 255, 150); 
                font-size: 11px;
                font-family: Consolas, monospace;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 30);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px;
                height: 12px;
                margin: -4px 0;
                background: white;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #88C0D0;
                transform: scale(1.2);
            }
            QSlider::sub-page:horizontal {
                background: #81A1C1;
                border-radius: 2px;
            }
            #VolumeSlider::sub-page:horizontal {
                background: rgba(255, 255, 255, 180);
            }
        """)

        # 【优化痛点】：更短的时间，更顺滑的阻尼曲线
        self._slide_anim = QPropertyAnimation(self._drawer, b"pos")
        self._slide_anim.setDuration(150)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._slide_anim.setStartValue(self._drawer.pos())
        self._slide_anim.setEndValue(self._drawer.pos())

        self._drawer.move(x, -_DRAWER_HEIGHT)

    def _build_trigger_zone(self, parent: QWidget) -> None:
        x = self._get_target_x()
        self._trigger_zone = QWidget(parent)
        self._trigger_zone.setObjectName("MusicPlayerTrigger")
        self._trigger_zone.setGeometry(x, 0, _DRAWER_WIDTH, _TRIGGER_ZONE_HEIGHT)
        self._trigger_zone.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._trigger_zone.setStyleSheet("background-color: transparent;")
        self._trigger_zone.installEventFilter(self._event_filter)
        self._trigger_zone.setVisible(True)
        self._trigger_zone.raise_()

    def _build_playlist_menu(self, parent: QWidget) -> None:
        self._playlist_menu = QListWidget(parent)
        self._playlist_menu.setObjectName("MusicPlayerPlaylist")
        self._playlist_menu.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self._playlist_menu.setStyleSheet("""
            QListWidget {
                background-color: rgba(30, 30, 40, 240);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 8px;
                color: white;
                font-size: 13px;
                padding: 6px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 30);
            }
            QListWidget::item:selected {
                background-color: rgba(129, 161, 193, 150);
                font-weight: bold;
            }
        """)
        _connect(self._playlist_menu.itemDoubleClicked, self._on_playlist_item_activated)
        self._playlist_menu.setVisible(False)
        self._playlist_menu.installEventFilter(self._event_filter)

        for song in self._playlist:
            item = QListWidgetItem(song.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(song))
            self._playlist_menu.addItem(item)

    def _slide_down(self) -> None:
        if self._is_showing:
            return
        if self._parent_widget and hasattr(self._parent_widget, "_set_active_overlay"):
            self._parent_widget._set_active_overlay("music")
        self._is_showing = True
        self._slide_anim.stop()
        self._drawer.raise_()
        
        x = self._get_target_x()
        self._slide_anim.setStartValue(self._drawer.pos())
        self._slide_anim.setEndValue(QPoint(x, 0))
        
        try:
            _disconnect(self._slide_anim.finished, self._on_slide_up_finished)
        except (TypeError, RuntimeError):
            pass
            
        self._slide_anim.start()

    def _slide_up(self) -> None:
        if not self._is_showing:
            return
        self._is_showing = False
        if self._parent_widget and hasattr(self._parent_widget, "_set_active_overlay"):
            self._parent_widget._set_active_overlay(None)
        self._slide_anim.stop()
        
        x = self._get_target_x()
        target_y = -_DRAWER_HEIGHT
        self._slide_anim.setStartValue(self._drawer.pos())
        self._slide_anim.setEndValue(QPoint(x, target_y))
        
        try:
            _disconnect(self._slide_anim.finished, self._on_slide_up_finished)
        except (TypeError, RuntimeError):
            pass
        _connect(self._slide_anim.finished, self._on_slide_up_finished)

        self._slide_anim.start()

    def _on_slide_up_finished(self) -> None:
        self._drawer.lower()

    def _on_volume_changed(self, value: int) -> None:
        if self._audio_output:
            self._audio_output.setVolume(value / 100.0 * 0.6)

    def _toggle_play(self) -> None:
        if self._player is None:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play_btn.setText("▶")
        else:
            if self._player.source().isEmpty() and self._playlist:
                self._current_index = 0
                self._load_current()
            self._player.play()
            self._play_btn.setText("⏸")

    def _play_next(self) -> None:
        if not self._playlist:
            return
        self._current_index = (self._current_index + 1) % len(self._playlist)
        self._load_current()
        self._player.play()
        self._play_btn.setText("⏸")

    def _play_previous(self) -> None:
        if not self._playlist:
            return
        self._current_index = (self._current_index - 1) % len(self._playlist)
        self._load_current()
        self._player.play()
        self._play_btn.setText("⏸")

    def _load_current(self) -> None:
        if self._player is None or self._current_index < 0 or self._current_index >= len(self._playlist):
            return
        path = self._playlist[self._current_index]
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        
        # 更新显示名称
        self._title_label.setText(path.stem)
        
        self._update_playlist_selection()
        self._progress_slider.setRange(0, 0)
        self._time_cur_label.setText("00:00")
        self._time_tot_label.setText("00:00")

    def _on_media_status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._play_next()

    def _on_position_changed(self, pos_ms: int) -> None:
        if self._slider_dragging or self._player is None:
            return
        total = self._player.duration()
        self._progress_slider.blockSignals(True)
        self._progress_slider.setRange(0, total if total > 0 else 0)
        self._progress_slider.setValue(pos_ms)
        self._progress_slider.blockSignals(False)
        self._update_time_labels(pos_ms, total)

    def _on_duration_changed(self, duration: int) -> None:
        if self._player:
            self._progress_slider.setRange(0, duration if duration > 0 else 0)

    def _on_slider_pressed(self) -> None:
        self._slider_dragging = True

    def _on_slider_released(self) -> None:
        self._slider_dragging = False
        if self._player:
            self._player.setPosition(self._progress_slider.value())

    def _on_slider_moved(self, pos: int) -> None:
        total = self._player.duration() if self._player else 0
        self._update_time_labels(pos, total)

    def _update_time_labels(self, pos_ms: int, total_ms: int) -> None:
        def fmt(ms: int) -> str:
            s = max(0, ms // 1000)
            m, s = divmod(s, 60)
            return f"{m:02d}:{s:02d}"
        self._time_cur_label.setText(fmt(pos_ms))
        self._time_tot_label.setText(fmt(total_ms))

    def _toggle_playlist(self) -> None:
        if self._playlist_menu is None:
            return
        if self._playlist_menu.isVisible():
            self._playlist_menu.setVisible(False)
            return
            
        # 准确定位歌单菜单到底部
        btn_global_pos = self._menu_btn.mapToGlobal(QPoint(0, self._menu_btn.height()))
        list_width = 300
        item_height = 36
        visible = min(len(self._playlist), _PLAYLIST_MAX_VISIBLE_ITEMS)
        list_height = visible * item_height + 12
        
        self._playlist_menu.setGeometry(
            btn_global_pos.x() - list_width + self._menu_btn.width(), 
            btn_global_pos.y() + 10, # 稍微往下偏移一点点
            list_width, 
            list_height
        )
        self._playlist_menu.setVisible(True)
        self._playlist_menu.raise_()

    def _on_playlist_item_activated(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.ItemDataRole.UserRole)
        for i, p in enumerate(self._playlist):
            if str(p) == path_str:
                self._current_index = i
                self._load_current()
                self._player.play()
                self._play_btn.setText("⏸")
                break
        self._playlist_menu.setVisible(False)

    def _update_playlist_selection(self) -> None:
        if self._playlist_menu is None:
            return
        for i in range(self._playlist_menu.count()):
            item = self._playlist_menu.item(i)
            path_str = item.data(Qt.ItemDataRole.UserRole)
            if self._current_index >= 0 and self._current_index < len(self._playlist):
                if str(self._playlist[self._current_index]) == path_str:
                    self._playlist_menu.setCurrentItem(item)
                    return
