from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chat_app.config import DEFAULT_ROLE_PROMPT, DEFAULT_USER_PROFILE_PROMPT, PROVIDERS
from chat_app.data.favorites_store import FavoritesStore
from chat_app.data.history_store import ChatHistoryStore, HistoryRecord
from chat_app.data.settings_store import AppSettings, SettingsStore


_DIALOG_STYLE = """
QWidget#framelessDialog {
    background: #0a0a14;
    border: 1px solid #2a2a3e;
}
QLabel {
    color: #c8c8d4;
    font-size: 13px;
    padding: 2px 0;
}
QLabel[heading="true"] {
    color: #e8e8f0;
    font-size: 15px;
    font-weight: bold;
    padding: 8px 0 4px 0;
}
QPushButton {
    background: #1e1e32;
    color: #c8c8d4;
    border: 1px solid #3a3a4e;
    border-radius: 4px;
    padding: 6px 18px;
    font-size: 13px;
    min-height: 24px;
}
QPushButton:hover {
    background: #2a2a42;
    border-color: #c8a86e;
    color: #e8e8f0;
}
QPushButton:pressed {
    background: #c8a86e;
    color: #0a0a14;
}
QLineEdit {
    background: #141420;
    color: #e8e8f0;
    border: 1px solid #3a3a4e;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 20px;
}
QLineEdit:focus {
    border-color: #c8a86e;
}
QPlainTextEdit {
    background: #141420;
    color: #e8e8f0;
    border: 1px solid #3a3a4e;
    border-radius: 4px;
    padding: 6px;
    font-size: 13px;
    selection-background-color: #c8a86e;
    selection-color: #0a0a14;
}
QPlainTextEdit:focus {
    border-color: #c8a86e;
}
QComboBox {
    background: #141420;
    color: #e8e8f0;
    border: 1px solid #3a3a4e;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #c8a86e;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid #3a3a4e;
}
QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: #1a1a2e;
    color: #c8c8d4;
    border: 1px solid #3a3a4e;
    selection-background-color: #2a2a42;
    selection-color: #e8e8f0;
    outline: none;
}
QTreeWidget {
    background: #0e0e1c;
    color: #c8c8d4;
    border: 1px solid #2a2a3e;
    border-radius: 4px;
    font-size: 13px;
    outline: none;
}
QTreeWidget::item {
    padding: 4px 2px;
    border-bottom: 1px solid #1a1a2e;
}
QTreeWidget::item:selected {
    background: #2a2a42;
    color: #e8e8f0;
    border-color: #c8a86e;
}
QTreeWidget::item:hover {
    background: #1e1e32;
}
QTreeWidget QHeaderView::section {
    background: #141428;
    color: #8888a0;
    border: none;
    border-bottom: 1px solid #2a2a3e;
    padding: 6px 4px;
    font-size: 12px;
}
QSplitter::handle {
    background: #2a2a3e;
    width: 1px;
}
QScrollBar:vertical {
    background: #0e0e1c;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a2a42;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #3a3a52;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #0e0e1c;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #2a2a42;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #3a3a52;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""


class _FramelessDialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setObjectName("framelessDialog")
        self.setStyleSheet(_DIALOG_STYLE)
        self._title_bar = QWidget(self)
        self._title_bar.setObjectName("titleBar")
        self._title_bar.setStyleSheet("#titleBar { background: #121220; border-bottom: 1px solid #2a2a3e; }")
        tb = QHBoxLayout(self._title_bar)
        tb.setContentsMargins(12, 6, 6, 6)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #e8e8f0; font-size: 15px; font-weight: bold;")
        tb.addWidget(title_label)
        tb.addStretch(1)
        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #666680; border: none; font-size: 15px; border-radius: 4px; }"
            "QPushButton:hover { background: #c0392b; color: white; }"
        )
        close_btn.clicked.connect(self.close)
        tb.addWidget(close_btn)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def moveEvent(self, event):
        if self.parent():
            pr = self.parent().geometry()
            self.move(pr.x() + (pr.width() - self.width()) // 2,
                      pr.y() + (pr.height() - self.height()) // 2)
        event.ignore()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            pr = self.parent().geometry()
            self.move(pr.x() + (pr.width() - self.width()) // 2,
                      pr.y() + (pr.height() - self.height()) // 2)


class HistoryDialog(_FramelessDialog):
    def __init__(
        self,
        store: ChatHistoryStore,
        settings_store: SettingsStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("历史记录", parent)
        self.store = store
        self.settings_store = settings_store or SettingsStore()
        self.records: list[HistoryRecord] = []

        self._fav_store = FavoritesStore()

        self.resize(820, 560)

        root_margin = QVBoxLayout(self)
        root_margin.setContentsMargins(0, 0, 0, 0)
        root_margin.addWidget(self._title_bar)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 16)
        content_layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal, content)

        self.tree = QTreeWidget(content)
        self.tree.setHeaderLabels(["分组/时间", "用户输入", "角色回复"])
        self.tree.setAlternatingRowColors(False)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setMinimumSectionSize(120)

        right_panel = QWidget(content)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        summary_label = QLabel("记忆摘要（可编辑）")
        summary_label.setProperty("heading", True)
        right_layout.addWidget(summary_label)
        self.summary_edit = QPlainTextEdit(right_panel)
        self.summary_edit.setPlaceholderText("这里显示用于长期记忆的摘要，可在此修改并保存。")
        self.summary_edit.setMaximumHeight(120)
        right_layout.addWidget(self.summary_edit)

        summary_btn_row = QHBoxLayout()
        summary_btn_row.setSpacing(8)
        self.save_summary_btn = QPushButton("保存记忆摘要")
        self.reload_summary_btn = QPushButton("重新读取摘要")
        self.save_summary_btn.clicked.connect(self.save_memory_summary)
        self.reload_summary_btn.clicked.connect(self.load_memory_summary)
        summary_btn_row.addWidget(self.save_summary_btn)
        summary_btn_row.addWidget(self.reload_summary_btn)
        summary_btn_row.addStretch(1)
        right_layout.addLayout(summary_btn_row)

        detail_label = QLabel("对话详情")
        detail_label.setProperty("heading", True)
        right_layout.addWidget(detail_label)
        self.detail_box = QPlainTextEdit(right_panel)
        self.detail_box.setReadOnly(True)
        right_layout.addWidget(self.detail_box, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.favorite_btn = QPushButton("收藏")
        self.delete_selected_btn = QPushButton("删除选中")
        self.delete_hour_btn = QPushButton("按小时删除")
        self.delete_date_btn = QPushButton("按日期删除")
        self.refresh_btn = QPushButton("刷新")

        self.favorite_btn.clicked.connect(self.favorite_selected_record)
        self.delete_selected_btn.clicked.connect(self.delete_selected_record)
        self.delete_hour_btn.clicked.connect(self.delete_by_selected_hour)
        self.delete_date_btn.clicked.connect(self.delete_by_selected_date)
        self.refresh_btn.clicked.connect(self.reload)

        for btn in (self.favorite_btn, self.delete_selected_btn, self.delete_hour_btn, self.delete_date_btn, self.refresh_btn):
            btn_row.addWidget(btn)
        btn_row.addStretch(1)

        right_layout.addLayout(btn_row)

        splitter.addWidget(self.tree)
        splitter.addWidget(right_panel)
        splitter.setSizes([420, 380])

        content_layout.addWidget(splitter, 1)
        root_margin.addWidget(content, 1)

        self.load_memory_summary()
        self.reload()

    def load_memory_summary(self) -> None:
        memory_state = self.settings_store.load_memory_state()
        self.summary_edit.setPlainText(memory_state.last_summary)

    def save_memory_summary(self) -> None:
        memory_state = self.settings_store.load_memory_state()
        memory_state.last_summary = self.summary_edit.toPlainText().strip()
        self.settings_store.save_memory_state(memory_state)
        QMessageBox.information(self, "提示", "记忆摘要已保存。")

    def reload(self) -> None:
        self.records = self.store.load_records()
        self.tree.clear()
        self.detail_box.clear()

        grouped_by_date: OrderedDict[str, list[HistoryRecord]] = OrderedDict()
        for record in self.records:
            date_key = record.timestamp[:10]
            grouped_by_date.setdefault(date_key, []).append(record)

        for date_key, date_records in grouped_by_date.items():
            date_item = QTreeWidgetItem([date_key, "", ""])
            date_item.setData(0, Qt.UserRole, {"level": "date", "key": date_key})
            self.tree.addTopLevelItem(date_item)

            hour_groups: OrderedDict[str, list[HistoryRecord]] = OrderedDict()
            for record in date_records:
                hour_key = record.timestamp[:13]
                hour_groups.setdefault(hour_key, []).append(record)

            for hour_key, hour_records in hour_groups.items():
                hour_item = QTreeWidgetItem([f"{hour_key}:00", "", ""])
                hour_item.setData(0, Qt.UserRole, {"level": "hour", "key": hour_key})
                date_item.addChild(hour_item)

                for record in hour_records:
                    user_preview = record.user_text.replace("\n", " ").strip()
                    reply_preview = record.reply_text.replace("\n", " ").strip()
                    child = QTreeWidgetItem([record.timestamp[-8:], user_preview[:30], reply_preview[:30]])
                    child.setData(0, Qt.UserRole, {"level": "record", "id": record.id})
                    hour_item.addChild(child)

            date_item.setExpanded(True)

    def on_selection_changed(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            self.detail_box.clear()
            return
        payload = item.data(0, Qt.UserRole) or {}
        level = payload.get("level")

        if level == "record":
            record_id = payload.get("id", "")
            record = self.find_record(record_id)
            if record is None:
                self.detail_box.clear()
                return
            self.detail_box.setPlainText(
                f"时间: {record.timestamp}\n\n你:\n{record.user_text}\n\nArcueid:\n{record.reply_text}"
            )
        elif level == "hour":
            self.detail_box.setPlainText(f"当前选中小时: {payload.get('key', '')}:00\n可点击「按小时删除」。")
        elif level == "date":
            self.detail_box.setPlainText(f"当前选中日期: {payload.get('key', '')}\n可点击「按日期删除」。")
        else:
            self.detail_box.clear()

    def find_record(self, record_id: str) -> HistoryRecord | None:
        for record in self.records:
            if record.id == record_id:
                return record
        return None

    def favorite_selected_record(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.UserRole) or {}
        if payload.get("level") != "record":
            QMessageBox.information(self, "提示", "请先选中具体记录再收藏。")
            return
        record_id = str(payload.get("id", "")).strip()
        record = self.find_record(record_id)
        if record is None:
            return
        self._fav_store.add(record.reply_text)
        QMessageBox.information(self, "提示", "已收藏。")

    def delete_selected_record(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.UserRole) or {}
        if payload.get("level") != "record":
            QMessageBox.information(self, "提示", "请先选中具体记录再删除。")
            return
        record_id = str(payload.get("id", "")).strip()
        if not record_id:
            return
        if QMessageBox.question(self, "确认", "确定删除这条历史记录吗？") != QMessageBox.Yes:
            return
        self.store.delete_record(record_id)
        self.reload()

    def delete_by_selected_hour(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.UserRole) or {}
        level = payload.get("level")
        if level == "record":
            record = self.find_record(str(payload.get("id", "")))
            hour_key = record.timestamp[:13] if record else ""
        elif level == "hour":
            hour_key = str(payload.get("key", "")).strip()
        else:
            hour_key = ""
        if not hour_key:
            QMessageBox.information(self, "提示", "请选中某小时或该小时内的一条记录。")
            return
        if QMessageBox.question(self, "确认", f"确定删除 {hour_key}:00 的全部记录吗？") != QMessageBox.Yes:
            return
        self.store.delete_by_hour(hour_key)
        self.reload()

    def delete_by_selected_date(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.UserRole) or {}
        level = payload.get("level")
        if level == "record":
            record = self.find_record(str(payload.get("id", "")))
            date_key = record.timestamp[:10] if record else ""
        elif level == "hour":
            date_key = str(payload.get("key", ""))[:10]
        elif level == "date":
            date_key = str(payload.get("key", "")).strip()
        else:
            date_key = ""

        if not date_key:
            QMessageBox.information(self, "提示", "请选中某日期/小时或该日期内的一条记录。")
            return
        if QMessageBox.question(self, "确认", f"确定删除 {date_key} 的全部记录吗？") != QMessageBox.Yes:
            return
        self.store.delete_by_date(date_key)
        self.reload()





class SettingsDialog(_FramelessDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__("设置", parent)
        self.resize(760, 640)

        self.original_fixed_requirements_prompt = settings.fixed_requirements_prompt
        self.role_edit = QPlainTextEdit(self)
        self.user_profile_edit = QPlainTextEdit(self)
        self.api_key_edit = QLineEdit(self)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("请输入 API 密钥")

        self.provider_combo = QComboBox(self)
        provider_keys = list(PROVIDERS.keys())
        self._provider_keys = provider_keys
        for key in provider_keys:
            self.provider_combo.addItem(PROVIDERS[key]["name"], key)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self.api_base_url_edit = QLineEdit(self)
        self.api_base_url_edit.setPlaceholderText("API Base URL（选择厂商后自动填充，可手动修改）")

        self.api_model_edit = QLineEdit(self)
        self.api_model_edit.setPlaceholderText("模型名称（选择厂商后自动填充，可手动修改）")

        self.role_edit.setPlainText(settings.role_prompt)
        self.user_profile_edit.setPlainText(settings.user_profile_prompt)
        self.api_key_edit.setText(settings.api_key)

        idx = self.provider_combo.findData(settings.provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        else:
            self.provider_combo.setCurrentIndex(0)

        if settings.api_base_url:
            self.api_base_url_edit.setText(settings.api_base_url)
        if settings.api_model:
            self.api_model_edit.setText(settings.api_model)

        root_margin = QVBoxLayout(self)
        root_margin.setContentsMargins(0, 0, 0, 0)
        root_margin.addWidget(self._title_bar)

        scroll_content = QWidget(self)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(20, 16, 20, 16)
        scroll_layout.setSpacing(4)

        def heading(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setProperty("heading", True)
            return lbl

        scroll_layout.addWidget(heading("API \u914D\u7F6E"))

        scroll_layout.addWidget(QLabel("API \u5BC6\u94A5"))
        scroll_layout.addWidget(self.api_key_edit)
        scroll_layout.addSpacing(8)

        scroll_layout.addWidget(QLabel("API \u5382\u5546"))
        scroll_layout.addWidget(self.provider_combo)
        scroll_layout.addSpacing(8)

        scroll_layout.addWidget(QLabel("API Base URL\uFF08\u53EF\u624B\u52A8\u4FEE\u6539\uFF09"))
        scroll_layout.addWidget(self.api_base_url_edit)
        scroll_layout.addSpacing(8)

        scroll_layout.addWidget(QLabel("\u6A21\u578B\u540D\u79F0\uFF08\u53EF\u624B\u52A8\u4FEE\u6539\uFF09"))
        scroll_layout.addWidget(self.api_model_edit)
        scroll_layout.addSpacing(12)

        scroll_layout.addWidget(heading("\u63D0\u793A\u8BCD\u8BBE\u7F6E"))

        scroll_layout.addWidget(QLabel("\u89D2\u8272\u63D0\u793A\u8BCD"))
        scroll_layout.addWidget(self.role_edit, 1)
        scroll_layout.addSpacing(8)

        scroll_layout.addWidget(QLabel("\u7528\u6237\u6863\u6848"))
        scroll_layout.addWidget(self.user_profile_edit, 1)
        scroll_layout.addSpacing(12)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        reset_btn = QPushButton("\u6062\u590D\u9ED8\u8BA4")
        save_btn = QPushButton("\u4FDD\u5B58")
        cancel_btn = QPushButton("\u53D6\u6D88")

        reset_btn.clicked.connect(self.reset_defaults)
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(reset_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        scroll_layout.addLayout(btn_row)

        root_margin.addWidget(scroll_content, 1)

    def _on_provider_changed(self, index: int) -> None:
        key = self._provider_keys[index]
        info = PROVIDERS.get(key)
        if info and key != "custom":
            if not self.api_base_url_edit.text() or self.api_base_url_edit.text() in {
                PROVIDERS[k]["base_url"] for k in self._provider_keys if k != "custom"
            }:
                self.api_base_url_edit.setText(info["base_url"])
            if not self.api_model_edit.text() or self.api_model_edit.text() in {
                PROVIDERS[k]["default_model"] for k in self._provider_keys if k != "custom"
            }:
                self.api_model_edit.setText(info["default_model"])
        elif key == "custom":
            pass

    def reset_defaults(self) -> None:
        self.role_edit.setPlainText(DEFAULT_ROLE_PROMPT)
        self.user_profile_edit.setPlainText(DEFAULT_USER_PROFILE_PROMPT)

    def to_settings(self) -> AppSettings:
        return AppSettings(
            fixed_requirements_prompt=self.original_fixed_requirements_prompt,
            role_prompt=self.role_edit.toPlainText().strip() or DEFAULT_ROLE_PROMPT,
            user_profile_prompt=self.user_profile_edit.toPlainText().strip() or DEFAULT_USER_PROFILE_PROMPT,
            api_key=self.api_key_edit.text().strip(),
            provider=self._provider_keys[self.provider_combo.currentIndex()],
            api_base_url=self.api_base_url_edit.text().strip(),
            api_model=self.api_model_edit.text().strip(),
        )
