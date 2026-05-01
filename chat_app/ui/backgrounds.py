from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QRect, QPropertyAnimation, Qt, Signal, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QScrollArea, QSizePolicy, QVBoxLayout, QWidget


class BackgroundCard(QWidget):
    clicked = Signal(object)

    def __init__(self, image_path: Path, selected: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image_path = image_path
        self.image_name = image_path.stem
        self._pixmap = QPixmap(str(image_path))
        self._selected = selected
        self._hover_scale = 1.0

        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(180)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(180)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_value_changed)

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.update()

    def enterEvent(self, event) -> None:
        self._animate_hover(1.05)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.image_path)
            event.accept()
            return
        super().mousePressEvent(event)

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_scale)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def _on_hover_value_changed(self, value) -> None:
        self._hover_scale = float(value)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        outer = self.rect().adjusted(8, 8, -8, -8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 12))
        painter.drawRoundedRect(outer, 10, 10)

        image_area = outer.adjusted(10, 10, -10, -36)
        image_height = int(image_area.width() * 9 / 16)
        image_height = min(image_height, image_area.height())
        image_top = image_area.top() + max(0, (image_area.height() - image_height) // 2)
        image_rect = image_area
        image_rect.setTop(image_top)
        image_rect.setHeight(image_height)

        radius = 10.0
        clip = QPainterPath()
        clip.addRoundedRect(image_rect, radius, radius)

        painter.save()
        painter.setClipPath(clip)
        if self._pixmap.isNull():
            painter.fillRect(image_rect, QColor(25, 25, 25, 210))
        else:
            scaled_w = image_rect.width() * self._hover_scale
            scaled_h = image_rect.height() * self._hover_scale
            dx = (scaled_w - image_rect.width()) / 2.0
            dy = (scaled_h - image_rect.height()) / 2.0
            draw_rect = image_rect.adjusted(int(-dx), int(-dy), int(dx), int(dy))
            scaled = self._pixmap.scaled(draw_rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            src_x = max(0, (scaled.width() - draw_rect.width()) // 2)
            src_y = max(0, (scaled.height() - draw_rect.height()) // 2)
            src_rect = QRect(src_x, src_y, draw_rect.width(), draw_rect.height())
            painter.drawPixmap(draw_rect, scaled, src_rect)
        painter.restore()

        if self._selected:
            border_pen = QPen(QColor(78, 180, 255), 3)
            border_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(border_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(image_rect, radius, radius)

        text_rect = outer.adjusted(10, image_rect.bottom() + 6, -10, -8)
        font = QFont(self.font())
        font.setPointSize(max(9, font.pointSize()))
        painter.setFont(font)
        painter.setPen(QColor(242, 244, 255, 230))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.image_name)


class BackgroundDrawer(QWidget):
    background_selected = Signal(object)
    pointer_left = Signal()

    def __init__(self, backgrounds: list[Path], current_background: Path | None, parent: QWidget) -> None:
        super().__init__(parent)
        self._drawer_width = 360
        self._backgrounds = backgrounds
        self._cards_by_path: dict[str, BackgroundCard] = {}
        self._is_open = False

        self.setMouseTracking(True)
        self.setFixedWidth(self._drawer_width)
        self.setStyleSheet(
            """
            QWidget#BackgroundDrawer {
                background-color: rgba(12, 12, 16, 208);
                border-left: 1px solid rgba(255, 255, 255, 40);
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 7px;
                margin: 10px 2px 10px 0;
            }
            QScrollBar::handle:vertical {
                min-height: 30px;
                border-radius: 3px;
                background: rgba(235, 240, 255, 135);
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(245, 247, 255, 170);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            """
        )
        self.setObjectName("BackgroundDrawer")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 16, 8, 14)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.container = QWidget(self.scroll_area)
        self.container.setMouseTracking(True)
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(4, 2, 8, 4)
        self.list_layout.setSpacing(10)

        self.scroll_area.setWidget(self.container)
        root.addWidget(self.scroll_area)

        for bg in backgrounds:
            card = BackgroundCard(bg, selected=current_background == bg, parent=self.container)
            card.clicked.connect(self._on_card_clicked)
            self.list_layout.addWidget(card)
            self._cards_by_path[str(bg)] = card

        self.list_layout.addStretch(1)

        self._pos_anim = QPropertyAnimation(self, b"pos", self)
        self._pos_anim.setDuration(300)
        self._pos_anim.setEasingCurve(QEasingCurve.OutExpo)
        self._pos_anim.finished.connect(self._on_anim_finished)

        self.hide()

    @property
    def drawer_width(self) -> int:
        return self._drawer_width

    @property
    def is_open(self) -> bool:
        return self._is_open

    def update_geometry(self, parent_size) -> None:
        self.setFixedHeight(parent_size.height())
        open_x = parent_size.width() - self._drawer_width
        hidden_x = parent_size.width()
        current_x = open_x if self._is_open else hidden_x
        self.move(current_x, 0)

    def open_drawer(self) -> None:
        if self._is_open and self.isVisible():
            return
        self._is_open = True
        self._animate_to(self.parentWidget().width() - self._drawer_width)

    def close_drawer(self) -> None:
        if not self._is_open and not self.isVisible():
            return
        self._is_open = False
        self._animate_to(self.parentWidget().width())

    def contains_global_pos(self, global_pos) -> bool:
        local = self.mapFromGlobal(global_pos)
        return self.rect().contains(local)

    def set_current_background(self, path: Path | None) -> None:
        selected_key = str(path) if path is not None else ""
        for key, card in self._cards_by_path.items():
            card.set_selected(key == selected_key)

    def leaveEvent(self, event) -> None:
        self.pointer_left.emit()
        super().leaveEvent(event)

    def _animate_to(self, target_x: int) -> None:
        self.show()
        self.raise_()
        self._pos_anim.stop()
        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPoint(target_x, 0))
        self._pos_anim.start()

    def _on_anim_finished(self) -> None:
        if not self._is_open:
            self.hide()

    def _on_card_clicked(self, path_obj: object) -> None:
        path = Path(path_obj)
        self.set_current_background(path)
        self.background_selected.emit(path)