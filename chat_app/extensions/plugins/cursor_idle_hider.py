from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QDialog, QMenu

from chat_app.extensions.api import BaseExtension

_IDLE_TIMEOUT_MS = 5000


class _GlobalInputFilter(QObject):
    """全局输入拦截器：监听整个应用程序的鼠标和键盘动作"""

    def __init__(self, hider: CursorIdleHider):
        super().__init__()
        self._hider = hider

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        # 只要应用内发生了鼠标移动、点击或键盘输入，立刻重置隐藏倒计时
        if event.type() in (QEvent.MouseMove, QEvent.HoverMove, QEvent.MouseButtonPress, QEvent.KeyPress):
            self._hider.reset_timer()
        return False


class CursorIdleHider(BaseExtension):
    """鼠标闲置光标隐藏插件（智能空间感知版）。

    仅当鼠标在主窗口的非交互区域（立绘、背景）闲置 5 秒时隐藏。
    在设置弹窗、背景抽屉、音乐播放器、右键菜单上方闲置时，不起作用。
    """

    @property
    def name(self) -> str:
        return "CursorIdleHider"

    def on_start(self) -> None:
        self._is_hidden = False
        
        # 初始化定时器
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_idle_timeout)

        # 安装全局事件过滤器，自动捕获全应用的鼠标动作，无需主窗口手动传递
        self._filter = _GlobalInputFilter(self)
        QApplication.instance().installEventFilter(self._filter)

        self._timer.start(_IDLE_TIMEOUT_MS)

    def on_stop(self) -> None:
        self._timer.stop()
        try:
            self._timer.timeout.disconnect(self._on_idle_timeout)
        except (TypeError, RuntimeError):
            pass
        if hasattr(self, "_filter"):
            QApplication.instance().removeEventFilter(self._filter)
        self._restore_cursor()

    def reset_timer(self) -> None:
        """被全局事件触发：唤醒光标并重新计时"""
        self._restore_cursor()
        self._timer.stop()
        self._timer.start(_IDLE_TIMEOUT_MS)

    def on_mouse_moved(self) -> None:
        """兼容接口：如果旧代码里主窗口显式调用了这个方法，照常工作"""
        self.reset_timer()

    def _on_idle_timeout(self) -> None:
        # 时间到了，先判断能不能隐藏
        if self._should_hide_cursor():
            self._hide_cursor()
        else:
            # 如果鼠标停在播放器等特殊区域内（不该隐藏），我们开启一个极短的轮询。
            # 这样一旦鼠标离开特殊区域，依然能迅速进入隐藏流程。
            self._timer.start(500)

    def _should_hide_cursor(self) -> bool:
        """核心逻辑：判断当前位置和状态是否允许隐藏光标"""
        
        # 1. 状态判断：如果有激活的弹窗(如历史/设置)或菜单(如右键菜单、歌单)，绝对不隐藏
        if QApplication.activePopupWidget() is not None:
            return False
        if isinstance(QApplication.activeWindow(), (QDialog, QMenu)):
            return False

        # 2. 空间判断：获取鼠标正下方针尖碰到的那个控件
        widget_under_mouse = QApplication.widgetAt(QCursor.pos())
        if widget_under_mouse:
            current = widget_under_mouse
            # 向上遍历父控件，看看它是不是属于某些“免隐藏保护区”
            while current:
                obj_name = current.objectName()
                
                # 保护区 A：音乐播放器的任何部件（抽屉、触发区、列表）
                if obj_name in ("MusicPlayerDrawer", "MusicPlayerTrigger", "MusicPlayerPlaylist"):
                    return False
                    
                # 保护区 B：背景选择抽屉
                if type(current).__name__ == "BackgroundDrawer":
                    return False
                    
                current = current.parent()

        return True

    def _hide_cursor(self) -> None:
        if not self._is_hidden:
            QApplication.setOverrideCursor(Qt.BlankCursor)
            self._is_hidden = True

    def _restore_cursor(self) -> None:
        if self._is_hidden:
            # 安全退出：因为 overrideCursor 是压栈机制，我们要把它全部弹出来
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            self._is_hidden = False