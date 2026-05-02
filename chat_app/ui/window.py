from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from chat_app.audio.audio_manager import AudioManager
from chat_app.audio.tts_client import GenieTTSClient, TtsSynthesisThread, TtsWarmupThread
from chat_app.audio.tts_pipeline import TtsPipelineManager
from chat_app.config import (
    ANIMATION_TICK_MS,
    CHARACTER_DIR,
    CHARACTER_EMOTIONS,
    CURSOR_BLINK_INTERVAL_MS,
    FONT_SIZE,
    FULLSCREEN_BASE_HEIGHT,
    FULLSCREEN_BASE_WIDTH,
    FULLSCREEN_MAX_SCALE,
    STATE_TO_ASSET,
    TYPEWRITER_INTERVAL_MS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from chat_app.core.app_context import AppContext
from chat_app.core.state_machine import ChatStateMachine
from chat_app.core.window_runtime import VirtualTimer
from chat_app.data.assets import find_backgrounds, load_character_images
from chat_app.data.history_store import ChatHistoryStore, HistoryRecord
from chat_app.data.settings_store import AppSettings, SettingsStore, MemoryState
from chat_app.extensions import ExtensionContext, ExtensionManager
from chat_app.services.api_client import ChatRequestThread, MemorySummaryThread
from chat_app.ui.backgrounds import BackgroundDrawer
from chat_app.ui.dialogs import HistoryDialog, SettingsDialog
from chat_app.ui.animation_mixin import AnimationMixin
from chat_app.ui.background_mixin import BackgroundMixin
from chat_app.ui.character_mixin import CharacterMixin
from chat_app.ui.text_render_mixin import TextRenderMixin
from chat_app.ui.audio_mixin import AudioMixin
from chat_app.ui.dialogue_mixin import DialogueMixin
from chat_app.ui.memory_mixin import MemoryMixin


class BackgroundWindow(
    DialogueMixin,
    BackgroundMixin,
    CharacterMixin,
    TextRenderMixin,
    AnimationMixin,
    AudioMixin,
    MemoryMixin,
    QWidget,
):
    ready = Signal()

    def __init__(self, background_dir: Path) -> None:
        super().__init__()
        self.background_dir = background_dir
        self._init_basic_state()
        self._init_ui_state()
        self._init_character_state()
        self.context = self._build_context()
        self._init_timers()
        self._connect_signals()
        self._setup_window()

    def _init_basic_state(self) -> None:
        self.backgrounds = find_backgrounds(self.background_dir)
        self.current_background: Path | None = None
        self.current_pixmap = QPixmap()
        self.scaled_background_pixmap = QPixmap()
        self.overlay_enabled = True
        self.chat_entries: list[str] = []
        self.cached_chat_lines: list[str] = []
        self.wrap_cache: dict[tuple[str, int], list[str]] = {}
        self.text_pixmap_cache: dict[str, QPixmap] = {}
        self._line_runs_dirty = True
        self._cursor_rect_dirty = True
        self._render_line_runs_cache: list[list[tuple[str, float]]] = [[("", 1.0)]]
        self._all_draw_lines_cache: list[str] = [""]
        self._cursor_rect_cache = QRectF()
        self.current_input = ""
        self.preedit_text = ""
        self.current_reply_full = ""
        self.current_reply_visible = ""
        self.pending_reply_segments: list[dict[str, str]] = []
        self.current_dialogue_page_text = ""
        self.current_dialogue_base_line_count = 0
        self.waiting_for_reply = False
        self.cursor_visible = True
        self.reply_output_active = False
        self.request_thread: ChatRequestThread | None = None
        self.memory_summary_thread: MemorySummaryThread | None = None
        self.is_outputting_narration = False
        self.tts_client = GenieTTSClient()
        self.tts_warmup_thread: TtsWarmupThread | None = None
        self.current_segment_requires_transition = False
        self.current_segment_is_followup = False
        self.current_dialogue_segment_index = 0
        self.pending_page_turn_before_next_segment = False

        self.is_fullscreen = False
        self.scale_factor = 1.0
        self._saved_geometry = None
        self._saved_flags = None

    def _init_ui_state(self) -> None:
        self.reply_output_started = False
        self.text_demote_target_alpha = 0.5
        self.text_demote_duration_ms = 350.0
        self.user_entry_alpha = 1.0
        self.latest_user_line_count = 0
        self.dialogue_history_stable_len = 0
        self.dialogue_demoting_end = 0
        self.dialogue_demoting_alpha = self.text_demote_target_alpha
        self.user_fade_start_alpha = 1.0
        self.dialogue_fade_start_alpha = self.text_demote_target_alpha
        self.text_fade_progress = 1.0
        self.pending_idle_after_text_demote = False
        self.text_font = QFont()
        self.text_font.setPointSize(FONT_SIZE)
        self.previous_character_pixmap = QPixmap()
        self.next_character_pixmap = QPixmap()
        self.text_layer_alpha = 1.0
        self.overlay_alpha = 1.0
        self.ui_visibility_factor = 1.0
        self._background_drawer_active = False
        self.drawer_trigger_margin_px = 200
        self.drawer_open_delay_ms = 80
        self.portrait_blend_progress = 1.0
        self.animation_phase = "idle"
        self.pending_resume_action = None

    def _init_character_state(self) -> None:
        self.character_images = load_character_images(CHARACTER_DIR)
        self.character_indices = {
            emotion: {state: -1 for state in STATE_TO_ASSET.values()}
            for emotion in CHARACTER_EMOTIONS
        }
        self.character_emotion = "normal"
        self.character_state = "idle"
        self.character_pixmap = QPixmap()
        self.character_draw_cache: dict[int, QRectF] = {}

    def _build_context(self) -> AppContext:
        self.chat_state = ChatStateMachine(self)
        self.chat_state.flags_changed.connect(self._apply_state_flags)

        self.history_store = ChatHistoryStore()
        self.history_records: list[HistoryRecord] = self.history_store.load_records()
        self.last_user_message = ""

        self.settings_store = SettingsStore()
        self.settings: AppSettings = self.settings_store.load()
        self.memory_state: MemoryState = self.settings_store.load_memory_state()

        self.tts_pipeline = TtsPipelineManager(self.tts_client)
        self.audio_manager = AudioManager(self)
        self.audio_manager.playback_finished.connect(self._on_audio_manager_finished)
        self.audio_manager.playback_failed.connect(self._on_audio_manager_failed)
        self._setup_audio_connections()

        ext_context = ExtensionContext(
            tts_pipeline=self.tts_pipeline,
            audio_manager=self.audio_manager,
            chat_state=self.chat_state,
            main_widget=self,
            emotion_changer=self.set_character_emotion,
        )
        self.extension_manager = ExtensionManager(ext_context, "chat_app.extensions.plugins")
        ext_result = self.extension_manager.load_all_extensions()
        if ext_result.loaded or ext_result.failed:
            print(
                f"[Extension] loaded={ext_result.loaded}, failed={ext_result.failed}",
                flush=True,
            )
        if self.settings.api_key:
            os.environ["DEEPSEEK_API_KEY"] = self.settings.api_key

        return AppContext(
            chat_state=self.chat_state,
            tts_client=self.tts_client,
            tts_pipeline=self.tts_pipeline,
            audio_manager=self.audio_manager,
            settings_store=self.settings_store,
            history_store=self.history_store,
            extension_manager=self.extension_manager,
        )

    def _init_timers(self) -> None:
        self.narration_wait_timer = QTimer(self)
        self.narration_wait_timer.setSingleShot(True)
        self.narration_wait_timer.timeout.connect(self.on_narration_wait_elapsed)

        self.cursor_timer = VirtualTimer(CURSOR_BLINK_INTERVAL_MS)
        self.typewriter_timer = VirtualTimer(TYPEWRITER_INTERVAL_MS)

        self.page_turn_timer = QTimer(self)
        self.page_turn_timer.setSingleShot(True)
        self.page_turn_timer.timeout.connect(self.on_segment_gap_elapsed)

        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self.return_to_idle)

        self.emotion_reset_timer = QTimer(self)
        self.emotion_reset_timer.setSingleShot(True)
        self.emotion_reset_timer.timeout.connect(self.reset_emotion_to_normal)

        self.animation_timer = VirtualTimer(ANIMATION_TICK_MS)
        self.text_fade_timer = VirtualTimer(ANIMATION_TICK_MS)

        self.render_timer = QTimer(self)
        self.render_timer.setInterval(ANIMATION_TICK_MS)
        self.render_timer.timeout.connect(self._on_render_tick)

        self.drawer_trigger_timer = QTimer(self)
        self.drawer_trigger_timer.setSingleShot(True)
        self.drawer_trigger_timer.timeout.connect(self._open_background_drawer_from_trigger)

    def _connect_signals(self) -> None:
        pass

    def _setup_window(self) -> None:
        self.setWindowTitle("chat with Saber")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.background_drawer = BackgroundDrawer(
            self.backgrounds, self.current_background, self
        )
        self.background_drawer.background_selected.connect(
            self._on_drawer_background_selected
        )
        self.background_drawer._pos_anim.valueChanged.connect(
            self._on_drawer_pos_changed
        )
        self.background_drawer._pos_anim.finished.connect(
            self._on_drawer_anim_finished
        )
        self.background_drawer.move(self.width(), 0)
        if self.backgrounds:
            saved = self.resolve_saved_background(self.settings.current_background)
            self.set_background(saved or self.backgrounds[0], persist=False)
        self.background_drawer.set_current_background(self.current_background)

        self.refresh_character_portrait()
        self.start_tts_warmup()
        if self.tts_warmup_thread is not None:
            self.tts_warmup_thread.warmed_up.connect(self._on_warmup_done)
            self.tts_warmup_thread.failed.connect(self._on_warmup_done)
            self.tts_warmup_thread.start()
        self._apply_state_flags()
        self.cursor_timer.start()
        self._refresh_render_timer_running()
        self.cleanup_all_temp_audio()
        self._active_overlay: str | None = None

    def _set_active_overlay(self, name: str | None) -> None:
        if name == self._active_overlay:
            return
        if name == "background":
            self._close_music_player()
        elif name == "music":
            self._close_background_drawer()
        self._active_overlay = name

    def _close_music_player(self) -> None:
        if not hasattr(self, "extension_manager"):
            return
        for ext in self.extension_manager.active_extensions:
            if hasattr(ext, "_is_showing") and ext._is_showing:
                ext._slide_up()

    def _close_background_drawer(self) -> None:
        if hasattr(self, "background_drawer") and self.background_drawer.is_open:
            self.background_drawer.close_drawer()

    def _on_warmup_done(self, *args) -> None:
        self.ready.emit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(100, self._refresh_ime)

    def _apply_state_flags(self) -> None:
        self.waiting_for_reply = self.chat_state.waiting_for_reply
        self.reply_output_active = self.chat_state.reply_output_active
        self.is_outputting_narration = self.chat_state.is_outputting_narration
        self.waiting_audio_before_next_segment = (
            self.chat_state.waiting_audio_before_next_segment
        )
        self._mark_layout_dirty()

    def resizeEvent(self, event) -> None:
        self.refresh_scaled_background()
        self.character_draw_cache.clear()
        self.wrap_cache.clear()
        self.rebuild_cached_chat_lines()
        self._mark_layout_dirty()
        if hasattr(self, "background_drawer"):
            self.background_drawer.update_geometry(self.size())
            self._sync_ui_visibility_with_drawer()
        if self.current_dialogue_page_text:
            self.current_dialogue_base_line_count = len(
                self.wrap_text(self.current_dialogue_page_text)
            )
        else:
            self.current_dialogue_base_line_count = 0
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:
        self.chat_state.begin_closing()
        self._apply_state_flags()
        self.render_timer.stop()
        self.narration_wait_timer.stop()
        self.drawer_trigger_timer.stop()
        self.page_turn_timer.stop()
        self.idle_timer.stop()
        self.emotion_reset_timer.stop()
        self.audio_manager.stop()
        if hasattr(self, "extension_manager"):
            self.extension_manager.unload_all()
        if self.request_thread is not None and self.request_thread.isRunning():
            self.request_thread.stop()
            self.request_thread.wait(2000)
        if hasattr(self, "tts_pipeline") and self.tts_pipeline._tts_thread is not None and self.tts_pipeline._tts_thread.isRunning():
            self.tts_pipeline._tts_thread.stop()
            self.tts_pipeline._tts_thread.wait(2000)
        if self.tts_warmup_thread is not None and self.tts_warmup_thread.isRunning():
            self.tts_warmup_thread.stop()
            self.tts_warmup_thread.wait(2000)
        if (
            self.memory_summary_thread is not None
            and self.memory_summary_thread.isRunning()
        ):
            self.memory_summary_thread.stop()
            self.memory_summary_thread.wait(2000)
        self.tts_client.shutdown()
        super().closeEvent(event)

    def toggle_fullscreen(self) -> None:
        if self.is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self) -> None:
        self._saved_geometry = self.geometry()
        self._saved_flags = self.windowFlags()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center())) or QApplication.primaryScreen()
        screen_geom = screen.availableGeometry()
        self.setGeometry(screen_geom)
        self.is_fullscreen = True
        self._update_scale_factor()
        self.showFullScreen()
        if hasattr(self, "fullscreen_action"):
            self.fullscreen_action.setChecked(True)

    def _exit_fullscreen(self) -> None:
        restore_flags = self._saved_flags if self._saved_flags else (
            Qt.Window |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinMaxButtonsHint
        )
        self.setWindowFlags(restore_flags)
        self.show()
        if self._saved_geometry:
            self.setGeometry(self._saved_geometry)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._update_scale_factor()
        self.is_fullscreen = False
        if hasattr(self, "fullscreen_action"):
            self.fullscreen_action.setChecked(False)

    def _update_scale_factor(self) -> None:
        if self.is_fullscreen:
            sw = self.width()
            sh = self.height()
            self.scale_factor = min(sw / FULLSCREEN_BASE_WIDTH, sh / FULLSCREEN_BASE_HEIGHT)
            self.scale_factor = min(self.scale_factor, FULLSCREEN_MAX_SCALE)
        else:
            self.scale_factor = 1.0
        self.character_draw_cache.clear()
        self.wrap_cache.clear()
        self.text_pixmap_cache.clear()
        self._mark_layout_dirty()
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_F11 or (event.key() == Qt.Key_Escape and self.is_fullscreen):
            self.toggle_fullscreen()
            event.accept()
            return
        super().keyPressEvent(event)

    @property
    def fullscreen_content_rect(self) -> QRect:
        if not self.is_fullscreen:
            return QRect(0, 0, self.width(), self.height())
        base_w = int(FULLSCREEN_BASE_WIDTH * self.scale_factor)
        base_h = int(FULLSCREEN_BASE_HEIGHT * self.scale_factor)
        return QRect(
            (self.width() - base_w) // 2,
            (self.height() - base_h) // 2,
            base_w,
            base_h,
        )
